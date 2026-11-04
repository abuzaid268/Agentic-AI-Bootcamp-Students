"""Rebuild app/destinations/data/areas.json: the world's countries and first-level regions (states, provinces,
governorates), so a destination box and the server can tell "Italy" (a country) or "Texas" (a state) from a city.
Run by hand to refresh:

    python -m app.destinations.build_areas --source <folder with countryInfo.txt and admin1CodesASCII.txt>

Both files are GeoNames' own exports (https://download.geonames.org/export/dump/, CC BY 4.0, no key, no cost). This
script never downloads anything itself. It keeps, for each country, its ISO code and English name, and for each
region its English name, its country and its GeoNames id; nothing else, and nothing typed in by hand.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from .areas import AREAS_PATH, SOURCE


def read_countries(path: Path) -> list[dict]:
    countries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) > 4 and len(cols[0]) == 2 and cols[4].strip():
            countries.append({"code": cols[0].upper(), "name": cols[4].strip()})
    return sorted(countries, key=lambda c: c["code"])


def read_regions(path: Path, country_codes: set[str]) -> list[dict]:
    regions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) < 4 or "." not in cols[0]:
            continue
        code = cols[0].split(".", 1)[0].upper()
        name = cols[1].strip()
        if code in country_codes and name and cols[3].strip().isdigit():
            regions.append({"name": name, "country_code": code, "id": int(cols[3])})
    return sorted(regions, key=lambda r: r["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="folder with the two GeoNames files")
    args = parser.parse_args()
    countries = read_countries(args.source / "countryInfo.txt")
    regions = read_regions(args.source / "admin1CodesASCII.txt", {c["code"] for c in countries})
    AREAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AREAS_PATH.write_text(json.dumps({
        "source": dict(SOURCE),
        "built": dt.date.today().isoformat(),
        "builder": "python -m app.destinations.build_areas --source <GeoNames export folder>",
        "countries": countries,
        "regions": regions,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(countries)} countries and {len(regions)} regions written to {AREAS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
