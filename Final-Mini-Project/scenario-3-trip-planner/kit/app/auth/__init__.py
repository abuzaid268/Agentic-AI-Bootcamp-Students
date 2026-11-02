"""Rihla sign-in: Google through Firebase Authentication, verified on the server, kept as an HttpOnly session.

    from app.auth import install_auth, traveller_id_for_request
    install_auth(app)          # once, right after `app = FastAPI(...)`

See app/auth/INTEGRATION.md for the settings and the two-line change app/main.py needs.
"""
from fastapi import FastAPI

from app.auth.identity import current_user, traveller_id_for_request
from app.auth.middleware import AuthMiddleware
from app.auth.routes import router

__all__ = ["install_auth", "current_user", "traveller_id_for_request"]


def install_auth(app: FastAPI) -> FastAPI:
    """Add the sign-in endpoints and AuthMiddleware to the app; calling it twice changes nothing."""
    if getattr(app.state, "rihla_auth_installed", False):
        return app
    app.include_router(router)
    app.add_middleware(AuthMiddleware)
    app.state.rihla_auth_installed = True
    return app
