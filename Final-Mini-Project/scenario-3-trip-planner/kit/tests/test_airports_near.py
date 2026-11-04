"""GET /api/airports/near: the airports near a chosen place, from the bundled data, no network.

The real bundled OurAirports data is used for the identity cases (Paris in France or Texas, Jerusalem, Singapore)
because those are exactly the cases where a wrong answer would send a traveller to the wrong country. Malformed
requests and the suggestion rule are checked with the same data and with small CSV files.
"""
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.airports import AirportError, AirportSearch, install_airports, normalize_coordinates
from app.airports.service import (NEAR_OTHER_COUNTRY_KM, RANKING_NOTE, SOLE_CANDIDATE_KM, SOLE_WINDOW_KM,
                                  distance_km)
from tests.test_airports import row, write_csv

SEARCH = AirportSearch()

# The places a destination box returns (GeoNames points, as in tests/test_destination_identity.py).
PLACES = {
    "Amman": (31.95522, 35.94503, "JO"), "Jerusalem": (31.76904, 35.21633, "IL"), "Paris FR": (48.85341, 2.3488, "FR"),
    "Paris TX": (33.66094, -95.55551, "US"), "Tbilisi": (41.69411, 44.83368, "GE"), "Cusco": (-13.52264, -71.96734, "PE"),
    "Singapore": (1.28967, 103.85007, "SG"), "Rome": (41.89193, 12.51133, "IT"), "London": (51.50853, -0.12574, "GB"),
    "Istanbul": (41.01384, 28.94966, "TR"), "Tokyo": (35.6895, 139.69171, "JP"), "Santiago": (-33.45694, -70.64827, "CL"),
}


def client(service=SEARCH):
    app = FastAPI()
    install_airports(app, service)
    return TestClient(app)


def near(name, **extra):
    lat, lon, country = PLACES[name]
    return client().get("/api/airports/near", params={"lat": lat, "lon": lon, "country": country, **extra})


def codes(body):
    return [a["iata"] for a in body["airports"]]


# ------------------------------------------------------------------ never confuse Paris, France with Paris, Texas
def test_paris_france_lists_french_airports_and_no_texan_one():
    body = near("Paris FR").json()
    assert codes(body)[:2] == ["ORY", "CDG"]
    assert {a["country_code"] for a in body["airports"]} == {"FR"}
    assert not {"PRX", "PHT", "TYR", "TXK"} & set(codes(body))


def test_paris_texas_lists_texan_airports_and_no_french_one():
    body = near("Paris TX").json()
    assert set(codes(body)) == {"TYR", "TXK"}  # the nearest with scheduled service; Paris's own field has none
    assert {a["country_code"] for a in body["airports"]} == {"US"}
    assert not {"CDG", "ORY", "LBG", "BVA"} & set(codes(body))
    assert all(a["distance_km"] > 100 for a in body["airports"])  # said as it is: they are far


def test_the_same_name_never_gets_the_other_countrys_airports_even_with_a_wide_search():
    texas = near("Paris TX", max_km=500).json()
    assert "CDG" not in codes(texas) and {a["country_code"] for a in texas["airports"] if a["in_country"]} == {"US"}
    france = near("Paris FR", max_km=500).json()
    assert not {"TYR", "DFW", "PRX"} & set(codes(france))


# ------------------------------------------------------------------ a city with no airport: Jerusalem
def test_jerusalem_gets_nearby_airports_and_the_ones_across_the_border_are_marked():
    body = near("Jerusalem").json()
    by = {a["iata"]: a for a in body["airports"]}
    assert by["TLV"]["in_country"] is True and by["TLV"]["country_code"] == "IL"
    assert by["AMM"]["in_country"] is False and by["AMM"]["country_code"] == "JO"
    assert by["ADJ"]["in_country"] is False
    assert body["airports"] == sorted(body["airports"], key=lambda a: a["distance_km"])
    assert body["suggested"] is None  # Tel Aviv is the one in Israel, but Amman is as close: the traveller chooses


def test_airports_across_a_border_are_only_listed_when_close():
    body = near("Amman").json()
    assert codes(body) == ["ADJ", "AMM"]  # Tel Aviv, 100 km away in another country, is not offered
    assert all(a["distance_km"] <= NEAR_OTHER_COUNTRY_KM or a["in_country"] for a in near("Jerusalem").json()["airports"])


def test_a_place_with_no_airport_in_reach_gets_an_empty_honest_answer():
    body = client().get("/api/airports/near", params={"lat": 0.0, "lon": -30.0, "country": "BR"}).json()  # mid-ocean
    assert body["airports"] == [] and body["count"] == 0 and body["suggested"] is None


# ------------------------------------------------------------------ ranking, and the nearest is not "the best"
@pytest.mark.parametrize("name", list(PLACES))
def test_airports_are_ranked_by_distance_with_a_true_distance(name):
    lat, lon, _ = PLACES[name]
    body = near(name).json()
    distances = [a["distance_km"] for a in body["airports"]]
    assert distances == sorted(distances)
    for a in body["airports"]:
        assert a["iata"] and a["scheduled_service"] is True
        assert abs(a["distance_km"] - distance_km(lat, lon, a["latitude"], a["longitude"])) < 0.06


def test_the_answer_says_that_the_nearest_airport_is_not_necessarily_the_best():
    body = near("Istanbul").json()
    assert body["note"] == RANKING_NOTE and "not always the best" in body["note"]
    assert codes(body)[:2] == ["SAW", "IST"]  # SAW is nearer to the centre; both are real choices


def test_a_big_city_lists_all_its_airports_and_preselects_none():
    for name in ("London", "Paris FR", "Rome", "Istanbul", "Tokyo", "Amman"):
        body = near(name).json()
        assert len(body["airports"]) >= 2 and body["suggested"] is None, name


# ------------------------------------------------------------------ exactly one clearly valid candidate
@pytest.mark.parametrize("name,iata", [("Tbilisi", "TBS"), ("Cusco", "CUZ"), ("Santiago", "SCL")])
def test_one_clear_airport_is_suggested(name, iata):
    body = near(name).json()
    assert codes(body) == [iata]
    assert body["suggested"] == body["airports"][0]["id"]


def test_a_sole_airport_in_another_country_is_never_suggested():
    body = near("Singapore").json()  # two Singapore airports and two across the border
    assert body["suggested"] is None
    assert [a["in_country"] for a in body["airports"]] == [True, True, False, False]


def test_without_a_country_nothing_is_suggested_and_nothing_is_called_in_or_out_of_country():
    lat, lon, _ = PLACES["Cusco"]
    body = client().get("/api/airports/near", params={"lat": lat, "lon": lon}).json()
    assert body["suggested"] is None and body["country"] is None
    assert all(a["in_country"] is None for a in body["airports"])


def test_the_suggestion_does_not_depend_on_how_far_the_caller_looks():
    narrow = near("Amman", max_km=10).json()  # only ADJ is within 10 km, but Queen Alia is 26 km away
    assert codes(narrow) == ["ADJ"] and narrow["suggested"] is None
    wide = near("Cusco", max_km=500).json()
    assert wide["suggested"] is not None


def test_a_sole_candidate_must_be_close_enough_to_be_the_citys_airport(tmp_path):
    path = write_csv(tmp_path / "a.csv", [row(id="1", iata_code="AAA", icao_code="LLAA", latitude_deg="31.0",
                                              longitude_deg="35.0", name="Far Field", municipality="Far")])
    service = AirportSearch(data_path=path)
    far = client(service).get("/api/airports/near", params={
        "lat": 31.0 + SOLE_CANDIDATE_KM * 1.5 / 111, "lon": 35.0, "country": "IL"}).json()
    assert [a["iata"] for a in far["airports"]] == ["AAA"] and far["suggested"] is None  # listed, not preselected
    close = client(service).get("/api/airports/near", params={"lat": 31.1, "lon": 35.0, "country": "IL"}).json()
    assert close["suggested"] == close["airports"][0]["id"]


def test_another_airport_in_the_same_country_within_the_window_blocks_the_suggestion(tmp_path):
    path = write_csv(tmp_path / "a.csv", [
        row(id="1", iata_code="AAA", icao_code="LLAA", latitude_deg="31.0", longitude_deg="35.0"),
        row(id="2", iata_code="BBB", icao_code="LLBB", latitude_deg=str(31.0 + (SOLE_WINDOW_KM - 20) / 111),
            longitude_deg="35.0", name="Second Field")])
    body = client(AirportSearch(data_path=path)).get(
        "/api/airports/near", params={"lat": 31.0, "lon": 35.0, "country": "IL"}).json()
    assert {a["iata"] for a in body["airports"]} == {"AAA", "BBB"} and body["suggested"] is None


def test_airports_without_scheduled_service_or_an_iata_code_are_never_offered(tmp_path):
    path = write_csv(tmp_path / "a.csv", [
        row(id="1", iata_code="AAA", icao_code="LLAA", scheduled_service="no"),
        row(id="2", iata_code="", icao_code="LLBB", name="No Code Field"),
        row(id="3", iata_code="CCC", icao_code="LLCC", name="Real Field", latitude_deg="32.01", longitude_deg="34.89")])
    body = client(AirportSearch(data_path=path)).get(
        "/api/airports/near", params={"lat": 32.0, "lon": 34.9, "country": "IL"}).json()
    assert [a["iata"] for a in body["airports"]] == ["CCC"]


# ------------------------------------------------------------------ strict validation
@pytest.mark.parametrize("params,code", [
    ({}, "missing_coordinates"), ({"lat": "1"}, "missing_coordinates"), ({"lon": "1"}, "missing_coordinates"),
    ({"lat": "abc", "lon": "1"}, "invalid_coordinates"), ({"lat": "1", "lon": "x"}, "invalid_coordinates"),
    ({"lat": "91", "lon": "1"}, "invalid_coordinates"), ({"lat": "-90.5", "lon": "1"}, "invalid_coordinates"),
    ({"lat": "1", "lon": "181"}, "invalid_coordinates"), ({"lat": "nan", "lon": "1"}, "invalid_coordinates"),
    ({"lat": "inf", "lon": "1"}, "invalid_coordinates"), ({"lat": "1,5", "lon": "1"}, "invalid_coordinates"),
    ({"lat": "1", "lon": "1", "country": "ITA"}, "invalid_country"),
    ({"lat": "1", "lon": "1", "country": "1A"}, "invalid_country"),
    ({"lat": "1", "lon": "1", "country": "ZZ"}, "unknown_country"),
    ({"lat": "1", "lon": "1", "max_km": "0"}, "invalid_distance"),
    ({"lat": "1", "lon": "1", "max_km": "501"}, "invalid_distance"),
    ({"lat": "1", "lon": "1", "max_km": "far"}, "invalid_distance"),
    ({"lat": "1", "lon": "1", "max_km": "nan"}, "invalid_distance"),
    ({"lat": "1", "lon": "1", "limit": "0"}, "invalid_limit"), ({"lat": "1", "lon": "1", "limit": "11"}, "invalid_limit"),
    ({"lat": "1", "lon": "1", "limit": "two"}, "invalid_limit"),
])
def test_bad_requests_are_refused_with_a_stable_code(params, code):
    response = client().get("/api/airports/near", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code and response.json()["error"]["retryable"] is False


def test_a_lowercase_country_is_accepted_and_limit_caps_the_list():
    lat, lon, _ = PLACES["London"]
    body = client().get("/api/airports/near", params={"lat": lat, "lon": lon, "country": "gb", "limit": 3}).json()
    assert body["country"] == {"code": "GB", "name": "United Kingdom"} and body["count"] == 3


def test_coordinates_are_never_coerced():
    for bad in (True, False, None, [1], {"a": 1}, "", "  "):
        with pytest.raises(AirportError):
            normalize_coordinates(bad, 1)
    assert normalize_coordinates("31.95", "35.94") == (31.95, 35.94)
    assert normalize_coordinates(0, 0) == (0.0, 0.0)


def test_distance_is_a_great_circle_distance():
    assert distance_km(0, 0, 0, 0) == 0
    assert math.isclose(distance_km(0, 0, 0, 180), 20015.1, rel_tol=1e-3)  # half the earth
    assert math.isclose(distance_km(40.6413, -73.7781, 51.4700, -0.4543), 5540, rel_tol=0.01)  # JFK to LHR, ~5,540 km

    def by_cosines(lat1, lon1, lat2, lon2):  # another formula, as an independent check of the haversine one
        p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
        return 6371.0088 * math.acos(math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl))
    for a, b in (((48.85341, 2.3488), (33.66094, -95.55551)), ((31.95522, 35.94503), (31.76904, 35.21633))):
        assert math.isclose(distance_km(*a, *b), by_cosines(*a, *b), rel_tol=1e-6)
    assert 7700 < distance_km(48.85341, 2.3488, 33.66094, -95.55551) < 7900  # Paris, France to Paris, Texas


def test_the_answer_is_read_only_cacheable_and_names_its_source():
    response = near("Cusco")
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json()["source"]["provider"] == "OurAirports"
    assert client().post("/api/airports/near").status_code == 405


def test_an_unavailable_dataset_is_a_clear_error_not_an_empty_answer(tmp_path):
    body = client(AirportSearch(data_path=tmp_path / "missing.csv")).get(
        "/api/airports/near", params={"lat": "1", "lon": "1"})
    assert body.status_code == 503 and body.json()["error"]["code"] == "data_unavailable"
