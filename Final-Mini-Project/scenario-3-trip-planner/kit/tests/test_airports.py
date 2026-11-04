"""GET /api/airports: airport search for departure and arrival. No network: the data is bundled.

Most tests search the real bundled OurAirports data (app/airports/data/airports.csv), so they also check that the
shipped file is sound. Malformed data is tested with small CSV files written in tmp_path.
"""
import csv
import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.airports import AirportError, AirportSearch, install_airports, normalize_airport, normalize_query
from app.airports.build_dataset import OUTPUT_COLUMNS, build, keep_row
from app.airports.service import DATA_PATH, META_PATH, _fold, read_airports, resolve_duplicate_codes

SEARCH = AirportSearch()  # the bundled data, loaded once for the whole module


def api(service=SEARCH):
    app = FastAPI()
    install_airports(app, service)
    return TestClient(app)


def get(q, **params):
    return api().get("/api/airports", params={"q": q, **params})


def codes(body):
    return [a["iata"] for a in body["results"]]


def row(**fields):
    base = {"id": "1", "ident": "LLBG", "type": "large_airport", "name": "Ben Gurion International Airport",
            "latitude_deg": "32.0114", "longitude_deg": "34.8867", "iso_country": "IL", "country_name": "Israel",
            "iso_region": "IL-M", "region_name": "Central District", "municipality": "Tel Aviv",
            "scheduled_service": "yes", "icao_code": "LLBG", "iata_code": "TLV", "keywords": ""}
    return {**base, **fields}


def write_csv(path, rows, columns=OUTPUT_COLUMNS):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


# ------------------------------------------------------------------ TLV
@pytest.mark.parametrize("q", ["TLV", "tlv", "LLBG", "Tel Aviv", "tel-aviv", "Ben Gurion", "ben gur"])
def test_tel_aviv_is_found_by_code_city_and_name(q):
    body = get(q).json()
    first = body["results"][0]
    assert first == {
        "id": first["id"], "name": "Ben Gurion International Airport", "city": "Tel Aviv",
        "region": "Central District", "country": "Israel", "country_code": "IL", "iata": "TLV", "icao": "LLBG",
        "latitude": first["latitude"], "longitude": first["longitude"], "type": "large_airport",
        "scheduled_service": True, "label": "Ben Gurion International Airport (TLV), Tel Aviv, Israel",
        "ambiguous_city": False}
    assert first["id"].startswith("ourairports:") and 31.9 < first["latitude"] < 32.1 and 34.8 < first["longitude"] < 35


def test_an_exact_code_is_the_only_or_first_answer():
    assert codes(get("TLV").json())[0] == "TLV"
    assert codes(get("LHR").json())[0] == "LHR"
    assert get("EGLL").json()["results"][0]["iata"] == "LHR"  # ICAO


# ------------------------------------------------------------------ London and duplicate city names
def test_london_lists_its_airports_first_and_flags_london_ontario():
    body = get("London", limit=10).json()
    found = codes(body)
    assert {"LHR", "LGW", "STN", "LCY", "LTN", "SEN", "YXU"} <= set(found)
    assert set(found[:4]) == {"LHR", "LGW", "STN", "LCY"}  # scheduled service, in London itself
    by_code = {a["iata"]: a for a in body["results"]}
    assert by_code["YXU"]["country"] == "Canada" and by_code["YXU"]["region"] == "Ontario"
    assert by_code["YXU"]["ambiguous_city"] and by_code["LHR"]["ambiguous_city"] and body["ambiguous"]
    assert by_code["LTN"]["city"] == "Luton" and not by_code["LTN"]["ambiguous_city"]  # "Luton, Luton" cleaned
    assert by_code["STN"]["city"] == "London, Essex"


def test_the_same_city_in_two_regions_of_one_country_is_ambiguous():
    body = get("Portland").json()
    by_code = {a["iata"]: a for a in body["results"]}
    assert by_code["PDX"]["region"] == "Oregon" and by_code["PWM"]["region"] == "Maine"
    assert by_code["PDX"]["ambiguous_city"] and by_code["PWM"]["ambiguous_city"]


def test_main_passenger_airports_outrank_small_fields_of_the_same_city_name():
    body = get("Paris").json()
    assert set(codes(body)[:2]) == {"CDG", "ORY"}
    texas = next(a for a in body["results"] if a["iata"] == "PRX")
    assert texas["region"] == "Texas" and texas["ambiguous_city"] and body["ambiguous"]


def test_a_country_name_lists_that_country_s_airports_first():
    assert set(codes(get("Jordan").json())[:3]) == {"AMM", "AQJ", "ADJ"}


def test_accents_and_alternative_names_match():
    assert codes(get("zurich").json())[0] == "ZRH"
    assert set(codes(get("NYC").json())[:3]) == {"JFK", "LGA", "EWR"}  # OurAirports keywords


# ------------------------------------------------------------------ missing IATA codes
def test_an_airport_without_iata_code_is_kept_with_null():
    first = get("OJKF").json()["results"][0]
    assert first["iata"] is None and first["icao"] == "OJKF" and first["country"] == "Jordan"
    assert first["label"] == "King Feisal Air Base (OJKF), Al-Jafr, Jordan"


def test_an_airport_without_any_code_has_a_label_without_brackets():
    airport = normalize_airport(row(iata_code="", icao_code=""))
    assert airport["iata"] is None and airport["icao"] is None
    assert airport["label"] == "Ben Gurion International Airport, Tel Aviv, Israel"


def test_scheduled_only_leaves_out_airports_without_scheduled_service():
    every = get("London", limit=10).json()
    scheduled = get("London", limit=10, scheduled_only="true").json()
    assert "BQH" in codes(every) and "BQH" not in codes(scheduled)
    assert all(a["scheduled_service"] for a in scheduled["results"])


# ------------------------------------------------------------------ answers and input
def test_answer_shape_source_and_cache_header():
    r = get("Amman")
    body = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    assert set(body) == {"query", "count", "results", "ambiguous", "cached", "source"}
    assert body["count"] == len(body["results"]) and "AMM" in codes(body)
    assert body["source"]["provider"] == "OurAirports" and body["source"]["licence"] == "Public domain"
    assert body["source"]["data_date"] == json.loads(META_PATH.read_text(encoding="utf-8"))["built"]


def test_no_match_is_an_empty_answer_not_an_error():
    r = get("zzqxqz")
    assert r.status_code == 200 and r.json()["count"] == 0 and r.json()["results"] == []
    assert r.json()["ambiguous"] is False


@pytest.mark.parametrize("q, code", [
    ("", "missing_query"), ("   ", "missing_query"), ("T", "query_too_short"), ("12", "invalid_query"),
    ("!!", "invalid_query"), ("TL\x00V", "invalid_query"), ("x" * 81, "query_too_long"),
])
def test_invalid_queries_are_refused(q, code):
    r = get(q)
    assert r.status_code == 422 and r.json()["error"] == {"code": code, "message": r.json()["error"]["message"],
                                                          "retryable": False}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 11}, {"scheduled_only": "maybe"}])
def test_out_of_range_parameters_are_rejected(params):
    assert get("TLV", **params).status_code == 422


def test_the_limit_is_applied():
    assert get("London", limit=3).json()["count"] == 3


def test_the_query_is_cleaned():
    assert normalize_query("  Tel   Aviv ") == "Tel Aviv"
    assert get("  tel   AVIV ").json()["query"] == "tel AVIV"


# ------------------------------------------------------------------ malformed data
def test_malformed_rows_are_skipped_and_bad_values_become_null(tmp_path):
    rows = [
        row(),
        row(id="2", name="", iata_code="AAA"),                     # no name
        row(id="x", iata_code="BBB"),                              # bad id
        row(id="4", type="heliport", iata_code="CCC"),            # not an airport
        row(id="5", type="closed", iata_code="DDD"),              # closed
        row(id="6", name="No Coordinates Field", latitude_deg="abc", iata_code="NCF", icao_code="KNCF"),
        row(id="7", name="Bad Codes Field", iata_code="T1V", icao_code="XX", iso_country="ISR"),
        row(id="8", name="Null Island Field", latitude_deg="0", longitude_deg="0", iata_code="NIF"),
    ]
    search = AirportSearch(data_path=write_csv(tmp_path / "a.csv", rows))
    assert search.search("Field", limit=10)["count"] == 3 and search.skipped_rows == 4
    by_name = {a["name"]: a for a in search.search("Field", limit=10)["results"]}
    assert by_name["No Coordinates Field"]["latitude"] is None and by_name["No Coordinates Field"]["iata"] == "NCF"
    assert by_name["Null Island Field"]["latitude"] is None and by_name["Null Island Field"]["longitude"] is None
    bad = by_name["Bad Codes Field"]
    assert bad["iata"] is None and bad["icao"] is None and bad["country_code"] is None


def test_a_code_given_to_two_airports_stays_with_the_more_likely_one(tmp_path):
    rows = [row(id="1", name="Small Strip", type="small_airport", scheduled_service="no"), row(id="2")]
    search = AirportSearch(data_path=write_csv(tmp_path / "a.csv", rows))
    by_name = {a["name"]: a for a in search.search("Tel Aviv")["results"]}
    assert by_name["Ben Gurion International Airport"]["iata"] == "TLV"
    assert by_name["Small Strip"]["iata"] is None and by_name["Small Strip"]["label"] == "Small Strip, Tel Aviv, Israel"
    assert search.search("TLV")["results"][0]["name"] == "Ben Gurion International Airport"


def test_duplicate_ids_keep_one_airport():
    airport = normalize_airport(row())
    assert len(resolve_duplicate_codes([airport, dict(airport)])) == 1


@pytest.mark.parametrize("content", [None, "", "id,name\n1,Only two columns\n", "id,type\n"])
def test_missing_or_broken_data_is_reported_never_an_empty_answer(tmp_path, content):
    path = tmp_path / "airports.csv"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    r = api(AirportSearch(data_path=path)).get("/api/airports", params={"q": "TLV"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "data_unavailable"


def test_data_that_appears_later_is_loaded_on_the_next_search(tmp_path):
    path = tmp_path / "airports.csv"
    search = AirportSearch(data_path=path)
    with pytest.raises(AirportError):
        search.search("TLV")
    write_csv(path, [row()])
    assert search.search("TLV")["count"] == 1


# ------------------------------------------------------------------ cache, threads, install
def test_answers_are_cached_case_and_space_insensitively():
    search = AirportSearch()
    assert search.search("Heathrow")["cached"] is False
    assert search.search("  HEATHROW ")["cached"] is True


def test_concurrent_first_searches_load_the_data_once():
    search = AirportSearch()
    answers = []
    threads = [threading.Thread(target=lambda: answers.append(search.search("TLV")["count"])) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert answers == [1] * 8


def test_install_is_idempotent_and_the_route_needs_no_sign_in():
    app = FastAPI()
    install_airports(app)
    routes_after_one = len(app.router.routes)
    install_airports(app)
    assert len(app.router.routes) == routes_after_one
    assert "/api/airports" in app.openapi()["paths"]
    from app.auth.middleware import PROTECTED_PREFIXES
    assert not any("/api/airports".startswith(p) for p in PROTECTED_PREFIXES)


# ------------------------------------------------------------------ the bundled data and its build
def test_the_bundled_data_is_clean_and_matches_its_metadata():
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    airports, _, skipped = read_airports(DATA_PATH)
    assert skipped == 0 and len(airports) == meta["airports"] > 9000
    iata = [a["iata"] for a in airports if a["iata"]]
    assert len(iata) == len(set(iata)) == meta["with_iata"]
    assert meta["licence"] == "Public domain" and "ourairports" in meta["url"]


def test_build_keeps_passenger_airports_and_adds_names(tmp_path):
    raw = [
        row(id="10", country_name=None, region_name=None),
        row(id="3", name="Big Field", type="medium_airport", iata_code="", scheduled_service="no", icao_code="LLBF"),
        row(id="11", name="Farm Strip", type="small_airport", iata_code="", scheduled_service="no", icao_code=""),
        row(id="12", name="Island Strip", type="small_airport", iata_code="ISS", scheduled_service="no"),
        row(id="13", name="Pad", type="heliport", iata_code="PAD"),
        row(id="14", name="", iata_code="NON"),
    ]
    raw_columns = [c for c in OUTPUT_COLUMNS if c not in ("country_name", "region_name")]
    write_csv(tmp_path / "airports.csv", raw, raw_columns)
    write_csv(tmp_path / "countries.csv", [{"code": "IL", "name": "Israel"}], ["code", "name"])
    write_csv(tmp_path / "regions.csv", [{"code": "IL-M", "name": "Central District"}], ["code", "name"])
    out, meta_out = tmp_path / "out" / "airports.csv", tmp_path / "out" / "meta.json"
    meta = build(tmp_path, out, meta_out)
    with out.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert [r["id"] for r in written] == ["3", "10", "12"]  # sorted by id; farm strip, heliport, nameless dropped
    assert written[1]["country_name"] == "Israel" and written[1]["region_name"] == "Central District"
    assert meta["airports"] == 3 and meta["with_iata"] == 2 and meta["skipped"] == {
        "not a passenger airport type": 2, "malformed": 1}
    assert json.loads(meta_out.read_text(encoding="utf-8"))["airports"] == 3


@pytest.mark.parametrize("fields, kept", [
    ({"type": "large_airport"}, True), ({"type": "medium_airport", "iata_code": ""}, True),
    ({"type": "small_airport", "iata_code": "", "scheduled_service": "no"}, False),
    ({"type": "small_airport", "iata_code": "", "scheduled_service": "yes"}, True),
    ({"type": "seaplane_base"}, False), ({"type": "closed"}, False), ({"type": "balloonport"}, False),
])
def test_which_rows_the_build_keeps(fields, kept):
    assert keep_row(row(**fields)) is kept


# ------------------------------------------------------------------ departure country
def test_a_country_filter_keeps_only_that_countrys_airports():
    body = get("International", country="jo", limit=10).json()
    assert body["results"] and {a["country_code"] for a in body["results"]} == {"JO"}
    assert "AMM" in codes(body)
    # "London" in Canada only: London, Ontario, never Heathrow.
    assert codes(get("London", country="CA").json())[0] == "YXU"
    assert "LHR" not in codes(get("London", country="CA").json())


def test_a_country_with_no_match_is_an_empty_answer():
    body = get("Heathrow", country="JO").json()
    assert body["count"] == 0 and body["results"] == []


@pytest.mark.parametrize("country", ["J", "JOR", "1A", "J0"])
def test_a_malformed_country_is_refused(country):
    response = get("Amman", country=country)
    assert response.status_code == 422
    if len(country) <= 2:  # longer values are refused by FastAPI's max_length before the service sees them
        assert response.json()["error"]["code"] == "invalid_country"


def test_an_empty_country_means_every_country():
    assert codes(get("London", country="").json())[:2] == codes(get("London").json())[:2]


def test_the_country_filter_is_part_of_the_cache_key():
    service = AirportSearch()
    assert {a["country_code"] for a in service.search("London", country="GB")["results"]} == {"GB"}
    assert {a["country_code"] for a in service.search("London", country="CA")["results"]} == {"CA"}


def test_the_countries_list_comes_from_the_bundled_data():
    response = api().get("/api/airports/countries")
    assert response.status_code == 200 and response.headers["cache-control"] == "public, max-age=86400"
    body = response.json()
    by_code = {c["code"]: c for c in body["countries"]}
    assert by_code["JO"]["name"] == "Jordan" and by_code["JO"]["airports"] >= 2
    assert body["count"] == len(body["countries"]) > 150
    keys = [(_fold(c["name"]), c["code"]) for c in body["countries"]]
    assert keys == sorted(keys) and len(by_code) == len(keys)  # by name, accents ignored; one entry per code
    assert sum(c["airports"] for c in body["countries"]) <= json.loads(META_PATH.read_text(encoding="utf-8"))["airports"]
    assert body["source"]["licence"] == "Public domain"


def test_the_countries_list_reports_missing_data_as_unavailable(tmp_path):
    response = api(AirportSearch(data_path=tmp_path / "missing.csv")).get("/api/airports/countries")
    assert response.status_code == 503 and response.json()["error"]["code"] == "data_unavailable"
