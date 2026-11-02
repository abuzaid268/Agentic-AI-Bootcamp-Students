"""Approval and the saved-trips endpoints: the Rihla Trip Store is the record of approved trips. No network."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.memory import sessions
from app.trip_store import TripStoreError
from test_api import make_pending_trip

client = TestClient(app)
ENV = {"TRAVEL_TRAVELLER_ID": "TRV-101"}


def setup_function():
    sessions.clear()


def approve(action_id="correct-id", approved=True):
    return client.post("/api/approve", json={"session_id": "test-session", "action_id": action_id,
                                             "approved": approved})


def test_without_a_configured_traveller_nothing_is_saved_and_the_reason_is_actionable():
    make_pending_trip()
    with patch.dict("os.environ", {"TRAVEL_TRAVELLER_ID": ""}), patch("app.main.save_trip_to_store") as save:
        r = approve()
    assert r.status_code == 503 and "TRAVEL_TRAVELLER_ID" in r.json()["detail"]
    save.assert_not_called()
    assert sessions["test-session"]["pending_action"] is not None  # retry possible once configured


def test_a_failed_save_is_never_reported_as_approved_and_can_be_retried():
    make_pending_trip()
    with patch.dict("os.environ", ENV), patch("app.main.save_trip_to_store",
                                               side_effect=[TripStoreError("down"), {"trip_id": "TRIP-7"}]):
        first = approve()
        second = approve()
    assert first.status_code == 503 and first.json()["detail"] == "Trip could not be saved. Please try again."
    assert second.status_code == 200 and second.json()["trip"]["trip_id"] == "TRIP-7"


def test_an_unverified_result_has_no_action_to_approve():
    sessions["test-session"] = {"pending_action": None}
    with patch.dict("os.environ", ENV), patch("app.main.save_trip_to_store") as save:
        r = approve()
    assert r.status_code == 404
    save.assert_not_called()


def test_saved_trips_are_listed_from_the_trip_store_for_this_traveller():
    trips = [{"trip_id": "TRIP-3001", "destination": "Tokyo", "created_at": "2026-10-30T10:00:00Z"}]
    detail = {"trip_id": "TRIP-3001", "itinerary": {"travellers": 3}}
    with patch.dict("os.environ", ENV), patch("app.main.list_trips_from_store", return_value=trips) as lst,             patch("app.main.get_trip_from_store", return_value=detail):
        r = client.get("/api/trips")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert r.json()["trips"][0] == {**trips[0], "travellers": 3}  # from the trip's own itinerary
    lst.assert_called_once_with("TRV-101")


def test_a_saved_trip_is_returned_only_to_its_own_traveller():
    trip = {"trip_id": "TRIP-3001", "traveller_id": "TRV-101", "itinerary": {"destination": "Tokyo", "days": []}}
    with patch.dict("os.environ", ENV), patch("app.main.get_trip_from_store", return_value=trip):
        assert client.get("/api/trips/TRIP-3001").json()["itinerary"]["destination"] == "Tokyo"
    other = {**trip, "traveller_id": "TRV-999"}
    with patch.dict("os.environ", ENV), patch("app.main.get_trip_from_store", return_value=other):
        assert client.get("/api/trips/TRIP-3001").status_code == 404
    with patch.dict("os.environ", ENV), patch("app.main.get_trip_from_store", return_value=None):
        assert client.get("/api/trips/TRIP-404").status_code == 404


@pytest.mark.parametrize("path", ["/api/trips", "/api/trips/TRIP-1"])
def test_store_failures_are_understandable(path):
    with patch.dict("os.environ", ENV), patch("app.main.list_trips_from_store", side_effect=TripStoreError("x")), \
            patch("app.main.get_trip_from_store", side_effect=TripStoreError("x")):
        r = client.get(path)
    assert r.status_code == 503 and "Trip Store could not be reached" in r.json()["detail"]
    with patch.dict("os.environ", {"TRAVEL_TRAVELLER_ID": ""}):
        assert "TRAVEL_TRAVELLER_ID" in client.get(path).json()["detail"]


def test_the_trip_store_client_reads_the_real_endpoints():
    """list/get go to the Travel API's own Trip Store routes, with the API key."""
    import httpx
    import app.trip_store as store
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("X-API-Key")))
        if request.url.path.endswith("/trips") and "travellers" in request.url.path:
            return httpx.Response(200, json={"trips": [{"trip_id": "A", "created_at": "1"},
                                                       {"trip_id": "B", "created_at": "2"}]})
        if request.url.path.endswith("/TRIP-404"):
            return httpx.Response(404, json={"error": {"code": "trip_not_found"}})
        return httpx.Response(200, json={"trip_id": "TRIP-1", "itinerary": {"days": []}})

    real = httpx.Client
    with patch.dict("os.environ", {"TRAVEL_API_URL": "http://store.invalid", "TRAVEL_API_KEY": "k"}), \
            patch("app.trip_store.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
        assert [t["trip_id"] for t in store.list_trips_from_store("TRV-101")] == ["B", "A"]  # newest first
        assert store.get_trip_from_store("TRIP-1")["trip_id"] == "TRIP-1"
        assert store.get_trip_from_store("TRIP-404") is None
    assert seen[0] == ("GET", "/api/travellers/TRV-101/trips", "k")
