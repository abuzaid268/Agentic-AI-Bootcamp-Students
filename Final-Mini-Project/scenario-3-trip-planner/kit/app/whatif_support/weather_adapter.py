"""Feeds Rihla's weather service (app/weather) to the WHAT IF rain scenario.

app/whatif.py forecast_rain() (backup/rihla-integration-wip branch) asks a read tool for
    read_tool("get_weather", {"city", "start_date", "end_date"})
and reads the kit's get_weather result: {"ok", "kind": "forecast", "mode": "live"|"replay", "source",
"days": [{"date", "precip_mm", "precip_probability_pct"}]}. Rain counts as confirmed only for kind "forecast" and
mode "live" (planning/verification.py freshness_of). This module builds that same result from app/weather, which
works by coordinates and has no replay cache:
    read_tool = make_weather_read_tool(WeatherService(), latitude, longitude)
    forecast_rain(destination, dates, read_tool)          # Member 1's code, unchanged

Honesty rules: only a real provider answer (data_status LIVE, or CACHED: the same answer fetched minutes ago) is
"live". Fixture or simulated weather is labelled mode "simulated", which forecast_rain treats as not live, so the
rain stays hypothetical. No answer (an error, or dates past the forecast horizon) is {"ok": False, ...}.
"""
from __future__ import annotations

from typing import Any, Callable

from app.weather.service import WeatherError

RAIN_MM, RAIN_PROBABILITY = 1.0, 60  # as app/whatif.py (WIP branch): a day counts as rainy at or above either


def to_get_weather_result(answer: Any) -> dict:
    """An app/weather answer as a get_weather result."""
    if not isinstance(answer, dict) or answer.get("data_status") not in ("LIVE", "CACHED") \
            or not isinstance(answer.get("days"), list):
        return {"ok": False, "error": {"code": "weather_unavailable", "message": "No real forecast is available."}}
    celsius = (answer.get("units") or {}).get("temperature") == "°C"
    days = []
    for d in answer["days"]:
        if not isinstance(d, dict) or not isinstance(d.get("date"), str):
            continue
        row = {"date": d["date"], "weather_code": d.get("weather_code"), "summary": d.get("condition"),
               "precip_mm": d.get("precipitation_sum_mm"),
               "precip_probability_pct": d.get("precipitation_probability_max_pct")}
        if celsius:
            row.update(temp_max_c=d.get("temperature_max"), temp_min_c=d.get("temperature_min"))
        days.append(row)
    source = answer.get("source") or {}
    return {"ok": True, "kind": "forecast", "mode": "live", "stale": False, "data_status": answer["data_status"],
            "days": days, "source": "Open-Meteo forecast API", "source_url": source.get("url"),
            "licence": source.get("licence"), "retrieved_at": answer.get("retrieved_at"),
            "timezone": (answer.get("location") or {}).get("timezone")}


def simulated_weather(days: list[dict], note: str) -> dict:
    """Weather for a fixture or a demo, in the get_weather shape but marked "simulated": never live, so a WHAT IF
    built on it says the rain is hypothetical."""
    return {"ok": True, "kind": "forecast", "mode": "simulated", "stale": False, "data_status": "SIMULATED",
            "days": [dict(d) for d in days], "source": "Simulated for a WHAT IF fixture", "note": note}


def make_weather_read_tool(service: Any, latitude: float, longitude: float) -> Callable[[str, dict], dict]:
    """A read_tool for forecast_rain() that answers get_weather from app/weather for these coordinates (the city
    argument is not needed: the trip's destination coordinates already say where)."""

    def read_tool(name: str, args: dict) -> dict:
        if name != "get_weather":
            return {"ok": False, "error": {"code": "unsupported_tool", "message": f"Only get_weather is served, not {name}."}}
        try:
            answer = service.forecast(latitude=latitude, longitude=longitude, start_date=(args or {}).get("start_date"),
                                      end_date=(args or {}).get("end_date"))
        except WeatherError as error:
            return {"ok": False, "error": {"code": error.code, "message": error.message}}
        return to_get_weather_result(answer)

    return read_tool


def rainy_dates(result: Any, *, mm: float = RAIN_MM, probability: float = RAIN_PROBABILITY) -> list[str]:
    """The dates a live result shows as rainy (the same rule as forecast_rain); [] for anything not live."""
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("kind") != "forecast" \
            or result.get("mode") != "live" or result.get("stale"):
        return []
    return [str(d.get("date")) for d in result.get("days") or [] if isinstance(d, dict) and (
        (d.get("precip_mm") or 0) >= mm or (d.get("precip_probability_pct") or 0) >= probability)]
