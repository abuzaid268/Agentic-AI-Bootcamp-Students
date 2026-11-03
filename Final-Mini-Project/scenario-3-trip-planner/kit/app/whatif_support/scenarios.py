"""WHAT IF scenario requests and their arithmetic, in the shape Member 1's simulation takes.

The contract is app/whatif.py on the backup/rihla-integration-wip branch (not merged into this branch):
    {"type": "budget_cut", "percent": 1-90 (default 30)}
    {"type": "delay", "hours": 1-12 whole hours (default 3)}
    {"type": "rain", "date": optional trip date}
    {"type": "closure", "place_id": ..., "date": ...}
This module checks a request against those bounds and computes what the simulation should arrive at, so fixtures
and tests can state expected values exactly. It does NOT simulate anything: interpretation, revision,
verification and approval are Member 1's (app/whatif.py, app/revision.py). If the two ever disagree, app/whatif.py
is the authority and this module must be brought in line.
"""
from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SCENARIO_TYPES = ("budget_cut", "rain", "closure", "delay")
DEFAULT_PERCENT, MIN_PERCENT, MAX_PERCENT = 30, 1, 90
DEFAULT_HOURS, MIN_HOURS, MAX_HOURS = 3, 1, 12


class ScenarioError(ValueError):
    """The request is not a valid WHAT IF scenario; the message says why."""


def _date(value: Any, field: str) -> str:
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ScenarioError(f"{field} must be a date like 2026-11-03.") from None


def validate_scenario(scenario: Any) -> dict:
    """The request with its defaults filled in, or ScenarioError. Only checks the request itself: whether a date
    belongs to the trip or a place to the plan is checked against the plan by app/whatif.py."""
    if not isinstance(scenario, dict) or scenario.get("type") not in SCENARIO_TYPES:
        raise ScenarioError("Choose one of the WHAT IF scenarios: budget cut, rain, closure or delay.")
    kind = scenario["type"]
    if kind == "budget_cut":
        percent = scenario.get("percent", DEFAULT_PERCENT)
        if not isinstance(percent, (int, float)) or isinstance(percent, bool) or not MIN_PERCENT <= percent <= MAX_PERCENT:
            raise ScenarioError(f"The budget cut must be between {MIN_PERCENT} and {MAX_PERCENT} percent.")
        return {"type": kind, "percent": percent}
    if kind == "delay":
        hours = scenario.get("hours", DEFAULT_HOURS)
        if not isinstance(hours, int) or isinstance(hours, bool) or not MIN_HOURS <= hours <= MAX_HOURS:
            raise ScenarioError(f"The delay must be a whole number of hours between {MIN_HOURS} and {MAX_HOURS}.")
        return {"type": kind, "hours": hours}
    if kind == "rain":
        return {"type": kind, "date": _date(scenario["date"], "date") if scenario.get("date") else None}
    place_id = scenario.get("place_id")
    if not isinstance(place_id, str) or not place_id.strip():
        raise ScenarioError("Choose an attraction from this itinerary.")
    if not scenario.get("date"):
        raise ScenarioError("Choose the date of the closure.")
    return {"type": kind, "place_id": place_id.strip(), "date": _date(scenario["date"], "date")}


def budget_after(total: Any, percent: Any) -> Decimal:
    """The reduced budget, to the cent (ROUND_HALF_UP), as app/whatif.py computes it."""
    if not isinstance(percent, (int, float)) or isinstance(percent, bool) or not MIN_PERCENT <= percent <= MAX_PERCENT:
        raise ScenarioError(f"The budget cut must be between {MIN_PERCENT} and {MAX_PERCENT} percent.")
    amount = Decimal(str(total))
    if amount < 0:
        raise ScenarioError("A budget cannot be negative.")
    return (amount * (Decimal(100) - Decimal(str(percent))) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


def delayed_start(start: str, hours: int, day_end: str) -> str:
    """The first day's new start after a delay ("09:00" + 3 h = "12:00"), or ScenarioError when no planning time
    would be left before day_end (the same rule as app/whatif.py)."""
    if not isinstance(hours, int) or isinstance(hours, bool) or not MIN_HOURS <= hours <= MAX_HOURS:
        raise ScenarioError(f"The delay must be a whole number of hours between {MIN_HOURS} and {MAX_HOURS}.")
    h, m = map(int, start.split(":"))
    total = h * 60 + m + hours * 60
    later = None if total >= 24 * 60 else f"{total // 60:02d}:{total % 60:02d}"
    if later is None or later >= day_end:
        raise ScenarioError(f"A {hours}-hour delay would leave no planning time (the day ends at {day_end}).")
    return later
