"""Flight search and price comparison: GET /api/flights.  See docs/flights.md.

Informational only: Rihla never books flights, creates orders or takes payments.
The app's owner installs it with one line, like app/auth:  install_flights(app)
"""
from fastapi import FastAPI

from .providers import DemoProvider, DuffelProvider, UnavailableProvider, normalize_duffel_offer, provider_from_env
from .routes import router
from .service import FlightError, FlightQuery, FlightSearch, validate_query

__all__ = ["install_flights", "router", "DemoProvider", "DuffelProvider", "FlightError", "FlightQuery",
           "FlightSearch", "UnavailableProvider", "normalize_duffel_offer", "provider_from_env", "validate_query"]


def install_flights(app: FastAPI, service: FlightSearch | None = None) -> FastAPI:
    """Add GET /api/flights to the app; calling it twice changes nothing. `service` replaces the default (the
    provider chosen from the environment: Duffel, or DEMO data), e.g. in tests."""
    if not getattr(app.state, "rihla_flights_installed", False):
        app.include_router(router)
        app.state.rihla_flights_installed = True
    if service is not None:
        app.state.flight_search = service
    return app
