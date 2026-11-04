"""Which plans may be offered for approval, and on what evidence (RIHLA_APPROVAL_PROPOSAL.md).

The verifier's verdict is never changed here: `verified` stays True only for PASS on fresh (live) evidence.
Approval eligibility is a separate decision, made from that verdict:

    PASS    + fresh evidence             eligible   verification_status "verified"             basis "live"
    PASS    + recorded or mixed evidence eligible   verification_status "verified_on_records"  basis "recorded"
    UNKNOWN (some fact could not be checked)        not eligible
    FAIL    (a confirmed problem)                   not eligible
    no hours or travel evidence at all              not eligible

A recorded-basis approval says so in the pending action's summary, the reply and the dashboard. Every check
(budget, schedule, opening hours, walking, places, coverage) must still pass: only the freshness of the evidence
behind a PASS is relaxed, and only with that disclosure.
"""
from __future__ import annotations

from typing import Any

# The pending-action statuses /api/approve accepts. Anything else is refused (403).
APPROVABLE_STATUSES = frozenset({"verified", "verified_on_records"})

RECORDED_DISCLOSURE = ("Every check passed, but against recorded data (the research listings and the travel data "
                       "cache), not live sources: opening hours, prices and travel times were not confirmed today.")


def approval_eligibility(report: Any, coverage_ok: bool) -> dict[str, Any]:
    """{eligible, verification_status, evidence_basis, basis, disclosure, reason} for the final VerificationReport.

    `report` is planning.verification.VerificationReport (or None when no verification ran)."""
    status = getattr(report, "status", None)
    evidence = getattr(report, "evidence_basis", None)
    out = {"eligible": False, "verification_status": None, "evidence_basis": evidence, "basis": None,
           "verified": getattr(report, "verified", False) is True, "disclosure": None, "reason": None}
    if report is None:
        return {**out, "reason": "The plan was not verified, so it cannot be approved."}
    if not coverage_ok:
        return {**out, "reason": "The plan does not cover the trip's days well enough to be approved."}
    if status == "FAIL":
        return {**out, "reason": "The verifier found problems it could not repair, so the plan cannot be approved."}
    if status != "PASS":
        unknown = [c.check.replace("_", " ") for c in getattr(report, "checks", None) or [] if c.status == "UNKNOWN"]
        what = ", ".join(unknown) if unknown else "some facts"
        return {**out, "reason": f"These checks could not be completed: {what}. The plan cannot be approved as it is "
                                 "(an unknown fact is never treated as a pass)."}
    if evidence == "fresh" and out["verified"]:
        return {**out, "eligible": True, "verification_status": "verified", "basis": "live"}
    if evidence in ("recorded", "mixed"):
        return {**out, "eligible": True, "verification_status": "verified_on_records", "basis": "recorded",
                "disclosure": RECORDED_DISCLOSURE}
    return {**out, "reason": "There is no opening-hours or travel evidence behind this plan, so it cannot be approved."}


# ------------------------------------------------------------------ saving a plan that is not eligible
# A traveller may keep any structurally valid plan the verifier did not make eligible, as their own decision, after
# reading what could not be confirmed. This is never an approval: the pending action above stays the only verified
# path, the verdict is unchanged, and the saved trip carries its status and every limitation with it.
#
#     UNKNOWN (facts missing, no confirmed problem)   mode "accepted_with_limitations"  "Saved · Not Fully Verified"
#     FAIL, or no verification at all                 mode "unverified_draft"           "Saved · Unverified Draft"
# (A PASS without the evidence or coverage approval needs is saved with limitations too.)
ACCEPTANCE_MODES = frozenset({"accepted_with_limitations", "unverified_draft"})

_UNCONFIRMED = {  # the verifier's check -> what the traveller is told could not be confirmed
    "opening_hours": "Opening hours could not be confirmed",
    "travel": "Travel times could not be measured",
    "walking": "Walking distances could not be measured",
    "budget": "The total cost could not be determined",
    "costs": "Some prices are unavailable",
    "required_places": "A place you asked for could not be found in the sources",
    "places": "Some places could not be identified in the sources",
    "schedule": "Parts of the schedule could not be checked",
    "evidence": "Some facts have no source evidence",
}


def _valid_structure(itinerary: Any) -> bool:
    days = itinerary.get("days") if isinstance(itinerary, dict) else None
    return (isinstance(days, list) and bool(days)
            and all(isinstance(d, dict) and d.get("date") for d in days)
            and any(isinstance(d.get("activities"), list) and d["activities"] for d in days))


def _names(itinerary: dict) -> dict[str, str]:
    return {a["place_id"]: str(a.get("name") or a["place_id"]) for d in itinerary.get("days") or []
            for a in d.get("activities") or [] if isinstance(a, dict) and a.get("place_id")}


def acceptance(eligibility: dict | None, itinerary: Any, verification: dict | None,
               budget: dict | None, place_names: dict[str, str] | None = None) -> dict[str, Any] | None:
    """How the traveller may save a plan the approval policy did not make eligible, or None (eligible, or no valid
    plan). `verification` is orchestrator.verification_summary(), `budget` orchestrator.budget_summary(): what is
    listed here comes from them only. Unknown prices stay unknown: the known subtotal is shown apart from them.
    `place_names` (place_id -> name, from the session's research) names the places findings refer to: the itinerary
    sent to the Trip Store carries no place_id."""
    if eligibility is None or eligibility.get("eligible") or not _valid_structure(itinerary):
        return None
    status = (verification or {}).get("status")
    mode = "unverified_draft" if status == "FAIL" or verification is None else "accepted_with_limitations"
    names = {**(place_names or {}), **_names(itinerary)}
    findings = (verification or {}).get("findings") or []
    b = budget or {}
    unpriced = [str(n) for n in b.get("unknown_price_items") or []]

    def where(f: dict) -> str:
        bits = [names.get(f.get("place_id"), f.get("place_id")) if f.get("place_id") else None, f.get("date")]
        return ", ".join(b for b in bits if b)

    problems = list(dict.fromkeys(f["explanation"] for f in findings
                                  if f.get("state") == "confirmed_problem" and f.get("explanation")))
    unconfirmed: dict[str, list[str]] = {}
    for f in findings:
        if f.get("state") == "unverifiable" and not (f.get("check") == "costs" and unpriced):  # listed once, below
            places = unconfirmed.setdefault(_UNCONFIRMED.get(f.get("check"), "Some facts could not be confirmed"), [])
            if where(f) and where(f) not in places:
                places.append(where(f))
    limitations = [f"{what}" + (f": {'; '.join(at[:6])}" + (f"; and {len(at) - 6} more" if len(at) > 6 else "")
                                if at else ".") for what, at in unconfirmed.items()]
    if verification is None:
        limitations.append("This plan was not verified: none of its facts were checked.")

    costs = {"currency": b.get("currency") or itinerary.get("currency"),
             "known_subtotal": b.get("planned_known_total"), "budget_total": b.get("budget_total"),
             "unpriced_items": unpriced, "not_included": list(b.get("not_included") or []),
             "budget_guaranteed": False}
    if unpriced:
        limitations.append(f"Price unavailable for {len(unpriced)} planned item(s): " + ", ".join(unpriced[:8])
                           + (" and others" if len(unpriced) > 8 else "")
                           + ". They are not counted in the known subtotal, so the final budget cannot be guaranteed.")
    label = "Saved · Not Fully Verified" if mode == "accepted_with_limitations" else "Saved · Unverified Draft"
    return {"mode": mode, "label": label, "verification_status": status, "verified": False,
            "evidence_basis": (verification or {}).get("evidence_basis"), "limitations": limitations,
            "confirmed_problems": problems, "costs": costs,
            "reason": eligibility.get("reason")}
