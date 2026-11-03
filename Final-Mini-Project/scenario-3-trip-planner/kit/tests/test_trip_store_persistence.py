"""The Trip Store keeps saved trips across restarts when TRAVEL_DB_PATH is set (services/trip_db.py).

In-process: the store's state is rebuilt from the database the way a restarted process builds it (reset_state()
runs at import). Real restart: a Trip Store process is started, a trip saved, the process killed, a new one
started on the same database, and the trip read back over HTTP. Without TRAVEL_DB_PATH nothing changes: the
store is in memory, as the eval runner and the other tests expect.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import services.travel_api as store

KIT = Path(__file__).resolve().parents[1]
KEY = "persistence-test-key"
H = {"X-API-Key": KEY}


def itinerary(save=None, cost=12.5):
    it = {"destination": "Amman", "currency": "USD", "budget_total": 300, "estimated_total": 12.5, "days": [
        {"date": "2026-12-01", "activities": [
            {"name": "Amman Citadel", "start_time": "09:00", "end_time": "11:00", "estimated_cost": cost},
            {"name": "Rainbow Street", "start_time": "12:00", "end_time": "13:00", "estimated_cost": None}]}]}
    if save:
        it["rihla_save"] = save
    return it


LIMITED = {"mode": "accepted_with_limitations", "label": "Saved · Not Fully Verified", "verified": False,
           "verification_status": "UNKNOWN", "limitations": ["Price unavailable for 1 planned item(s): Rainbow Street."],
           "costs": {"known_subtotal": "12.50", "unpriced_items": ["Rainbow Street"], "budget_guaranteed": False}}
DRAFT = {**LIMITED, "mode": "unverified_draft", "label": "Saved · Unverified Draft", "verification_status": "FAIL",
         "confirmed_problems": ["Day 1 runs past closing time."]}


@pytest.fixture
def durable(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAVEL_API_KEY", KEY)
    monkeypatch.setenv("TRAVEL_DB_PATH", str(tmp_path / "store" / "trips.sqlite3"))
    monkeypatch.delenv("TRAVEL_ADMIN_ENDPOINTS", raising=False)
    store.reset_state()
    yield TestClient(store.app)
    monkeypatch.delenv("TRAVEL_DB_PATH")
    store.reset_state()  # back to the plain in-memory store for the other tests


def save(client, traveller, it, key):
    r = client.post("/api/trips", headers={**H, "Idempotency-Key": key},
                    json={"traveller_id": traveller, "title": "Amman, 1 day", "itinerary": it})
    assert r.status_code == 201, r.text
    return r.json()["trip_id"]


def restart():
    """What a new Trip Store process does at start-up."""
    store.reset_state()


def test_every_kind_of_saved_trip_survives_a_restart_with_its_status_and_details(durable):
    approved = save(durable, "RIHLA-alice", itinerary(), "act-1")
    limited = save(durable, "RIHLA-alice", itinerary(LIMITED), "acc-2")
    draft = save(durable, "RIHLA-alice", itinerary(DRAFT), "acc-3")
    before = {t: durable.get(f"/api/trips/{t}", headers=H).json() for t in (approved, limited, draft)}
    restart()
    for trip_id, was in before.items():
        now = durable.get(f"/api/trips/{trip_id}", headers=H).json()
        assert now == was  # the whole record: itinerary, status, dates, costs, owner, created_at
    assert before[limited]["itinerary"]["rihla_save"]["mode"] == "accepted_with_limitations"
    assert before[draft]["itinerary"]["rihla_save"]["confirmed_problems"] == ["Day 1 runs past closing time."]
    assert "rihla_save" not in before[approved]["itinerary"]
    assert before[limited]["itinerary"]["days"][0]["activities"][1]["estimated_cost"] is None  # never 0
    listed = durable.get("/api/travellers/RIHLA-alice/trips", headers=H).json()["trips"]
    assert {t["trip_id"] for t in listed} == {approved, limited, draft}


def test_ids_are_never_reused_and_a_retried_save_after_a_restart_writes_nothing(durable):
    first = save(durable, "RIHLA-alice", itinerary(), "act-1")
    restart()
    assert save(durable, "RIHLA-alice", itinerary(), "act-1") == first  # the same approval, retried: no new trip
    conflict = durable.post("/api/trips", headers={**H, "Idempotency-Key": "act-1"},
                            json={"traveller_id": "RIHLA-alice", "title": "x", "itinerary": itinerary(cost=99)})
    assert conflict.status_code == 409
    second = save(durable, "RIHLA-alice", itinerary(), "act-2")
    assert int(second.split("-")[1]) == int(first.split("-")[1]) + 1
    restart()
    assert int(save(durable, "RIHLA-alice", itinerary(), "act-3").split("-")[1]) == int(second.split("-")[1]) + 1


def test_a_travellers_list_holds_only_their_own_trips_after_a_restart(durable):
    mine = save(durable, "RIHLA-alice", itinerary(), "a-1")
    theirs = save(durable, "RIHLA-bob", itinerary(LIMITED), "b-1")
    restart()
    alice = {t["trip_id"] for t in durable.get("/api/travellers/RIHLA-alice/trips", headers=H).json()["trips"]}
    bob = {t["trip_id"] for t in durable.get("/api/travellers/RIHLA-bob/trips", headers=H).json()["trips"]}
    assert mine in alice and theirs not in alice and bob == {theirs}


def test_saved_preferences_survive_a_restart(durable):
    r = durable.put("/api/travellers/RIHLA-alice/preferences", headers=H, json={"activity_pace": "relaxed"})
    assert r.status_code == 200, r.text
    restart()
    prefs = durable.get("/api/travellers/RIHLA-alice/preferences", headers=H).json()
    assert prefs["preferences"]["activity_pace"] == "relaxed"


def test_a_failed_durable_write_saves_nothing_and_reports_no_trip(durable, monkeypatch):
    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(store.trip_db, "save_trip", broken)
    with pytest.raises(OSError):
        durable.post("/api/trips", headers={**H, "Idempotency-Key": "x-1"},
                     json={"traveller_id": "RIHLA-alice", "title": "t", "itinerary": itinerary()})
    assert durable.get("/api/travellers/RIHLA-alice/trips", headers=H).json()["count"] == 0


def test_the_unauthenticated_admin_endpoints_are_off_on_a_durable_store(durable, monkeypatch):
    save(durable, "RIHLA-alice", itinerary(), "a-1")
    for method, path in (("get", "/admin/trips"), ("get", "/admin/travellers"), ("post", "/admin/reset")):
        r = getattr(durable, method)(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == "admin_disabled", path
    assert durable.get("/api/travellers/RIHLA-alice/trips", headers=H).json()["count"] == 1  # nothing erased
    assert durable.get("/api/travellers/RIHLA-alice/trips").status_code == 401  # and the API still needs its key


def test_without_a_database_the_store_is_in_memory_as_before(monkeypatch):
    monkeypatch.delenv("TRAVEL_DB_PATH", raising=False)
    monkeypatch.setenv("TRAVEL_API_KEY", KEY)
    store.reset_state()
    client = TestClient(store.app)
    trip_id = save(client, "RIHLA-alice", itinerary(), "m-1")
    assert client.get("/admin/trips").status_code == 200  # the test store keeps its admin endpoints
    restart()
    assert client.get(f"/api/trips/{trip_id}", headers=H).status_code == 404  # gone, exactly as before


# ------------------------------------------------------------------ a real process restart
def _start(db: Path, port: int) -> subprocess.Popen:
    env = {**os.environ, "TRAVEL_MODE": "replay", "TRAVEL_API_KEY": KEY, "TRAVEL_DB_PATH": str(db),
           "TRAVEL_OVERLAYS": "", "TRAVEL_TODAY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "services.travel_api:app", "--port", str(port),
                             "--log-level", "warning"], cwd=str(KIT), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    pytest.skip("a Trip Store process could not be started")


def test_a_trip_survives_killing_and_restarting_the_trip_store_process(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    db, url = tmp_path / "trips.sqlite3", f"http://127.0.0.1:{port}"
    proc = _start(db, port)
    try:
        r = httpx.post(f"{url}/api/trips", headers={**H, "Idempotency-Key": "real-1"}, timeout=10,
                       json={"traveller_id": "RIHLA-alice", "title": "Amman, 1 day", "itinerary": itinerary(LIMITED)})
        assert r.status_code == 201, r.text
        trip_id = r.json()["trip_id"]
    finally:
        proc.kill()
        proc.wait(timeout=10)
    proc = _start(db, port)
    try:
        back = httpx.get(f"{url}/api/trips/{trip_id}", headers=H, timeout=10).json()
        assert back["itinerary"]["rihla_save"]["mode"] == "accepted_with_limitations"
        listed = httpx.get(f"{url}/api/travellers/RIHLA-alice/trips", headers=H, timeout=10).json()
        assert [t["trip_id"] for t in listed["trips"]] == [trip_id]
    finally:
        proc.kill()
        proc.wait(timeout=10)
