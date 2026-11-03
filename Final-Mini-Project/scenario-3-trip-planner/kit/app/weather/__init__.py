"""Daily weather forecast from Open-Meteo: GET /api/weather.  See docs/weather.md.

The app's owner installs it with one line, like app/auth:  install_weather(app)
"""
from fastapi import FastAPI

from .routes import router
from .service import OpenMeteoProvider, WeatherError, WeatherQuery, WeatherService, normalize_forecast, \
    validate_query

__all__ = ["install_weather", "router", "OpenMeteoProvider", "WeatherError", "WeatherQuery", "WeatherService",
           "normalize_forecast", "validate_query"]


def install_weather(app: FastAPI, service: WeatherService | None = None) -> FastAPI:
    """Add GET /api/weather to the app; calling it twice changes nothing. `service` replaces the default, e.g. in
    tests."""
    if not getattr(app.state, "rihla_weather_installed", False):
        app.include_router(router)
        app.state.rihla_weather_installed = True
    if service is not None:
        app.state.weather_service = service
    return app
