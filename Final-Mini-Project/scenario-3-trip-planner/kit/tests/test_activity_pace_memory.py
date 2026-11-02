"""The saved activity pace reaches the planner: /api/chat loads the signed-in user's own preferences through MCP
get_preferences (app/traveller_memory.py), the orchestrator fills the trip's pace from them, and the research step
receives it. Never another user's preferences, never a pace the trip itself set, never an unknown value."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth import sessions
from app.memory import sessions as memory_sessions
from app.orchestrator import orchestrate_trip
from app.research_adapter import ResearchInputError
from app.traveller_memory import apply_preferences, describe_preferences
from test_auth import ORIGIN, PROJECT, auth_env, real_app, sign_in  # noqa: F401  (auth_env: autouse env)

FORM = {"destination": "Rome", "start_date": "2027-03-01", "end_date": "2027-03-04", "travellers": 1,
        "budget": 900, "currency": "EUR", "interests": ["history"]}


# --- apply_preferences -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("pace", ["relaxed", "balanced", "packed"])
def test_a_saved_pace_fills_the_trip(pace):
    trip = {}
    used = apply_preferences(trip, {"activity_pace": pace})
    assert trip["activity_pace"] == pace
    assert used == [f"activity pace: {pace}"]


def test_a_pace_given_for_this_trip_wins_and_unknown_values_are_ignored():
    trip = {"activity_pace": "packed"}
    assert apply_preferences(trip, {"activity_pace": "relaxed"}) == []
    assert trip["activity_pace"] == "packed"
    for bad in ("turbo", "", None, 3, ["relaxed"]):
        trip = {}
        apply_preferences(trip, {"activity_pace": bad})
        assert "activity_pace" not in trip, bad


def test_the_pace_is_described_with_the_other_saved_preferences():
    assert describe_preferences({"activity_pace": "relaxed", "home_currency": "EUR"}) == "pace: relaxed; currency: EUR"


# --- The orchestrator hands the pace to research -----------------------------------------------------------------

def test_the_saved_pace_reaches_the_research_step_and_is_reported():
    seen = {}

    def research(trip_info):
        seen.update(trip_info)
        raise ResearchInputError("stop here")  # the pipeline after research is tested elsewhere

    memory_sessions.clear()
    with patch("app.orchestrator.run_research_pipeline", side_effect=research):
        result = orchestrate_trip("Plan my trip", session_id="pace-1", trip_form=FORM,
                                  preferences={"activity_pace": "relaxed", "max_walk_minutes": 15})
    assert seen["activity_pace"] == "relaxed"
    assert seen["max_walk_minutes"] == 15  # the walking limit still comes along (a hard limit, unlike pace)
    assert seen["currency"] == "EUR"  # what the form said is kept
    assert "activity pace: relaxed" in result["preferences_used"]


def test_without_saved_preferences_the_trip_has_no_pace_and_nothing_is_reported():
    seen = {}

    def research(trip_info):
        seen.update(trip_info)
        raise ResearchInputError("stop here")

    memory_sessions.clear()
    with patch("app.orchestrator.run_research_pipeline", side_effect=research):
        result = orchestrate_trip("Plan my trip", session_id="pace-2", trip_form=FORM, preferences=None)
    assert "activity_pace" not in seen
    assert "preferences_used" not in result


# --- /api/chat loads only the caller's own preferences -----------------------------------------------------------

class FakeMemory:
    """MCP get_preferences against a per-traveller store, as services/travel_mcp.py answers it."""

    def __init__(self, stored, available=True):
        self.stored, self.available, self.asked = stored, available, []

    def __call__(self, name, args):
        assert name == "get_preferences"
        self.asked.append(args["traveller_id"])
        if not self.available:
            raise ConnectionError("MCP server down")
        prefs = self.stored.get(args["traveller_id"])
        if prefs is None:
            return {"ok": False, "error": {"code": "traveller_not_found"}}
        return {"ok": True, "traveller_id": args["traveller_id"], "preferences": prefs}


def chat(client, session_id, **extra):
    return client.post("/api/chat", headers=ORIGIN, json={"session_id": session_id, "message": "Plan my trip",
                                                          "trip": FORM, **extra})


def planned_with(orchestrate):
    return orchestrate.call_args.kwargs["preferences"]


@pytest.fixture
def two_users():
    memory_sessions.clear()
    alice_tid = sessions.traveller_id_for("alice", PROJECT)
    bob_tid = sessions.traveller_id_for("bob", PROJECT)
    memory = FakeMemory({alice_tid: {"activity_pace": "relaxed"}, bob_tid: {"activity_pace": "packed"},
                         "TRV-101": {"activity_pace": "balanced"}})
    alice, bob = TestClient(real_app()), TestClient(real_app())
    sign_in(alice, "alice")
    sign_in(bob, "bob")
    return alice, bob, alice_tid, bob_tid, memory


def stopped(*_args, **_kwargs):
    return {"status": "needs_clarification", "message": "stop", "preferences_used": ["activity pace: x"]}


def test_each_signed_in_user_plans_with_their_own_saved_pace(two_users):
    alice, bob, alice_tid, bob_tid, memory = two_users
    with patch("app.traveller_memory.call_app_tool", side_effect=memory), \
            patch("app.main.orchestrate_trip", side_effect=stopped) as orchestrate:
        assert chat(alice, "s-alice").status_code == 200
        assert planned_with(orchestrate) == {"activity_pace": "relaxed"}
        r = chat(bob, "s-bob")
        assert planned_with(orchestrate) == {"activity_pace": "packed"}
    assert memory.asked == [alice_tid, bob_tid]
    assert r.json()["memory_notes"] == ["Used for this plan: activity pace: x."]


def test_a_signed_in_user_cannot_plan_with_someone_elses_preferences(two_users):
    alice, _bob, alice_tid, bob_tid, memory = two_users
    with patch("app.traveller_memory.call_app_tool", side_effect=memory), \
            patch("app.main.orchestrate_trip", side_effect=stopped) as orchestrate:
        chat(alice, "s-alice-2", user={"traveller_id": bob_tid, "name": "Bob"})  # the body is never trusted
        assert planned_with(orchestrate) == {"activity_pace": "relaxed"}
    assert memory.asked == [alice_tid]


def test_a_changed_pace_is_used_by_the_next_trip(two_users):
    alice, _bob, alice_tid, _bob_tid, memory = two_users
    with patch("app.traveller_memory.call_app_tool", side_effect=memory), \
            patch("app.main.orchestrate_trip", side_effect=stopped) as orchestrate:
        chat(alice, "s-trip-1")
        memory.stored[alice_tid] = {"activity_pace": "packed"}  # saved on My Profile in between
        chat(alice, "s-trip-2")  # the website starts a new session for each new trip
        assert planned_with(orchestrate) == {"activity_pace": "packed"}


def test_the_open_contract_without_a_user_loads_no_preferences(two_users, monkeypatch):
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", "false")
    _alice, _bob, _a, _b, memory = two_users
    guest = TestClient(real_app())
    with patch("app.traveller_memory.call_app_tool", side_effect=memory), \
            patch("app.main.orchestrate_trip", side_effect=stopped) as orchestrate:
        chat(guest, "s-guest")
        assert planned_with(orchestrate) is None  # not even the demo traveller's: evaluations are unchanged
        chat(guest, "s-contract", user={"traveller_id": "TRV-101", "name": "Test"})  # CONTRACT §5
        assert planned_with(orchestrate) == {"activity_pace": "balanced"}
    assert memory.asked == ["TRV-101"]


def test_planning_continues_and_says_so_when_preferences_cannot_be_loaded(two_users):
    alice, _bob, _a, _b, _memory = two_users
    with patch("app.traveller_memory.call_app_tool", side_effect=FakeMemory({}, available=False)), \
            patch("app.main.orchestrate_trip", side_effect=lambda *a, **k: {"status": "needs_clarification",
                                                                            "message": "stop"}) as orchestrate:
        r = chat(alice, "s-down")
    assert r.status_code == 200
    assert planned_with(orchestrate) is None
    assert r.json()["memory_notes"] == [
        "I could not load your saved preferences right now, so this plan does not use them."]
