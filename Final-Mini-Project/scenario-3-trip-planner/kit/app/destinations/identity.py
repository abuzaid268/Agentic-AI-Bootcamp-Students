"""The destination's geographic identity in a trip request, and the server's checks of it.

The trip form sends `trip.destination` as text (CONTRACT, unchanged) and, from a client that has it, the place the
traveller chose in the destination box as `trip.place`: GeoNames id, name, region, country, ISO country code and
coordinates (the same record GET /api/destinations returned). Older clients and saved requests send no place and
are planned as before.

The server never trusts the browser alone (check_destination):
- a place must be a city with a GeoNames id, a known ISO country code and real coordinates, and its name cannot be
  its own country's name (a country sent as a "city");
- the destination text must name that place (its label, "name, country" or its name): the text and the
  coordinates can never describe two different places;
- without a place, a destination that is only a country's name ("Italy") is refused with a request for a city,
  unless a city of that name is a known destination (Singapore, Monaco, Luxembourg).
Nothing here calls a provider: the checks use the bundled GeoNames data (areas.py, popular_destinations.json).
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.destinations.areas import area_matches, country_name, fold


class DestinationPlace(BaseModel):
    """The chosen city, as GET /api/destinations returned it."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=r"^geonames:[1-9][0-9]{0,9}$", description="GeoNames id, e.g. geonames:2988507")
    kind: Literal["city"] = "city"  # Rihla plans a city: a country or a region is not a place here
    name: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    country_code: str = Field(pattern=r"^[A-Za-z]{2}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = Field(min_length=2, max_length=200)

    @field_validator("country_code")
    @classmethod
    def _known_country(cls, code: str) -> str:
        code = code.upper()
        if country_name(code) is None:
            raise ValueError(f"{code} is not a known ISO country code.")
        return code

    @field_validator("latitude", "longitude")
    @classmethod
    def _real_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Coordinates must be real numbers.")
        return value


@lru_cache(maxsize=1)
def _popular_city_names() -> frozenset[tuple[str, str]]:
    """(folded name, country code) of the bundled popular destinations: real cities of those names."""
    from app.destinations.service import load_popular  # here: service imports this package's other modules
    return frozenset((fold(p["name"]), p["country_code"]) for p in load_popular())


def _is_known_city(name: str, code: str | None = None) -> bool:
    return any(n == fold(name) and (code is None or c == code) for n, c in _popular_city_names())


def _suggestion(code: str) -> str:
    from app.destinations.service import load_popular
    cities = sorted((p for p in load_popular() if p["country_code"] == code), key=lambda p: -(p["population"] or 0))
    return f", for example {cities[0]['name']}" if cities else ""


def destination_texts(place: DestinationPlace) -> set[str]:
    """The texts that name this place (folded): what the destination box puts in the form for it."""
    texts = {place.label, f"{place.name}, {place.country}", place.name}
    if place.region:
        texts.add(f"{place.name}, {place.region}, {place.country}")
    return {fold(t) for t in texts}


def research_destination(destination: str, place: DestinationPlace | None) -> str:
    """The text the research uses: the chosen place's full label ("Paris, Texas, United States") when the form
    named it more briefly ("Paris"), so the travel sources look up that place and not a namesake. The same place
    (check_destination has made sure of it), only named precisely; within the form's 100 characters."""
    if place is not None and fold(destination) != fold(place.label) and len(place.label) <= 100:
        return place.label
    return destination


def check_destination(destination: str, place: DestinationPlace | None) -> None:
    """Raise ValueError (a 422 for the trip form) when the destination is not a city the trip can be planned for."""
    if place is not None:
        if fold(place.name) == fold(country_name(place.country_code) or "") and not _is_known_city(
                place.name, place.country_code):
            raise ValueError(f"{place.name} is a country. Choose a city in {place.name}"
                             f"{_suggestion(place.country_code)}.")
        if fold(destination) not in destination_texts(place):
            raise ValueError(f"The destination '{destination}' does not match the chosen place ({place.label}). "
                             "Choose the destination again.")
        return
    if "," in destination:  # qualified text ("Paris, Texas"): the country or region already narrows it
        return
    areas = area_matches(destination)
    countries = [a for a in areas if a["kind"] == "country"]
    if countries and not _is_known_city(destination):
        name, code = countries[0]["name"], countries[0]["country_code"]
        regions = [a["country"] for a in areas if a["kind"] == "region"]
        also = f" (and a region in {', '.join(regions)})" if regions else ""
        raise ValueError(f"{name} is a country{also}. Choose a city in {name}{_suggestion(code)}, or the city you "
                         "mean from the destination suggestions.")
