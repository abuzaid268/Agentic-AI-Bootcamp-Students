"""Indoor or outdoor, from a researched place's own listing: for the WHAT IF rain scenario.

Evidence only: the research's interest tags and the listing's own words (its name, then its description). A place
with evidence both ways, or none, is "unclear" and is never moved on a guess; the caller says so. Restaurants and
cafes count as indoor (a meal is not moved for rain).
"""
from __future__ import annotations

import re
from typing import Literal

from .research import ResearchedPlace

Setting = Literal["indoor", "outdoor", "unclear"]

OUTDOOR_TAGS = {"nature", "views", "adventure"}
INDOOR_TAGS = {"museum", "art"}
OUTDOOR_WORDS = re.compile(
    r"open[- ]air|outdoor|\bruins?\b|citadel|hippodrome|amphitheat|\broman theat|\bsquare\b|promenade|beach|"
    r"\bpark\b|gardens?\b|cruise|\bboat\b|ferry|walking tour|viewpoint|lookout|\bhik(e|ing)\b|\btrail\b|"
    r"cable car|rooftop|\bzoo\b|\bforum\b|aqueduct|city walls|\bhill\b|\bvalley\b|\bwadi\b", re.IGNORECASE)
INDOOR_WORDS = re.compile(
    r"museum|gallery|galleries|mosque|church|cathedral|synagogue|chapel|basilica|cistern|hamm?am|turkish bath|"
    r"\bpalace\b|covered|grand bazaar|\bmall\b|department store|aquarium|cinema|indoor|library|food hall|"
    r"\btheatre\b(?!.*(roman|ancient))|opera house|concert hall|planetarium", re.IGNORECASE)


def _evidence(text: str, tags: set[str]) -> tuple[bool, bool]:
    return (bool(tags & INDOOR_TAGS) or bool(INDOOR_WORDS.search(text)),
            bool(tags & OUTDOOR_TAGS) or bool(OUTDOOR_WORDS.search(text)))


def setting(place: ResearchedPlace) -> Setting:
    if place.category == "restaurant" or place.kind in ("eat", "drink"):
        return "indoor"
    tags = set(place.tags)
    indoor, outdoor = _evidence(place.name, tags)
    if indoor != outdoor:
        return "indoor" if indoor else "outdoor"
    name_only = _evidence(place.name, set())
    if name_only[0] != name_only[1]:  # the place's own name settles a tie between its tags
        return "indoor" if name_only[0] else "outdoor"
    if not indoor and not outdoor and place.description:
        indoor, outdoor = _evidence(place.description, set())
        if indoor != outdoor:
            return "indoor" if indoor else "outdoor"
    return "unclear"
