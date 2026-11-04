"""services/travel_data.py: a qualified city name ("Paris, Texas, United States") reaches the right Wikivoyage page,
never a namesake; replay keeps its recorded cities; transient upstream failures are retried a bounded number of
times. Every upstream is mocked (httpx.MockTransport): no network, no cost.
"""
import httpx
import pytest

import services.travel_data as td

# Open-Meteo (GeoNames) places, as the geocoding API returns them (real ids and coordinates).
PARIS_FR = {"id": 2988507, "name": "Paris", "latitude": 48.85341, "longitude": 2.3488, "feature_code": "PPLC",
            "country_code": "FR", "country": "France", "admin1": "Île-de-France Region", "population": 2138551}
PARIS_TX = {"id": 4717560, "name": "Paris", "latitude": 33.66094, "longitude": -95.55551, "feature_code": "PPLA2",
            "country_code": "US", "country": "United States", "admin1": "Texas", "population": 24782}
ITALY_COUNTRY = {"id": 3175395, "name": "Italy", "latitude": 42.83333, "longitude": 12.83333, "feature_code": "PCLI",
                 "country_code": "IT", "country": "Italy", "population": 58915656}
ITALY_TX = {"id": 4701458, "name": "Italy", "latitude": 32.18404, "longitude": -96.88472, "feature_code": "PPL",
            "country_code": "US", "country": "United States", "admin1": "Texas", "population": 1897}
TOKYO = {"id": 1850147, "name": "Tokyo", "latitude": 35.6895, "longitude": 139.69171, "feature_code": "PPLC",
         "country_code": "JP", "country": "Japan", "admin1": "Tokyo", "population": 9733276}
NYC = {"id": 5128581, "name": "New York", "latitude": 40.71427, "longitude": -74.00597, "feature_code": "PPL",
       "country_code": "US", "country": "United States", "admin1": "New York", "population": 8804190}
CUSCO = {"id": 3941584, "name": "Cusco", "latitude": -13.52264, "longitude": -71.96734, "feature_code": "PPLA",
         "country_code": "PE", "country": "Peru", "admin1": "Cuzco Department", "population": 312140}
PARIS_TN = {**PARIS_TX, "id": 4646571, "latitude": 36.302, "longitude": -88.3267, "admin1": "Tennessee"}
# Wikivoyage page coordinates (prop=coordinates), as recorded on 2026-11-04 ("New York" is the state's page).
WV_COORDS = {"Paris": (48.856, 2.351), "Paris (Texas)": (33.66083, -95.55556), "Italy": (42.5, 12.5),
             "Tokyo": (35.689506, 139.6917), "New York": (43.0, -75.5), "New York City": (40.7127, -74.0059),
             "Cusco": (-13.525, -71.972)}
PLACES = {"Paris": [PARIS_FR, PARIS_TX, PARIS_TN], "Italy": [ITALY_COUNTRY, ITALY_TX], "Tokyo": [TOKYO],
          "New York": [NYC], "Cusco": [CUSCO]}


class Upstream:
    """Open-Meteo geocoding and the Wikivoyage API, scripted; records every request."""

    def __init__(self, geosearch=None):
        self.requests, self.geosearch = [], geosearch or []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = dict(request.url.params)
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": PLACES.get(params["name"], [])})
        if params.get("list") == "geosearch":
            return httpx.Response(200, json={"query": {"geosearch": self.geosearch}})
        if params.get("prop") == "coordinates":
            pages = []
            for title in params["titles"].split("|"):
                if title in WV_COORDS:
                    lat, lon = WV_COORDS[title]
                    pages.append({"title": title, "coordinates": [{"lat": lat, "lon": lon}]})
                else:
                    pages.append({"title": title, "missing": True})
            return httpx.Response(200, json={"query": {"pages": pages}})
        raise AssertionError(f"unexpected request {request.url}")


@pytest.fixture()
def live(monkeypatch):
    """Live mode with scripted upstreams, no waiting, a clean memory cache."""
    monkeypatch.setenv("TRAVEL_MODE", "live")
    monkeypatch.setattr(td.time, "sleep", lambda s: None)
    monkeypatch.setattr(td, "_MEM", {})
    upstream = Upstream()

    def use(handler):
        monkeypatch.setattr(td, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
        return handler
    use(upstream)
    upstream.use = use
    return upstream


# ------------------------------------------------------------------ the right page, never a namesake
def test_same_name_cities_in_different_countries_get_their_own_pages(live):
    assert td.city_title("Paris, Texas, United States") == "Paris (Texas)"
    assert td.city_title("Paris, Île-de-France Region, France") == "Paris"


def test_a_namesake_town_never_gets_the_country_page(live):
    with pytest.raises(td.DataError) as raised:
        td.city_title("Italy, Texas, United States")
    assert raised.value.status == 404 and raised.value.code == "no_guide"
    assert "Italy, Texas, United States" in raised.value.message and "km away" in raised.value.message


def test_a_page_found_near_the_point_is_used_when_its_title_is_the_place(live):
    live.geosearch = [{"title": "Tokyo/Shinjuku", "lat": 35.69, "lon": 139.70}, {"title": "Tokyo", "lat": 35.6895,
                                                                                  "lon": 139.6917}]
    assert td.city_title("Tokyo, Japan") == "Tokyo"


def test_a_place_not_in_the_given_region_or_country_is_not_located(live):
    with pytest.raises(td.DataError) as raised:
        td.city_title("Paris, Ontario, Canada")
    assert raised.value.code == "place_not_found"


def test_each_qualified_name_is_resolved_and_cached_by_its_own_identity(live):
    td.city_title("Paris, Texas, United States")
    td.city_title("Paris, Texas, United States")
    td.city_title("Paris, Île-de-France Region, France")
    geocoding = [r for r in live.requests if r.url.host == "geocoding-api.open-meteo.com"]
    assert len(geocoding) == 2  # one per place, the repeat came from the cache
    assert {k for (kind, k) in td._MEM if kind == "wikivoyage_title"} == {
        "paris-texas-united-states", "paris-ile-de-france-region-france"}


def test_a_city_whose_guide_is_called_city_is_found_and_the_state_page_is_not_used(live):
    assert td.city_title("New York, United States") == "New York City"


def test_a_hand_typed_region_is_tolerated_only_when_the_country_has_one_such_place(live):
    assert td.city_title("Cusco, Peru") == "Cusco"  # one Cusco in Peru (its region is "Cuzco Department")
    with pytest.raises(td.DataError) as raised:  # Paris, Texas and Paris, Tennessee: the wrong region decides nothing
        td.city_title("Paris, Ontario, United States")
    assert raised.value.code == "place_not_found"


def test_a_bare_name_is_looked_up_as_before(live):
    assert td.city_title("Paris") == "Paris"  # older clients: the page of that name, no extra lookups
    assert td.city_title("amman") == "Amman"  # the recorded city's own spelling
    assert live.requests == []


def test_the_weather_point_of_a_qualified_name_is_the_located_city(live):
    td.city_title("Paris, Texas, United States")
    point = td.city_point("Paris, Texas, United States")
    assert point == {"name": "Paris (Texas)", "lat": 33.6609, "lon": -95.5555}


# ------------------------------------------------------------------ replay: recorded data only, never a namesake
@pytest.fixture()
def replay(monkeypatch):
    monkeypatch.setenv("TRAVEL_MODE", "replay")

    def no_network(request):
        raise AssertionError("replay mode called the network")
    monkeypatch.setattr(td, "_client", httpx.Client(transport=httpx.MockTransport(no_network)))


@pytest.mark.parametrize("city", ["Amman", "Amman, Jordan", "Amman, Amman Governorate, Jordan", "Istanbul",
                                  "Istanbul, Turkey", "Istanbul, Republic of Türkiye"])
def test_replay_serves_its_recorded_cities_however_they_are_named(replay, city):
    assert td.city_title(city) in ("Amman", "Istanbul")


@pytest.mark.parametrize("city", ["Amman, Texas, United States", "Istanbul, Ontario, Canada",
                                  "Paris, Texas, United States", "Italy, Texas, United States"])
def test_replay_never_serves_a_recorded_city_for_a_namesake(replay, city):
    with pytest.raises(td.DataError) as raised:
        td.city_title(city)
    assert raised.value.code == "not_cached" and raised.value.status == 404


# ------------------------------------------------------------------ transient failures: bounded retries
def sequence(*replies):
    calls = []

    def handler(request):
        calls.append(request)
        reply = replies[min(len(calls), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply
    handler.calls = calls
    return handler


def test_a_server_error_is_retried_then_succeeds(live):
    handler = live.use(sequence(httpx.Response(503), httpx.Response(200, json={"ok": True})))
    r, _ = td.http_get("https://en.wikivoyage.org/w/api.php")
    assert r.status_code == 200 and len(handler.calls) == 2


def test_a_rate_limit_waits_as_told_within_a_bound(live, monkeypatch):
    waits = []
    monkeypatch.setattr(td.time, "sleep", waits.append)
    live.use(sequence(httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(429, headers={"Retry-After": "600"}),
                      httpx.Response(200)))
    r, _ = td.http_get("https://example.test/a")
    assert r.status_code == 200 and [w for w in waits if w >= 1] == [2.0, td.MAX_RETRY_WAIT_S]


def test_a_dropped_connection_is_retried(live):
    handler = live.use(sequence(httpx.ConnectError("refused"), httpx.Response(200)))
    assert td.http_get("https://example.test/a")[0].status_code == 200 and len(handler.calls) == 2


def test_retries_are_bounded_and_the_last_answer_is_reported(live):
    handler = live.use(sequence(httpx.Response(503)))
    r, _ = td.http_get("https://example.test/a")
    assert r.status_code == 503 and len(handler.calls) == td.MAX_ATTEMPTS
    handler = live.use(sequence(httpx.ConnectError("down")))
    with pytest.raises(httpx.ConnectError):
        td.http_get("https://example.test/a")
    assert len(handler.calls) == td.MAX_ATTEMPTS


@pytest.mark.parametrize("reply", [httpx.Response(404), httpx.Response(400), httpx.ReadTimeout("slow")])
def test_answers_and_timeouts_are_not_retried(live, reply):
    handler = live.use(sequence(reply))
    if isinstance(reply, Exception):
        with pytest.raises(httpx.ReadTimeout):
            td.http_get("https://example.test/a")
    else:
        assert td.http_get("https://example.test/a")[0].status_code == reply.status_code
    assert len(handler.calls) == 1


def test_a_failed_live_source_without_a_copy_is_an_error_not_data(live):
    live.use(sequence(httpx.Response(503)))
    with pytest.raises(td.DataError) as raised:
        td.city_listings("Paris, Texas, United States")
    assert raised.value.status in (502, 503)


# ------------------------------------------------------------------ the travel API: no listings for a namesake
def test_the_attractions_endpoint_says_no_guide_instead_of_listing_another_place(live, monkeypatch):
    from fastapi.testclient import TestClient
    from services import travel_api
    monkeypatch.setenv("TRAVEL_API_KEY", "test-key")
    r = TestClient(travel_api.app).get("/api/attractions", params={"city": "Italy, Texas, United States"},
                                        headers={"X-API-Key": "test-key"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_guide" and "attractions" not in r.json()
