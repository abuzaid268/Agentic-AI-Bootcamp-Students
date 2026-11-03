"""Rebuild app/airports/data/airports.csv from OurAirports' open data (public domain). Run by hand to refresh:

    python -m app.airports.build_dataset --source <folder with airports.csv, countries.csv and regions.csv>

The three files are at https://davidmegginson.github.io/ourairports-data/ (no key, no cost). This script never
downloads anything itself. It keeps large and medium airports, and small airports with an IATA code or scheduled
service; it adds country and region names, drops rows normalize_airport rejects, cleans invalid codes and gives
a code shared by several airports to the most likely one only. Output is sorted by id, so a refresh diffs cleanly.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from .service import DATA_PATH, META_PATH, SOURCE, normalize_airport, resolve_duplicate_codes

OUTPUT_COLUMNS = ["id", "ident", "type", "name", "latitude_deg", "longitude_deg", "iso_country", "country_name",
                  "iso_region", "region_name", "municipality", "scheduled_service", "icao_code", "iata_code",
                  "keywords"]
MAX_KEYWORDS = 300


def keep_row(row: dict) -> bool:
    """The airports a traveller can plausibly fly from or to."""
    kind = (row.get("type") or "").strip()
    if kind in ("large_airport", "medium_airport"):
        return True
    return kind == "small_airport" and bool((row.get("iata_code") or "").strip()
                                            or (row.get("scheduled_service") or "").strip() == "yes")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build(source: Path, output: Path = DATA_PATH, meta_output: Path = META_PATH,
          today: dt.date | None = None) -> dict:
    countries = {r["code"]: r["name"] for r in _read(source / "countries.csv") if r.get("code")}
    regions = {r["code"]: r["name"] for r in _read(source / "regions.csv") if r.get("code")}
    rows, airports, skipped = {}, [], Counter()
    for row in _read(source / "airports.csv"):
        if not keep_row(row):
            skipped["not a passenger airport type"] += 1
            continue
        row = {**row, "country_name": countries.get(row.get("iso_country", "")),
               "region_name": regions.get(row.get("iso_region", ""))}
        airport = normalize_airport(row)
        if airport is None:
            skipped["malformed"] += 1
            continue
        rows[airport["id"]] = row
        airports.append(airport)

    resolved = resolve_duplicate_codes(airports)
    skipped["duplicate id"] = len(airports) - len(resolved)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for airport in sorted(resolved, key=lambda a: int(a["id"].split(":")[1])):
            row = rows[airport["id"]]
            writer.writerow({
                **{column: (row.get(column) or "").strip() for column in OUTPUT_COLUMNS},
                "latitude_deg": "" if airport["latitude"] is None else airport["latitude"],
                "longitude_deg": "" if airport["longitude"] is None else airport["longitude"],
                "iata_code": airport["iata"] or "",
                "icao_code": airport["icao"] or "",
                "keywords": (row.get("keywords") or "").strip()[:MAX_KEYWORDS],
            })

    meta = {
        **SOURCE,
        "files": "https://davidmegginson.github.io/ourairports-data/ (airports.csv, countries.csv, regions.csv)",
        "built": (today or dt.date.today()).isoformat(),
        "airports": len(resolved),
        "with_iata": sum(1 for a in resolved if a["iata"]),
        "with_scheduled_service": sum(1 for a in resolved if a["scheduled_service"]),
        "by_type": dict(Counter(a["type"] for a in resolved)),
        "skipped": {k: v for k, v in skipped.items() if v},
    }
    meta_output.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="folder with the three OurAirports CSV files")
    print(json.dumps(build(parser.parse_args().source), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
