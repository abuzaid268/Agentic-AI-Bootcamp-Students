"""GET /api/auth/config: the Firebase web settings the login modal needs, from the server's environment.

A copy of Rihla without rihla-frontend/.env.local (another person's clone, the Docker image) can still sign in:
the browser takes the public web config from its backend. The project is always the one ID tokens are verified
against; the response names missing settings, and never contains the session secret. Placeholder values only.
"""
from fastapi.testclient import TestClient

from test_auth import PROJECT, auth_env, real_app  # noqa: F401  (auth_env: autouse env)

SECRET = "s" * 48  # what auth_env sets as RIHLA_SESSION_SECRET


def config(monkeypatch, **env):
    for name in ("RIHLA_FIREBASE_WEB_API_KEY", "RIHLA_FIREBASE_APP_ID", "RIHLA_FIREBASE_AUTH_DOMAIN",
                 "VITE_FIREBASE_API_KEY", "VITE_FIREBASE_APP_ID", "VITE_FIREBASE_AUTH_DOMAIN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    r = TestClient(real_app()).get("/api/auth/config")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert SECRET not in r.text
    return r.json()


def test_the_web_config_comes_from_the_server_with_the_verified_project(monkeypatch):
    body = config(monkeypatch, RIHLA_FIREBASE_WEB_API_KEY="web-key", RIHLA_FIREBASE_APP_ID="1:2:web:3")
    assert body["configured"] is True and body["missing"] == []
    assert body["web"] == {"apiKey": "web-key", "authDomain": f"{PROJECT}.firebaseapp.com", "projectId": PROJECT,
                           "appId": "1:2:web:3"}


def test_the_frontend_vite_names_are_accepted_but_never_change_the_project(monkeypatch):
    body = config(monkeypatch, VITE_FIREBASE_API_KEY="web-key", VITE_FIREBASE_APP_ID="1:2:web:3",
                  VITE_FIREBASE_AUTH_DOMAIN="custom.example.com", VITE_FIREBASE_PROJECT_ID="someone-else")
    assert body["web"]["projectId"] == PROJECT and body["web"]["authDomain"] == "custom.example.com"


def test_missing_settings_are_named_and_no_partial_config_is_given(monkeypatch):
    body = config(monkeypatch, RIHLA_FIREBASE_WEB_API_KEY="web-key")
    assert body["web"] is None and body["missing"] == ["RIHLA_FIREBASE_APP_ID"]
    monkeypatch.delenv("RIHLA_SESSION_SECRET")
    monkeypatch.delenv("RIHLA_FIREBASE_PROJECT_ID")
    body = config(monkeypatch)
    assert body["configured"] is False and body["web"] is None
    assert body["missing"] == ["RIHLA_FIREBASE_PROJECT_ID", "RIHLA_SESSION_SECRET (at least 32 characters)",
                               "RIHLA_FIREBASE_WEB_API_KEY", "RIHLA_FIREBASE_APP_ID"]
