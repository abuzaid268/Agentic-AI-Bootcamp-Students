"""Worldwide destination (city) search: GET /api/destinations?q=…  See docs/destinations.md.

The app's owner installs it with one line, like app/auth:  install_destinations(app)
"""
from fastapi import FastAPI

from .routes import router
from .service import DestinationError, DestinationSearch, normalize_query, normalize_result

__all__ = ["install_destinations", "router", "DestinationError", "DestinationSearch", "normalize_query",
           "normalize_result"]


def install_destinations(app: FastAPI, service: DestinationSearch | None = None) -> FastAPI:
    """Add GET /api/destinations to the app; calling it twice changes nothing. `service` replaces the default
    (Open-Meteo) search, e.g. in tests."""
    if not getattr(app.state, "rihla_destinations_installed", False):
        app.include_router(router)
        app.state.rihla_destinations_installed = True
    if service is not None:
        app.state.destination_search = service
    return app
