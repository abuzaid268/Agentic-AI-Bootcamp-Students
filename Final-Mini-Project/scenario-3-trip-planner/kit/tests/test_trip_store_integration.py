"""Approval through the REAL Rihla Trip Store (services.travel_api, in-process): no LLM, no network.

The backend's store calls (app/trip_store.py, httpx) are routed into the Travel API app itself, so this runs the
real save, Idempotency-Key handling, listing and retrieval: a verified trip is approved once, appears in the
saved trips, opens with the same itinerary, and a repeated approval creates no second trip.
"""
from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import services.travel_api as travel_api
from app.main import app
from app.memory import sessions
from test_api import make_pending_trip

client = TestClient(app)
STORE_ENV = {"TRAVEL_API_URL": "http://trip-store.test", "TRAVEL_API_KEY": "integration-key",
             "TRAVEL_TRAVELLER_ID": "TRV-INTEGRATION"}


@pytest.fixture()
def store():
    travel_api.reset_state()
    sessions.clear()
    with patch.dict("os.environ", STORE_ENV):
        store_client = TestClient(travel_api.app)
        with patch("app.trip_store.httpx.Client", lambda **kw: store_client):
            yield store_client
    travel_api.reset_state()


def stored_trips():
    return [t for t in travel_api.STATE["trips"] if t["traveller_id"] == "TRV-INTEGRATION"]


def approve(session="test-session", action="correct-id"):
    return client.post("/api/approve", json={"session_id": session, "action_id": action, "approved": True})


def test_a_verified_trip_is_approved_saved_listed_and_opened(store):
    itinerary = make_pending_trip()
    r = approve()
    assert r.status_code == 200 and r.json()["status"] == "approved"
    trip_id = r.json()["trip"]["trip_id"]
    assert trip_id.startswith("TRIP-") and len(stored_trips()) == 1

    listed = client.get("/api/trips").json()
    assert [t["trip_id"] for t in listed["trips"]] == [trip_id]
    assert listed["trips"][0]["destination"] == itinerary["destination"]

    opened = client.get(f"/api/trips/{trip_id}").json()
    assert opened["itinerary"] == itinerary  # exactly what was verified and approved


def test_repeated_approval_creates_no_second_trip(store):
    make_pending_trip()
    first, second = approve(), approve()
    assert second.json()["already_approved"] is True
    assert second.json()["trip"]["trip_id"] == first.json()["trip"]["trip_id"]
    assert len(stored_trips()) == 1


def test_a_lost_response_retry_is_absorbed_by_the_stores_idempotency_key(store):
    """Even if the backend forgot the approval (a retry before it recorded it), the store's Idempotency-Key
    replays the first save: still one trip."""
    make_pending_trip()
    pending = deepcopy(sessions["test-session"]["pending_action"])
    first = approve()
    sessions["test-session"]["pending_action"] = pending  # as if the first response was lost
    sessions["test-session"].pop("approved_actions")
    again = approve()
    assert again.json()["trip"]["trip_id"] == first.json()["trip"]["trip_id"]
    assert len(stored_trips()) == 1


def test_an_unverified_or_tampered_trip_never_reaches_the_store(store):
    make_pending_trip()
    sessions["test-session"]["pending_action"]["verification_status"] = "not_verified"
    assert approve().status_code == 403
    make_pending_trip()
    sessions["test-session"]["pending_action"]["payload"]["itinerary"]["budget_total"] = 1  # changed after checks
    assert approve().status_code == 403
    assert stored_trips() == []


def test_another_travellers_trip_is_not_shown(store):
    make_pending_trip()
    trip_id = approve().json()["trip"]["trip_id"]
    with patch.dict("os.environ", {"TRAVEL_TRAVELLER_ID": "TRV-SOMEONE-ELSE"}):
        assert client.get("/api/trips").json()["trips"] == []
        assert client.get(f"/api/trips/{trip_id}").status_code == 404


def test_a_store_that_rejects_the_trip_leaves_it_unapproved_and_retryable(store):
    make_pending_trip()
    with patch.object(travel_api, "check_itinerary", return_value=["itinerary.days must be a non-empty list"]):
        r = approve()
    assert r.status_code == 503 and stored_trips() == []
    assert sessions["test-session"]["pending_action"] is not None
    assert approve().status_code == 200 and len(stored_trips()) == 1
