"""Airport search for departure and arrival: GET /api/airports?q=…  See docs/airports.md.

The app's owner installs it with one line, like app/auth:  install_airports(app)
"""
from fastapi import FastAPI

from .routes import router
from .service import (AirportError, AirportSearch, normalize_airport, normalize_coordinates, normalize_country,
                      normalize_query)

__all__ = ["install_airports", "router", "AirportError", "AirportSearch", "normalize_airport", "normalize_coordinates",
           "normalize_country", "normalize_query"]


def install_airports(app: FastAPI, service: AirportSearch | None = None) -> FastAPI:
    """Add GET /api/airports to the app; calling it twice changes nothing. `service` replaces the default
    (bundled OurAirports data) search, e.g. in tests."""
    if not getattr(app.state, "rihla_airports_installed", False):
        app.include_router(router)
        app.state.rihla_airports_installed = True
    if service is not None:
        app.state.airport_search = service
    return app
