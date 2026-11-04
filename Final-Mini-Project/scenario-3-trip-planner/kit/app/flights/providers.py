"""Flight offer providers: Duffel (test or, only when allowed, live) and Rihla's DEMO sample flights.

Duffel Flights API: POST https://api.duffel.com/air/offer_requests?return_offers=true (Duffel-Version: v2). Only
that one search endpoint is ever called: never orders, payments or anything that books. Docs:
https://duffel.com/docs/api/v2/offer-requests/create-offer-request
"""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import logging
import math
import os
import random
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.deployment_env import deployment_env

from .service import FlightError, FlightQuery, ProviderAnswer, _env_number, default_airport_lookup

log = logging.getLogger("rihla.flights")  # never logs the token, the request headers or the offers
DUFFEL_URL = "https://api.duffel.com"
DUFFEL_VERSION = "v2"
MAX_CONNECTIONS = 1


# ------------------------------------------------------------------ helpers shared by both providers
def iso_minutes(value: Any) -> int | None:
    """An ISO 8601 duration ("PT2H26M", "P1DT3H") in minutes, or None."""
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", value or "") \
        if isinstance(value, str) else None
    if not match or value in ("P", "PT"):
        return None
    days, hours, minutes, seconds = (float(g) if g else 0 for g in match.groups())
    return int(days * 1440 + hours * 60 + minutes + round(seconds / 60))


def _local_time(value: Any) -> str | None:
    """"2026-12-01T08:10:00" -> "2026-12-01T08:10" (the airport's local time, as the provider gives it)."""
    return value[:16] if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value) else None


def _amount(value: Any) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(\.\d+)?", value.strip()):
        return None
    try:
        number = Decimal(value.strip())
    except InvalidOperation:
        return None
    return value.strip() if number > 0 else None


def _code(value: Any, length: int = 3) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(rf"[A-Z0-9]{{{length}}}", value) else None


def _iata(place: Any) -> str | None:
    return _code(place.get("iata_code")) if isinstance(place, dict) else None


def _carrier(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = raw.get("name") if isinstance(raw.get("name"), str) and raw["name"].strip() else None
    code = _code(raw.get("iata_code"), 2)
    return {"name": name.strip() if name else None, "iata_code": code} if name or code else None


def _baggage(segment: dict) -> dict:
    """Bags for the first passenger on one segment: {"checked": n, "carry_on": n}, None where unknown."""
    passengers = segment.get("passengers")
    if not isinstance(passengers, list) or not passengers or not isinstance(passengers[0], dict) \
            or not isinstance(passengers[0].get("baggages"), list):
        return {"checked": None, "carry_on": None}
    counts = {"checked": 0, "carry_on": 0}
    for bag in passengers[0]["baggages"]:
        if isinstance(bag, dict) and bag.get("type") in counts and isinstance(bag.get("quantity"), int) \
                and bag["quantity"] >= 0:
            counts[bag["type"]] += bag["quantity"]
    return counts


def _least(values: list[int | None]) -> int | None:
    return None if not values or any(v is None for v in values) else min(values)


def _slice(raw: Any) -> dict | None:
    segments = raw.get("segments") if isinstance(raw, dict) else None
    if not isinstance(segments, list) or not segments or not all(isinstance(s, dict) for s in segments):
        return None
    legs = []
    for seg in segments:
        marketing = _carrier(seg.get("marketing_carrier"))
        number = seg.get("marketing_carrier_flight_number")
        legs.append({
            "origin": _iata(seg.get("origin")),
            "destination": _iata(seg.get("destination")),
            "departing_at": _local_time(seg.get("departing_at")),
            "arriving_at": _local_time(seg.get("arriving_at")),
            "duration_minutes": iso_minutes(seg.get("duration")),
            "flight_number": f"{marketing['iata_code'] or ''}{number}".strip() if marketing and
            isinstance(number, str) and number.strip() else None,
            "marketing_carrier": marketing,
            "operating_carrier": _carrier(seg.get("operating_carrier")),
            "technical_stops": len(seg["stops"]) if isinstance(seg.get("stops"), list) else 0,
            "baggage": _baggage(seg),
        })
    first, last = legs[0], legs[-1]
    if not (first["origin"] and last["destination"] and first["departing_at"] and last["arriving_at"]):
        return None
    return {
        "origin": first["origin"],
        "destination": last["destination"],
        "departing_at": first["departing_at"],
        "arriving_at": last["arriving_at"],
        "duration_minutes": iso_minutes(raw.get("duration")),
        "stops": len(legs) - 1 + sum(leg["technical_stops"] for leg in legs),
        "connections": [leg["destination"] for leg in legs[:-1] if leg["destination"]],
        "segments": legs,
    }


def normalize_duffel_offer(raw: Any, adults: int) -> dict | None:
    """One Duffel offer as Rihla's offer, or None when it has no id, no usable price or no usable journey."""
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"].strip():
        return None
    amount = _amount(raw.get("total_amount"))
    currency = raw.get("total_currency") if isinstance(raw.get("total_currency"), str) and \
        re.fullmatch(r"[A-Z]{3}", raw["total_currency"]) else None
    slices_raw = raw.get("slices")
    if not amount or not currency or not isinstance(slices_raw, list) or not slices_raw:
        return None
    slices = [_slice(s) for s in slices_raw]
    if any(s is None for s in slices):
        return None
    legs = [leg for s in slices for leg in s["segments"]]
    cabins = {(leg_raw.get("passengers") or [{}])[0].get("cabin_class")
              for s in slices_raw for leg_raw in s["segments"]
              if isinstance(leg_raw.get("passengers"), list) and leg_raw["passengers"]
              and isinstance(leg_raw["passengers"][0], dict)}
    passengers = raw.get("passengers")
    expires = raw.get("expires_at") if isinstance(raw.get("expires_at"), str) else None
    return {
        "id": f"duffel:{raw['id']}",
        "provider_offer_id": raw["id"],
        "airline": _carrier(raw.get("owner")) or {"name": None, "iata_code": None},
        "total_amount": amount,
        "currency": currency,
        "passengers": len(passengers) if isinstance(passengers, list) and passengers else adults,
        "cabin_class": cabins.pop() if len(cabins) == 1 else None,
        "slices": slices,
        "baggage": {"checked": _least([leg["baggage"]["checked"] for leg in legs]),
                    "carry_on": _least([leg["baggage"]["carry_on"] for leg in legs])},
        "expires_at": expires,
        "time_basis": "local",
        "data_mode": "LIVE" if raw.get("live_mode") is True else "TEST",
        "provider": "Duffel",
    }


def _retry_after(response: httpx.Response, now: float) -> int:
    """Seconds to wait, from Duffel's ratelimit-reset header (a date) or Retry-After; 60 when unknown."""
    for header in ("retry-after", "ratelimit-reset"):
        value = (response.headers.get(header) or "").strip()
        if value.isdigit():
            number = int(value)
            return max(1, number - int(now)) if number > 10 ** 9 else max(1, number)
        if value:
            try:
                return max(1, math.ceil(email.utils.parsedate_to_datetime(value).timestamp() - now))
            except (TypeError, ValueError):
                continue
    return 60


class DuffelProvider:
    """Searches Duffel's offer requests. data_mode follows the token: TEST for duffel_test_, LIVE for duffel_live_
    (only built when RIHLA_FLIGHTS_ALLOW_LIVE=true)."""

    name = "Duffel"
    calls_network = True

    def __init__(self, token: str, *, client: httpx.Client | None = None, base_url: str | None = None,
                 timeout_s: float | None = None, clock=None):
        self._token = token
        self.data_mode = "LIVE" if token.startswith("duffel_live_") else "TEST"
        self.base_url = (base_url or os.getenv("RIHLA_FLIGHTS_URL") or DUFFEL_URL).rstrip("/")
        timeout = timeout_s if timeout_s is not None else _env_number("RIHLA_FLIGHTS_TIMEOUT_S", 25, 3, 70)
        # Ask Duffel to stop waiting for airlines a little before we stop waiting for Duffel.
        self.supplier_timeout_ms = int(max(2, min(60, timeout - 5)) * 1000)
        self._client = client or httpx.Client(timeout=timeout)
        self._clock = clock or time.time

    def __repr__(self) -> str:  # never show the token
        return f"DuffelProvider(data_mode={self.data_mode!r}, base_url={self.base_url!r})"

    def _body(self, query: FlightQuery) -> dict:
        slices = [{"origin": query.origin, "destination": query.destination,
                   "departure_date": query.departure_date.isoformat()}]
        if query.return_date:
            slices.append({"origin": query.destination, "destination": query.origin,
                           "departure_date": query.return_date.isoformat()})
        return {"data": {"slices": slices, "passengers": [{"type": "adult"} for _ in range(query.adults)],
                         "cabin_class": query.cabin_class, "max_connections": MAX_CONNECTIONS}}

    def search(self, query: FlightQuery) -> ProviderAnswer:
        try:
            answer = self._search(query)
        except FlightError as error:
            log.warning("Duffel %s search failed: %s (status %s)", self.data_mode, error.code, error.status)
            raise
        if answer.skipped:
            log.info("Duffel %s search: %d offers dropped as unusable", self.data_mode, answer.skipped)
        return answer

    def _search(self, query: FlightQuery) -> ProviderAnswer:
        try:
            response = self._client.post(
                f"{self.base_url}/air/offer_requests",
                params={"return_offers": "true", "supplier_timeout": str(self.supplier_timeout_ms)},
                json=self._body(query),
                headers={"Authorization": f"Bearer {self._token}", "Duffel-Version": DUFFEL_VERSION,
                         "Accept": "application/json", "Content-Type": "application/json"})
        except httpx.TimeoutException as exc:
            raise FlightError(504, "provider_timeout", "The flight search service did not answer in time. Please "
                              "try again.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise FlightError(503, "provider_unavailable", "The flight search service cannot be reached right "
                              "now. Please try again.", retryable=True) from exc

        status = response.status_code
        if status in (401, 403):
            raise FlightError(502, "provider_auth_failed", "Flight search is not set up correctly on this server "
                              "(the provider refused its credentials).")
        if status == 429:
            raise FlightError(503, "provider_rate_limited", "The flight search service is busy. Please try again "
                              "shortly.", retryable=True, retry_after=_retry_after(response, self._clock()))
        if status >= 500:
            raise FlightError(502, "provider_error", "The flight search service or an airline had a problem. "
                              "Please try again.", retryable=True)
        try:
            body = response.json()
        except ValueError as exc:
            raise FlightError(502, "provider_bad_response", "The flight search service sent an unreadable "
                              "answer.") from exc
        if status >= 400:
            raise FlightError(502, "provider_rejected", "The flight search service could not run this search.")
        offers = body.get("data", {}).get("offers") if isinstance(body, dict) and \
            isinstance(body.get("data"), dict) else None
        if not isinstance(offers, list):
            raise FlightError(502, "provider_bad_response", "The flight search service sent an unexpected answer.")
        normalized = [normalize_duffel_offer(o, query.adults) for o in offers]
        kept = [o for o in normalized if o is not None]
        modes = {o["data_mode"] for o in kept}
        return ProviderAnswer(kept, modes.pop() if len(modes) == 1 else self.data_mode, self.name,
                              skipped=len(normalized) - len(kept))


# ------------------------------------------------------------------ DEMO
DEMO_AIRLINES = ("Rihla Demo Air", "Sample Skyways", "Example Airlines", "Placeholder Jet")
DEMO_HUBS = ("IST", "DXB", "DOH", "FRA", "AMS", "CDG", "LHR", "SIN", "JFK")
CABIN_FACTOR = {"economy": 1.0, "premium_economy": 1.7, "business": 3.2, "first": 5.5}


def _km(a: dict | None, b: dict | None) -> float:
    if not a or not b or a.get("latitude") is None or b.get("latitude") is None:
        return 1500.0  # unknown position: a medium-haul guess, and the offer says it is DEMO anyway
    lat1, lon1, lat2, lon2 = map(math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _flight_minutes(km: float) -> int:
    return int(round((km / 780 * 60 + 35) / 5) * 5)


class DemoProvider:
    """Deterministic sample flights for a demo without a provider account. The same search always gives the same
    offers. Airlines, flight numbers, times and prices are made up and labelled DEMO everywhere; times are UTC."""

    name = "Rihla demo data"
    data_mode = "DEMO"
    calls_network = False

    def __init__(self, *, lookup=None, reason: str | None = None):
        self._lookup = lookup or default_airport_lookup
        self.reason = reason

    def _slice(self, rng: random.Random, origin: str, destination: str, day: dt.date, stops: int,
               airline: str, number: int) -> tuple[dict, float]:
        here, there = self._lookup(origin), self._lookup(destination)
        route = [origin, destination]
        if stops:
            hubs = [h for h in DEMO_HUBS if h not in route]
            hub = min(hubs, key=lambda h: (_km(here, self._lookup(h)) + _km(self._lookup(h), there), h))
            route = [origin, hub, destination]
        start = dt.datetime.combine(day, dt.time(rng.randrange(6, 22), rng.choice((0, 15, 30, 45))))
        legs, clock, total_km = [], start, 0.0
        for i, (a, b) in enumerate(zip(route, route[1:])):
            km = _km(self._lookup(a), self._lookup(b))
            total_km += km
            minutes = _flight_minutes(km)
            if i:
                clock += dt.timedelta(minutes=rng.randrange(70, 200, 5))  # connection time
            arrive = clock + dt.timedelta(minutes=minutes)
            legs.append({"origin": a, "destination": b, "departing_at": clock.strftime("%Y-%m-%dT%H:%M"),
                         "arriving_at": arrive.strftime("%Y-%m-%dT%H:%M"), "duration_minutes": minutes,
                         "flight_number": f"DEMO {number + i}", "marketing_carrier": {"name": airline,
                                                                                     "iata_code": None},
                         "operating_carrier": {"name": airline, "iata_code": None}, "technical_stops": 0})
            clock = arrive
        return {"origin": origin, "destination": destination, "departing_at": legs[0]["departing_at"],
                "arriving_at": legs[-1]["arriving_at"],
                "duration_minutes": int((clock - start).total_seconds() // 60), "stops": len(legs) - 1,
                "connections": route[1:-1], "segments": legs}, total_km

    def search(self, query: FlightQuery) -> ProviderAnswer:
        seed = hashlib.sha256(repr(sorted(query.as_dict().items())).encode()).hexdigest()
        rng = random.Random(int(seed[:16], 16))
        direct_km = _km(self._lookup(query.origin), self._lookup(query.destination))
        baggage = ({"checked": 1, "carry_on": 1}, {"checked": 0, "carry_on": 1},
                   {"checked": None, "carry_on": None}, {"checked": 2, "carry_on": 1})
        offers = []
        for i, airline in enumerate(DEMO_AIRLINES):
            stops = 0 if i < 2 and direct_km < 9000 else 1
            number = 100 + i * 100 + rng.randrange(0, 90)
            slices, km = [], 0.0
            out, k = self._slice(rng, query.origin, query.destination, query.departure_date, stops, airline, number)
            slices.append(out)
            km += k
            if query.return_date:
                back, k = self._slice(rng, query.destination, query.origin, query.return_date, stops, airline,
                                      number + 50)
                slices.append(back)
                km += k
            per_adult = (45 + 0.07 * km) * CABIN_FACTOR[query.cabin_class] * rng.uniform(0.85, 1.3) * \
                (0.85 if stops else 1.0)
            for s in slices:
                for leg in s["segments"]:
                    leg["baggage"] = dict(baggage[i])
            offers.append({
                "id": f"demo:{seed[:10]}-{i}",
                "provider_offer_id": None,
                "airline": {"name": airline, "iata_code": None},
                "total_amount": f"{round(per_adult) * query.adults:.2f}",
                "currency": "USD",
                "passengers": query.adults,
                "cabin_class": query.cabin_class,
                "slices": slices,
                "baggage": dict(baggage[i]),
                "expires_at": None,
                "time_basis": "utc",
                "data_mode": "DEMO",
                "provider": self.name,
            })
        return ProviderAnswer(offers, "DEMO", self.name, notices=(self.reason,) if self.reason else ())


class UnavailableProvider:
    """No provider that this deployment may use: every search answers 503 flights_unavailable. Production uses it
    instead of sample or sandbox data, which must never reach real travellers."""

    name = None
    data_mode = None
    calls_network = False

    def __init__(self, reason: str):
        self.reason = reason

    def search(self, query: FlightQuery) -> ProviderAnswer:
        raise FlightError(503, "flights_unavailable", "Real-time flight prices are not available on this service "
                          "right now. Check airline or travel websites directly.")


def provider_from_env(environment: str | None = None) -> DuffelProvider | DemoProvider | UnavailableProvider:
    """The provider this deployment (RIHLA_ENV) may use:
    - production: Duffel only with a live token AND RIHLA_FLIGHTS_ALLOW_LIVE=true; otherwise unavailable (never
      TEST or DEMO data);
    - test: Duffel with a test token, else DEMO; live tokens are never used;
    - development: as test, and a live token with RIHLA_FLIGHTS_ALLOW_LIVE=true.
    A live token alone never turns on live (possibly billed) searches."""
    env = environment or deployment_env()
    token = (os.getenv("DUFFEL_ACCESS_TOKEN") or "").strip()
    allow_live = (os.getenv("RIHLA_FLIGHTS_ALLOW_LIVE") or "").strip().lower() in ("1", "true", "yes")
    if env == "production":
        if token.startswith("duffel_live_") and allow_live:
            return DuffelProvider(token)
        return UnavailableProvider("No approved live flight provider is configured (production needs a live Duffel "
                                   "token and RIHLA_FLIGHTS_ALLOW_LIVE=true; it never shows test or demo flights).")
    if token.startswith("duffel_test_"):
        return DuffelProvider(token)
    if token.startswith("duffel_live_"):
        if env == "development" and allow_live:
            return DuffelProvider(token)
        return DemoProvider(reason="A live Duffel token is set, but live searches are switched off "
                                   f"({'RIHLA_FLIGHTS_ALLOW_LIVE is not true' if env == 'development' else 'never in the test environment'}). "
                                   "Showing DEMO data.")
    if token:
        return DemoProvider(reason="DUFFEL_ACCESS_TOKEN is not a Duffel token. Showing DEMO data.")
    return DemoProvider(reason="No flight provider is set up on this server (DUFFEL_ACCESS_TOKEN). Showing DEMO "
                               "data.")
