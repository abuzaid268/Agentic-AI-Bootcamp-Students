"""WHAT IF: a hypothetical condition applied to the plan on screen, previewed, and kept only if the traveller applies it.

    scenario -> structured operations (no LLM reads the request) -> app/revision.run_trip_revision(commit=False):
    the same revision edits, Revision Agent, verification, coverage and density as a typed change request
    -> a proposal kept in the session; the session's plan is unchanged until POST /api/whatif/apply

Scenarios (each says it is hypothetical; nothing claims the condition really happened):
    budget_cut  {percent: 1-90, default 30}       set_budget to the current budget minus that share
    rain        {date: optional}                  outdoor places on that date (or every date) replaced by indoor
                                                  ones the research found; a live forecast is reported when there is one
    closure     {place_id, date}                  that attraction replaced, or removed when nothing fits
    delay       {hours: 1-12, default 3}          the first day starts that much later; what no longer fits is moved
                                                  or dropped by the scheduler, other days are kept as they are
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from planning.user_revision import Interpretation, PlanState, RevisionOp

SCENARIOS = ("budget_cut", "rain", "closure", "delay")
MAX_PROPOSALS = 5  # per session, newest kept
RAIN_MM, RAIN_PROBABILITY = 1.0, 60  # a forecast day counts as rainy at or above either


class WhatIfError(ValueError):
    """The scenario cannot be set up for this plan; the message says why. Nothing is changed."""


def _dates(st: PlanState) -> list[dt.date]:
    return [d.date for d in st.itinerary.days]


def _date(value: Any, st: PlanState) -> dt.date:
    try:
        day = dt.date.fromisoformat(str(value))
    except ValueError:
        raise WhatIfError("Choose one of the trip's dates.") from None
    if day not in _dates(st):
        raise WhatIfError(f"{day} is not a date of this trip.")
    return day


def _planned(st: PlanState) -> dict[str, dt.date]:
    return {a.place_id: d.date for d in st.itinerary.days for a in d.activities if a.place_id}


def _add_hours(hhmm: str, hours: int) -> str | None:
    h, m = map(int, hhmm.split(":"))
    total = h * 60 + m + hours * 60
    return None if total >= 24 * 60 else f"{total // 60:02d}:{total % 60:02d}"


def forecast_rain(destination: str, dates: list[dt.date], read_tool=None) -> dict[str, Any]:
    """What the weather data says about rain on the trip dates. Rain is "confirmed" only by a live forecast (never by
    last year's values, a replayed cache or a failed lookup); otherwise the scenario stays hypothetical."""
    if read_tool is None:
        from researcher.mcp_client import call_read_tool as read_tool
    from planning.verification import freshness_of
    try:
        result = read_tool("get_weather", {"city": destination, "start_date": str(min(dates)),
                                           "end_date": str(max(dates))})
    except Exception:
        result = None
    if not isinstance(result, dict) or result.get("ok") is not True:
        return {"available": False, "live": False, "rainy_dates": [],
                "note": "No weather data could be read, so the rain is hypothetical."}
    live = result.get("kind") == "forecast" and freshness_of(result) == "fresh"
    rainy = [str(d.get("date")) for d in result.get("days") or [] if isinstance(d, dict) and (
        (d.get("precip_mm") or 0) >= RAIN_MM or (d.get("precip_probability_pct") or 0) >= RAIN_PROBABILITY)]
    if not live:
        return {"available": True, "live": False, "rainy_dates": [],
                "note": "There is no live forecast for these dates (only recorded or last year's values), so the "
                        "rain is hypothetical."}
    return {"available": True, "live": True, "rainy_dates": rainy, "source": result.get("source"),
            "note": (f"The live forecast ({result.get('source') or 'Open-Meteo'}) shows rain on {', '.join(rainy)}."
                     if rainy else "The live forecast shows no rain on these dates: this is a hypothetical rain.")}


def interpretation_for(scenario: dict, st: PlanState, *, read_tool=None) -> tuple[Interpretation, dict[str, Any]]:
    """The structured operations for a scenario, and what the traveller is told about it. Raises WhatIfError."""
    kind = scenario.get("type")
    if kind not in SCENARIOS:
        raise WhatIfError("Choose one of the WHAT IF scenarios: budget cut, rain, closure or delay.")
    info: dict[str, Any] = {"type": kind, "hypothetical": True}

    if kind == "budget_cut":
        percent = scenario.get("percent", 30)
        if not isinstance(percent, (int, float)) or isinstance(percent, bool) or not 1 <= percent <= 90:
            raise WhatIfError("The budget cut must be between 1 and 90 percent.")
        total = st.budget_report.budget_total
        if total is None:
            raise WhatIfError("This plan has no budget to cut.")
        amount = (Decimal(str(total)) * (Decimal(100) - Decimal(str(percent))) / 100).quantize(
            Decimal("0.01"), ROUND_HALF_UP)
        info.update(title=f"What if the budget were {percent:g}% lower?", percent=percent,
                    budget_before=str(total), budget_after=str(amount),
                    assumption=f"A hypothetical budget of {amount} {st.budget_report.currency} instead of {total}.")
        return Interpretation(ops=[RevisionOp(kind="set_budget", amount=amount, note=info["assumption"])],
                              understood=[info["assumption"]]), info

    if kind == "rain":
        day = _date(scenario["date"], st) if scenario.get("date") else None
        dates = [day] if day else _dates(st)
        weather = forecast_rain(st.bundle.trip.destination, dates, read_tool)
        where = str(day) if day else "every day of the trip"
        info.update(title=f"What if it rained on {where}?", date=str(day) if day else None, weather=weather,
                    assumption=f"Hypothetical rain on {where}: outdoor places are swapped for indoor ones the "
                               "research found, where one fits.")
        return Interpretation(ops=[RevisionOp(kind="rain_indoor", date=day, note=info["assumption"])],
                              understood=[info["assumption"]]), info

    if kind == "closure":
        place_id = scenario.get("place_id")
        planned = _planned(st)
        if not isinstance(place_id, str) or place_id not in planned:
            raise WhatIfError("Choose an attraction from this itinerary.")
        place = next((p for p in st.bundle.places if p.place_id == place_id), None)
        if place is not None and place.category == "restaurant":
            raise WhatIfError("Choose an attraction, not a restaurant.")
        day = planned[place_id]
        name = place.name if place else place_id
        info.update(title=f"What if {name} were closed?", place_id=place_id, place_name=name, date=str(day),
                    assumption=f"A hypothetical closure of {name} on {day}: it is not known to be closed.")
        return Interpretation(ops=[RevisionOp(kind="closed", place_id=place_id, date=day, note=info["assumption"])],
                              understood=[info["assumption"]]), info

    hours = scenario.get("hours", 3)
    if not isinstance(hours, int) or isinstance(hours, bool) or not 1 <= hours <= 12:
        raise WhatIfError("The delay must be a whole number of hours between 1 and 12.")
    first = _dates(st)[0]
    start = st.rules.day_starts.get(str(first)) or st.rules.day_start
    later = _add_hours(start, hours)
    if later is None or later >= st.rules.day_end:
        raise WhatIfError(f"A {hours}-hour delay would leave no planning time on {first} (the day ends at "
                          f"{st.rules.day_end}).")
    info.update(title=f"What if you arrived {hours} hours late?", hours=hours, date=str(first), start_before=start,
                start_after=later, assumption=f"A hypothetical {hours}-hour delay: {first} starts at {later} instead "
                                              f"of {start}.")
    return Interpretation(ops=[RevisionOp(kind="start_time", date=first, time=later, note=info["assumption"])],
                          understood=[info["assumption"]]), info


def preview(session: dict, scenario: dict, trip_info: dict, *, base_version: str | None, read_tool=None,
            revise=None) -> dict[str, Any]:
    """Run the scenario on the session's plan without changing it. Returns a result like a revision's, with a
    "whatif" block; an applicable proposal is kept in the session under its proposal_id."""
    from app.revision import _no_change, run_trip_revision
    revise = revise or run_trip_revision
    state: PlanState | None = session.get("plan_state")
    if state is None:
        return _no_change("needs_clarification", "There is no plan in this session to try a WHAT IF on: plan the "
                          "trip again (a saved trip opened from My Trips is not kept in memory).", "no_plan", None)
    if base_version and base_version != state.version:
        return _no_change("needs_clarification", "This itinerary is not the latest version of your plan. Reload it, "
                          "then try the WHAT IF again.", "stale_plan", state)
    try:
        interpretation, info = interpretation_for(scenario, state, read_tool=read_tool)
    except WhatIfError as exc:
        out = _no_change("whatif_not_feasible", str(exc), "not_feasible", state)
        out["whatif"] = {"type": scenario.get("type"), "hypothetical": True, "outcome": "not_feasible", "reason": str(exc)}
        return out

    result = revise(session, info["title"], trip_info, base_version=state.version, interpretation=interpretation,
                    commit=False)
    new_state = result.pop("_plan_state", None)
    outcome = (result.get("revision") or {}).get("outcome")
    info["outcome"] = outcome or "not_feasible"
    info["base_version"] = state.version
    if outcome != "revised" or new_state is None:
        if info["type"] == "rain" and str(result.get("message", "")).startswith("Nothing in the itinerary needed"):
            result["message"] = ("No planned activity is outdoors (going by each place's own listing), so rain would "
                                 "not change this plan. Your itinerary has not been changed.")
        info["reason"] = result.get("message")
        result["status"] = "whatif_not_feasible" if result.get("status") == "revision_not_feasible" else result.get("status")
        result["whatif"] = info
        return result

    proposal_id = uuid.uuid4().hex[:12]
    proposals = session.setdefault("whatif_proposals", {})
    proposals[proposal_id] = {"state": new_state, "result": {k: v for k, v in result.items()},
                              "base_version": state.version, "info": info}
    for old in list(proposals)[:-MAX_PROPOSALS]:
        proposals.pop(old, None)
    info["proposal_id"] = proposal_id
    info["result_status"] = result["status"]  # what verification said about the revised plan
    result["whatif"] = info
    result["status"] = "whatif_preview"
    return result


def apply_proposal(session: dict, proposal_id: str) -> dict[str, Any]:
    """Make a previewed proposal the session's plan (only if the plan it was made from is still the current one).
    Returns the proposal's result, which then goes through the same approval gate as any revised plan."""
    from app.revision import _no_change
    proposals = session.get("whatif_proposals") or {}
    proposal = proposals.get(proposal_id)
    state: PlanState | None = session.get("plan_state")
    if proposal is None:
        return _no_change("needs_clarification", "That WHAT IF preview is no longer available (it was applied, "
                          "replaced or the server restarted). Run it again.", "no_proposal", state)
    if state is None or state.version != proposal["base_version"]:
        return _no_change("needs_clarification", "Your plan changed since this WHAT IF was previewed, so it was not "
                          "applied. Run it again on the current plan.", "stale_plan", state)
    session["plan_state"] = proposal["state"]
    session["itinerary"] = proposal["state"].itinerary.to_trip_store()
    session["whatif_proposals"] = {}
    result = dict(proposal["result"])
    result["whatif"] = {**proposal["info"], "applied": True}
    return result
