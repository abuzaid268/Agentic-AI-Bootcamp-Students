"""Saving a plan that is not eligible for approval: the traveller's own acknowledged decision (POST /api/accept).

Real here, as in test_my_trips_journey: app.main behind install_auth (sessions, CSRF, session ownership), the
approval policy, MCP save_trip over stdio -> the Travel API's Trip Store process, GET /api/trips and /api/trips/{id}.

TEST FIXTURE (labelled): the planning pipeline's result, with a Python verdict of UNKNOWN (a price and opening hours
the sources do not give) or FAIL (a confirmed schedule conflict). The verdict is never changed by what is tested here.
"""
from copy import deepcopy
from types import SimpleNamespace

from app.approval_policy import acceptance, approval_eligibility
from test_auth import ORIGIN, auth_env  # noqa: F401  (auth_env: autouse env)
from test_mcp_integration import api, travel_api  # noqa: F401  (the real Trip Store process and its reset)
from test_my_trips_journey import COVERED, ISTANBUL, decide, plan, planned, store_trips, traveller, user

AMMAN = {"destination": "Amman", "currency": "USD", "travellers": 2, "budget_total": 500, "estimated_total": 30,
         "days": [
             {"date": "2026-11-05", "activities": [
                 {"place_id": "wv-amman-citadel", "name": "Amman Citadel", "start_time": "09:00", "end_time": "11:00",
                  "estimated_cost": 30, "source_url": "https://en.wikivoyage.org/wiki/Amman#See"},
                 {"place_id": "wv-amman-rainbow", "name": "Rainbow Street", "start_time": "12:00", "end_time": "13:30",
                  "estimated_cost": None, "source_url": "https://en.wikivoyage.org/wiki/Amman#See"}]}]}
FINDINGS = [
    {"code": "hours_unknown", "state": "unverifiable", "check": "opening_hours", "date": "2026-11-05",
     "place_id": "wv-amman-rainbow", "explanation": "The listing gives no opening hours."},
    {"code": "cost_unknown", "state": "unverifiable", "check": "costs", "date": None,
     "place_id": "wv-amman-rainbow", "explanation": "No price in the sources."},
    {"code": "route_unknown", "state": "unverifiable", "check": "travel", "date": "2026-11-05",
     "place_id": "wv-amman-rainbow", "explanation": "The walking leg could not be measured."}]
BUDGET = {"currency": "USD", "budget_total": "500.00", "planned_known_total": "30.00",
          "unknown_price_items": ["Rainbow Street"], "not_included": ["accommodation", "flights"]}


def unverified(itinerary=AMMAN, status="UNKNOWN", findings=FINDINGS):
    """TEST FIXTURE: a pipeline result whose final Python verdict is UNKNOWN (or FAIL)."""
    final = SimpleNamespace(status=status, evidence_basis="recorded", verified=False,
                            checks=[SimpleNamespace(check="opening_hours", status=status)])
    return {"status": "verification_required", "message": "Some facts could not be checked.",
            "itinerary": deepcopy(itinerary), "coverage": COVERED,
            "verification_result": {"verified": False, "verifier_report": SimpleNamespace(verification=final)},
            "verification": {"status": status, "verified": False, "evidence_basis": "recorded",
                             "state": "unverifiable" if status == "UNKNOWN" else "confirmed_problem",
                             "findings": deepcopy(findings)},
            "budget": deepcopy(BUDGET)}


def accept(client, session_id, offer, acknowledged=True, mode=None):
    return client.post("/api/accept", headers=ORIGIN, json={
        "session_id": session_id, "acceptance_id": offer["acceptance_id"], "acknowledged": acknowledged,
        "mode": mode or offer["mode"]})


# ------------------------------------------------------------------ the policy (no store)
def test_unknown_facts_are_listed_and_prices_are_never_counted():
    report = SimpleNamespace(status="UNKNOWN", evidence_basis="recorded", verified=False, checks=[])
    offer = acceptance(approval_eligibility(report, True), AMMAN, unverified()["verification"], BUDGET)
    assert offer["mode"] == "accepted_with_limitations" and offer["label"] == "Saved · Not Fully Verified"
    assert offer["verified"] is False and offer["verification_status"] == "UNKNOWN"
    text = " ".join(offer["limitations"])
    assert "Opening hours could not be confirmed: Rainbow Street, 2026-11-05" in text
    assert "Travel times could not be measured" in text
    assert "Price unavailable for 1 planned item(s): Rainbow Street" in text and "cannot be guaranteed" in text
    assert "Some prices are unavailable" not in text  # the unpriced items are listed once, by name


def test_findings_name_places_from_the_research_not_by_id():
    itinerary = deepcopy(AMMAN)
    for a in itinerary["days"][0]["activities"]:
        a.pop("place_id")  # as the Trip Store payload: no place_id
    report = SimpleNamespace(status="UNKNOWN", evidence_basis="recorded", verified=False, checks=[])
    offer = acceptance(approval_eligibility(report, True), itinerary, unverified()["verification"], BUDGET,
                       {"wv-amman-rainbow": "Rainbow Street"})
    text = " ".join(offer["limitations"])
    assert "Opening hours could not be confirmed: Rainbow Street, 2026-11-05" in text and "wv-amman" not in text
    assert offer["costs"] == {"currency": "USD", "known_subtotal": "30.00", "budget_total": "500.00",
                              "unpriced_items": ["Rainbow Street"], "not_included": ["accommodation", "flights"],
                              "budget_guaranteed": False}


def test_a_confirmed_problem_makes_it_an_unverified_draft_and_eligible_plans_get_no_offer():
    problem = [{"code": "day_overloaded", "state": "confirmed_problem", "check": "schedule", "date": "2026-11-05",
                "place_id": None, "explanation": "Day 1 runs past closing time."}]
    report = SimpleNamespace(status="FAIL", evidence_basis="recorded", verified=False, checks=[])
    offer = acceptance(approval_eligibility(report, True), AMMAN, unverified(status="FAIL", findings=problem)
                       ["verification"], BUDGET)
    assert offer["mode"] == "unverified_draft" and offer["confirmed_problems"] == ["Day 1 runs past closing time."]
    passed = SimpleNamespace(status="PASS", evidence_basis="recorded", verified=False, checks=[])
    assert acceptance(approval_eligibility(passed, True), AMMAN, {"status": "PASS"}, BUDGET) is None
    assert acceptance(approval_eligibility(report, True), {"days": []}, None, None) is None  # no valid plan


# ------------------------------------------------------------------ the journey (real MCP and Trip Store)
def test_unknown_plan_has_no_approval_but_can_be_accepted_saved_listed_and_opened(api):
    alice = user("alice")
    data = plan(alice, "s-a", unverified())
    assert data["pending_action"] is None  # the verified approval path is unchanged: no action for UNKNOWN
    offer = data["pending_acceptance"]
    assert offer["mode"] == "accepted_with_limitations" and "payload" not in offer
    unsure = unverified()
    unsure["message"] = "The itinerary could not be fully verified. No approval is allowed."
    said = plan(alice, "s-a2", unsure)
    assert "cannot be approved as verified, but you can save it with its limitations" in said["message"]
    assert "cannot be approved yet" in said["reply"] and said["pending_action"] is None
    assert alice.post("/api/approve", headers=ORIGIN, json={"session_id": "s-a", "action_id": offer["acceptance_id"],
                                                            "approved": True}).json()["status"] == "no_pending_action"

    r = accept(alice, "s-a", offer)
    assert r.status_code == 200, r.text
    body = r.json()
    trip_id = body["result"]["trip_id"]
    assert body["status"] == "saved_unverified" and trip_id.startswith("TRIP-") and "not a verification" in body["reply"]
    [rec] = store_trips(api)
    assert rec["trip_id"] == trip_id and rec["traveller_id"] == traveller("alice")
    saved = rec["itinerary"]
    assert saved["days"][0]["activities"][1]["estimated_cost"] is None  # unknown stays unknown, never 0
    assert saved["rihla_save"]["mode"] == "accepted_with_limitations" and saved["rihla_save"]["verified"] is False
    assert saved["rihla_save"]["costs"]["unpriced_items"] == ["Rainbow Street"]

    again = accept(alice, "s-a", offer).json()  # a double click writes nothing
    assert again["result"]["trip_id"] == trip_id and len(store_trips(api)) == 1
    [card] = alice.get("/api/trips").json()["trips"]
    assert card["trip_id"] == trip_id and card["save_mode"] == "accepted_with_limitations"
    opened = alice.get(f"/api/trips/{trip_id}").json()
    assert opened["itinerary"]["rihla_save"]["label"] == "Saved · Not Fully Verified"
    assert user("bob").get(f"/api/trips/{trip_id}").status_code == 404  # another account cannot open it


def test_cancel_wrong_mode_and_another_user_save_nothing(api):
    alice = user("alice")
    offer = plan(alice, "s-c", unverified())["pending_acceptance"]
    cancelled = accept(alice, "s-c", offer, acknowledged=False).json()
    assert cancelled["status"] == "not_saved" and cancelled["result"] is None
    assert accept(alice, "s-c", offer, mode="unverified_draft").status_code == 409
    assert accept(user("bob"), "s-c", offer).status_code == 403  # the session belongs to alice
    assert store_trips(api) == [] and alice.get("/api/trips").json()["count"] == 0
    assert accept(alice, "s-c", offer).json()["status"] == "saved_unverified"  # still possible after a cancel


def test_a_failed_plan_is_saved_only_as_an_unverified_draft(api):
    alice = user("alice")
    problem = [{"code": "day_overloaded", "state": "confirmed_problem", "check": "schedule", "date": "2026-11-05",
                "place_id": None, "explanation": "Day 1 runs past closing time."}]
    offer = plan(alice, "s-f", unverified(ISTANBUL, status="FAIL", findings=problem))["pending_acceptance"]
    assert offer["mode"] == "unverified_draft" and offer["label"] == "Saved · Unverified Draft"
    assert accept(alice, "s-f", offer).json()["result"]["mode"] == "unverified_draft"
    assert alice.get("/api/trips").json()["trips"][0]["save_mode"] == "unverified_draft"


def test_an_approved_trip_is_listed_as_approved(api):
    alice = user("alice")
    data = plan(alice, "s-v", planned())
    assert data["pending_acceptance"] is None
    assert decide(alice, "s-v", data["pending_action"]["action_id"]).json()["status"] == "approved"
    assert alice.get("/api/trips").json()["trips"][0]["save_mode"] == "approved"
