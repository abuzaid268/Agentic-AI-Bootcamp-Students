"""GET /api/weather: daily forecasts from Open-Meteo. The provider is mocked (httpx.MockTransport): no network.

The main fixture is a real Open-Meteo answer recorded once (tests/fixtures/open_meteo_forecast_amman.json,
Amman 2026-11-03..05).
"""
import datetime as dt
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.weather import OpenMeteoProvider, WeatherError, WeatherService, install_weather, validate_query
from app.weather.service import CUSTOMER_URL, FREE_URL, provider_allowed

AMMAN = json.loads((Path(__file__).parent / "fixtures" / "open_meteo_forecast_amman.json").read_text(encoding="utf-8"))
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc).timestamp()
TODAY = dt.date(2026, 11, 3)
PLACE = {"latitude": "31.9539", "longitude": "35.9106"}
TRIP = {**PLACE, "start_date": "2026-11-03", "end_date": "2026-11-05"}


class OpenMeteo:
    """A scripted Open-Meteo: answers each request with the next reply, and records what it was asked."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)


def service(meteo, *, api_key=None, environment="development", clock=lambda: NOW, monotonic=lambda: 0.0,
            **kwargs):
    provider = OpenMeteoProvider(api_key=api_key, client=httpx.Client(transport=httpx.MockTransport(meteo)))
    return WeatherService(provider, environment=environment, clock=clock, monotonic=monotonic, **kwargs)


def api(svc):
    app = FastAPI()
    install_weather(app, svc)
    return TestClient(app)


def with_daily(**changes):
    return {**AMMAN, "daily": {**AMMAN["daily"], **changes}}


# ------------------------------------------------------------------ valid answers
def test_a_forecast_is_normalized_with_units_time_zone_and_source():
    meteo = OpenMeteo(AMMAN)
    r = api(service(meteo)).get("/api/weather", params=TRIP)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, max-age=600"
    body = r.json()
    assert body["data_status"] == "LIVE" and body["kind"] == "forecast"
    assert body["location"]["timezone"] == "Asia/Amman" and body["location"]["utc_offset_seconds"] == 10800
    assert body["units"] == {"temperature": "°C", "precipitation": "mm", "wind_speed": "km/h", "wind_direction": "°"}
    assert [d["date"] for d in body["days"]] == ["2026-11-03", "2026-11-04", "2026-11-05"]
    first = body["days"][0]
    assert first == {"date": "2026-11-03", "weather_code": 3, "condition": "overcast", "temperature_max": 24.5,
                     "temperature_min": 14.7, "precipitation_sum_mm": 0.0, "precipitation_probability_max_pct": 3.0,
                     "wind_speed_max_kmh": 15.5, "wind_gusts_max_kmh": 34.9, "wind_direction_dominant_deg": 258.0,
                     "wet": False}
    assert body["retrieved_at"] == "2026-11-03T12:00:00Z" and body["cache_expires_at"] == "2026-11-03T12:30:00Z"
    assert body["forecast_horizon_end"] == "2026-11-18" and body["missing_dates"] == []
    assert body["source"]["provider"] == "Open-Meteo" and body["source"]["licence"] == "CC BY 4.0"
    sent = meteo.requests[0].url
    assert str(sent).startswith(FREE_URL) and "apikey" not in sent.params
    assert sent.params["timezone"] == "auto" and sent.params["start_date"] == "2026-11-03"
    assert sent.params["latitude"] == "31.9539" and "precipitation_probability_max" in sent.params["daily"]


def test_one_day_defaults_to_today_and_fahrenheit_is_passed_on():
    meteo = OpenMeteo(AMMAN)
    body = service(meteo).forecast(**PLACE, temperature_unit="Fahrenheit")
    assert [d["date"] for d in body["days"]] == ["2026-11-03"] and body["units"]["temperature"] == "°F"
    assert meteo.requests[0].url.params["temperature_unit"] == "fahrenheit"


# ------------------------------------------------------------------ input
@pytest.mark.parametrize("params, code, field", [
    ({"latitude": "91"}, "invalid_coordinates", "latitude"),
    ({"latitude": "-90.5"}, "invalid_coordinates", "latitude"),
    ({"longitude": "-181"}, "invalid_coordinates", "longitude"),
    ({"latitude": "abc"}, "invalid_coordinates", "latitude"),
    ({"latitude": "nan"}, "invalid_coordinates", "latitude"),
    ({"longitude": "inf"}, "invalid_coordinates", "longitude"),
    ({"latitude": ""}, "invalid_coordinates", "latitude"),
    ({"start_date": "03/11/2026"}, "invalid_date", "start_date"),
    ({"start_date": "2026-02-30"}, "invalid_date", "start_date"),
    ({"end_date": "2026-11-02"}, "invalid_date_range", "end_date"),
    ({"start_date": "2026-11-01", "end_date": "2026-11-03"}, "date_in_past", "start_date"),
    ({"end_date": "2026-11-19"}, "beyond_forecast_horizon", "end_date"),
    ({"temperature_unit": "kelvin"}, "invalid_unit", "temperature_unit"),
])
def test_invalid_requests_are_refused_without_calling_the_provider(params, code, field):
    meteo = OpenMeteo(AMMAN)
    r = api(service(meteo)).get("/api/weather", params={**TRIP, **params})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code and r.json()["error"]["field"] == field
    assert r.json()["data_status"] == "UNAVAILABLE" and meteo.requests == []


def test_the_forecast_horizon_is_the_providers_and_never_extended():
    with pytest.raises(WeatherError) as raised:
        validate_query(**PLACE, start_date="2026-11-10", end_date="2026-11-30", today=TODAY)
    assert raised.value.details == {"forecast_available_until": "2026-11-18"}
    assert validate_query(**PLACE, end_date="2026-11-18", today=TODAY).end_date == dt.date(2026, 11, 18)


def test_yesterday_in_utc_is_allowed_because_the_place_may_still_be_there():
    # 00:30 UTC: in Honolulu (UTC-10) it is still the previous day.
    assert validate_query(latitude="21.3", longitude="-157.9", start_date="2026-11-02", today=TODAY).start_date \
        == dt.date(2026, 11, 2)


# ------------------------------------------------------------------ missing and malformed data
def test_missing_values_stay_null_and_are_never_filled_in():
    meteo = OpenMeteo(with_daily(temperature_2m_max=[None, 22.1, 20.8], precipitation_probability_max=[150, None],
                                 weather_code=[42, None, 3], wind_speed_10m_max="oops",
                                 wind_direction_10m_dominant=[400, 10, 20]))
    days = service(meteo).forecast(**TRIP)["days"]
    assert days[0]["temperature_max"] is None and days[0]["precipitation_probability_max_pct"] is None
    assert days[0]["condition"] == "unknown" and days[1]["condition"] is None and days[1]["wet"] is None
    assert all(d["wind_speed_max_kmh"] is None for d in days) and days[0]["wind_direction_dominant_deg"] is None
    assert days[1]["precipitation_probability_max_pct"] is None  # list too short


def test_a_day_the_provider_left_out_is_reported_missing():
    meteo = OpenMeteo(with_daily(time=["2026-11-03", "2026-11-05"]))
    body = service(meteo).forecast(**TRIP)
    assert [d["date"] for d in body["days"]] == ["2026-11-03", "2026-11-05"]
    assert body["missing_dates"] == ["2026-11-04"] and any("2026-11-04" in n for n in body["notices"])


def test_rain_codes_are_marked_wet():
    meteo = OpenMeteo(with_daily(weather_code=[61, 95, 2]))
    assert [d["wet"] for d in service(meteo).forecast(**TRIP)["days"]] == [True, True, False]


# ------------------------------------------------------------------ provider failures
@pytest.mark.parametrize("reply, status, code, retryable", [
    (httpx.ReadTimeout("slow"), 504, "provider_timeout", True),
    (httpx.ConnectError("down"), 503, "provider_unavailable", True),
    (httpx.Response(429, json={"error": True, "reason": "Daily API request limit exceeded"}), 503,
     "provider_rate_limited", True),
    (httpx.Response(500), 502, "provider_error", True),
    (httpx.Response(400, json={"error": True, "reason": "Cannot initialize WeatherVariable"}), 502,
     "provider_rejected", False),
    (httpx.Response(200, json={"error": True, "reason": "?"}), 502, "provider_rejected", False),
    (httpx.Response(200, text="<html>"), 502, "provider_bad_response", True),
    (httpx.Response(200, json={"latitude": 31.9}), 502, "provider_bad_response", True),
    (httpx.Response(200, json={"daily": {"time": "2026-11-03"}}), 502, "provider_bad_response", True),
    (httpx.Response(200, json=[1, 2]), 502, "provider_bad_response", True),
])
def test_provider_failures_are_reported_never_filled_in(reply, status, code, retryable):
    r = api(service(OpenMeteo(reply))).get("/api/weather", params=TRIP)
    assert r.status_code == status
    body = r.json()
    assert body["error"]["code"] == code and body["error"]["retryable"] is retryable
    assert body["data_status"] == "UNAVAILABLE" and "days" not in body


def test_a_failure_is_not_cached():
    meteo = OpenMeteo(httpx.ConnectError("down"), AMMAN)
    svc = service(meteo)
    with pytest.raises(WeatherError):
        svc.forecast(**TRIP)
    assert svc.forecast(**TRIP)["data_status"] == "LIVE" and len(meteo.requests) == 2


# ------------------------------------------------------------------ cache and limits
def test_a_cached_answer_says_cached_and_keeps_its_retrieval_time():
    now, tick = [NOW], [0.0]
    meteo = OpenMeteo(AMMAN)
    svc = service(meteo, clock=lambda: now[0], monotonic=lambda: tick[0])
    svc.forecast(**TRIP)
    now[0], tick[0] = NOW + 600, 600.0
    again = svc.forecast(**{**TRIP, "latitude": "31.9541"})  # about 20 m away: the same forecast cell
    assert again["data_status"] == "CACHED" and again["retrieved_at"] == "2026-11-03T12:00:00Z"
    assert again["cache_expires_at"] == "2026-11-03T12:30:00Z" and len(meteo.requests) == 1


def test_expired_cache_entries_are_never_served():
    tick = [0.0]
    meteo = OpenMeteo(AMMAN)
    svc = service(meteo, monotonic=lambda: tick[0])
    svc.forecast(**TRIP)
    tick[0] = 1800.0
    assert svc.forecast(**TRIP)["data_status"] == "LIVE" and len(meteo.requests) == 2


def test_the_cache_is_bounded():
    meteo = OpenMeteo(AMMAN)
    svc = service(meteo, cache_entries=2)
    for day in ("2026-11-03", "2026-11-04", "2026-11-05"):
        svc.forecast(**PLACE, start_date=day)
    assert svc.forecast(**PLACE, start_date="2026-11-05")["data_status"] == "CACHED"
    assert svc.forecast(**PLACE, start_date="2026-11-03")["data_status"] == "LIVE"  # evicted, fetched again
    assert len(svc._cache) == 2


def test_provider_calls_are_capped_per_minute_and_per_day():
    tick = [0.0]
    svc = service(OpenMeteo(AMMAN), monotonic=lambda: tick[0], max_calls_per_minute=2, max_calls_per_day=3)
    svc.forecast(**PLACE, start_date="2026-11-03")
    svc.forecast(**PLACE, start_date="2026-11-04")
    with pytest.raises(WeatherError) as raised:
        svc.forecast(**PLACE, start_date="2026-11-05")
    assert raised.value.code == "rate_limited" and raised.value.status == 429
    assert svc.forecast(**PLACE, start_date="2026-11-03")["data_status"] == "CACHED"  # never counts
    tick[0] = 61.0
    svc.forecast(**PLACE, start_date="2026-11-05")
    tick[0] = 122.0
    with pytest.raises(WeatherError) as raised:
        svc.forecast(**PLACE, start_date="2026-11-06")
    assert raised.value.code == "daily_limit_reached"


# ------------------------------------------------------------------ production and secrets
@pytest.mark.parametrize("env, key, flag, allowed", [
    ("development", None, None, True), ("test", None, None, True),
    ("production", None, None, False), ("production", None, "false", False),
    ("production", None, "true", True), ("production", "paid-key", None, True),
])
def test_production_needs_a_paid_key_or_a_stated_non_commercial_use(monkeypatch, env, key, flag, allowed):
    for name, value in (("RIHLA_OPEN_METEO_API_KEY", key), ("RIHLA_WEATHER_NONCOMMERCIAL", flag)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert provider_allowed(env)[0] is allowed


def test_production_without_permission_says_unavailable_and_calls_nobody(monkeypatch):
    monkeypatch.setenv("RIHLA_ENV", "production")
    monkeypatch.delenv("RIHLA_OPEN_METEO_API_KEY", raising=False)
    monkeypatch.delenv("RIHLA_WEATHER_NONCOMMERCIAL", raising=False)
    client = api(WeatherService(clock=lambda: NOW))
    status = client.get("/api/weather/status").json()
    assert status["available"] is False and "non-commercial" in status["notice"]
    r = client.get("/api/weather", params=TRIP)
    assert r.status_code == 503 and r.json()["error"]["code"] == "weather_unavailable"
    assert r.json()["data_status"] == "UNAVAILABLE" and "days" not in r.json()


def test_a_paid_key_goes_to_the_customer_endpoint_and_never_into_answers_or_logs(caplog):
    caplog.set_level(logging.INFO)
    meteo = OpenMeteo(AMMAN)
    svc = service(meteo, api_key="secret-key-123", environment="production")
    body = api(svc).get("/api/weather", params=TRIP).text
    sent = meteo.requests[0].url
    assert str(sent).startswith(CUSTOMER_URL) and sent.params["apikey"] == "secret-key-123"
    assert "secret-key-123" not in body and "secret-key-123" not in repr(svc.provider)
    assert "HTTP Request" in caplog.text and "apikey=REDACTED" in caplog.text  # httpx logs the URL
    assert "secret-key-123" not in caplog.text


def test_status_in_development():
    status = service(OpenMeteo(AMMAN)).status()
    assert status["available"] is True and status["provider"] == "Open-Meteo" and status["forecast_days"] == 16
    assert status["limits"]["scope"] == "per server process"


def test_weather_is_never_simulated():
    body = service(OpenMeteo(AMMAN)).forecast(**TRIP)
    assert body["data_status"] in ("LIVE", "CACHED") and "SIMULATED" not in json.dumps(body)
    source = "".join(p.read_text(encoding="utf-8") for p in Path("app/weather").glob("*.py"))
    assert "random" not in source


def test_install_is_idempotent_read_only_and_needs_no_sign_in():
    app = FastAPI()
    install_weather(app)
    count = len(app.router.routes)
    install_weather(app)
    assert len(app.router.routes) == count
    paths = {p: set(ops) for p, ops in app.openapi()["paths"].items() if p.startswith("/api/weather")}
    assert paths == {"/api/weather": {"get"}, "/api/weather/status": {"get"}}
    from app.auth.middleware import PROTECTED_PREFIXES
    assert not any("/api/weather".startswith(p) for p in PROTECTED_PREFIXES)
