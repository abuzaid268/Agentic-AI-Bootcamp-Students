"""GET /api/weather: the daily forecast for coordinates and dates (Open-Meteo). Read-only, no sign-in needed.
(Not to be confused with the kit's travel API /api/weather on port 8103, which takes a city name.)"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from .service import WeatherError, WeatherService

router = APIRouter(prefix="/api/weather", tags=["weather"])


def _service(request: Request) -> WeatherService:
    service = getattr(request.app.state, "weather_service", None)
    if service is None:
        service = request.app.state.weather_service = WeatherService()
    return service


@router.get("/status")
def weather_status(request: Request):
    """Whether forecasts can be shown here, before asking for one."""
    return JSONResponse(_service(request).status(), headers={"Cache-Control": "no-store"})


@router.get("")
def weather_forecast(
    request: Request,
    latitude: str = Query("", max_length=20, description="-90 to 90"),
    longitude: str = Query("", max_length=20, description="-180 to 180"),
    start_date: str = Query("", max_length=10, description="YYYY-MM-DD, default today"),
    end_date: str = Query("", max_length=10, description="YYYY-MM-DD, default start_date; at most 16 days ahead"),
    temperature_unit: str = Query("celsius", max_length=12, description="celsius or fahrenheit"),
):
    try:
        answer = _service(request).forecast(latitude=latitude, longitude=longitude, start_date=start_date,
                                            end_date=end_date, temperature_unit=temperature_unit)
    except WeatherError as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
        return JSONResponse(error.as_dict(), status_code=error.status, headers=headers)
    return JSONResponse(answer, headers={"Cache-Control": "private, max-age=600"})
