"""The signed-in approval journey through the REAL backend, the REAL MCP server and the REAL Trip Store process.

Real here: app.main's endpoints behind install_auth (sessions, CSRF origin check, session ownership), the approval
policy, POST /api/approve -> MCP save_trip over stdio -> the Travel API's Trip Store (a uvicorn subprocess, replay
mode, with its Idempotency-Key handling), GET /api/trips and /api/trips/{id}.

TEST FIXTURE (labelled): the AI planning pipeline's result. Real replay and live plans for these cities are UNKNOWN
today (a restaurant without a price, a place without listed hours, an uncached walking leg), so no real plan is
approvable yet and the policy rightly refuses them. `planned()` returns a pipeline result whose Python verdict is
PASS on recorded evidence: the case the policy approves with a disclosure. Nothing else is faked.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import sessions as auth_sessions
from app.memory import sessions
from test_auth import ORIGIN, PROJECT, auth_env, real_app, sign_in  # noqa: F401  (auth_env: autouse env)
from test_mcp_integration import api, travel_api  # noqa: F401  (the real Trip Store process and its reset)

ISTANBUL = {"destination": "Istanbul", "currency": "USD", "travellers": 1, "budget_total": 300, "estimated_total": 66,
            "days": [
                {"date": "2026-11-05", "activities": [
                    {"name": "Hagia Sophia", "start_time": "09:00", "end_time": "11:00", "estimated_cost": 25,
                     "source_url": "https://en.wikivoyage.org/wiki/Istanbul/Sultanahmet-Old_City#See"},
                    {"name": "Basilica Cistern", "start_time": "11:30", "end_time": "12:30", "estimated_cost": 41,
                     "source_url": "https://en.wikivoyage.org/wiki/Istanbul/Sultanahmet-Old_City#See"}]},
                {"date": "2026-11-06", "activities": [
                    {"name": "Galata Tower", "start_time": "10:00", "end_time": "11:00", "estimated_cost": 0,
                     "source_url": "https://en.wikivoyage.org/wiki/Istanbul/Beyoglu#See"}]}]}
COVERED = {"trip_days": 2, "sufficient": True, "covered_dates": ["2026-11-05", "2026-11-06"], "meal_only_dates": [],
           "empty_dates": []}


def planned(itinerary=ISTANBUL):
    """TEST FIXTURE: a pipeline result whose final Python verdict is PASS on recorded evidence."""
    final = SimpleNamespace(status="PASS", evidence_basis="recorded", verified=False)
    return {"status": "verification_required", "message": "Every check passed on recorded data.",
            "itinerary": deepcopy(itinerary), "coverage": COVERED,
            "verification_result": {"verified": False, "verifier_report": SimpleNamespace(verification=final)},
            "verification": {"status": "PASS", "verified": False, "evidence_basis": "recorded",
                             "state": "supported_by_records", "findings": []}}


def store_trips(api):
    return httpx.get(f"{api}/admin/trips", timeout=10).json()["trips"]


def traveller(uid):
    return auth_sessions.traveller_id_for(uid, PROJECT)


def user(uid):
    client = TestClient(real_app())
    sign_in(client, uid)
    return client


def plan(client, session_id, result=None, message="Plan 2 days in Istanbul"):
    with patch("app.main.orchestrate_trip", return_value=result or planned()):
        r = client.post("/api/chat", headers=ORIGIN, json={"session_id": session_id, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


def decide(client, session_id, action_id, approved=True):
    r = client.post("/api/approve", headers=ORIGIN,
                    json={"session_id": session_id, "action_id": action_id, "approved": approved})
    return r


def test_approve_save_list_open_logout_login_and_isolation(api):
    alice = user("alice")
    data = plan(alice, "s-alice")
    action = data["pending_action"]
    # 3. an eligible pending action, saying what the approval relies on
    assert data["status"] == "pending_approval" and action["verification_status"] == "verified_on_records"
    assert "recorded data" in action["summary"] and data["approval_eligibility"]["eligible"] is True
    assert store_trips(api) == []  # nothing is written before the approval

    # 4-5. approve: saved through MCP save_trip in the real Trip Store, for Alice's own traveller
    saved = decide(alice, "s-alice", action["action_id"]).json()
    trip_id = saved["result"]["trip_id"]
    assert saved["status"] == "approved" and trip_id.startswith("TRIP-")
    assert [(c["tool"], c["ok"], c["via"]) for c in saved["tool_calls"]] == [("save_trip", True, "mcp")]
    assert [(t["trip_id"], t["traveller_id"]) for t in store_trips(api)] == [(trip_id, traveller("alice"))]

    # duplicate approval (a double click): the same trip, no second write
    again = decide(alice, "s-alice", action["action_id"]).json()
    assert again["result"] == {"trip_id": trip_id} and again["tool_calls"] == [] and len(store_trips(api)) == 1

    # 6. My Trips lists it, and it opens with exactly the approved itinerary
    listed = alice.get("/api/trips").json()
    assert [t["trip_id"] for t in listed["trips"]] == [trip_id]
    assert alice.get(f"/api/trips/{trip_id}").json()["itinerary"] == ISTANBUL

    # 7-8. logout ends the session; a new sign-in (same Google account) finds the trip again
    alice.post("/api/auth/logout", headers=ORIGIN)
    assert alice.get("/api/trips").status_code == 401
    later = user("alice")
    assert [t["trip_id"] for t in later.get("/api/trips").json()["trips"]] == [trip_id]

    # 9. another user sees none of it and cannot act on Alice's session
    bob = user("bob")
    assert bob.get("/api/trips").json()["trips"] == []
    assert bob.get(f"/api/trips/{trip_id}").status_code == 404
    assert decide(bob, "s-alice", action["action_id"]).status_code == 403
    assert len(store_trips(api)) == 1


def test_reject_writes_nothing(api):
    bob = user("bob")
    action = plan(bob, "s-bob")["pending_action"]
    r = decide(bob, "s-bob", action["action_id"], approved=False).json()
    assert r["status"] == "rejected" and r["result"] is None and "TRIP-" not in r["reply"]
    assert decide(bob, "s-bob", action["action_id"]).json()["result"] is None  # approving it later: still nothing
    assert store_trips(api) == [] and bob.get("/api/trips").json()["trips"] == []


def test_the_open_approval_survives_an_unrelated_message(api):
    alice = user("alice")
    action = plan(alice, "s-keep")["pending_action"]
    question = plan(alice, "s-keep", {"status": "unsupported_request", "message": "Please send a trip request."},
                    message="what's the weather like?")
    assert question["pending_action"]["action_id"] == action["action_id"]
    saved = decide(alice, "s-keep", action["action_id"]).json()
    assert saved["status"] == "approved" and len(store_trips(api)) == 1


def test_unknown_plans_are_never_offered_or_saved(api):
    alice = user("alice")
    unknown = planned()
    unknown["verification_result"]["verifier_report"].verification = SimpleNamespace(
        status="UNKNOWN", evidence_basis="mixed", verified=False, checks=[SimpleNamespace(check="costs", status="UNKNOWN")])
    data = plan(alice, "s-unknown", unknown)
    assert data["pending_action"] is None and data["approval_eligibility"]["eligible"] is False
    assert "costs" in data["approval_eligibility"]["reason"]
    assert store_trips(api) == []


def test_a_store_restart_loses_the_trips_and_my_trips_shows_none(api):
    """The simulated Trip Store keeps trips in memory: after a restart (here /admin/reset) they are gone. The
    backend says so honestly (an empty list); the frontend warns with the copy it kept (myTrips.lostApprovals)."""
    alice = user("alice")
    action = plan(alice, "s-restart")["pending_action"]
    trip_id = decide(alice, "s-restart", action["action_id"]).json()["result"]["trip_id"]
    httpx.post(f"{api}/admin/reset", headers={"Content-Type": "application/json"}, timeout=10).raise_for_status()
    assert alice.get("/api/trips").json()["trips"] == []
    assert alice.get(f"/api/trips/{trip_id}").status_code == 404
    sessions.clear()
