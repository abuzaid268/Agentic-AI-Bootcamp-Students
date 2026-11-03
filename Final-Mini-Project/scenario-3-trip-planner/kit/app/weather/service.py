"""Daily weather forecast for a place and dates: GET /api/weather. Real provider data only (Open-Meteo).

Provider: the Open-Meteo forecast API (https://open-meteo.com/en/docs), data under CC BY 4.0. Its free API is
for non-commercial use only (https://open-meteo.com/en/terms; 600 calls/minute, 5,000/hour, 10,000/day per
IP); commercial use needs a paid plan, whose key goes to customer-api.open-meteo.com. So:
- development and test may use the free API;
- production may call Open-Meteo only with RIHLA_OPEN_METEO_API_KEY (paid plan) or with
  RIHLA_OPEN_METEO_NONCOMMERCIAL=true (the team states the deployment is non-commercial: no ads, no subscriptions);
  otherwise weather is reported unavailable. The same decision covers app/destinations (app/open_meteo.py).

Nothing is invented: a value the provider does not give is null, a day beyond the 16-day forecast horizon is
refused rather than filled, and a provider failure is reported (data_status UNAVAILABLE), never replaced.
data_status is LIVE for an answer fetched now, CACHED for one served from this server's cache (with its original
retrieval time); expired cache entries are never served.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import os
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app.deployment_env import deployment_env
from app.open_meteo import api_key, licence_allows, protect_httpx_logs

log = logging.getLogger("rihla.weather")  # never logs the API key or request URLs

FREE_URL = "https://api.open-meteo.com/v1/forecast"
CUSTOMER_URL = "https://customer-api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16  # Open-Meteo: "Up to 16 days of forecast are possible"
SOURCE = {
    "provider": "Open-Meteo",
    "url": "https://open-meteo.com/",
    "licence": "CC BY 4.0",
    "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
}
DAILY = ("weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
         "precipitation_probability_max", "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant")
# WMO weather interpretation codes, as in the kit's services/travel_data.py.
WMO = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "rime fog",
       51: "light drizzle", 53: "drizzle", 55: "dense drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
       73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers", 82: "violent showers",
       85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with hail",
       99: "thunderstorm with hail"}
WET_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
UNITS = {"celsius": "°C", "fahrenheit": "°F"}


class WeatherError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None,
                 retryable: bool = False, retry_after: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field
        self.retryable, self.retry_after, self.details = retryable, retry_after, details or {}

    def as_dict(self) -> dict:
        error = {"code": self.code, "message": self.message, "retryable": self.retryable, **self.details}
        if self.field:
            error["field"] = self.field
        if self.retry_after is not None:
            error["retry_after"] = self.retry_after
        return {"error": error, "data_status": "UNAVAILABLE"}


@dataclass(frozen=True)
class WeatherQuery:
    latitude: float
    longitude: float
    start_date: dt.date
    end_date: dt.date
    temperature_unit: str

    def key(self) -> tuple:
        # About 1 km: nearby requests share a provider call (Open-Meteo's grid is coarser than that anyway).
        return round(self.latitude, 2), round(self.longitude, 2), self.start_date, self.end_date, self.temperature_unit


def _coordinate(value: Any, field: str, bound: float) -> float:
    try:
        number = float(str(value).strip())
    except ValueError:
        number = math.nan
    if not math.isfinite(number) or not -bound <= number <= bound:
        name = "Latitude" if field == "latitude" else "Longitude"
        raise WeatherError(422, "invalid_coordinates", f"{name} must be a number between -{bound:g} and {bound:g}.",
                           field=field)
    return number


def _day(value: Any, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError:
        raise WeatherError(422, "invalid_date", f"{field.replace('_', ' ').capitalize()} must be a date like "
                           "2026-12-01.", field=field) from None


def validate_query(*, latitude: Any, longitude: Any, start_date: Any = None, end_date: Any = None,
                   temperature_unit: Any = "celsius", today: dt.date) -> WeatherQuery:
    """The forecast request, or WeatherError(422). `today` is the UTC date: the place's own date can be one day
    either side of it, so one day of slack is allowed at the start and the horizon is the provider's."""
    lat = _coordinate(latitude, "latitude", 90)
    lon = _coordinate(longitude, "longitude", 180)
    start = _day(start_date, "start_date") if start_date not in (None, "") else today
    end = _day(end_date, "end_date") if end_date not in (None, "") else start
    if end < start:
        raise WeatherError(422, "invalid_date_range", "The end date is before the start date.", field="end_date")
    if start < today - dt.timedelta(days=1):
        raise WeatherError(422, "date_in_past", "The start date is in the past: this is a forecast, not a "
                           "weather history.", field="start_date")
    horizon = today + dt.timedelta(days=FORECAST_DAYS - 1)
    if end > horizon:
        raise WeatherError(422, "beyond_forecast_horizon", f"Forecasts reach only {FORECAST_DAYS} days ahead (to "
                           f"{horizon}). Check again closer to the date.", field="end_date",
                           details={"forecast_available_until": horizon.isoformat()})
    unit = str(temperature_unit or "celsius").strip().lower()
    if unit not in UNITS:
        raise WeatherError(422, "invalid_unit", "Temperature unit must be celsius or fahrenheit.",
                           field="temperature_unit")
    return WeatherQuery(lat, lon, start, end, unit)


def _num(values: Any, i: int) -> float | None:
    if not isinstance(values, list) or i >= len(values):
        return None
    v = values[i]
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def normalize_forecast(body: Any, query: WeatherQuery) -> tuple[dict, list[dict], list[str]]:
    """Open-Meteo's answer as (location, days, missing dates). Raises WeatherError(502) if it is not a forecast."""
    daily = body.get("daily") if isinstance(body, dict) else None
    times = daily.get("time") if isinstance(daily, dict) else None
    if not isinstance(times, list) or not all(isinstance(t, str) for t in times):
        raise WeatherError(502, "provider_bad_response", "The weather service sent an unexpected answer.",
                           retryable=True)
    wanted = {(query.start_date + dt.timedelta(days=i)).isoformat()
              for i in range((query.end_date - query.start_date).days + 1)}
    days = []
    for i, day in enumerate(times):
        if day not in wanted:
            continue
        code = _num(daily.get("weather_code"), i)
        code = int(code) if code is not None else None
        probability = _num(daily.get("precipitation_probability_max"), i)
        direction = _num(daily.get("wind_direction_10m_dominant"), i)
        days.append({
            "date": day,
            "weather_code": code,
            "condition": WMO.get(code, "unknown") if code is not None else None,
            "temperature_max": _num(daily.get("temperature_2m_max"), i),
            "temperature_min": _num(daily.get("temperature_2m_min"), i),
            "precipitation_sum_mm": _num(daily.get("precipitation_sum"), i),
            "precipitation_probability_max_pct": probability if probability is None or 0 <= probability <= 100
            else None,
            "wind_speed_max_kmh": _num(daily.get("wind_speed_10m_max"), i),
            "wind_gusts_max_kmh": _num(daily.get("wind_gusts_10m_max"), i),
            "wind_direction_dominant_deg": direction if direction is None or 0 <= direction <= 360 else None,
            "wet": code in WET_CODES if code is not None else None,
        })
    found = {d["date"] for d in days}
    location = {
        "latitude": _num([body.get("latitude")], 0),
        "longitude": _num([body.get("longitude")], 0),
        "elevation_m": _num([body.get("elevation")], 0),
        "timezone": body.get("timezone") if isinstance(body.get("timezone"), str) else None,
        "timezone_abbreviation": body.get("timezone_abbreviation")
        if isinstance(body.get("timezone_abbreviation"), str) else None,
        "utc_offset_seconds": int(body["utc_offset_seconds"]) if isinstance(body.get("utc_offset_seconds"), int)
        and not isinstance(body.get("utc_offset_seconds"), bool) else None,
    }
    return location, sorted(days, key=lambda d: d["date"]), sorted(wanted - found)


def _env_number(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError:
        return default
    return value if low <= value <= high else default


class OpenMeteoProvider:
    """Calls the Open-Meteo forecast API: the free endpoint, or the customer endpoint with a paid plan's key."""

    name = "Open-Meteo"

    def __init__(self, *, api_key: str | None = None, client: httpx.Client | None = None, url: str | None = None,
                 timeout_s: float | None = None):
        self._key = api_key
        self.commercial = bool(api_key)
        if api_key:
            protect_httpx_logs()
        self.url = url or os.getenv("RIHLA_WEATHER_URL") or (CUSTOMER_URL if api_key else FREE_URL)
        timeout = timeout_s if timeout_s is not None else _env_number("RIHLA_WEATHER_TIMEOUT_S", 6, 1, 30)
        self._client = client or httpx.Client(timeout=timeout, headers={"User-Agent": "Rihla-trip-planner"})

    def __repr__(self) -> str:  # never show the key
        return f"OpenMeteoProvider(url={self.url!r}, commercial={self.commercial})"

    def fetch(self, query: WeatherQuery) -> dict:
        params = {"latitude": f"{query.latitude:.4f}", "longitude": f"{query.longitude:.4f}", "timezone": "auto",
                  "start_date": query.start_date.isoformat(), "end_date": query.end_date.isoformat(),
                  "daily": ",".join(DAILY), "temperature_unit": query.temperature_unit, "wind_speed_unit": "kmh",
                  "precipitation_unit": "mm"}
        if self._key:
            params["apikey"] = self._key
        try:
            response = self._client.get(self.url, params=params)
        except httpx.TimeoutException as exc:
            raise WeatherError(504, "provider_timeout", "The weather service did not answer in time. Please try "
                               "again.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise WeatherError(503, "provider_unavailable", "The weather service cannot be reached right now.",
                               retryable=True) from exc
        if response.status_code == 429:
            raise WeatherError(503, "provider_rate_limited", "The weather service is busy. Please try again later.",
                               retryable=True, retry_after=60)
        if response.status_code in (401, 403):
            raise WeatherError(502, "provider_auth_failed", "Weather is not set up correctly on this server.")
        if response.status_code >= 500:
            raise WeatherError(502, "provider_error", "The weather service had a problem. Please try again.",
                               retryable=True)
        try:
            body = response.json()
        except ValueError as exc:
            raise WeatherError(502, "provider_bad_response", "The weather service sent an unreadable answer.",
                               retryable=True) from exc
        if response.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            raise WeatherError(502, "provider_rejected", "The weather service could not answer this request.")
        return body


provider_allowed = licence_allows  # the decision is shared with app/destinations: app/open_meteo.py


class WeatherService:
    """Validates, caches (bounded, short) and caps provider calls. Thread-safe. The caps count in this process's
    memory only: several workers or instances each count separately."""

    def __init__(self, provider: OpenMeteoProvider | None = None, *, environment: str | None = None,
                 clock: Callable[[], float] = time.time, monotonic: Callable[[], float] = time.monotonic,
                 cache_ttl_s: float = 1800, cache_entries: int = 256, max_calls_per_minute: int | None = None,
                 max_calls_per_day: int | None = None):
        self.environment = environment or deployment_env()
        self.allowed, self.reason = provider_allowed(self.environment)
        if provider is not None and provider.commercial:  # a paid plan's key: commercial use is licensed
            self.allowed, self.reason = True, None
        if provider is None and self.allowed:
            provider = OpenMeteoProvider(api_key=api_key())
        self.provider = provider
        self._clock, self._monotonic = clock, monotonic
        self._ttl, self._max_entries = cache_ttl_s, cache_entries
        self._max_minute = int(max_calls_per_minute if max_calls_per_minute is not None
                               else _env_number("RIHLA_WEATHER_MAX_PER_MINUTE", 60, 1, 600))
        self._max_day = int(max_calls_per_day if max_calls_per_day is not None
                            else _env_number("RIHLA_WEATHER_MAX_PER_DAY", 5000, 1, 100000))
        self._cache: OrderedDict[tuple, tuple[float, dict, str]] = OrderedDict()
        self._calls: deque[float] = deque()
        self._day: tuple[dt.date | None, int] = (None, 0)
        self._lock = threading.Lock()

    def status(self) -> dict:
        available = self.allowed and self.provider is not None
        return {"environment": self.environment, "available": available,
                "provider": self.provider.name if available else None,
                "notice": None if available else self.reason or "No weather provider is set up.",
                "forecast_days": FORECAST_DAYS, **({"source": dict(SOURCE)} if available else {}),
                "limits": {"per_minute": self._max_minute, "per_day": self._max_day, "scope": "per server process"}}

    def _take_call_slot(self, tick: float, today: dt.date) -> None:
        with self._lock:
            while self._calls and tick - self._calls[0] >= 60:
                self._calls.popleft()
            if len(self._calls) >= self._max_minute:
                raise WeatherError(429, "rate_limited", "Too many weather requests right now. Please try again in "
                                   "a moment.", retryable=True,
                                   retry_after=max(1, math.ceil(60 - (tick - self._calls[0]))))
            day, used = self._day if self._day[0] == today else (today, 0)
            if used >= self._max_day:
                raise WeatherError(429, "daily_limit_reached", "Weather has reached its daily limit on this server. "
                                   "Please try again tomorrow.", retryable=True)
            self._calls.append(tick)
            self._day = (day, used + 1)

    def forecast(self, **params: Any) -> dict:
        if not self.status()["available"]:
            raise WeatherError(503, "weather_unavailable", "Weather forecasts are not available on this service "
                               "right now.")
        now = dt.datetime.fromtimestamp(self._clock(), dt.timezone.utc)
        query = validate_query(**params, today=now.date())
        tick = self._monotonic()
        key = query.key()
        with self._lock:
            hit = self._cache.get(key)
            if hit and tick >= hit[0]:
                del self._cache[key]  # expired: never served
                hit = None
            if hit:
                self._cache.move_to_end(key)
        if hit:
            expires_tick, body, retrieved_at = hit
            status = "CACHED"
        else:
            self._take_call_slot(tick, now.date())
            try:
                body = self.provider.fetch(query)
                normalize_forecast(body, query)  # refuse a malformed answer before caching it
            except WeatherError as error:
                log.warning("Open-Meteo forecast failed: %s (status %s)", error.code, error.status)
                raise
            retrieved_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
            expires_tick = tick + self._ttl
            with self._lock:
                self._cache[key] = (expires_tick, body, retrieved_at)
                while len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)
            status = "LIVE"
        location, days, missing = normalize_forecast(body, query)
        cache_expires = now + dt.timedelta(seconds=max(0.0, expires_tick - tick))
        notices = ["Forecast: it changes, check again closer to the date."]
        if missing:
            notices.append(f"The provider gave no forecast for {', '.join(missing)}.")
        return {
            "location": location,
            "requested": {"latitude": query.latitude, "longitude": query.longitude,
                          "start_date": query.start_date.isoformat(), "end_date": query.end_date.isoformat()},
            "kind": "forecast",
            "data_status": status,
            "units": {"temperature": UNITS[query.temperature_unit], "precipitation": "mm", "wind_speed": "km/h",
                      "wind_direction": "°"},
            "days": days,
            "missing_dates": missing,
            "retrieved_at": retrieved_at,
            "cache_expires_at": cache_expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "forecast_horizon_end": (now.date() + dt.timedelta(days=FORECAST_DAYS - 1)).isoformat(),
            "source": dict(SOURCE),
            "environment": self.environment,
            "notices": notices,
        }
