"""The destination's geographic identity in POST /api/chat (app/destinations/identity.py, TripForm.place).

A trip is planned for the city the traveller chose, never a namesake: the server checks the optional place against
the text, refuses a country where a city is needed, and passes the fully qualified name to the research. Older
clients that send only the text keep working. The orchestrator is replaced by a recorder: no LLM, no network.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.destinations.identity import DestinationPlace, check_destination, research_destination
from app.main import app
from app.schemas import TripForm

client = TestClient(app)

PARIS_TX = {"id": "geonames:4717560", "name": "Paris", "region": "Texas", "country": "United States",
            "country_code": "US", "latitude": 33.66094, "longitude": -95.55551, "label": "Paris, Texas, United States"}
PARIS_FR = {"id": "geonames:2988507", "name": "Paris", "region": "Île-de-France Region", "country": "France",
            "country_code": "FR", "latitude": 48.85341, "longitude": 2.3488,
            "label": "Paris, Île-de-France Region, France"}
AMMAN = {"id": "geonames:250441", "kind": "city", "name": "Amman", "region": "Amman Governorate", "country": "Jordan",
         "country_code": "JO", "latitude": 31.95522, "longitude": 35.94503, "label": "Amman, Amman Governorate, Jordan"}
DATES = {"start_date": "2026-12-01", "end_date": "2026-12-03", "travellers": 2, "budget": 900}


def form(destination, place=None, **extra):
    return TripForm(destination=destination, place=place, **DATES, **extra)


def chat(trip):
    """POST /api/chat with a recorded orchestrator; returns (status code, body, the form the orchestrator got)."""
    seen = {}

    def orchestrate(*args, **kwargs):
        seen["trip_form"] = kwargs.get("trip_form")
        return {"status": "needs_clarification", "message": "recorded"}
    with patch("app.main.orchestrate_trip", side_effect=orchestrate):
        r = client.post("/api/chat", json={"session_id": f"identity-{id(trip)}", "message": "Plan my trip", "trip": trip})
    return r.status_code, r.json(), seen.get("trip_form")


# ------------------------------------------------------------------ countries are not cities
@pytest.mark.parametrize("text, country", [("Italy", "Italy"), ("italy", "Italy"), ("Japan", "Japan"),
                                           ("Georgia", "Georgia"), ("France", "France")])
def test_a_country_alone_is_refused_with_a_request_for_a_city(text, country):
    with pytest.raises(ValidationError) as raised:
        form(text)
    message = str(raised.value)
    assert f"{country} is a country" in message and "Choose a city" in message


def test_georgia_says_it_is_also_a_region_and_suggests_a_real_city():
    with pytest.raises(ValidationError) as raised:
        form("Georgia")
    assert "a region in United States" in str(raised.value) and "Tbilisi" in str(raised.value)


@pytest.mark.parametrize("text", ["Singapore", "Monaco", "Luxembourg"])
def test_a_city_state_is_a_city(text):
    assert form(text).destination == text


@pytest.mark.parametrize("text", ["Amman", "Paris", "London", "Tokyo", "Italy, Texas, United States", "Paris, Texas",
                                  "New York", "Washington"])
def test_cities_and_qualified_names_are_accepted_as_before(text):
    assert form(text).destination == text


def test_over_http_a_country_is_a_422_that_names_the_problem():
    status, body, seen = chat({"destination": "Italy", **DATES})
    assert status == 422 and seen is None  # refused before any planning
    assert "Italy is a country" in str(body["detail"])


# ------------------------------------------------------------------ a structured place
def test_the_chosen_place_is_validated_and_kept():
    trip = form("Paris, Texas, United States", PARIS_TX)
    assert trip.place.country_code == "US" and trip.place.id == "geonames:4717560" and trip.place.kind == "city"
    assert trip.destination == "Paris, Texas, United States"


def test_the_text_and_the_place_must_name_the_same_city():
    with pytest.raises(ValidationError) as raised:
        form("Paris, Île-de-France Region, France", PARIS_TX)
    assert "does not match the chosen place" in str(raised.value)


@pytest.mark.parametrize("text", ["Paris", "Paris, United States"])
def test_shorter_names_of_the_place_are_researched_by_its_full_label(text):
    assert form(text, PARIS_TX).destination == "Paris, Texas, United States"  # never just "Paris"


def test_the_full_label_is_kept_as_written():
    assert form("paris, texas, united states", PARIS_TX).destination == "paris, texas, united states"


def test_same_name_cities_in_different_countries_keep_their_identity():
    assert form("Paris", PARIS_FR).destination == "Paris, Île-de-France Region, France"
    assert form("Paris", PARIS_TX).destination == "Paris, Texas, United States"


@pytest.mark.parametrize("change, problem", [
    ({"id": "osm:12"}, "id"), ({"id": "geonames:0"}, "id"), ({"country_code": "XX"}, "not a known ISO country code"),
    ({"country_code": "USA"}, "country_code"), ({"latitude": 91}, "latitude"), ({"longitude": float("nan")}, "longitude"),
    ({"kind": "country"}, "kind"), ({"population": 3}, "population"),
])
def test_an_invalid_place_is_refused(change, problem):
    with pytest.raises(ValidationError) as raised:
        form("Paris, Texas, United States", {**PARIS_TX, **change})
    assert problem in str(raised.value)


def test_a_country_sent_as_a_city_is_refused():
    italy = {"id": "geonames:3175395", "name": "Italy", "country": "Italy", "country_code": "IT", "latitude": 42.8,
             "longitude": 12.8, "label": "Italy"}
    with pytest.raises(ValidationError) as raised:
        form("Italy", italy)
    assert "Italy is a country" in str(raised.value)


def test_over_http_the_orchestrator_gets_the_qualified_name_and_the_old_fields():
    status, _, seen = chat({"destination": "Amman", **DATES, "place": AMMAN})
    assert status == 200 and seen["destination"] == "Amman, Amman Governorate, Jordan"
    assert seen["place"]["country_code"] == "JO" and seen["start_date"] == "2026-12-01"


def test_over_http_an_older_client_without_a_place_works_as_before():
    status, _, seen = chat({"destination": "Amman", **DATES})
    assert status == 200 and seen["destination"] == "Amman" and seen["place"] is None


def test_an_unknown_field_in_the_place_is_refused_over_http():
    status, _, seen = chat({"destination": "Amman, Amman Governorate, Jordan", **DATES, "place": {**AMMAN, "x": 1}})
    assert status == 422 and seen is None


def test_helpers_directly():
    place = DestinationPlace(**PARIS_TX)
    check_destination("Paris, Texas", None)  # qualified text: accepted
    assert research_destination("Paris", place) == "Paris, Texas, United States"
    assert research_destination("Amman", None) == "Amman"


# ------------------------------------------------------------------ what the traveller is told when attractions fail
from app.research_errors import attraction_failure_message  # noqa: E402
from planning.research import ToolFailure  # noqa: E402


@pytest.mark.parametrize("code, says, retry", [
    ("not_cached", "recorded travel data (replay mode)", False),
    ("no_guide", "a different place of the same name is never used instead", False),
    ("place_not_found", "could not be located", False),
    ("timeout", "unavailable right now (timeout)", True),
    ("upstream_unavailable", "unavailable right now (upstream_unavailable)", True),
])
def test_the_failure_message_gives_the_real_reason_and_the_right_advice(code, says, retry):
    message = attraction_failure_message("Italy, Texas, United States",
                                         ToolFailure(tool="find_attractions", code=code, message="x"))
    assert says in message and "I did not make a plan, so nothing was proposed or saved." in message
    assert ("try again in a few minutes" in message) is retry
