"""The approval policy (app/approval_policy.py) through /api/chat and /api/approve.

PASS + fresh evidence -> approvable as "verified"; PASS + recorded evidence -> approvable as "verified_on_records",
said in the summary, the reply and the response; UNKNOWN or FAIL -> never approvable. The verifier's own verdict
(`verified`) is never changed. The open approval survives messages that bring no new plan.
Pipeline results are test fixtures (SimpleNamespace reports); the save is mocked (no store here).
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.approval_policy import APPROVABLE_STATUSES, RECORDED_DISCLOSURE, approval_eligibility
from app.main import app
from app.memory import sessions

client = TestClient(app)

AMMAN = {"destination": "Amman", "currency": "USD", "travellers": 1, "budget_total": 600, "estimated_total": 8.46,
         "days": [{"date": "2026-11-02", "activities": [
             {"name": "Amman Citadel", "start_time": "09:00", "end_time": "10:30", "estimated_cost": 8.46,
              "source_url": "https://en.wikivoyage.org/wiki/Amman#See"}]}]}
COVERED = {"trip_days": 1, "sufficient": True, "covered_dates": ["2026-11-02"], "meal_only_dates": [],
           "empty_dates": []}
STATES = {("PASS", "fresh"): "confirmed_valid", ("PASS", "recorded"): "supported_by_records",
          ("PASS", "mixed"): "supported_by_records", ("UNKNOWN", "mixed"): "unverifiable",
          ("FAIL", "fresh"): "confirmed_problem"}


def report(status, basis):
    return SimpleNamespace(status=status, evidence_basis=basis, verified=status == "PASS" and basis == "fresh")


def pipeline(status="PASS", basis="recorded", itinerary=AMMAN):
    final = report(status, basis)
    return {"status": "verified" if final.verified else "verification_required", "message": "checked",
            "itinerary": deepcopy(itinerary), "coverage": COVERED,
            "verification_result": {"verified": final.verified, "verifier_report": SimpleNamespace(verification=final)},
            "verification": {"status": status, "verified": final.verified, "evidence_basis": basis,
                             "state": STATES[(status, basis)], "findings": []}}


def chat(session_id, result, message="Plan Amman"):
    with patch("app.main.orchestrate_trip", return_value=result):
        return client.post("/api/chat", json={"session_id": session_id, "message": message}).json()


@pytest.fixture(autouse=True)
def fresh_sessions(monkeypatch):
    monkeypatch.setenv("TRAVEL_TRAVELLER_ID", "TRV-101")
    sessions.clear()
    yield
    sessions.clear()


# --- The policy itself --------------------------------------------------------------------------------------

@pytest.mark.parametrize("status,basis,eligible,vstatus,approval_basis", [
    ("PASS", "fresh", True, "verified", "live"),
    ("PASS", "recorded", True, "verified_on_records", "recorded"),
    ("PASS", "mixed", True, "verified_on_records", "recorded"),
    ("PASS", "none", False, None, None),
    ("UNKNOWN", "fresh", False, None, None),
    ("UNKNOWN", "recorded", False, None, None),
    ("FAIL", "fresh", False, None, None),
    ("FAIL", "recorded", False, None, None),
])
def test_the_policy_table(status, basis, eligible, vstatus, approval_basis):
    out = approval_eligibility(report(status, basis), coverage_ok=True)
    assert (out["eligible"], out["verification_status"], out["basis"]) == (eligible, vstatus, approval_basis)
    assert out["verified"] is (status == "PASS" and basis == "fresh")  # never changed by the policy
    assert (out["disclosure"] is not None) is (approval_basis == "recorded")
    assert (out["reason"] is None) is eligible  # every refusal says why


def test_an_unknown_verdict_names_the_checks_that_could_not_be_completed():
    rep = SimpleNamespace(status="UNKNOWN", evidence_basis="mixed", verified=False,
                          checks=[SimpleNamespace(check="opening_hours", status="PASS"),
                                  SimpleNamespace(check="budget", status="UNKNOWN"),
                                  SimpleNamespace(check="costs", status="UNKNOWN")])
    reason = approval_eligibility(rep, coverage_ok=True)["reason"]
    assert "budget, costs" in reason and "opening hours" not in reason


def test_thin_coverage_or_no_report_is_never_eligible():
    assert approval_eligibility(report("PASS", "fresh"), coverage_ok=False)["eligible"] is False
    assert approval_eligibility(None, coverage_ok=True)["eligible"] is False
    assert APPROVABLE_STATUSES == {"verified", "verified_on_records"}


# --- Through the API ----------------------------------------------------------------------------------------

def test_pass_on_live_evidence_is_offered_as_verified():
    data = chat("s-live", pipeline("PASS", "fresh"))
    action = data["pending_action"]
    assert data["status"] == "pending_approval" and action["verification_status"] == "verified"
    assert action["approval_basis"] == "live" and action["disclosure"] is None
    assert data["approval_eligibility"]["eligible"] is True and data["verification"]["verified"] is True
    assert "recorded data" not in data["reply"] and "Approve or reject" in data["reply"]


def test_pass_on_recorded_evidence_is_approvable_and_says_so_everywhere():
    data = chat("s-rec", pipeline("PASS", "recorded"))
    action = data["pending_action"]
    assert data["status"] == "pending_approval"
    assert action["verification_status"] == "verified_on_records" and action["evidence_basis"] == "recorded"
    assert RECORDED_DISCLOSURE in action["summary"] and RECORDED_DISCLOSURE in data["reply"]
    assert data["approval_eligibility"] == {"eligible": True, "verification_status": "verified_on_records",
                                "evidence_basis": "recorded", "basis": "recorded", "verified": False,
                                "disclosure": RECORDED_DISCLOSURE, "reason": None}
    assert data["verification"]["verified"] is False and data["verification"]["state"] == "supported_by_records"

    with patch("app.main.save_trip_to_store", return_value={"trip_id": "TRIP-3001"}) as save:
        saved = client.post("/api/approve", json={"session_id": "s-rec", "action_id": action["action_id"],
                                                  "approved": True}).json()
    assert saved["status"] == "approved" and saved["result"] == {"trip_id": "TRIP-3001"}
    assert "recorded data" in saved["reply"]
    assert save.call_args.kwargs["action_id"] == action["action_id"]  # the idempotency key


@pytest.mark.parametrize("status,basis", [("UNKNOWN", "mixed"), ("FAIL", "fresh")])
def test_unknown_or_fail_is_never_offered(status, basis):
    data = chat("s-no", pipeline(status, basis))
    assert data["status"] == "verification_required" and data["pending_action"] is None
    assert data["itinerary"] is not None  # shown, with the reason, never hidden
    assert data["approval_eligibility"]["eligible"] is False and data["approval_eligibility"]["reason"]
    assert "cannot be approved" in data["reply"]
    assert sessions["s-no"]["pending_action"] is None


def test_a_forged_status_on_a_pending_action_is_refused():
    action = chat("s-forge", pipeline("PASS", "recorded"))["pending_action"]
    sessions["s-forge"]["pending_action"]["verification_status"] = "unverifiable"
    with patch("app.main.save_trip_to_store") as save:
        r = client.post("/api/approve", json={"session_id": "s-forge", "action_id": action["action_id"],
                                              "approved": True})
    assert r.status_code == 403 and not save.called


# --- The open approval survives messages without a new plan (B3) ---------------------------------------------

@pytest.mark.parametrize("answer", [
    {"status": "unsupported_request", "message": "Please send me a trip planning request."},
    {"status": "needs_clarification", "message": "Which day?"},
    {"status": "needs_clarification", "message": "Nothing changed.", "revision": {"outcome": "not_feasible"}},
])
def test_a_message_without_a_new_plan_keeps_the_open_approval(answer):
    first = chat("s-keep", pipeline("PASS", "recorded"))["pending_action"]
    data = chat("s-keep", answer, message="what's the weather like?")
    assert data["pending_action"]["action_id"] == first["action_id"]
    assert "still waiting for your approval" in data["reply"]
    with patch("app.main.save_trip_to_store", return_value={"trip_id": "TRIP-3002"}):
        saved = client.post("/api/approve", json={"session_id": "s-keep", "action_id": first["action_id"],
                                                  "approved": True}).json()
    assert saved["result"] == {"trip_id": "TRIP-3002"}


def test_a_new_plan_replaces_the_open_approval_and_an_unapprovable_one_clears_it():
    first = chat("s-new", pipeline("PASS", "recorded"))["pending_action"]
    second = chat("s-new", pipeline("PASS", "fresh", {**AMMAN, "budget_total": 500}))["pending_action"]
    assert second["action_id"] != first["action_id"]
    third = chat("s-new", pipeline("UNKNOWN", "mixed"))
    assert third["pending_action"] is None and sessions["s-new"]["pending_action"] is None
    with patch("app.main.save_trip_to_store") as save:
        old = client.post("/api/approve", json={"session_id": "s-new", "action_id": second["action_id"],
                                                "approved": True}).json()
    assert old["status"] == "no_pending_action" and not save.called


def test_reject_writes_nothing_and_a_later_approve_of_it_writes_nothing():
    action = chat("s-rej", pipeline("PASS", "recorded"))["pending_action"]
    with patch("app.main.save_trip_to_store") as save:
        no = client.post("/api/approve", json={"session_id": "s-rej", "action_id": action["action_id"],
                                               "approved": False}).json()
        again = client.post("/api/approve", json={"session_id": "s-rej", "action_id": action["action_id"],
                                                  "approved": True}).json()
    assert no["status"] == "rejected" and no["result"] is None and "TRIP-" not in no["reply"]
    assert again["result"] is None and not save.called
