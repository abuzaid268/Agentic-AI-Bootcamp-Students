"""Checks a WHAT IF result against a scenario fixture (tests/fixtures/whatif/). Read-only: it never revises,
approves or saves anything.

A result is what app/whatif.py preview()/apply_proposal() return (backup/rihla-integration-wip branch): a dict with
"status" ("whatif_preview", "whatif_not_feasible", "needs_clarification", ...), the revised "itinerary" in the
README's save_trip schema, and a "whatif" block. Each check returns a list of violations (strings); [] means it
passed. Useful for Member 1's tests and evals; nothing here decides what the plan should become.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any, Iterable

NOT_FEASIBLE = ("whatif_not_feasible", "needs_clarification")
SAVED_MARKERS = ("trip_id",)
_HHMM = re.compile(r"^([01]\d|2[0-4]):[0-5]\d$")


def minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _windows(place: dict, weekday: str) -> list[tuple[int, int]] | None:
    """Opening windows in minutes for that weekday; [] when the listing says closed; None when it cannot be told
    (no weekly hours, or an unparsable window such as "?-20:00")."""
    weekly = place.get("weekly")
    if not isinstance(weekly, dict) or not weekly:
        return None
    windows = []
    for window in weekly.get(weekday, []):
        start, _, end = str(window).partition("-")
        if not (_HHMM.match(start) and _HHMM.match(end)):
            return None
        windows.append((minutes(start), minutes(end)))
    return windows


def _place_of(activity: dict, places: dict[str, dict]) -> dict | None:
    if activity.get("place_id") in places:
        return places[activity["place_id"]]
    return next((p for p in places.values() if p.get("name") == activity.get("name")), None)


def _ids(day: dict, places: dict[str, dict]) -> list[str]:
    out = []
    for a in day.get("activities") or []:
        place = _place_of(a, places)
        out.append(place["place_id"] if place else str(a.get("name")))
    return out


def check_itinerary(itinerary: Any, *, places: dict[str, dict], travel_minutes: dict[str, int] | None = None,
                    max_total: float | Decimal | None = None) -> list[str]:
    """Times, overlaps, the listed opening hours, the stated travel times and the budget of one itinerary."""
    if not isinstance(itinerary, dict) or not isinstance(itinerary.get("days"), list):
        return ["The result has no itinerary in the save_trip schema."]
    problems, known = [], Decimal(0)
    travel = travel_minutes or {}
    for day in itinerary["days"]:
        try:
            weekday = dt.date.fromisoformat(str(day.get("date"))).strftime("%a")
        except ValueError:
            problems.append(f"A day has no valid date: {day.get('date')!r}.")
            continue
        previous = None
        for a in day.get("activities") or []:
            name, start, end = a.get("name"), a.get("start_time"), a.get("end_time")
            if not (isinstance(start, str) and isinstance(end, str) and _HHMM.match(start) and _HHMM.match(end)) \
                    or minutes(end) <= minutes(start):
                problems.append(f"{day['date']} {name}: start and end times are missing or not in order.")
                continue
            place = _place_of(a, places)
            if place is not None:
                windows = _windows(place, weekday)
                if windows == []:
                    problems.append(f"{day['date']} {name}: the listing says it is closed on {weekday}.")
                elif windows and not any(s <= minutes(start) and minutes(end) <= e for s, e in windows):
                    problems.append(f"{day['date']} {name} {start}-{end}: outside the listed hours "
                                    f"{place['weekly'].get(weekday)}.")
            if previous is not None:
                prev_activity, prev_place = previous
                gap = minutes(start) - minutes(prev_activity["end_time"])
                if gap < 0:
                    problems.append(f"{day['date']} {name} starts before {prev_activity.get('name')} ends.")
                elif prev_place and place:
                    need = travel.get(f"{prev_place['place_id']}|{place['place_id']}")
                    if need is not None and gap < need:
                        problems.append(f"{day['date']} {prev_activity.get('name')} -> {name}: {gap} min between "
                                        f"them, {need} min needed to get there.")
            previous = (a, place)
            cost = a.get("estimated_cost")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                known += Decimal(str(cost))
    if max_total is not None and known > Decimal(str(max_total)):
        problems.append(f"The known costs ({known}) exceed {max_total}.")
    return problems


def _walk(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def check_no_automatic_save(result: Any) -> list[str]:
    """A WHAT IF preview or an applied proposal is never saved or approved by itself: the save_trip approval gate
    (POST /api/approve) is the only way. A pending_action that asks for approval is fine."""
    if not isinstance(result, dict):
        return ["The result is not a dict."]
    problems = []
    if result.get("status") in ("saved", "approved"):
        problems.append(f"The result says {result['status']!r}: a WHAT IF must not save or approve by itself.")
    if any(key in SAVED_MARKERS for key in _walk(result)):
        problems.append("The result carries a trip_id: something was saved without the traveller's approval.")
    return problems


def check_against_fixture(fixture: dict, result: Any) -> list[str]:
    """Every expectation the fixture states, on one result. [] means the result is acceptable."""
    problems = check_no_automatic_save(result)
    if problems or not isinstance(result, dict):
        return problems
    expected = fixture["expected"]
    places = {p["place_id"]: p for p in fixture["places"]}
    original = fixture["original_itinerary"]

    if result.get("status") in NOT_FEASIBLE:
        if "not_feasible" not in expected["outcome_one_of"]:
            problems.append("The fixture expects a revised plan, but the result is not feasible.")
        if not str(result.get("message") or (result.get("whatif") or {}).get("reason") or "").strip():
            problems.append("A scenario that cannot be applied must say why.")
        return problems
    if result.get("status") != "whatif_preview" and not (result.get("whatif") or {}).get("applied"):
        return [f"Unexpected status {result.get('status')!r} for a WHAT IF."]
    if "revised" not in expected["outcome_one_of"]:
        problems.append("The fixture expects this scenario to be refused, but a revised plan was proposed.")

    revised = result.get("itinerary")
    rules = expected.get("if_revised", {})
    problems += check_itinerary(revised, places=places, travel_minutes=fixture.get("travel_minutes"),
                                max_total=rules.get("max_known_total"))
    if not isinstance(revised, dict):
        return problems
    by_date = {d.get("date"): d for d in revised.get("days") or []}
    original_by_date = {d["date"]: d for d in original["days"]}
    if rules.get("same_dates") and sorted(by_date) != sorted(original_by_date):
        problems.append(f"The trip dates changed: {sorted(by_date)} instead of {sorted(original_by_date)}.")
    for date in rules.get("unchanged_dates", []):
        if _ids(by_date.get(date, {}), places) != _ids(original_by_date[date], places):
            problems.append(f"{date} should be unchanged.")
    for date, gone in rules.get("absent_on", {}).items():
        still = [pid for pid in _ids(by_date.get(date, {}), places) if pid in gone]
        if still:
            problems.append(f"{date} still has {still}.")
    for pid in rules.get("never_added", []):
        if any(pid in _ids(d, places) for d in by_date.values()):
            problems.append(f"{pid} was added, but the fixture rules it out.")
    first = rules.get("first_start_not_before")
    if first:
        acts = by_date.get(first["date"], {}).get("activities") or []
        starts = [a.get("start_time") for a in acts if isinstance(a.get("start_time"), str)]
        if starts and min(starts) < first["time"]:
            problems.append(f"{first['date']} starts at {min(starts)}, before {first['time']}.")
    if "budget_total" in rules and revised.get("budget_total") != rules["budget_total"]:
        problems.append(f"budget_total is {revised.get('budget_total')}, expected {rules['budget_total']}.")
    return problems
