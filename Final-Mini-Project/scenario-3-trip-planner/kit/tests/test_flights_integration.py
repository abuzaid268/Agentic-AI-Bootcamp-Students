"""Flights end to end, with Duffel mocked (httpx.MockTransport): no network, no token, no cost.

- the airport the traveller picks from the nearby list is exactly what Duffel is asked about;
- a flight search that fails (Duffel down, slow, refusing) never blocks the sightseeing trip request;
- flight prices stay out of the plan, the budget and everything that builds them.

The Duffel answers are SYNTHETIC, in the shape of Duffel's documented schema. No real Duffel call has ever been made.
"""
import json
import re
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.airports import AirportSearch, install_airports
from app.flights import DemoProvider, DuffelProvider, FlightSearch, install_flights
from planning.budget_analyst import UNACCOUNTED_CATEGORIES
from tests.test_flights import NOW, TODAY, TOKEN, Duffel, duffel_answer, offer, segment

ROOT = Path(__file__).resolve().parents[1]
AIRPORTS = AirportSearch()  # the bundled data: the same airports the boxes search
JERUSALEM = {"lat": 31.76904, "lon": 35.21633, "country": "IL"}
DEPARTURE = "2026-12-01"


def real_lookup(code):
    found = AIRPORTS.search(code, limit=1)["results"]
    return found[0] if found and found[0]["iata"] == code else None


def app_with(duffel, **kwargs):
    """The real airport routes and the flight route backed by a scripted Duffel, in one app."""
    app = FastAPI()
    install_airports(app, AIRPORTS)
    provider = DuffelProvider(TOKEN, client=httpx.Client(transport=httpx.MockTransport(duffel)),
                              base_url="https://duffel.test", timeout_s=25, clock=lambda: NOW)
    install_flights(app, FlightSearch(provider, airport_lookup=real_lookup, clock=lambda: NOW, environment="development",
                                      **kwargs))
    return app, TestClient(app)


def one_offer(origin, destination, amount="412.30"):
    return offer("off_1", amount, slices=[{"duration": "PT5H10M", "segments": [
        segment(origin, destination, f"{DEPARTURE}T08:00:00", f"{DEPARTURE}T11:10:00")]}])


# ------------------------------------------------------------------ nearby list -> flight search -> Duffel
def test_the_airport_picked_from_the_nearby_list_is_what_duffel_is_asked_about():
    duffel = Duffel(duffel_answer(one_offer("TLV", "LHR")))
    _, client = app_with(duffel)
    near = client.get("/api/airports/near", params=JERUSALEM).json()
    by = {a["iata"]: a for a in near["airports"]}
    assert by["TLV"]["in_country"] is True and by["AMM"]["in_country"] is False and near["suggested"] is None
    picked = by["TLV"]  # the traveller chooses Tel Aviv from the list
    body = client.get("/api/flights", params={"origin": picked["iata"], "destination": "LHR", "departure_date": DEPARTURE}).json()
    sent = json.loads(duffel.requests[0].content)["data"]
    assert sent["slices"] == [{"origin": "TLV", "destination": "LHR", "departure_date": DEPARTURE}]
    assert body["data_mode"] == "TEST" and body["offers"][0]["slices"][0]["origin"] == "TLV"


def test_an_airport_across_the_border_is_searched_only_if_the_traveller_picks_it():
    duffel = Duffel(duffel_answer(one_offer("AMM", "LHR")))
    _, client = app_with(duffel)
    body = client.get("/api/flights", params={"origin": "AMM", "destination": "LHR", "departure_date": DEPARTURE}).json()
    assert json.loads(duffel.requests[0].content)["data"]["slices"][0]["origin"] == "AMM"
    assert body["offers"][0]["slices"][0]["origin"] == "AMM"
    # and nothing is ever picked by the server: it only answers the searched route
    assert len(duffel.requests) == 1


def test_a_country_or_a_city_name_is_never_turned_into_an_airport_by_the_flight_search():
    duffel = Duffel(duffel_answer(one_offer("TLV", "LHR")))
    _, client = app_with(duffel)
    for origin in ("Italy", "Paris", "Jerusalem", "IT", "ITALY"):
        r = client.get("/api/flights", params={"origin": origin, "destination": "LHR", "departure_date": DEPARTURE})
        assert r.status_code == 422 and r.json()["error"]["code"] in ("invalid_airport_code", "missing_airport")
    assert duffel.requests == []  # nothing reached the provider


def test_the_duffel_test_data_is_labelled_test_and_cannot_be_read_as_a_real_fare():
    _, client = app_with(Duffel(duffel_answer(one_offer("TLV", "LHR"))))
    body = client.get("/api/flights", params={"origin": "TLV", "destination": "LHR", "departure_date": DEPARTURE}).json()
    assert body["data_mode"] == "TEST" and all(o["data_mode"] == "TEST" for o in body["offers"])
    assert body["booking_supported"] is False and "not real" in body["notices"][0]
    assert "Rihla does not book flights" in " ".join(body["notices"])


# ------------------------------------------------------------------ a failed flight search never blocks the trip
FAILURES = [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.Response(500), httpx.Response(401),
            httpx.Response(429), httpx.Response(201, text="<html>")]


@pytest.mark.parametrize("failure", FAILURES, ids=lambda f: type(f).__name__ if isinstance(f, Exception) else str(f.status_code))
def test_a_flight_failure_is_an_error_for_flights_only_and_the_trip_request_still_works(failure):
    from app.main import app as rihla
    flights_app, flights = app_with(Duffel(failure))
    r = flights.get("/api/flights", params={"origin": "TLV", "destination": "LHR", "departure_date": DEPARTURE})
    assert r.status_code in (502, 503, 504) and r.json()["error"]["code"].startswith("provider_")
    assert "offers" not in r.json()  # nothing invented in its place

    trip = {"destination": "Amman", "start_date": "2026-12-01", "end_date": "2026-12-03", "travellers": 2, "budget": 900}
    with patch("app.main.orchestrate_trip", return_value={"status": "needs_clarification", "message": "recorded"}) as run:
        chat = TestClient(rihla).post("/api/chat", json={"session_id": "flights-isolation", "message": "Plan", "trip": trip})
    assert chat.status_code == 200 and chat.json()["status"] == "needs_clarification"
    assert run.call_count == 1


def test_the_flight_routes_are_read_only_and_separate_from_the_trip_routes():
    from app.main import app as rihla
    # OpenAPI lists every route however the framework nests included routers.
    paths = {path: set(methods) for path, methods in rihla.openapi()["paths"].items()}
    assert {p for p in paths if "flight" in p} == {"/api/flights", "/api/flights/status"}
    assert paths["/api/flights"] == {"get"} and paths["/api/flights/status"] == {"get"}
    assert paths["/api/airports/near"] == {"get"}
    assert not [p for p in paths if re.search(r"book|order|pay|ticket|checkout", p)]


# ------------------------------------------------------------------ flight prices never reach the plan or the budget
BUILDERS = ["app/orchestrator.py", "app/schemas.py", "app/memory.py", "app/revision.py", "app/coverage.py",
            "planning/budget_analyst.py", "planning/itinerary_planner.py", "planning/research.py"]


@pytest.mark.parametrize("path", [p for p in BUILDERS if (ROOT / p).exists()])
def test_nothing_that_builds_the_plan_or_the_budget_uses_flight_search(path):
    source = (ROOT / path).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+app\.flights|flights\.service|DuffelProvider|DemoProvider", source, re.M), path


def test_the_budget_says_flights_are_not_in_it():
    assert "flights and intercity transport" in UNACCOUNTED_CATEGORIES


def test_the_chat_contract_has_no_flight_fields():
    from app.schemas import ChatRequest, ChatResponse, TripForm
    names = set(TripForm.model_fields) | set(ChatRequest.model_fields) | set(ChatResponse.model_fields)
    assert not [n for n in names if re.search(r"flight|airfare|airline|airport|iata", n, re.I)]


def test_demo_flights_never_carry_a_real_airline_or_a_bookable_offer():
    service = FlightSearch(DemoProvider(lookup=real_lookup), airport_lookup=real_lookup, clock=lambda: NOW,
                           environment="development")
    body = service.search(origin="AMM", destination="IST", departure_date=DEPARTURE, return_date="2026-12-08", adults="2")
    assert body["data_mode"] == "DEMO" and body["booking_supported"] is False and TODAY.year == 2026
    assert all(o["airline"]["iata_code"] is None and o["provider_offer_id"] is None for o in body["offers"])
    assert all(o["data_mode"] == "DEMO" and len(o["slices"]) == 2 for o in body["offers"])
