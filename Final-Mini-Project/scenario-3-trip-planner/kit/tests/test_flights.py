"""GET /api/flights: flight search and price comparison. No network: Duffel is mocked with httpx.MockTransport.

The Duffel answers below are SYNTHETIC, built in the shape of Duffel's documented offer schema
(https://duffel.com/docs/api/v2/offers/schema). No real Duffel call was made: no token is available here.
"""
import datetime as dt
import json
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.flights import DemoProvider, DuffelProvider, FlightError, FlightSearch, install_flights, \
    normalize_duffel_offer, provider_from_env, validate_query
from app.flights.providers import iso_minutes

TODAY = dt.date(2026, 11, 2)
NOW = dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc).timestamp()
TOKEN = "duffel_test_not-a-real-token-123"
AIRPORTS = {"TLV": (32.01, 34.89), "LHR": (51.47, -0.46), "ATH": (37.94, 23.94), "AMM": (31.72, 35.99),
            "JFK": (40.64, -73.78), "IST": (41.26, 28.74), "DXB": (25.25, 55.36), "FRA": (50.03, 8.56)}


def lookup(code):
    if code not in AIRPORTS:
        return None
    lat, lon = AIRPORTS[code]
    return {"iata": code, "latitude": lat, "longitude": lon}


SEARCH = {"origin": "TLV", "destination": "LHR", "departure_date": "2026-12-01"}


# ------------------------------------------------------------------ synthetic Duffel answers
def segment(origin, destination, departing, arriving, *, duration="PT5H10M", carrier="ZZ", number="101",
            bags=((("checked", 1), ("carry_on", 1))), stops=None, cabin="economy"):
    passenger = {"passenger_id": "pas_1", "cabin_class": cabin}
    if bags is not None:
        passenger["baggages"] = [{"type": t, "quantity": q} for t, q in bags]
    return {"origin": {"iata_code": origin}, "destination": {"iata_code": destination},
            "departing_at": departing, "arriving_at": arriving, "duration": duration,
            "marketing_carrier": {"name": "Duffel Airways", "iata_code": carrier},
            "marketing_carrier_flight_number": number,
            "operating_carrier": {"name": "Duffel Airways", "iata_code": carrier},
            "stops": stops or [], "passengers": [passenger]}


def offer(oid, amount, currency="USD", *, slices=None, expires="2026-11-02T12:30:00Z", passengers=1, live=False):
    slices = slices or [{"duration": "PT5H10M", "segments": [
        segment("TLV", "LHR", "2026-12-01T08:00:00", "2026-12-01T11:10:00")]}]
    return {"id": oid, "live_mode": live, "total_amount": amount, "total_currency": currency, "expires_at": expires,
            "owner": {"name": "Duffel Airways", "iata_code": "ZZ"}, "slices": slices,
            "passengers": [{"id": f"pas_{i}", "type": "adult"} for i in range(passengers)]}


VIA_ATH = {"duration": "PT7H45M", "segments": [
    segment("TLV", "ATH", "2026-12-01T06:00:00", "2026-12-01T08:00:00", duration="PT2H", number="20", bags=None),
    segment("ATH", "LHR", "2026-12-01T09:30:00", "2026-12-01T11:45:00", duration="PT4H15M", number="21",
            bags=None)]}
RETURN = {"duration": "PT5H20M", "segments": [
    segment("LHR", "TLV", "2026-12-08T12:00:00", "2026-12-08T19:20:00", duration="PT5H20M", number="102")]}


def duffel_answer(*offers):
    return {"data": {"id": "orq_1", "live_mode": False, "offers": list(offers)}}


class Duffel:
    """A scripted Duffel: answers each request with the next reply, and records what it was asked."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(201, json=reply)


def duffel_service(duffel, *, clock=lambda: NOW, monotonic=lambda: 0.0, token=TOKEN, environment="development",
                   **kwargs):
    provider = DuffelProvider(token, client=httpx.Client(transport=httpx.MockTransport(duffel)),
                              base_url="https://duffel.test", timeout_s=25, clock=clock)
    return FlightSearch(provider, airport_lookup=lookup, clock=clock, monotonic=monotonic, environment=environment,
                        **kwargs)


def demo_service(environment="development", **kwargs):
    return FlightSearch(DemoProvider(lookup=lookup), airport_lookup=lookup, clock=lambda: NOW,
                        environment=environment, **kwargs)


def api(service):
    app = FastAPI()
    install_flights(app, service)
    return TestClient(app)


# ------------------------------------------------------------------ input
@pytest.mark.parametrize("params, code, field", [
    ({"origin": ""}, "missing_airport", "origin"),
    ({"destination": " "}, "missing_airport", "destination"),
    ({"origin": "TL"}, "invalid_airport_code", "origin"),
    ({"origin": "T1V"}, "invalid_airport_code", "origin"),
    ({"destination": "LLBG"}, "invalid_airport_code", "destination"),
    ({"destination": "QQQ"}, "unknown_airport", "destination"),
    ({"destination": "tlv"}, "same_airport", "destination"),
    ({"departure_date": ""}, "invalid_date", "departure_date"),
    ({"departure_date": "01/12/2026"}, "invalid_date", "departure_date"),
    ({"departure_date": "2026-02-30"}, "invalid_date", "departure_date"),
    ({"departure_date": "2026-11-01"}, "date_in_past", "departure_date"),
    ({"departure_date": "2027-12-01"}, "date_too_far", "departure_date"),
    ({"return_date": "2026-11-30"}, "return_before_departure", "return_date"),
    ({"return_date": "soon"}, "invalid_date", "return_date"),
    ({"adults": "0"}, "invalid_passengers", "adults"),
    ({"adults": "10"}, "invalid_passengers", "adults"),
    ({"adults": "two"}, "invalid_passengers", "adults"),
    ({"cabin_class": "luxury"}, "invalid_cabin_class", "cabin_class"),
])
def test_invalid_searches_are_refused_without_calling_the_provider(params, code, field):
    duffel = Duffel(duffel_answer())
    r = api(duffel_service(duffel)).get("/api/flights", params={**SEARCH, **params})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code and r.json()["error"]["field"] == field
    assert duffel.requests == []


def test_codes_and_cabin_are_normalized():
    query = validate_query(origin=" tlv", destination="lhr", departure_date="2026-12-01", adults=" 2 ",
                           cabin_class="Business", today=TODAY, lookup=lookup)
    assert (query.origin, query.destination, query.adults, query.cabin_class) == ("TLV", "LHR", 2, "business")
    assert query.as_dict()["trip_type"] == "one_way"


def test_the_real_airport_data_checks_codes():
    from app.flights.service import default_airport_lookup
    with pytest.raises(FlightError) as raised:
        validate_query(origin="TLV", destination="QQQ", departure_date="2026-12-01", today=TODAY,
                       lookup=default_airport_lookup)
    assert raised.value.code == "unknown_airport"
    assert validate_query(origin="TLV", destination="LHR", departure_date="2026-12-01", today=TODAY,
                          lookup=default_airport_lookup).destination == "LHR"


# ------------------------------------------------------------------ DEMO
def test_demo_one_way_is_labelled_demo_everywhere_and_never_real():
    r = api(demo_service()).get("/api/flights", params=SEARCH)
    body = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert body["data_mode"] == "DEMO" and body["provider"] == "Rihla demo data"
    assert body["notices"][0].startswith("DEMO data") and body["booking_supported"] is False
    assert body["count"] == 4 and body["query"]["trip_type"] == "one_way"
    for o in body["offers"]:
        assert o["data_mode"] == "DEMO" and o["id"].startswith("demo:") and o["provider_offer_id"] is None
        assert o["airline"]["iata_code"] is None  # made-up airlines never borrow a real airline code
        assert all(leg["flight_number"].startswith("DEMO ") for s in o["slices"] for leg in s["segments"])
        assert len(o["slices"]) == 1 and o["slices"][0]["origin"] == "TLV" and o["time_basis"] == "utc"


def test_demo_round_trip_has_a_return_slice():
    body = demo_service().search(**SEARCH, return_date="2026-12-08")
    assert body["query"]["trip_type"] == "round_trip"
    for o in body["offers"]:
        out, back = o["slices"]
        assert (out["origin"], out["destination"], back["origin"], back["destination"]) == ("TLV", "LHR", "LHR", "TLV")
        assert back["departing_at"].startswith("2026-12-08")


def test_demo_is_deterministic_and_priced_for_every_passenger():
    one, again = demo_service().search(**SEARCH, adults="3"), demo_service().search(**SEARCH, adults="3")
    assert one["offers"] == again["offers"]
    assert all(o["passengers"] == 3 and float(o["total_amount"]) % 3 == 0 for o in one["offers"])


def test_demo_shows_unknown_baggage_as_null():
    offers = demo_service().search(**SEARCH)["offers"]
    assert {"checked": None, "carry_on": None} in [o["baggage"] for o in offers]


def test_demo_is_not_capped_like_a_paid_provider():
    service = demo_service(max_calls_per_minute=1)
    for day in ("2026-12-01", "2026-12-02", "2026-12-03"):
        assert service.search(**{**SEARCH, "departure_date": day})["data_mode"] == "DEMO"


# ------------------------------------------------------------------ Duffel: normalization, sorting, currencies
def test_duffel_offers_are_normalized_sorted_and_compared_per_currency():
    duffel = Duffel(duffel_answer(
        offer("off_direct", "412.30"),
        offer("off_via_ath", "389.10", slices=[VIA_ATH]),
        offer("off_eur", "350.00", "EUR"),
        offer("off_no_price", None),
        offer("off_expired", "120.00", expires="2026-11-02T11:59:00Z"),
        offer("off_zero", "0.00"),
    ))
    body = api(duffel_service(duffel)).get("/api/flights", params=SEARCH).json()
    assert body["data_mode"] == "TEST" and body["provider"] == "Duffel" and body["notices"][0].startswith("TEST")
    assert [o["id"] for o in body["offers"]] == ["duffel:off_via_ath", "duffel:off_direct", "duffel:off_eur"]
    assert body["currencies"] == ["USD", "EUR"] and body["comparable"] is False and body["cheapest"] is None
    assert body["cheapest_by_currency"] == {
        "USD": {"offer_id": "duffel:off_via_ath", "total_amount": "389.10", "currency": "USD"},
        "EUR": {"offer_id": "duffel:off_eur", "total_amount": "350.00", "currency": "EUR"}}
    assert any("several currencies" in n for n in body["notices"])
    assert body["skipped_offers"] == {"unusable": 2, "expired": 1}
    assert body["retrieved_at"] == "2026-11-02T12:00:00Z"


def test_the_cheapest_offer_in_one_currency_is_first_and_reported():
    duffel = Duffel(duffel_answer(offer("a", "500.00"), offer("b", "99.99"), offer("c", "250.5")))
    body = duffel_service(duffel).search(**SEARCH)
    assert [o["total_amount"] for o in body["offers"]] == ["99.99", "250.5", "500.00"]
    assert body["comparable"] is True and body["cheapest"] == {"offer_id": "duffel:b", "total_amount": "99.99",
                                                               "currency": "USD"}


def test_a_duffel_offer_in_full():
    o = normalize_duffel_offer(offer("off_1", "412.30", passengers=2), adults=2)
    assert o == {
        "id": "duffel:off_1", "provider_offer_id": "off_1", "airline": {"name": "Duffel Airways", "iata_code": "ZZ"},
        "total_amount": "412.30", "currency": "USD", "passengers": 2, "cabin_class": "economy",
        "slices": [{"origin": "TLV", "destination": "LHR", "departing_at": "2026-12-01T08:00",
                    "arriving_at": "2026-12-01T11:10", "duration_minutes": 310, "stops": 0, "connections": [],
                    "segments": o["slices"][0]["segments"]}],
        "baggage": {"checked": 1, "carry_on": 1}, "expires_at": "2026-11-02T12:30:00Z", "time_basis": "local",
        "data_mode": "TEST", "provider": "Duffel"}
    leg = o["slices"][0]["segments"][0]
    assert leg["flight_number"] == "ZZ101" and leg["operating_carrier"]["name"] == "Duffel Airways"


def test_connections_technical_stops_and_missing_baggage():
    o = normalize_duffel_offer(offer("x", "389.10", slices=[VIA_ATH]), adults=1)
    assert o["slices"][0]["stops"] == 1 and o["slices"][0]["connections"] == ["ATH"]
    assert o["baggage"] == {"checked": None, "carry_on": None}  # unknown, never assumed
    tech = {"duration": "PT6H", "segments": [segment("TLV", "LHR", "2026-12-01T08:00", "2026-12-01T14:00",
                                                      stops=[{"airport": {"iata_code": "ATH"}}])]}
    assert normalize_duffel_offer(offer("y", "10.00", slices=[tech]), 1)["slices"][0]["stops"] == 1


def test_a_live_mode_offer_is_labelled_live():
    assert normalize_duffel_offer(offer("z", "10.00", live=True), 1)["data_mode"] == "LIVE"


@pytest.mark.parametrize("broken", [
    "not an offer", {"id": ""}, {**offer("a", "1.00"), "total_currency": "usd"},
    {**offer("a", "1.00"), "total_amount": "-5"}, {**offer("a", "1.00"), "total_amount": 12.5},
    {**offer("a", "1.00"), "slices": []}, {**offer("a", "1.00"), "slices": [{"segments": []}]},
    {**offer("a", "1.00"), "slices": [{"segments": [{"origin": {}, "destination": {}}]}]},
])
def test_unusable_offers_are_dropped_never_repaired(broken):
    assert normalize_duffel_offer(broken, 1) is None


def test_round_trip_and_passengers_are_sent_to_duffel():
    duffel = Duffel(duffel_answer(offer("rt", "800.00", slices=[
        {"duration": "PT5H10M", "segments": [segment("TLV", "LHR", "2026-12-01T08:00", "2026-12-01T11:10")]},
        RETURN], passengers=3)))
    body = duffel_service(duffel).search(**SEARCH, return_date="2026-12-08", adults="3", cabin_class="business")
    request = duffel.requests[0]
    assert request.method == "POST" and request.url.path == "/air/offer_requests"
    assert request.url.params["return_offers"] == "true" and request.url.params["supplier_timeout"] == "20000"
    assert request.headers["Duffel-Version"] == "v2" and request.headers["Authorization"] == f"Bearer {TOKEN}"
    sent = json.loads(request.content)["data"]
    assert sent["slices"] == [{"origin": "TLV", "destination": "LHR", "departure_date": "2026-12-01"},
                              {"origin": "LHR", "destination": "TLV", "departure_date": "2026-12-08"}]
    assert sent["passengers"] == [{"type": "adult"}] * 3 and sent["cabin_class"] == "business"
    o = body["offers"][0]
    assert o["passengers"] == 3 and [s["origin"] for s in o["slices"]] == ["TLV", "LHR"]


def test_no_available_flights_is_an_empty_answer_not_an_error():
    body = duffel_service(Duffel(duffel_answer())).search(**SEARCH)
    assert body["count"] == 0 and body["offers"] == [] and body["cheapest"] is None
    assert any("No flights were offered" in n for n in body["notices"])


# ------------------------------------------------------------------ Duffel failures
@pytest.mark.parametrize("reply, status, code, retryable", [
    (httpx.ReadTimeout("slow"), 504, "provider_timeout", True),
    (httpx.ConnectError("down"), 503, "provider_unavailable", True),
    (httpx.Response(401, json={"errors": [{"code": "access_token_not_found"}]}), 502, "provider_auth_failed", False),
    (httpx.Response(403, json={"errors": [{"code": "insufficient_permissions"}]}), 502, "provider_auth_failed", False),
    (httpx.Response(429, headers={"ratelimit-reset": "Mon, 02 Nov 2026 12:00:42 GMT"}), 503,
     "provider_rate_limited", True),
    (httpx.Response(500), 502, "provider_error", True),
    (httpx.Response(504, json={"errors": [{"code": "airline_internal"}]}), 502, "provider_error", True),
    (httpx.Response(422, json={"errors": [{"type": "validation_error"}]}), 502, "provider_rejected", False),
    (httpx.Response(201, text="<html>"), 502, "provider_bad_response", False),
    (httpx.Response(201, json={"data": {"offers": "none"}}), 502, "provider_bad_response", False),
])
def test_provider_failures_are_reported_never_filled_in(reply, status, code, retryable):
    r = api(duffel_service(Duffel(reply))).get("/api/flights", params=SEARCH)
    assert r.status_code == status
    error = r.json()["error"]
    assert error["code"] == code and error["retryable"] is retryable and "offers" not in r.json()
    assert TOKEN not in r.text
    if code == "provider_rate_limited":
        assert error["retry_after"] == 42 and r.headers["retry-after"] == "42"


def test_a_failure_is_not_cached():
    duffel = Duffel(httpx.ConnectError("down"), duffel_answer(offer("a", "10.00")))
    service = duffel_service(duffel)
    with pytest.raises(FlightError):
        service.search(**SEARCH)
    assert service.search(**SEARCH)["count"] == 1 and len(duffel.requests) == 2


# ------------------------------------------------------------------ cache, expiry, rate limit
def test_a_cached_answer_keeps_its_retrieval_time_and_drops_offers_that_expire():
    now, tick = [NOW], [0.0]
    duffel = Duffel(duffel_answer(offer("soon", "10.00", expires="2026-11-02T12:02:00Z"),
                                  offer("later", "20.00", expires="2026-11-02T12:30:00Z")))
    service = duffel_service(duffel, clock=lambda: now[0], monotonic=lambda: tick[0])
    assert service.search(**SEARCH)["count"] == 2
    now[0], tick[0] = NOW + 180, 180.0
    again = service.search(**SEARCH)
    assert again["cached"] is True and again["retrieved_at"] == "2026-11-02T12:00:00Z"
    assert [o["id"] for o in again["offers"]] == ["duffel:later"] and again["skipped_offers"]["expired"] == 1
    tick[0] = 301.0
    assert service.search(**SEARCH)["cached"] is False and len(duffel.requests) == 2


def test_provider_calls_are_capped_per_minute():
    tick = [0.0]
    service = duffel_service(Duffel(duffel_answer()), monotonic=lambda: tick[0], max_calls_per_minute=2)
    service.search(**SEARCH)
    service.search(**{**SEARCH, "departure_date": "2026-12-02"})
    with pytest.raises(FlightError) as raised:
        service.search(**{**SEARCH, "departure_date": "2026-12-03"})
    assert raised.value.status == 429 and raised.value.retry_after == 60
    assert service.search(**SEARCH)["cached"] is True  # a cached search never counts
    tick[0] = 60.0
    assert service.search(**{**SEARCH, "departure_date": "2026-12-03"})["cached"] is False


def test_concurrent_searches_respect_the_cap():
    service = duffel_service(Duffel(duffel_answer()), max_calls_per_minute=3)
    outcomes = []

    def run(day):
        try:
            service.search(**{**SEARCH, "departure_date": f"2026-12-{day:02d}"})
            outcomes.append("ok")
        except FlightError as e:
            outcomes.append(e.code)

    threads = [threading.Thread(target=run, args=(d,)) for d in range(1, 11)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 3 and outcomes.count("rate_limited") == 7


# ------------------------------------------------------------------ provider choice and secrets
@pytest.mark.parametrize("token, allow, kind, mode", [
    (None, None, DemoProvider, "DEMO"),
    ("duffel_test_abc", None, DuffelProvider, "TEST"),
    ("duffel_live_abc", None, DemoProvider, "DEMO"),       # a live token alone never turns on paid searches
    ("duffel_live_abc", "false", DemoProvider, "DEMO"),
    ("duffel_live_abc", "true", DuffelProvider, "LIVE"),
    ("something-else", None, DemoProvider, "DEMO"),
])
def test_the_provider_is_chosen_from_the_environment(monkeypatch, token, allow, kind, mode):
    monkeypatch.delenv("RIHLA_ENV", raising=False)  # development
    for name, value in (("DUFFEL_ACCESS_TOKEN", token), ("RIHLA_FLIGHTS_ALLOW_LIVE", allow)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    provider = provider_from_env()
    assert isinstance(provider, kind) and provider.data_mode == mode
    if kind is DemoProvider:
        assert "DEMO" in provider.reason
    assert "abc" not in repr(provider)


def test_the_demo_reason_reaches_the_traveller(monkeypatch):
    monkeypatch.delenv("DUFFEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RIHLA_ENV", raising=False)
    service = FlightSearch(airport_lookup=lookup, clock=lambda: NOW)
    assert any("No flight provider is set up" in n for n in service.search(**SEARCH)["notices"])


# ------------------------------------------------------------------ informational only: nothing books or pays
def test_the_api_only_reads():
    app = FastAPI()
    install_flights(app)
    paths = {p: set(ops) for p, ops in app.openapi()["paths"].items() if p.startswith("/api/flights")}
    assert paths == {"/api/flights": {"get"}, "/api/flights/status": {"get"}}
    r = TestClient(app).post("/api/flights", json={})
    assert r.status_code == 405


def test_duffel_is_only_ever_asked_for_offers():
    duffel = Duffel(duffel_answer(offer("a", "10.00")))
    service = duffel_service(duffel)
    service.search(**SEARCH)
    service.search(**SEARCH, return_date="2026-12-08")
    assert {r.url.path for r in duffel.requests} == {"/air/offer_requests"}
    source = "".join(p.read_text(encoding="utf-8") for p in Path("app/flights").glob("*.py"))
    for forbidden in ("/air/orders", "/payments", "payment_intents", "/air/order_"):
        assert forbidden not in source


def test_install_is_idempotent_and_the_route_needs_no_sign_in():
    app = FastAPI()
    install_flights(app)
    count = len(app.router.routes)
    install_flights(app)
    assert len(app.router.routes) == count and "/api/flights" in app.openapi()["paths"]
    from app.auth.middleware import PROTECTED_PREFIXES
    assert not any("/api/flights".startswith(p) for p in PROTECTED_PREFIXES)


# ------------------------------------------------------------------ environments: production never shows sample data
@pytest.mark.parametrize("raw, env", [
    (None, "development"), ("", "development"), ("test", "test"), (" Production ", "production"),
    ("prod", "production"), ("staging", "production"),  # unknown values fail closed
])
def test_the_deployment_environment(monkeypatch, raw, env):
    from app.deployment_env import deployment_env
    if raw is None:
        monkeypatch.delenv("RIHLA_ENV", raising=False)
    else:
        monkeypatch.setenv("RIHLA_ENV", raw)
    assert deployment_env() == env


@pytest.mark.parametrize("env, token, allow, kind, mode", [
    ("production", None, None, "UnavailableProvider", None),
    ("production", "duffel_test_abc", None, "UnavailableProvider", None),   # never TEST in production
    ("production", "duffel_live_abc", None, "UnavailableProvider", None),   # never live without the switch
    ("production", "duffel_live_abc", "true", "DuffelProvider", "LIVE"),
    ("test", "duffel_test_abc", None, "DuffelProvider", "TEST"),
    ("test", "duffel_live_abc", "true", "DemoProvider", "DEMO"),             # never live in the test environment
    ("test", None, None, "DemoProvider", "DEMO"),
])
def test_providers_per_environment(monkeypatch, env, token, allow, kind, mode):
    for name, value in (("DUFFEL_ACCESS_TOKEN", token), ("RIHLA_FLIGHTS_ALLOW_LIVE", allow)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    provider = provider_from_env(env)
    assert type(provider).__name__ == kind and provider.data_mode == mode
    assert "abc" not in repr(provider)


def production(monkeypatch):
    monkeypatch.setenv("RIHLA_ENV", "production")
    monkeypatch.delenv("DUFFEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RIHLA_FLIGHTS_ALLOW_LIVE", raising=False)
    return api(FlightSearch(airport_lookup=lookup, clock=lambda: NOW))


def test_production_without_a_provider_says_unavailable_and_never_shows_demo(monkeypatch):
    client = production(monkeypatch)
    status = client.get("/api/flights/status").json()
    assert status["environment"] == "production" and status["available"] is False and status["data_mode"] is None
    assert "never shows test or demo" in status["notice"]
    for params in (SEARCH, {**SEARCH, "origin": "??"}):  # unavailable before any input check
        r = client.get("/api/flights", params=params)
        assert r.status_code == 503 and r.json()["error"]["code"] == "flights_unavailable"
        assert r.json()["error"]["retryable"] is False
        assert "DEMO" not in r.text and "offers" not in r.json()


def test_production_refuses_demo_or_test_answers_even_if_a_provider_is_injected():
    demo = FlightSearch(DemoProvider(lookup=lookup), airport_lookup=lookup, clock=lambda: NOW, environment="production")
    assert demo.status()["available"] is False
    with pytest.raises(FlightError) as raised:
        demo.search(**SEARCH)
    assert raised.value.code == "flights_unavailable"
    sandbox = duffel_service(Duffel(duffel_answer(offer("a", "10.00"))), environment="production")
    with pytest.raises(FlightError) as raised:
        sandbox.search(**SEARCH)
    assert raised.value.code == "flights_unavailable"


def test_production_live_keeps_only_live_offers():
    duffel = Duffel(duffel_answer(offer("live", "100.00", live=True), offer("sandbox", "50.00", live=False)))
    service = duffel_service(duffel, token="duffel_live_not-real", environment="production")
    assert service.status() == {**service.status(), "available": True, "data_mode": "LIVE", "provider": "Duffel"}
    body = service.search(**SEARCH)
    assert body["data_mode"] == "LIVE" and [o["id"] for o in body["offers"]] == ["duffel:live"]
    assert body["skipped_offers"]["unusable"] == 1 and body["notices"][0].startswith("Live prices")


def test_development_status_explains_demo(monkeypatch):
    monkeypatch.delenv("RIHLA_ENV", raising=False)
    monkeypatch.delenv("DUFFEL_ACCESS_TOKEN", raising=False)
    status = api(FlightSearch(airport_lookup=lookup)).get("/api/flights/status").json()
    assert status["available"] is True and status["data_mode"] == "DEMO" and status["booking_supported"] is False
    assert status["limits"]["scope"] == "per server process"


def test_the_daily_limit_stops_provider_calls_until_midnight_utc():
    tick = [0.0]
    service = duffel_service(Duffel(duffel_answer()), monotonic=lambda: tick[0], max_calls_per_day=2)
    service.search(**SEARCH)
    tick[0] = 61.0
    service.search(**{**SEARCH, "departure_date": "2026-12-02"})
    tick[0] = 122.0
    with pytest.raises(FlightError) as raised:
        service.search(**{**SEARCH, "departure_date": "2026-12-03"})
    assert raised.value.code == "daily_limit_reached" and raised.value.retry_after == 12 * 3600


def test_failures_are_logged_without_the_token(caplog):
    caplog.set_level("DEBUG")
    with pytest.raises(FlightError):
        duffel_service(Duffel(httpx.Response(401, json={"errors": [{"code": "access_token_not_found"}]}))).search(**SEARCH)
    assert "provider_auth_failed" in caplog.text and TOKEN not in caplog.text


@pytest.mark.parametrize("value, minutes", [
    ("PT5H10M", 310), ("PT45M", 45), ("P1DT2H", 1560), ("PT2H30M40S", 151), ("PT", None), ("", None),
    (None, None), ("5h", None)])
def test_durations(value, minutes):
    assert iso_minutes(value) == minutes
