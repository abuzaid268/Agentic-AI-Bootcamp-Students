"""Airport search for the trip form's departure and arrival boxes (search as you type).

Data: OurAirports (https://ourairports.com/data/), public domain, bundled as app/airports/data/airports.csv and
rebuilt by hand with app/airports/build_dataset.py. Nothing is fetched at search time, so search needs no key,
no network and no rate limit.

The bundle keeps large and medium airports, and small airports that have an IATA code or scheduled service;
heliports, seaplane bases, balloon ports and closed airports are left out. `scheduled_service` is OurAirports'
flag, kept as data: it is a ranking hint, not a promise that an airline flies there today.

Matching: every word of the query must start a word of the airport's name, city, region, country, alternative
names, IATA or ICAO code. An exact IATA or ICAO code ranks first, then a city or name that starts with the
query, then airports with scheduled service and larger airports. Malformed rows in the data are skipped, never
repaired; an airport without an IATA code is kept with `iata: null`.
"""
from __future__ import annotations

import csv
import json
import math
import re
import threading
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

DATA_DIR = Path(__file__).with_name("data")
DATA_PATH = DATA_DIR / "airports.csv"
META_PATH = DATA_DIR / "airports.meta.json"
SOURCE = {
    "provider": "OurAirports",
    "url": "https://ourairports.com/data/",
    "licence": "Public domain",
    "attribution": "Airport data from OurAirports (ourairports.com), released to the public domain.",
}

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 80
DEFAULT_LIMIT = 8
MAX_LIMIT = 10

AIRPORT_TYPES = ("large_airport", "medium_airport", "small_airport")
REQUIRED_COLUMNS = {"id", "type", "name", "latitude_deg", "longitude_deg", "iso_country", "municipality",
                    "scheduled_service", "icao_code", "iata_code"}
_TYPE_WEIGHT = {"large_airport": 40, "medium_airport": 20, "small_airport": 0}
_WORD = re.compile(r"\w+")


class AirportError(Exception):
    """A search that could not be answered: an HTTP status, a stable code, a message for the traveller."""

    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.status, self.code, self.message, self.retryable = status, code, message, retryable

    def as_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "retryable": self.retryable}}


def normalize_query(raw: Any) -> str:
    """The query as searched: Unicode NFC, whitespace collapsed. Raises AirportError(422) when unusable."""
    if not isinstance(raw, str) or not raw.strip():
        raise AirportError(422, "missing_query", "Type at least 2 letters of an airport, a city or a code.")
    text = " ".join(unicodedata.normalize("NFC", raw).split())
    if any(unicodedata.category(ch) == "Cc" for ch in text):
        raise AirportError(422, "invalid_query", "The search text contains characters that are not allowed.")
    if not any(ch.isalpha() for ch in text):
        raise AirportError(422, "invalid_query", "Type an airport, a city or a code (letters, not only numbers "
                                                 "or symbols).")
    if len(text) < MIN_QUERY_LENGTH:
        raise AirportError(422, "query_too_short", "Type at least 2 letters of an airport, a city or a code.")
    if len(text) > MAX_QUERY_LENGTH:
        raise AirportError(422, "query_too_long", f"The search text is limited to {MAX_QUERY_LENGTH} characters.")
    return text


def normalize_country(raw: Any) -> str | None:
    """An optional ISO 3166-1 alpha-2 country filter ("jo" -> "JO"), or None. Raises AirportError(422) if malformed."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    text = raw.strip().upper() if isinstance(raw, str) else ""
    if not re.fullmatch(r"[A-Z]{2}", text):
        raise AirportError(422, "invalid_country", "The country must be a 2-letter code, such as JO.")
    return text


# ------------------------------------------------------------------ nearby airports (GET /api/airports/near)
# Only airports a traveller can fly from are offered: an IATA code (flight search needs one), coordinates, and
# OurAirports' scheduled-service flag. That flag is data, not a promise that an airline flies there today or that a
# route exists: nothing here says which routes are served.
NEAR_DEFAULT_KM = 150  # how far from the place an airport in the place's own country is still listed
NEAR_MAX_KM = 500
NEAR_OTHER_COUNTRY_KM = 80  # an airport across a border is listed only this close, and always marked as such
NEAR_DEFAULT_LIMIT = 6
NEAR_MAX_LIMIT = 10
# "Exactly one clearly valid candidate": the only airport within these distances of the place, in its own country,
# and close enough to be that city's airport. Anything else is left to the traveller.
SOLE_CANDIDATE_KM = 60  # how close the one airport must be
SOLE_WINDOW_KM = 100  # ...and no other airport in the same country within this distance
RANKING_NOTE = ("Ranked by straight-line distance only. The nearest airport is not always the best one for your "
                "route: check which airports have the flights you need.")


def normalize_coordinates(lat: Any, lon: Any) -> tuple[float, float]:
    """A latitude and longitude as numbers in range, or AirportError(422). Booleans, NaN, infinity and text that is
    not a plain number are refused, never coerced."""
    if lat is None or lon is None or (isinstance(lat, str) and not lat.strip()) or (isinstance(lon, str) and not lon.strip()):
        raise AirportError(422, "missing_coordinates", "Give the place's latitude and longitude.")
    values = []
    for raw, bound, name in ((lat, 90.0, "latitude"), (lon, 180.0, "longitude")):
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise AirportError(422, "invalid_coordinates", f"The {name} must be a number.")
        try:
            number = float(raw.strip() if isinstance(raw, str) else raw)
        except ValueError:
            raise AirportError(422, "invalid_coordinates", f"The {name} must be a number.") from None
        if not math.isfinite(number) or abs(number) > bound:
            raise AirportError(422, "invalid_coordinates", f"The {name} must be between -{bound:g} and {bound:g}.")
        values.append(number)
    return values[0], values[1]


def _bounded_number(raw: Any, default: float, low: float, high: float, code: str, what: str) -> float:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return default
    try:
        number = float(raw.strip() if isinstance(raw, str) else raw)
    except (TypeError, ValueError):
        number = math.nan
    if isinstance(raw, bool) or not math.isfinite(number) or not low <= number <= high:
        raise AirportError(422, code, f"{what} must be a number from {low:g} to {high:g}.")
    return number


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(a)))


def _fold(text: str) -> str:
    """Case- and accent-insensitive form, to compare names ("Zürich" == "zurich")."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def _words(text: str | None) -> list[str]:
    return _WORD.findall(_fold(text)) if text else []


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _code(value: Any, pattern: str) -> str | None:
    text = _text(value)
    return text.upper() if text and re.fullmatch(pattern, text.upper()) else None


def _coordinate(value: Any, bound: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and -bound <= number <= bound else None


def _city(value: Any) -> str | None:
    """OurAirports' municipality, with a repeated part dropped ("Luton, Luton" -> "Luton")."""
    parts: list[str] = []
    for part in (_text(value) or "").split(","):
        part = part.strip()
        if part and (not parts or _fold(part) != _fold(parts[-1])):
            parts.append(part)
    return ", ".join(parts) or None


def _region(value: Any) -> str | None:
    name = _text(value)
    return None if not name or name.startswith("(") else name  # "(unassigned)"


def normalize_airport(row: Any) -> dict | None:
    """One OurAirports row (with country_name and region_name added) as Rihla's airport, or None when it is not a
    usable airport. Invalid codes and coordinates become null; a row without id, name or airport type is dropped."""
    if not isinstance(row, Mapping):
        return None
    kind = _text(row.get("type"))
    name = _text(row.get("name"))
    try:
        pid = int(str(row.get("id", "")).strip())
    except ValueError:
        return None
    if kind not in AIRPORT_TYPES or not name or pid <= 0:
        return None
    lat, lon = _coordinate(row.get("latitude_deg"), 90), _coordinate(row.get("longitude_deg"), 180)
    if lat is None or lon is None or (lat == 0 and lon == 0):
        lat = lon = None
    iata, icao = _code(row.get("iata_code"), r"[A-Z]{3}"), _code(row.get("icao_code"), r"[A-Z]{4}")
    city, country = _city(row.get("municipality")), _text(row.get("country_name"))
    code = iata or icao
    return {
        "id": f"ourairports:{pid}",
        "name": name,
        "city": city,
        "region": _region(row.get("region_name")),
        "country": country,
        "country_code": _code(row.get("iso_country"), r"[A-Z]{2}"),
        "iata": iata,
        "icao": icao,
        "latitude": round(lat, 5) if lat is not None else None,
        "longitude": round(lon, 5) if lon is not None else None,
        "type": kind,
        "scheduled_service": _text(row.get("scheduled_service")) == "yes",
        "label": ", ".join(part for part in (f"{name} ({code})" if code else name, city, country) if part),
    }


def quality(airport: Mapping) -> int:
    """How likely a traveller means this airport, other things equal: scheduled service, size, an IATA code."""
    return (200 if airport.get("scheduled_service") else 0) + _TYPE_WEIGHT.get(airport.get("type"), 0) \
        + (15 if airport.get("iata") else 0)


def resolve_duplicate_codes(airports: Iterable[dict]) -> list[dict]:
    """IATA and ICAO codes are unique: when the data gives one to several airports, the most likely airport keeps
    it and the others get null (never a guessed code). Duplicate ids keep their first row."""
    ordered = sorted(airports, key=lambda a: -quality(a))
    seen_ids: set[str] = set()
    taken: dict[str, set[str]] = {"iata": set(), "icao": set()}
    kept = []
    for airport in ordered:
        if airport["id"] in seen_ids:
            continue
        seen_ids.add(airport["id"])
        changed = dict(airport)
        for field in ("iata", "icao"):
            if changed[field] and changed[field] in taken[field]:
                changed[field] = None
            elif changed[field]:
                taken[field].add(changed[field])
        if changed != airport:
            code = changed["iata"] or changed["icao"]
            changed["label"] = ", ".join(part for part in (
                f"{changed['name']} ({code})" if code else changed["name"], changed["city"], changed["country"])
                if part)
        kept.append(changed)
    return kept


@dataclass(frozen=True)
class _Entry:
    airport: dict
    words: frozenset[str]
    name: str
    city: str
    country: str
    city_key: str
    quality: int


def _entry(airport: dict, keywords: str | None) -> _Entry:
    name, city, country = _words(airport["name"]), _words(airport["city"]), _words(airport["country"])
    words = set(name) | set(city) | set(country) | set(_words(airport["region"])) | set(_words(keywords))
    words |= {code.lower() for code in (airport["iata"], airport["icao"]) if code}
    # "Paris (Roissy-en-France, Val-d'Oise)" and "London, Essex" are in the city "Paris" / "London".
    first_city_part = _words(re.split(r"[,(]", airport["city"] or "")[0])
    return _Entry(airport, frozenset(words), " ".join(name), " ".join(city), " ".join(country),
                  " ".join(first_city_part), quality(airport))


def _score(entry: _Entry, query: str, tokens: list[str]) -> int | None:
    if not all(any(word.startswith(token) for word in entry.words) for token in tokens):
        return None
    airport, score = entry.airport, entry.quality
    if airport["iata"] and airport["iata"].lower() == query:
        score += 1000
    elif airport["icao"] and airport["icao"].lower() == query:
        score += 900
    # Only the strongest text match counts, so a small field named "Paris Airport" in Paris, Texas does not
    # outrank Paris-Charles de Gaulle just because the query matches both its city and its name.
    score += max(
        400 if entry.city_key == query or entry.city == query else 200 if entry.city.startswith(query) else 0,
        300 if entry.name.startswith(query) else 120 if f" {query}" in f" {entry.name}" else 0,
        300 if entry.country == query else 0,
    )
    return score


def read_airports(path: Path) -> tuple[list[dict], dict[str, str], int]:
    """The airports in a bundled CSV, their search keywords by id, and the number of rows skipped as malformed."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"airport data is missing columns: {sorted(missing)}")
        airports, keywords, skipped = [], {}, 0
        for row in reader:
            airport = normalize_airport(row)
            if airport is None:
                skipped += 1
                continue
            airports.append(airport)
            if _text(row.get("keywords")):
                keywords[airport["id"]] = row["keywords"]
    return airports, keywords, skipped


class AirportSearch:
    """Searches the bundled airport data, loaded once on first use. Thread-safe."""

    def __init__(self, *, data_path: Path | str | None = None, meta_path: Path | str | None = None,
                 cache_entries: int = 512):
        self.data_path = Path(data_path) if data_path else DATA_PATH
        self.meta_path = Path(meta_path) if meta_path else (META_PATH if data_path is None else None)
        self._entries: list[_Entry] | None = None
        self._by_prefix: dict[str, list[int]] = {}
        self._source = dict(SOURCE)
        self.skipped_rows = 0
        self._cache: OrderedDict[tuple, list[dict]] = OrderedDict()
        self._cache_entries = cache_entries
        self._lock = threading.Lock()

    def _load(self) -> list[_Entry]:
        with self._lock:
            if self._entries is not None:
                return self._entries
            try:
                airports, keywords, skipped = read_airports(self.data_path)
            except (OSError, ValueError, csv.Error) as exc:
                raise AirportError(503, "data_unavailable", "Airport search is not available on this server "
                                   "right now.") from exc
            if not airports:
                raise AirportError(503, "data_unavailable", "Airport search is not available on this server "
                                   "right now.")
            entries = [_entry(a, keywords.get(a["id"])) for a in resolve_duplicate_codes(airports)]
            by_prefix: dict[str, list[int]] = {}
            for index, entry in enumerate(entries):
                for prefix in {word[:2] for word in entry.words if len(word) >= 2}:
                    by_prefix.setdefault(prefix, []).append(index)
            self._by_prefix, self.skipped_rows = by_prefix, skipped
            self._source.update(self._read_meta())
            self._entries = entries
            return entries

    def _read_meta(self) -> dict:
        try:
            meta = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path else {}
        except (OSError, ValueError):
            return {}
        return {"data_date": meta["built"]} if isinstance(meta, dict) and isinstance(meta.get("built"), str) else {}

    def _candidates(self, tokens: list[str], count: int) -> Iterable[int]:
        long_tokens = [t for t in tokens if len(t) >= 2]
        if not long_tokens:
            return range(count)
        lists = sorted((self._by_prefix.get(t[:2], []) for t in long_tokens), key=len)
        return lists[0]

    def countries(self) -> dict:
        """The countries that have an airport in the bundled data, by name: for a departure country picker."""
        entries = self._load()
        found: dict[str, dict] = {}
        for entry in entries:
            code, name = entry.airport["country_code"], entry.airport["country"]
            if code and name:
                item = found.setdefault(code, {"code": code, "name": name, "airports": 0})
                item["airports"] += 1
        countries = sorted(found.values(), key=lambda c: (_fold(c["name"]), c["code"]))
        return {"count": len(countries), "countries": countries, "source": dict(self._source)}

    def nearest(self, lat: Any, lon: Any, *, country: Any = None, max_km: Any = None, limit: Any = None) -> dict:
        """The airports near a place (its coordinates and, when known, its ISO country code), nearest first.

        Never mixes countries up: with a `country`, airports in that country are listed up to `max_km` away and
        airports across a border only when within NEAR_OTHER_COUNTRY_KM, each marked `in_country`. Without one,
        `in_country` is null and nothing is suggested. `suggested` is the id of the one airport that can be
        preselected, or null: see SOLE_CANDIDATE_KM. An empty list is an honest answer (no airport with scheduled
        service within reach), never filled in with farther or same-named airports.
        """
        latitude, longitude = normalize_coordinates(lat, lon)
        code = normalize_country(country)
        reach = _bounded_number(max_km, NEAR_DEFAULT_KM, 1, NEAR_MAX_KM, "invalid_distance", "The distance")
        count = int(_bounded_number(limit, NEAR_DEFAULT_LIMIT, 1, NEAR_MAX_LIMIT, "invalid_limit", "The limit"))
        entries = self._load()
        country_name = None
        if code:
            country_name = next((e.airport["country"] for e in entries if e.airport["country_code"] == code), None)
            if country_name is None:
                raise AirportError(422, "unknown_country", f"No airports are listed for the country code {code}.")
        across = min(reach, NEAR_OTHER_COUNTRY_KM)
        scan = max(reach, SOLE_WINDOW_KM)  # the suggestion never depends on how far the caller asked to look
        nearby = []
        for entry in entries:
            airport = entry.airport
            if not (airport["iata"] and airport["scheduled_service"] and airport["latitude"] is not None):
                continue
            km = distance_km(latitude, longitude, airport["latitude"], airport["longitude"])
            if km <= scan:
                inside = None if code is None else airport["country_code"] == code
                nearby.append((round(km, 1), airport["iata"], airport["id"], airport, inside))
        nearby.sort(key=lambda item: (item[0], item[1], item[2]))
        shown = [item for item in nearby if item[0] <= (across if item[4] is False else reach)]
        airports = [{**airport, "distance_km": km, "in_country": inside}
                    for km, _, _, airport, inside in shown[:count]]
        suggested = None
        if code:
            same = [item for item in nearby if item[4] and item[0] <= SOLE_WINDOW_KM]
            across_near = [item for item in nearby if item[4] is False and item[0] <= NEAR_OTHER_COUNTRY_KM]
            if len(same) == 1 and not across_near and same[0][0] <= SOLE_CANDIDATE_KM:
                suggested = same[0][3]["id"]
        return {
            "point": {"latitude": latitude, "longitude": longitude},
            "country": {"code": code, "name": country_name} if code else None,
            "max_km": reach,
            "other_country_km": across if code else None,
            "count": len(airports),
            "airports": airports,
            "suggested": suggested,
            "note": RANKING_NOTE,
            "source": dict(self._source),
        }

    def search(self, raw_query: Any, *, limit: int = DEFAULT_LIMIT, scheduled_only: bool = False,
               country: Any = None) -> dict:
        query = normalize_query(raw_query)
        country = normalize_country(country)
        limit = max(1, min(MAX_LIMIT, int(limit)))
        entries = self._load()
        tokens = _words(query)
        folded = " ".join(tokens)
        key = (folded, limit, bool(scheduled_only), country)
        with self._lock:
            found = self._cache.get(key)
            if found is not None:
                self._cache.move_to_end(key)
        if found is None:
            ranked = []
            for index in self._candidates(tokens, len(entries)):
                entry = entries[index]
                if scheduled_only and not entry.airport["scheduled_service"]:
                    continue
                if country and entry.airport["country_code"] != country:
                    continue
                score = _score(entry, folded, tokens) if tokens else None
                if score is not None:
                    ranked.append((-score, entry.airport["name"], entry.airport["id"], index))
            ranked.sort()
            found = [index for *_, index in ranked[:limit]]
            with self._lock:
                self._cache[key] = found
                while len(self._cache) > self._cache_entries:
                    self._cache.popitem(last=False)
            cached = False
        else:
            cached = True
        return self._answer(query, [entries[i] for i in found], cached)

    def _answer(self, query: str, entries: list[_Entry], cached: bool) -> dict:
        # The same city name in another country or region ("London", England or Ontario): show where each one is.
        places: dict[str, set] = {}
        for entry in entries:
            if entry.city_key:
                places.setdefault(entry.city_key, set()).add((entry.airport["country_code"], entry.airport["region"]))
        results = [{**entry.airport, "ambiguous_city": len(places.get(entry.city_key, ())) > 1} for entry in entries]
        return {
            "query": query,
            "count": len(results),
            "results": results,
            "ambiguous": bool(results) and results[0]["ambiguous_city"],
            "cached": cached,
            "source": dict(self._source),
        }
