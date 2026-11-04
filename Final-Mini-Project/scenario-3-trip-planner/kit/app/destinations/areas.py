"""Countries and first-level regions of the world (data/areas.json, GeoNames, CC BY 4.0; built by build_areas.py).

Rihla plans a trip to a city. These names let the destination box and the server tell a country ("Italy") or a
state, province or governorate ("Texas", "Georgia") from a city, without calling any provider:

    area_matches("Georgia") -> [{"kind": "country", "name": "Georgia", "country_code": "GE", ...},
                                {"kind": "region", "name": "Georgia", "country_code": "US", ...}]

Only a whole name counts (case and accents ignored): "Ital" or "Italy, Texas" match nothing. Many regions share
their name with their main city ("Tokyo", "Amman", "Madrid"), so a region match alone is never a reason to refuse a
destination: it is a reason to ask the traveller which place they mean.
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

AREAS_PATH = Path(__file__).parent / "data" / "areas.json"
SOURCE = {
    "provider": "GeoNames (countryInfo.txt, admin1CodesASCII.txt)",
    "url": "https://download.geonames.org/export/dump/",
    "licence": "CC BY 4.0",
    "attribution": "Country and region names from GeoNames (geonames.org), CC BY 4.0",
}


def fold(text: str) -> str:
    """Case- and accent-insensitive form, spaces collapsed ("  São  Paulo" == "sao paulo")."""
    text = " ".join(unicodedata.normalize("NFC", str(text or "")).split())
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _index(path: Path = AREAS_PATH) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """(folded name -> areas with that name, country code -> country name). Empty when the file is missing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    countries = {c["code"]: c["name"] for c in data.get("countries") or [] if c.get("code") and c.get("name")}
    by_name: dict[str, list[dict]] = {}
    for code, name in countries.items():
        by_name.setdefault(fold(name), []).append(
            {"kind": "country", "name": name, "country_code": code, "country": name})
    for region in data.get("regions") or []:
        code, name = region.get("country_code"), region.get("name")
        if code in countries and name:
            by_name.setdefault(fold(name), []).append({"kind": "region", "name": name, "country_code": code,
                                                       "country": countries[code], "id": region.get("id")})
    return by_name, countries


def area_matches(text: str, extra_country_names: dict[str, str] | None = None) -> list[dict]:
    """The countries and regions whose whole name is `text`: countries first, then regions by country name.
    `extra_country_names` adds other spellings of a country (name -> ISO code), such as the provider's own."""
    by_name, countries = _index()
    wanted = fold(text)
    if not wanted:
        return []
    found = list(by_name.get(wanted, []))
    for name, code in (extra_country_names or {}).items():
        if fold(name) == wanted and code in countries and not any(
                a["kind"] == "country" and a["country_code"] == code for a in found):
            found.append({"kind": "country", "name": countries[code], "country_code": code, "country": countries[code]})
    return sorted(found, key=lambda a: (a["kind"] != "country", fold(a["country"]), fold(a["name"])))


def country_name(code: str) -> str | None:
    """The English name of an ISO 3166-1 alpha-2 country code, or None."""
    return _index()[1].get(str(code or "").upper())


def countries_named(text: str, extra_country_names: dict[str, str] | None = None) -> list[dict]:
    """Only the countries among area_matches(text)."""
    return [a for a in area_matches(text, extra_country_names) if a["kind"] == "country"]
