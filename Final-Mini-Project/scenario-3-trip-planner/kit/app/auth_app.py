"""The Rihla API with sign-in installed, for the web app:  uvicorn app.auth_app:app --port 8000

It is app.main's app plus app/auth (the /api/auth endpoints and AuthMiddleware). Once app/main.py calls
install_auth itself (app/auth/INTEGRATION.md), `app.main:app` and this module serve the same thing.
"""
from app.auth import install_auth
from app.main import app

install_auth(app)
