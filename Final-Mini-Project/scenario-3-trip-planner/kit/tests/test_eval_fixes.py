"""Fixes found by the official sample evaluation (evals/cases.sample.jsonl).

S3-07: the attractions source is down: the reply says so, nothing is planned or proposed, no sight is named.
S3-09: "restaurants near the old city" is a location, not a required place no listing could match.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.coordinator import required_sights
from app.main import app
from app.memory import sessions
from planning.research import ResearchBundle

client = TestClient(app)
FORM = {"destination": "Istanbul", "start_date": "2026-11-05", "end_date": "2026-11-06", "travellers": 1,
        "budget": 400, "currency": "USD", "interests": ["history"]}


def test_area_phrases_are_not_required_places_and_named_places_are_kept():
    assert required_sights(["old city", "the Old City", "city centre", "downtown", "historic center", "the old town"]) == []
    assert required_sights(["Topkapi Palace", "Grand Bazaar", "Sultanahmet", "Galata Tower"]) == \
        ["Topkapi Palace", "Grand Bazaar", "Sultanahmet", "Galata Tower"]
    assert required_sights(None) is None and required_sights([]) == []


def test_an_attractions_outage_is_said_and_nothing_is_planned_or_proposed():
    down = ResearchBundle.from_tool_results(
        {"destination": "Istanbul", "currency": "USD", "travellers": 1, "start_date": "2026-11-05",
         "end_date": "2026-11-06", "interests": ["history"]},
        attractions=[{"ok": False, "error": {"code": "service_unavailable", "message": "503", "status": 503}}],
        restaurants=[{"ok": True, "restaurants": [{"id": "wv-x-r", "name": "Somewhere To Eat", "kind": "eat"}]}])
    sessions.clear()
    with patch("app.orchestrator.run_research_pipeline", return_value=down), \
            patch("app.orchestrator.run_planning_pipeline") as plan:
        r = client.post("/api/chat", json={"session_id": "s07", "message": "Plan 2 days in Istanbul", "trip": FORM})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "research_unavailable"
    assert "unavailable" in body["reply"] and "could not load attractions" in body["reply"]
    assert body["pending_action"] is None and body["itinerary"] is None and body["result"] is None
    assert "Somewhere To Eat" not in body["reply"]  # no place is presented
    plan.assert_not_called()


# S3-04: "the reply says what changed (or that the plan already fitted)"
def test_a_revised_plan_says_what_changed_before_the_plan():
    itinerary = {"destination": "Istanbul", "currency": "USD", "travellers": 1, "budget_total": 560, "estimated_total": 150.63,
                 "days": [{"date": "2026-11-02", "activities": [{"name": "Basilica Cistern", "start_time": "09:00",
                                                                 "end_time": "10:30", "estimated_cost": 41}]}]}
    changes = ["Budget changed from 700.00 to 560.00 USD.",
               "The plan's known costs (150.63 USD) already fit the new budget, so no activity had to change."]
    result = {"status": "verification_required", "message": "Your itinerary has been updated.", "itinerary": itinerary,
              "revision": {"outcome": "revised", "changes": changes}}
    sessions.clear()
    with patch("app.main.orchestrate_trip", return_value=result):
        reply = client.post("/api/chat", json={"session_id": "s04", "message": "Cut the budget by 20%",
                                               "revision": True}).json()["reply"]
    assert reply.startswith("I revised your plan. What changed:\n- Budget changed from 700.00 to 560.00 USD.")
    assert "already fit the new budget" in reply and "Day 1" in reply
