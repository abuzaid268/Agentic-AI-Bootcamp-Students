"""WHAT IF (app/whatif.py): four hypothetical scenarios on the plan on screen, previewed without changing it, applied
only on request, and then gated like any revised plan.

Offline, like tests/test_trip_revision.py: the Istanbul research fixture and the REAL revision edit, Budget Analyst
fitting, scheduler and Python verification, on recorded travel times. Replaced (test fixtures): the Revision
Agent's choice (Python's default), the Verifier agent (Python's own verify_itinerary), and the weather tool's answer.
"""
import datetime as dt
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import whatif
from app.auth import sessions as auth_sessions  # noqa: F401
from app.memory import get_session, sessions
from app.revision import run_trip_revision
from planning.setting import setting
from test_trip_revision import TRIP_INFO, plan_state, python_verification  # also puts tests/planning on the path
from research_fixtures import recorded_lookup  # noqa: E402
from test_auth import ORIGIN, auth_env, real_app, sign_in  # noqa: F401,E402  (auth_env: autouse env)

REPLAYED_FORECAST = {"ok": True, "kind": "forecast", "mode": "replay", "days": [
    {"date": "2026-11-02", "precip_mm": 9.0, "precip_probability_pct": 90}]}  # recorded: never a confirmation
LIVE_RAIN = {"ok": True, "kind": "forecast", "mode": "live", "source": "Open-Meteo forecast API", "days": [
    {"date": "2026-11-02", "precip_mm": 0.0, "precip_probability_pct": 10},
    {"date": "2026-11-04", "precip_mm": 6.5, "precip_probability_pct": 85}]}


def weather(answer):
    return lambda name, args: answer


def revise(session, request, trip_info, *, base_version=None, interpretation=None, commit=True):
    """run_trip_revision with the LLM parts replaced (see the module docstring)."""
    def make_decide(llm, b, report, run):
        def decide(points):
            run.called = True
            return {p.id: p.default for p in points}
        return decide
    with patch("app.verification_adapter.run_verification_pipeline", side_effect=python_verification), \
            patch("app.revision.make_decide", make_decide):
        return run_trip_revision(session, request, trip_info, base_version=base_version, llm=object(),
                                 lookups=(None, recorded_lookup()), interpretation=interpretation, commit=commit)


@pytest.fixture()
def session():
    sessions.clear()
    s = get_session("w")
    s["plan_state"] = plan_state()  # Istanbul, 2026-11-02..04, 700 USD
    s["itinerary"] = s["plan_state"].itinerary.to_trip_store()
    return s


def preview(session, scenario, answer=REPLAYED_FORECAST):
    return whatif.preview(session, scenario, TRIP_INFO, base_version=session["plan_state"].version,
                          read_tool=weather(answer), revise=revise)


def names(itinerary, day):
    return [a["name"] for a in itinerary["days"][day]["activities"]]


# --- every scenario is a preview: the plan on screen does not change ----------------------------------------

@pytest.mark.parametrize("scenario", [{"type": "budget_cut"}, {"type": "closure", "place_id": "wv-istanbul-pera-museum"},
                                      {"type": "delay"}])
def test_a_preview_never_changes_the_session_plan(session, scenario):
    before, version = dict(session["itinerary"]), session["plan_state"].version
    out = preview(session, scenario)
    assert out["status"] == "whatif_preview" and out["whatif"]["hypothetical"] is True
    assert out["whatif"]["proposal_id"] in session["whatif_proposals"]
    assert session["plan_state"].version == version and session["itinerary"] == before
    assert out["verification"] is not None  # every proposal is verified again
    assert out["whatif"]["result_status"] in ("verified", "verification_required")


# --- 1. budget reduction --------------------------------------------------------------------------------------

def test_budget_cut_by_30_percent_reuses_the_plan_and_recalculates(session):
    out = preview(session, {"type": "budget_cut", "percent": 30})
    assert out["whatif"]["budget_before"] == "700.00" and out["whatif"]["budget_after"] == "490.00"
    assert out["itinerary"]["budget_total"] == 490.0
    assert out["revision"]["budget_before"] == "700.00" and out["revision"]["budget_after"] == "490.00"
    known = out["itinerary"]["estimated_total"]
    assert known <= 490.0  # the known costs fit the reduced budget (unknown prices are said, never counted as 0)
    assert any("unknown" in c for c in out["revision"]["changes"])
    assert out["itinerary"]["days"] == session["itinerary"]["days"]  # nothing had to change: the same activities


def test_a_budget_cut_too_deep_for_the_required_places_is_refused_not_invented(session):
    out = preview(session, {"type": "budget_cut", "percent": 90})
    if out["status"] == "whatif_preview":  # the plan may still fit: then it must really fit
        assert out["itinerary"]["estimated_total"] <= 70.0
    else:
        assert out["status"] in ("whatif_not_feasible", "needs_clarification") and out["whatif"]["reason"]
        assert "whatif_proposals" not in session or not session["whatif_proposals"]


# --- 2. rain ---------------------------------------------------------------------------------------------------

def test_indoor_and_outdoor_come_from_each_listing():
    places = {p.place_id: p for p in plan_state().bundle.places}
    assert setting(places["wv-istanbul-galata-tower"]) == "outdoor"  # a viewpoint tower
    assert setting(places["wv-istanbul-hagia-sophia"]) == "indoor"
    assert setting(places["wv-istanbul-hurrem-sultan-hamami"]) == "indoor"  # a bathhouse ("hamamı")


def test_rain_on_an_all_indoor_plan_changes_nothing_and_says_why(session):
    out = preview(session, {"type": "rain"})
    assert out["status"] == "whatif_not_feasible" and "No planned activity is outdoors" in out["message"]
    assert out["whatif"]["weather"]["live"] is False  # a replayed forecast never confirms rain
    assert "hypothetical" in out["whatif"]["weather"]["note"]


def test_rain_swaps_an_outdoor_place_for_an_indoor_one_and_a_live_forecast_is_reported(session):
    # First a closure that brings an outdoor place into the plan (Pera Museum -> Galata Tower), applied ...
    closure = preview(session, {"type": "closure", "place_id": "wv-istanbul-pera-museum"})
    assert "Galata Tower" in names(closure["itinerary"], 2)
    applied = whatif.apply_proposal(session, closure["whatif"]["proposal_id"])
    assert applied["whatif"]["applied"] is True and "Galata Tower" in names(session["itinerary"], 2)
    # ... then rain on that day: the tower goes, an indoor place the research found comes in; other days stay.
    out = preview(session, {"type": "rain", "date": "2026-11-04"}, answer=LIVE_RAIN)
    assert out["status"] == "whatif_preview"
    assert "Galata Tower" not in names(out["itinerary"], 2)
    places = {p.place_id: p for p in session["plan_state"].bundle.places}
    by_name = {p.name: p for p in places.values()}
    assert all(setting(by_name[n]) == "indoor" for n in names(out["itinerary"], 2))
    assert "Pera Museum" not in names(out["itinerary"], 2)  # the place the traveller took out never comes back
    assert out["revision"]["unchanged_dates"] == ["2026-11-02", "2026-11-03"]
    assert out["whatif"]["weather"] == {**out["whatif"]["weather"], "live": True, "rainy_dates": ["2026-11-04"]}


# --- 3. attraction closure -------------------------------------------------------------------------------------

def test_a_closure_replaces_the_attraction_and_never_claims_it_is_closed(session):
    out = preview(session, {"type": "closure", "place_id": "wv-istanbul-pera-museum"})
    assert "Pera Museum" not in names(out["itinerary"], 2)
    assert any("replaced Pera Museum" in c for c in out["revision"]["changes"])
    assert "not known to be closed" in out["whatif"]["assumption"]
    assert out["revision"]["unchanged_dates"] == ["2026-11-02", "2026-11-03"]


@pytest.mark.parametrize("scenario, why", [
    ({"type": "closure", "place_id": "wv-istanbul-galata-tower"}, "Choose an attraction from this itinerary"),
    ({"type": "closure"}, "Choose an attraction from this itinerary"),
    ({"type": "delay", "hours": 12}, "no planning time"),
    ({"type": "rain", "date": "2026-12-25"}, "not a date of this trip"),
    ({"type": "teleport"}, "Choose one of the WHAT IF scenarios"),
])
def test_impossible_scenarios_are_explained_and_change_nothing(session, scenario, why):
    out = preview(session, scenario)
    assert out["status"] == "whatif_not_feasible" and why in out["whatif"]["reason"]
    assert not session.get("whatif_proposals")


# --- 4. three-hour delay ---------------------------------------------------------------------------------------

def test_a_three_hour_delay_shifts_the_first_day_and_keeps_the_others(session):
    out = preview(session, {"type": "delay", "hours": 3})
    first = out["itinerary"]["days"][0]["activities"]
    assert out["whatif"]["start_before"] == "09:00" and out["whatif"]["start_after"] == "12:00"
    assert all(a["start_time"] >= "12:00" for a in first if a.get("start_time"))
    assert out["revision"]["unchanged_dates"] == ["2026-11-03", "2026-11-04"]
    assert out["itinerary"]["days"][1:] == session["itinerary"]["days"][1:]


# --- applying ---------------------------------------------------------------------------------------------------

def test_apply_only_the_proposal_of_the_current_plan(session):
    one = preview(session, {"type": "delay", "hours": 3})
    two = preview(session, {"type": "budget_cut", "percent": 30})
    applied = whatif.apply_proposal(session, two["whatif"]["proposal_id"])
    assert applied["itinerary"]["budget_total"] == 490.0 and session["plan_state"].budget_report.budget_total == 490
    stale = whatif.apply_proposal(session, one["whatif"]["proposal_id"])  # made from the plan before this one
    assert stale["revision"]["outcome"] in ("no_proposal", "stale_plan")
    assert session["plan_state"].budget_report.budget_total == 490


# --- through the API: signed in, session-bound, never an approval without applying ------------------------------

def api_patches():
    def make_decide(llm, b, report, run):
        return lambda points: {p.id: p.default for p in points}
    return [patch("app.verification_adapter.run_verification_pipeline", side_effect=python_verification),
            patch("app.revision.make_decide", make_decide),
            patch("app.planning_adapter.create_planning_llm", return_value=object()),
            patch("app.mcp_lookup_adapter.create_travel_lookup", return_value=recorded_lookup()),
            patch("app.mcp_lookup_adapter.create_hours_lookup", return_value=None),
            patch("researcher.mcp_client.call_read_tool", side_effect=weather(REPLAYED_FORECAST))]


def test_the_whatif_api_previews_applies_and_is_private(session):
    alice, bob = TestClient(real_app()), TestClient(real_app())
    sign_in(alice, "alice")
    sign_in(bob, "bob")
    session["pending_action"] = {"action_id": "keep", "type": "save_trip", "verification_status": "verified_on_records"}
    patches = api_patches()
    for p in patches:
        p.start()
    try:
        options = alice.post("/api/whatif/options", headers=ORIGIN, json={"session_id": "w"}).json()
        assert options["available"] is True and options["dates"] == ["2026-11-02", "2026-11-03", "2026-11-04"]
        assert {"place_id": "wv-istanbul-pera-museum", "name": "Pera Museum", "date": "2026-11-04",
                "setting": "indoor"} in options["attractions"]
        assert all(a["name"] != "Ali Usta Çiğ Köfte" for a in options["attractions"])  # restaurants are not offered

        r = alice.post("/api/whatif", headers=ORIGIN, json={"session_id": "w", "base_version": options["plan_version"],
                                                            "scenario": {"type": "delay", "hours": 3}}).json()
        assert r["status"] == "whatif_preview" and r["pending_action"] is None
        assert r["reply"].startswith("WHAT IF preview (hypothetical): your itinerary has not been changed")
        assert sessions["w"]["pending_action"]["action_id"] == "keep"  # the open approval is untouched

        # another account can neither preview nor apply on this session
        assert bob.post("/api/whatif", headers=ORIGIN, json={"session_id": "w", "scenario": {"type": "delay"}}).status_code == 403
        assert bob.post("/api/whatif/apply", headers=ORIGIN, json={"session_id": "w", "proposal_id": r["whatif"]["proposal_id"]}).status_code == 403

        applied = alice.post("/api/whatif/apply", headers=ORIGIN,
                             json={"session_id": "w", "proposal_id": r["whatif"]["proposal_id"]}).json()
        assert applied["whatif"]["applied"] is True and applied["plan_version"] != options["plan_version"]
        assert applied["itinerary"]["days"][0]["activities"][0]["start_time"] >= "12:00"
        # applied plans go through the approval gate: UNKNOWN here (recorded data), so no action, and the old one
        # (for the plan that was replaced) is gone
        assert applied["approval_eligibility"]["eligible"] is False and applied["pending_action"] is None
        assert sessions["w"]["pending_action"] is None
    finally:
        for p in patches:
            p.stop()


def test_whatif_needs_sign_in_when_required():
    assert TestClient(real_app()).post("/api/whatif", json={"session_id": "w", "scenario": {"type": "delay"}},
                                       headers=ORIGIN).status_code == 401
