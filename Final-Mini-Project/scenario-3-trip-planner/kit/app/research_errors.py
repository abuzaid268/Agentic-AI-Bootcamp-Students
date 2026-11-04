"""What the traveller is told when the attractions source returned nothing for their destination.

The reason decides the advice. A recorded-data server cannot cover a city it never recorded, so "try again in a
few minutes" would be wrong advice for it; a guide that does not exist will not appear on a retry either; only a
failed or slow source is worth retrying. No plan is made in any of these cases, and nothing is filled in.
"""
from __future__ import annotations

NO_PLAN = "I did not make a plan, so nothing was proposed or saved."

# The travel API's error codes (services/travel_data.py, services/travel_mcp.py) and what they mean here.
_REASONS = {
    "not_cached": ("this server uses recorded travel data (replay mode), which does not include {destination}",
                   "Choose one of the recorded cities, or ask the team to run the travel data in live mode."),
    "no_guide": ("the travel guide (Wikivoyage) has no page about {destination}, and a different place of the "
                 "same name is never used instead", "Choose a nearby larger city."),
    "place_not_found": ("{destination} could not be located", "Check the destination, or choose it again from "
                        "the suggestions."),
    "page_not_found": ("the travel guide (Wikivoyage) has no page about {destination}",
                       "Choose a nearby larger city."),
}
_RETRY = "Please try again in a few minutes."


def attraction_failure_message(destination: str, failure) -> str:
    """The message for a failed find_attractions call (`failure`: planning.research.ToolFailure)."""
    code = str(getattr(failure, "code", "") or "unknown")
    if code in _REASONS:
        reason, advice = _REASONS[code]
        return f"I could not load attractions for {destination}: {reason.format(destination=destination)}. " \
               f"{NO_PLAN} {advice}"
    return (f"I could not load attractions for {destination}: the attractions source is unavailable right now "
            f"({code}). {NO_PLAN} {_RETRY}")
