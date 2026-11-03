"""Flight search and price comparison for a trip: informational only. Rihla never books, orders or pays.

The provider is chosen from the environment (see provider_from_env in providers.py):
- a Duffel test token (duffel_test_…): Duffel's free sandbox, data_mode TEST (Duffel Airways, unrealistic prices);
- a Duffel live token, only with RIHLA_FLIGHTS_ALLOW_LIVE=true: real offers, data_mode LIVE;
- otherwise: Rihla's deterministic sample flights, data_mode DEMO, never presented as real.

Every answer says which data mode it is in, when it was retrieved and from which provider. Offers without a
usable price, or already expired, are dropped and counted, never filled in. Offers are sorted by total price
within one currency; offers in different currencies are never compared numerically (there is no verified
conversion here), so the cheapest offer is reported per currency.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import re
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Protocol

CABIN_CLASSES = ("economy", "premium_economy", "business", "first")
MAX_ADULTS = 9
MAX_DAYS_AHEAD = 361  # airlines sell about eleven months ahead
DEFAULT_LIMIT = 20
MAX_LIMIT = 50

NOTICES = {
    "LIVE": "Live prices from the provider at the time shown. They change and expire; Rihla does not book flights.",
    "TEST": "TEST data from the provider's sandbox: not real flights, schedules or prices.",
    "DEMO": "DEMO data: sample flights made up by Rihla to show the feature. They are not real flights, schedules "
            "or prices.",
}
INFORMATIONAL = "Flight prices are for information only and are not part of the trip budget. Rihla does not book " \
                "flights or take payments."


class FlightError(Exception):
    """A search that could not be answered: an HTTP status, a stable code, a message for the traveller, and the
    form field at fault when there is one."""

    def __init__(self, status: int, code: str, message: str, *, field: str | None = None,
                 retryable: bool = False, retry_after: int | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field
        self.retryable, self.retry_after = retryable, retry_after

    def as_dict(self) -> dict:
        error = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.field:
            error["field"] = self.field
        if self.retry_after is not None:
            error["retry_after"] = self.retry_after
        return {"error": error}


@dataclass(frozen=True)
class FlightQuery:
    origin: str
    destination: str
    departure_date: dt.date
    return_date: dt.date | None
    adults: int
    cabin_class: str

    def as_dict(self) -> dict:
        return {"origin": self.origin, "destination": self.destination,
                "departure_date": self.departure_date.isoformat(),
                "return_date": self.return_date.isoformat() if self.return_date else None,
                "adults": self.adults, "cabin_class": self.cabin_class,
                "trip_type": "round_trip" if self.return_date else "one_way"}


@dataclass
class ProviderAnswer:
    offers: list[dict]
    data_mode: str
    provider: str
    skipped: int = 0
    notices: tuple[str, ...] = ()


class FlightProvider(Protocol):
    name: str
    data_mode: str
    calls_network: bool

    def search(self, query: FlightQuery) -> ProviderAnswer: ...


AirportLookup = Callable[[str], "dict | None"]
_airport_search = None


def default_airport_lookup(code: str) -> dict | None:
    """The bundled airport (app/airports) with this IATA code, or None."""
    global _airport_search
    if _airport_search is None:
        from app.airports import AirportSearch
        _airport_search = AirportSearch()
    results = _airport_search.search(code, limit=1)["results"]
    return results[0] if results and results[0]["iata"] == code else None


def _airport(value: Any, field: str, lookup: AirportLookup) -> str:
    name = "departure" if field == "origin" else "arrival"
    text = value.strip().upper() if isinstance(value, str) else ""
    if not text:
        raise FlightError(422, "missing_airport", f"Choose a {name} airport.", field=field)
    if not re.fullmatch(r"[A-Z]{3}", text):
        raise FlightError(422, "invalid_airport_code", f"The {name} airport must be a 3-letter IATA code, "
                                                       "such as LHR.", field=field)
    try:
        known = lookup(text)
    except Exception as exc:  # the airport data is unavailable: do not guess
        raise FlightError(503, "airports_unavailable", "Airport data is not available right now.",
                          retryable=True) from exc
    if not known:
        raise FlightError(422, "unknown_airport", f"No airport with the code {text} was found.", field=field)
    return text


def _date(value: Any, field: str, today: dt.date) -> dt.date:
    label = "departure" if field == "departure_date" else "return"
    try:
        day = dt.date.fromisoformat(value.strip()) if isinstance(value, str) and \
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()) else None
    except ValueError:
        day = None
    if day is None:
        raise FlightError(422, "invalid_date", f"The {label} date must be a date like 2026-12-01.", field=field)
    if day < today:
        raise FlightError(422, "date_in_past", f"The {label} date is in the past.", field=field)
    if day > today + dt.timedelta(days=MAX_DAYS_AHEAD):
        raise FlightError(422, "date_too_far", f"Flights can be searched up to {MAX_DAYS_AHEAD} days ahead.",
                          field=field)
    return day


def validate_query(*, origin: Any, destination: Any, departure_date: Any, return_date: Any = None,
                   adults: Any = 1, cabin_class: Any = "economy", today: dt.date,
                   lookup: AirportLookup = default_airport_lookup) -> FlightQuery:
    """The search as Rihla runs it, or FlightError(422) naming the field at fault."""
    o = _airport(origin, "origin", lookup)
    d = _airport(destination, "destination", lookup)
    if o == d:
        raise FlightError(422, "same_airport", "Departure and arrival must be different airports.",
                          field="destination")
    depart = _date(departure_date, "departure_date", today)
    back = None
    if isinstance(return_date, str) and return_date.strip():
        back = _date(return_date, "return_date", today)
        if back < depart:
            raise FlightError(422, "return_before_departure", "The return date is before the departure date.",
                              field="return_date")
    elif return_date not in (None, ""):
        raise FlightError(422, "invalid_date", "The return date must be a date like 2026-12-08.",
                          field="return_date")
    try:
        count = int(str(adults).strip())
    except ValueError:
        count = 0
    if isinstance(adults, bool) or not 1 <= count <= MAX_ADULTS:
        raise FlightError(422, "invalid_passengers", f"Choose 1 to {MAX_ADULTS} adult passengers.", field="adults")
    cabin = (cabin_class or "economy").strip().lower() if isinstance(cabin_class, str) or cabin_class is None else ""
    if cabin not in CABIN_CLASSES:
        raise FlightError(422, "invalid_cabin_class", "Cabin class must be economy, premium_economy, business or "
                                                      "first.", field="cabin_class")
    return FlightQuery(o, d, depart, back, count, cabin)


def parse_utc(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def _total_minutes(offer: dict) -> int:
    minutes = [s.get("duration_minutes") for s in offer["slices"]]
    return sum(minutes) if all(isinstance(m, int) for m in minutes) else 10 ** 6


def sort_offers(offers: list[dict]) -> list[dict]:
    """By total price within a currency (the most common currency first), then by duration. Different currencies
    are kept apart: there is no verified conversion to compare them."""
    counts: dict[str, int] = {}
    for offer in offers:
        counts[offer["currency"]] = counts.get(offer["currency"], 0) + 1
    rank = {c: i for i, c in enumerate(sorted(counts, key=lambda c: (-counts[c], c)))}
    return sorted(offers, key=lambda o: (rank[o["currency"]], Decimal(o["total_amount"]), _total_minutes(o), o["id"]))


def price_summary(offers: list[dict]) -> dict:
    cheapest: dict[str, dict] = {}
    for offer in offers:
        best = cheapest.get(offer["currency"])
        if best is None or Decimal(offer["total_amount"]) < Decimal(best["total_amount"]):
            cheapest[offer["currency"]] = {"offer_id": offer["id"], "total_amount": offer["total_amount"],
                                           "currency": offer["currency"]}
    currencies = sorted(cheapest, key=lambda c: (-sum(o["currency"] == c for o in offers), c))
    return {
        "currencies": currencies,
        "comparable": len(currencies) <= 1,
        "cheapest": cheapest[currencies[0]] if len(currencies) == 1 else None,
        "cheapest_by_currency": {c: cheapest[c] for c in currencies},
    }


def _env_number(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError:
        return default
    return value if low <= value <= high else default


class FlightSearch:
    """Validates the search, asks the provider (cached briefly, capped per minute and per day), drops expired
    offers and sorts by price. In production only LIVE offers ever leave this class. Thread-safe.

    The caps are counted in this server process's memory: with several workers or instances, each has its own
    count, so they are not a global (or financial) limit."""

    def __init__(self, provider: FlightProvider | None = None, *, airport_lookup: AirportLookup | None = None,
                 clock: Callable[[], float] = time.time, monotonic: Callable[[], float] = time.monotonic,
                 max_calls_per_minute: int | None = None, max_calls_per_day: int | None = None,
                 cache_ttl_s: float = 300, cache_entries: int = 128, environment: str | None = None):
        from app.deployment_env import deployment_env
        self.environment = environment or deployment_env()
        if provider is None:
            from .providers import provider_from_env
            provider = provider_from_env(self.environment)
        self.provider = provider
        self._lookup = airport_lookup or default_airport_lookup
        self._clock, self._monotonic = clock, monotonic
        self._max_calls = int(max_calls_per_minute if max_calls_per_minute is not None
                              else _env_number("RIHLA_FLIGHTS_MAX_PER_MINUTE", 30, 1, 600))
        self._max_daily = int(max_calls_per_day if max_calls_per_day is not None
                              else _env_number("RIHLA_FLIGHTS_MAX_PER_DAY", 500, 1, 100000))
        self._ttl, self._max_entries = cache_ttl_s, cache_entries
        self._cache: OrderedDict[FlightQuery, tuple[float, ProviderAnswer, str]] = OrderedDict()
        self._calls: deque[float] = deque()
        self._day: tuple[dt.date | None, int] = (None, 0)
        self._lock = threading.Lock()

    def status(self) -> dict:
        """What this server can offer, without searching: for the page to explain itself up front."""
        provider = self.provider
        available = provider.data_mode is not None and (self.environment != "production"
                                                        or provider.data_mode == "LIVE")
        return {
            "environment": self.environment,
            "available": available,
            "data_mode": provider.data_mode if available else None,
            "provider": provider.name if available else None,
            "notice": getattr(provider, "reason", None) or (NOTICES.get(provider.data_mode) if available else None),
            "booking_supported": False,
            "limits": {"per_minute": self._max_calls, "per_day": self._max_daily, "scope": "per server process"},
        }

    def _unavailable(self) -> FlightError:
        return FlightError(503, "flights_unavailable", "Real-time flight prices are not available on this service "
                           "right now. Check airline or travel websites directly.")

    def _take_call_slot(self, now: float, today: dt.date, now_utc: dt.datetime) -> None:
        with self._lock:
            while self._calls and now - self._calls[0] >= 60:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                wait = max(1, math.ceil(60 - (now - self._calls[0])))
                raise FlightError(429, "rate_limited", "Too many flight searches right now. Please try again in a "
                                  "moment.", retryable=True, retry_after=wait)
            day, used = self._day if self._day[0] == today else (today, 0)
            if used >= self._max_daily:
                midnight = dt.datetime.combine(today + dt.timedelta(days=1), dt.time(), dt.timezone.utc)
                raise FlightError(429, "daily_limit_reached", "Flight search has reached its daily limit on this "
                                  "server. Please try again tomorrow.", retryable=True,
                                  retry_after=max(1, math.ceil((midnight - now_utc).total_seconds())))
            self._calls.append(now)
            self._day = (day, used + 1)

    def search(self, *, limit: int = DEFAULT_LIMIT, **params: Any) -> dict:
        if not self.status()["available"]:
            raise self._unavailable()  # before validating: no input can make it available
        now_utc = dt.datetime.fromtimestamp(self._clock(), dt.timezone.utc)
        query = validate_query(**params, today=now_utc.date(), lookup=self._lookup)
        limit = max(1, min(MAX_LIMIT, int(limit)))
        tick = self._monotonic()
        with self._lock:
            hit = self._cache.get(query)
            if hit and tick >= hit[0]:
                del self._cache[query]
                hit = None
        if hit:
            _, answer, retrieved_at = hit
            cached = True
        else:
            if self.provider.calls_network:
                self._take_call_slot(tick, now_utc.date(), now_utc)
            answer = self.provider.search(query)
            if self.environment == "production":
                # Defence in depth: whatever the provider says, only LIVE offers may reach real travellers.
                live_only = [o for o in answer.offers if o.get("data_mode") == "LIVE"]
                if answer.data_mode != "LIVE":
                    raise self._unavailable()
                answer = ProviderAnswer(live_only, "LIVE", answer.provider,
                                        answer.skipped + len(answer.offers) - len(live_only), answer.notices)
            retrieved_at = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")
            with self._lock:
                self._cache[query] = (tick + self._ttl, answer, retrieved_at)
                while len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)
            cached = False

        live, expired = [], 0
        for offer in answer.offers:
            expires = parse_utc(offer.get("expires_at"))
            if expires is not None and expires <= now_utc:
                expired += 1
            else:
                live.append(offer)
        ordered = sort_offers(live)
        notices = [NOTICES[answer.data_mode], *answer.notices]
        if not ordered:
            notices.append("No flights were offered for this search. Try other dates or nearby airports.")
        summary = price_summary(ordered)
        if not summary["comparable"]:
            notices.append("Offers come in several currencies. Prices are compared only within the same currency.")
        notices.append(INFORMATIONAL)
        return {
            "query": query.as_dict(),
            "environment": self.environment,
            "data_mode": answer.data_mode,
            "provider": answer.provider,
            "retrieved_at": retrieved_at,
            "cached": cached,
            "count": min(len(ordered), limit),
            "total_offers": len(ordered),
            "offers": ordered[:limit],
            **summary,
            "skipped_offers": {"unusable": answer.skipped, "expired": expired},
            "notices": notices,
            "booking_supported": False,
        }
