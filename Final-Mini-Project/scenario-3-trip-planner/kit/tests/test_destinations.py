"""GET /api/destinations: worldwide city search. The provider is mocked (httpx.MockTransport): no network.

The main fixture is a real Open-Meteo answer recorded once (tests/fixtures/open_meteo_geocoding_pari.json).
"""
import json
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.destinations import DestinationError, DestinationSearch, install_destinations, normalize_query, \
    normalize_result

PARI = json.loads((Path(__file__).parent / "fixtures" / "open_meteo_geocoding_pari.json").read_text(encoding="utf-8"))


class Provider:
    """A scripted provider: answers each request with the next reply, and records what it was asked."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)


def service(provider, clock=None, environment="development", **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(provider))
    return DestinationSearch(client=client, url=kwargs.pop("url", "https://geo.test/v1/search"),
                             clock=clock or (lambda: 1000.0), environment=environment, **kwargs)


def api(provider, **kwargs):
    app = FastAPI()
    install_destinations(app, service(provider, **kwargs))
    return TestClient(app)


# ------------------------------------------------------------------ results
def test_prefix_search_returns_structured_cities_with_stable_ids():
    provider = Provider(PARI)
    r = api(provider).get("/api/destinations", params={"q": "Pari"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Pari" and body["count"] == 3
    first = body["results"][0]
    assert first == {
        "id": "geonames:2988507", "provider_id": 2988507, "name": "Paris", "region": "Île-de-France Region",
        "country": "France", "country_code": "FR", "latitude": first["latitude"], "longitude": first["longitude"],
        "population": 2138551, "timezone": "Europe/Paris", "feature_code": "PPLC",
        "label": "Paris, Île-de-France Region, France", "ambiguous_name": True}
    assert 48 < first["latitude"] < 49 and 2 < first["longitude"] < 3
    assert [x["label"] for x in body["results"][1:]] == ["Paris, Texas, United States", "Paris, Tennessee, United States"]
    assert body["source"]["licence"] == "CC BY 4.0" and "GeoNames" in body["source"]["attribution"]
    assert r.headers["cache-control"] == "private, max-age=300"
    sent = provider.requests[0].url.params
    assert sent["name"] == "Pari" and sent["language"] == "en" and sent["format"] == "json"
    assert sent["count"] == "24"  # over-fetched (8 x 3) so dropped non-city matches leave the list full


def test_a_name_shared_by_several_places_is_flagged_ambiguous():
    body = api(Provider(PARI)).get("/api/destinations", params={"q": "Paris"}).json()
    assert body["ambiguous"] is True and all(x["ambiguous_name"] for x in body["results"])


def test_a_unique_best_match_is_not_ambiguous():
    reply = {"results": [{"id": 1, "name": "Amman", "latitude": 31.95, "longitude": 35.93, "feature_code": "PPLC",
                          "country": "Jordan", "country_code": "JO", "admin1": "Amman"}]}
    body = api(Provider(reply)).get("/api/destinations", params={"q": "Amman"}).json()
    assert body["ambiguous"] is False
    assert body["results"][0]["label"] == "Amman, Jordan"  # region equal to the city is not repeated


def test_no_match_is_an_empty_answer_not_an_error():
    body = api(Provider({"generationtime_ms": 0.2})).get("/api/destinations", params={"q": "zzqxqz"}).json()
    assert body == {**body, "count": 0, "results": [], "ambiguous": False}


@pytest.mark.parametrize("item, kept", [
    ({"feature_code": "PPLH"}, False),  # historical place
    ({"feature_code": "PPLX"}, False),  # section of a city
    ({"feature_code": "ADM1"}, False),  # a region, not a city
    ({"feature_code": "AIRP"}, False),  # an airport
    ({"feature_code": None}, False),
    ({"latitude": 95}, False), ({"longitude": float("nan")}, False), ({"latitude": 0, "longitude": 0}, False),
    ({"latitude": "48.8"}, False), ({"id": "2988507"}, False), ({"id": True}, False), ({"name": "  "}, False),
    ({"population": -5}, True), ({"country_code": "FRA"}, True), ({}, True),
])
def test_only_valid_populated_places_are_kept(item, kept):
    base = {"id": 7, "name": "Paris", "latitude": 48.85, "longitude": 2.35, "feature_code": "PPL",
            "country": "France", "country_code": "FR", "population": 100}
    place = normalize_result({**base, **item})
    assert (place is not None) is kept
    if place and "population" in item:
        assert place["population"] is None  # an impossible value is dropped, never guessed
    if place and "country_code" in item:
        assert place["country_code"] is None


def test_duplicates_are_removed_and_the_limit_is_applied():
    city = {"name": "Rome", "latitude": 41.89, "longitude": 12.48, "feature_code": "PPL", "country": "Italy"}
    reply = {"results": [{**city, "id": 1}, {**city, "id": 1}] + [{**city, "id": i} for i in range(2, 12)]}
    body = api(Provider(reply)).get("/api/destinations", params={"q": "Rom", "limit": 3}).json()
    assert [x["provider_id"] for x in body["results"]] == [1, 2, 3]


def test_garbage_entries_in_the_answer_do_not_break_the_search():
    reply = {"results": ["nonsense", None, 42, PARI["results"][0]]}
    body = api(Provider(reply)).get("/api/destinations", params={"q": "Pari"}).json()
    assert body["count"] == 1 and body["results"][0]["name"] == "Paris"


# ------------------------------------------------------------------ input
@pytest.mark.parametrize("q, code", [
    ("", "missing_query"), ("   ", "missing_query"), ("P", "query_too_short"), ("12", "invalid_query"),
    ("!!", "invalid_query"), ("Pa\x00ris", "invalid_query"), ("x" * 81, "query_too_long"),
])
def test_invalid_input_is_refused_without_calling_the_provider(q, code):
    provider = Provider(PARI)
    r = api(provider).get("/api/destinations", params={"q": q})
    assert r.status_code == 422 and r.json()["error"]["code"] == code and r.json()["error"]["retryable"] is False
    assert provider.requests == []


def test_the_query_is_cleaned_before_it_is_sent():
    assert normalize_query("  New   York ") == "New York"
    assert normalize_query("São Paulo") == "São Paulo"  # NFC


@pytest.mark.parametrize("params", [{"q": "Pari", "limit": 0}, {"q": "Pari", "limit": 11}, {"q": "Pari", "lang": "eng"}])
def test_out_of_range_parameters_are_rejected(params):
    assert api(Provider(PARI)).get("/api/destinations", params=params).status_code == 422


# ------------------------------------------------------------------ provider failures
@pytest.mark.parametrize("reply, status, code, retryable", [
    (httpx.ReadTimeout("slow"), 504, "provider_timeout", True),
    (httpx.ConnectError("down"), 503, "provider_unavailable", True),
    (httpx.Response(429, headers={"Retry-After": "30"}), 503, "provider_rate_limited", True),
    (httpx.Response(500), 502, "provider_error", True),
    (httpx.Response(503, text="maintenance"), 502, "provider_error", True),
    (httpx.Response(400, json={"error": True, "reason": "bad"}), 502, "provider_rejected", False),
    (httpx.Response(200, json={"error": True, "reason": "No value found"}), 502, "provider_rejected", False),
    (httpx.Response(200, text="<html>not json</html>"), 502, "provider_bad_response", False),
    (httpx.Response(200, json={"results": "oops"}), 502, "provider_bad_response", False),
    (httpx.Response(200, json=[1, 2]), 502, "provider_rejected", False),
])
def test_provider_failures_are_reported_never_filled_in(reply, status, code, retryable):
    r = api(Provider(reply)).get("/api/destinations", params={"q": "Pari"})
    assert r.status_code == status
    error = r.json()["error"]
    assert error["code"] == code and error["retryable"] is retryable and error["message"]
    assert "results" not in r.json()
    if code == "provider_rate_limited":
        assert error["retry_after"] == 30 and r.headers["retry-after"] == "30"


def test_a_failure_is_not_cached():
    provider = Provider(httpx.ConnectError("down"), PARI)
    client = api(provider)
    assert client.get("/api/destinations", params={"q": "Pari"}).status_code == 503
    assert client.get("/api/destinations", params={"q": "Pari"}).status_code == 200
    assert len(provider.requests) == 2


# ------------------------------------------------------------------ caching and limits
def test_answers_are_cached_case_and_accent_insensitively():
    provider = Provider(PARI)
    client = api(provider)
    first = client.get("/api/destinations", params={"q": "Pari"}).json()
    again = client.get("/api/destinations", params={"q": "  pari "}).json()
    assert first["cached"] is False and again["cached"] is True and len(provider.requests) == 1
    assert again["results"] == first["results"]


def test_cache_entries_expire():
    now = [0.0]
    provider = Provider({"results": []}, PARI)
    search = service(provider, clock=lambda: now[0], empty_ttl_s=600)
    assert search.search("Pari")["count"] == 0
    now[0] = 599
    assert search.search("Pari")["cached"] is True
    now[0] = 601  # an empty answer is kept for a short time only
    assert search.search("Pari")["count"] == 3 and len(provider.requests) == 2


def test_provider_calls_per_minute_are_capped_and_the_window_slides():
    now = [0.0]
    search = service(Provider(PARI), clock=lambda: now[0], max_calls_per_minute=2)
    search.search("Ab")
    search.search("Cd")
    with pytest.raises(DestinationError) as raised:
        search.search("Ef")
    assert raised.value.status == 429 and raised.value.code == "rate_limited" and raised.value.retry_after == 60
    assert search.search("ab")["cached"] is True  # a cached query never counts
    now[0] = 60
    assert search.search("Ef")["cached"] is False


def test_the_rate_limit_answer_over_http():
    client = api(Provider(PARI), max_calls_per_minute=1)
    client.get("/api/destinations", params={"q": "Ab"})
    r = client.get("/api/destinations", params={"q": "Cd"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited" and "retry-after" in r.headers


def test_concurrent_searches_respect_the_cap():
    search = service(Provider(PARI), max_calls_per_minute=5)
    outcomes = []

    def run(i):
        try:
            search.search(f"City{i}")
            outcomes.append("ok")
        except DestinationError as e:
            outcomes.append(e.code)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 5 and outcomes.count("rate_limited") == 15


# ------------------------------------------------------------------ licence: production needs an explicit decision
@pytest.fixture()
def no_licence(monkeypatch):
    for name in ("RIHLA_OPEN_METEO_API_KEY", "RIHLA_OPEN_METEO_NONCOMMERCIAL", "RIHLA_ENV"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("environment", ["production"])
def test_production_without_a_licence_decision_never_calls_the_provider(no_licence, environment):
    provider = Provider(PARI)
    client = api(provider, environment=environment)
    r = client.get("/api/destinations", params={"q": "Pari"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "destinations_unavailable"
    assert r.json()["error"]["retryable"] is False and "type the destination yourself" in r.json()["error"]["message"]
    assert "results" not in r.json() and provider.requests == []
    status = client.get("/api/destinations/status").json()
    assert status["available"] is False and "non-commercial" in status["notice"]
    # even for input that would be refused anyway: the licence comes first
    assert client.get("/api/destinations", params={"q": ""}).json()["error"]["code"] == "destinations_unavailable"


@pytest.mark.parametrize("raw", ["production", "PRODUCTION", "prod", "staging"])
def test_any_production_like_or_unknown_rihla_env_is_gated(no_licence, raw):
    no_licence.setenv("RIHLA_ENV", raw)
    provider = Provider(PARI)
    client = httpx.Client(transport=httpx.MockTransport(provider))
    search = DestinationSearch(client=client, url="https://geo.test/v1/search")
    with pytest.raises(DestinationError) as raised:
        search.search("Pari")
    assert raised.value.code == "destinations_unavailable" and provider.requests == []


def test_production_with_a_stated_non_commercial_use_calls_the_free_api(no_licence):
    no_licence.setenv("RIHLA_OPEN_METEO_NONCOMMERCIAL", "true")
    provider = Provider(PARI)
    body = api(provider, environment="production").get("/api/destinations", params={"q": "Pari"}).json()
    assert body["count"] == 3 and "apikey" not in provider.requests[0].url.params


def test_a_paid_key_goes_to_the_customer_server_and_never_into_answers_or_logs(no_licence, caplog):
    import logging
    from app.destinations.service import CUSTOMER_URL
    caplog.set_level(logging.INFO)
    provider = Provider(PARI)
    search = service(provider, environment="production", api_key="secret-geo-key-42", url=None)
    app = FastAPI()
    install_destinations(app, search)
    text = TestClient(app).get("/api/destinations", params={"q": "Pari"}).text
    sent = provider.requests[0].url
    assert str(sent).startswith(CUSTOMER_URL) and sent.params["apikey"] == "secret-geo-key-42"
    assert "secret-geo-key-42" not in text and "secret-geo-key-42" not in repr(search)
    assert "apikey=REDACTED" in caplog.text and "secret-geo-key-42" not in caplog.text


def test_development_and_test_use_the_free_api_without_a_decision(no_licence):
    for environment in ("development", "test"):
        provider = Provider(PARI)
        assert service(provider, environment=environment).search("Pari")["count"] == 3


def test_a_licensed_production_search_still_reports_provider_failures(no_licence):
    no_licence.setenv("RIHLA_OPEN_METEO_NONCOMMERCIAL", "true")
    r = api(Provider(httpx.ReadTimeout("slow")), environment="production").get("/api/destinations", params={"q": "Pari"})
    assert r.status_code == 504 and r.json()["error"]["code"] == "provider_timeout" and "results" not in r.json()


def test_install_is_idempotent_and_the_route_needs_no_sign_in():
    app = FastAPI()
    install_destinations(app)
    routes_after_one = len(app.router.routes)
    install_destinations(app)
    assert len(app.router.routes) == routes_after_one
    assert "/api/destinations" in app.openapi()["paths"]
    from app.auth.middleware import PROTECTED_PREFIXES
    assert not any("/api/destinations".startswith(p) for p in PROTECTED_PREFIXES)
