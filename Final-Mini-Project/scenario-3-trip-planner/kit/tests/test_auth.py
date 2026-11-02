"""Rihla sign-in (app/auth): Firebase ID-token verification, the HttpOnly session, access rules, CSRF and isolation.
No network and no real Google account: tokens are signed here with a test RSA key the verifier is given."""
import inspect
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import current_user, install_auth, traveller_id_for_request
from app.auth import sessions
from app.auth.config import settings
from app.auth.firebase_tokens import FirebaseTokenVerifier, TokenError
from app.auth.middleware import forget_sessions
import app.main as app_main
from app.main import app as main_app
from app.memory import sessions as memory_sessions
from test_api import make_pending_trip

PROJECT = "rihla-test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ORIGIN = {"Origin": "http://localhost:5173"}


def id_token(sub="google-user-1", key=KEY, kid="k1", algorithm="RS256", **claims):
    now = int(time.time())
    body = {
        "iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": sub, "iat": now,
        "exp": now + 3600, "auth_time": now, "email": f"{sub}@example.com", "email_verified": True,
        "name": f"User {sub}", "picture": "https://example.com/a.png", "firebase": {"sign_in_provider": "google.com"},
    }
    body.update(claims)
    return jwt.encode(body, key, algorithm=algorithm, headers={"kid": kid})


def verifier():
    return FirebaseTokenVerifier(PROJECT, keys=lambda: {"k1": KEY.public_key()})


@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    monkeypatch.setenv("RIHLA_FIREBASE_PROJECT_ID", PROJECT)
    monkeypatch.setenv("RIHLA_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", "true")
    monkeypatch.setenv("TRAVEL_TRAVELLER_ID", "TRV-101")
    monkeypatch.delenv("RIHLA_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("RIHLA_COOKIE_SECURE", raising=False)
    forget_sessions()


def stub_app():
    """Endpoints at the protected paths that only report who the middleware says is calling."""
    app = FastAPI()

    def who():
        user = current_user()
        return {"uid": user["uid"] if user else None, "traveller_id": traveller_id_for_request()}

    @app.post("/api/chat")
    def chat(body: dict):
        return who()

    @app.post("/api/approve")
    def approve(body: dict):
        return who()

    @app.get("/api/trips")
    def trips():
        return who()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    install_auth(app)
    app.state.rihla_token_verifier = verifier()
    return app


def real_app():
    """app.main's real endpoints behind install_auth, without changing app.main's own app object."""
    app = FastAPI()
    app.router.routes.extend(main_app.router.routes)
    install_auth(app)
    app.state.rihla_token_verifier = verifier()
    return app


def sign_in(client, sub="google-user-1"):
    r = client.post("/api/auth/session", json={"id_token": id_token(sub)}, headers=ORIGIN)
    assert r.status_code == 200, r.text
    return r


# --- The ID token -------------------------------------------------------------------------------------------

def test_a_valid_google_sign_in_is_accepted():
    claims = verifier().verify(id_token())
    assert claims["sub"] == "google-user-1"


@pytest.mark.parametrize("token", [
    id_token(aud="another-project"),
    id_token(iss="https://securetoken.google.com/another-project"),
    id_token(kid="unknown-kid"),
    id_token(key=OTHER_KEY),
    id_token(exp=int(time.time()) - 600),
    id_token(sub=""),
    id_token(auth_time=int(time.time()) - 3600),
    id_token(iat=int(time.time()) + 3600),
    id_token(firebase={"sign_in_provider": "password"}),
    jwt.encode({"sub": "x", "aud": PROJECT}, "a-shared-secret-that-is-long-enough!", algorithm="HS256",
               headers={"kid": "k1"}),
    "not.a.token",
])
def test_anything_but_a_recent_google_sign_in_for_this_project_is_refused(token):
    with pytest.raises(TokenError):
        verifier().verify(token)


# --- The session --------------------------------------------------------------------------------------------

def test_signing_in_sets_an_httponly_session_cookie_and_me_returns_the_user():
    client = TestClient(stub_app())
    r = sign_in(client)
    cookie = r.headers["set-cookie"].lower()
    assert "rihla_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    user = r.json()["user"]
    assert user["uid"] == "google-user-1" and user["name"] == "User google-user-1"
    assert "traveller_id" not in user  # the browser never sees or chooses it
    assert client.get("/api/auth/me").json()["user"]["email"] == "google-user-1@example.com"


def test_a_refused_token_opens_no_session():
    client = TestClient(stub_app())
    r = client.post("/api/auth/session", json={"id_token": id_token(key=OTHER_KEY)}, headers=ORIGIN)
    assert r.status_code == 401 and "set-cookie" not in r.headers
    assert client.get("/api/auth/me").status_code == 401


def test_without_configuration_sign_in_is_unavailable_and_says_so(monkeypatch):
    monkeypatch.setenv("RIHLA_SESSION_SECRET", "too-short")
    r = TestClient(stub_app()).post("/api/auth/session", json={"id_token": id_token()}, headers=ORIGIN)
    assert r.status_code == 503 and r.json()["code"] == "auth_not_configured"


def test_a_forged_or_expired_session_cookie_is_no_session():
    s = settings()
    user = sessions.user_from_claims({"sub": "u1", "name": "U"}, PROJECT)
    forged = jwt.encode({"sub": "u1", "sid": "x", "iat": 1, "exp": 2**31, "iss": sessions.ISSUER,
                         "aud": sessions.AUDIENCE}, "a-different-secret-" * 3, algorithm="HS256")
    expired, _ = sessions.issue(user, s, now=time.time() - s.session_ttl_s - 10)
    for token in (forged, expired, "garbage"):
        client = TestClient(stub_app())
        client.cookies.set(sessions.COOKIE_NAME, token)
        assert client.get("/api/auth/me").status_code == 401
        r = client.post("/api/chat", json={"session_id": "s1"}, headers=ORIGIN)
        assert r.status_code == 401 and "expired" in r.json()["detail"]


def test_logout_ends_the_session_on_the_server_not_only_in_the_browser():
    client = TestClient(stub_app())
    sign_in(client)
    stolen = client.cookies.get(sessions.COOKIE_NAME)
    assert client.post("/api/auth/logout", headers=ORIGIN).json() == {"status": "logged_out"}
    assert client.get("/api/auth/me").status_code == 401
    replay = TestClient(stub_app())
    replay.cookies.set(sessions.COOKIE_NAME, stolen)
    assert replay.get("/api/auth/me").status_code == 401


# --- Access rules -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/chat", {"session_id": "s1", "message": "Plan Amman"}),
    ("post", "/api/approve", {"session_id": "s1", "action_id": "a1", "approved": True}),
    ("get", "/api/trips", None),
    ("get", "/api/trips/TRIP-1", None),
])
def test_the_real_trip_endpoints_refuse_an_anonymous_call_when_sign_in_is_required(method, path, body):
    client = TestClient(real_app())
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 401 and r.json()["code"] == "auth_required"
    assert client.get("/health").json() == {"status": "ok"}


def test_with_sign_in_optional_the_official_contract_stays_open(monkeypatch):
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", "false")
    r = TestClient(real_app()).post("/api/approve", json={"session_id": "eval-1", "action_id": "a", "approved": True})
    assert r.status_code == 404  # reached the real endpoint: no pending action in that session


def test_a_signed_in_user_gets_their_own_traveller_and_an_anonymous_call_the_demo_one(monkeypatch):
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", "false")
    alice, bob, anonymous = (TestClient(stub_app()) for _ in range(3))
    sign_in(alice, "alice")
    sign_in(bob, "bob")
    a = alice.get("/api/trips").json()
    b = bob.get("/api/trips").json()
    assert a["uid"] == "alice" and a["traveller_id"].startswith("RIHLA-")
    assert b["traveller_id"] != a["traveller_id"]
    assert a["traveller_id"] == alice.get("/api/trips").json()["traveller_id"]  # stable
    assert anonymous.get("/api/trips").json() == {"uid": None, "traveller_id": "TRV-101"}


def test_a_planning_session_cannot_be_used_by_another_account_or_anonymously(monkeypatch):
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", "false")
    alice, bob, anonymous = (TestClient(stub_app()) for _ in range(3))
    sign_in(alice, "alice")
    sign_in(bob, "bob")
    assert alice.post("/api/chat", json={"session_id": "s-alice"}, headers=ORIGIN).status_code == 200
    for intruder in (bob, anonymous):
        r = intruder.post("/api/approve", json={"session_id": "s-alice", "action_id": "a", "approved": True},
                          headers=ORIGIN)
        assert r.status_code == 403 and r.json()["code"] == "session_not_yours"
    assert alice.post("/api/approve", json={"session_id": "s-alice"}, headers=ORIGIN).status_code == 200


# --- CSRF ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}, {"Origin": "null"}])
def test_sign_in_and_cookie_carrying_writes_must_come_from_the_rihla_web_app(headers):
    client = TestClient(stub_app())
    r = client.post("/api/auth/session", json={"id_token": id_token()}, headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "origin_not_allowed"
    sign_in(client)
    r = client.post("/api/chat", json={"session_id": "s1"}, headers=headers)
    assert r.status_code == 403
    assert client.post("/api/chat", json={"session_id": "s1"}, headers=ORIGIN).status_code == 200


def test_an_allowed_origin_can_be_configured(monkeypatch):
    monkeypatch.setenv("RIHLA_ALLOWED_ORIGINS", "https://rihla.example")
    client = TestClient(stub_app())
    assert client.post("/api/auth/session", json={"id_token": id_token()}, headers=ORIGIN).status_code == 403
    r = client.post("/api/auth/session", json={"id_token": id_token()}, headers={"Origin": "https://rihla.example"})
    assert r.status_code == 200 and "secure" in r.headers["set-cookie"].lower()  # https origin: Secure cookie


# --- Isolation in the real endpoints (needs app/main.py to use traveller_id_for_request: INTEGRATION.md) ------

INTEGRATED = "traveller_id_for_request" in inspect.getsource(app_main)
needs_integration = pytest.mark.skipif(
    not INTEGRATED, reason="app/main.py does not use app.auth's traveller_id_for_request yet (app/auth/INTEGRATION.md)")


@needs_integration
def test_each_user_lists_and_opens_only_their_own_saved_trips():
    alice_tid = sessions.traveller_id_for("alice", PROJECT)
    bob_tid = sessions.traveller_id_for("bob", PROJECT)
    store = {"TRIP-A": {"trip_id": "TRIP-A", "traveller_id": alice_tid, "itinerary": {"travellers": 1}},
             "TRIP-B": {"trip_id": "TRIP-B", "traveller_id": bob_tid, "itinerary": {"travellers": 2}}}
    listing = lambda tid: [{"trip_id": t["trip_id"]} for t in store.values() if t["traveller_id"] == tid]  # noqa: E731
    alice, bob = TestClient(real_app()), TestClient(real_app())
    sign_in(alice, "alice")
    sign_in(bob, "bob")
    with patch("app.main.list_trips_from_store", side_effect=listing), \
            patch("app.main.get_trip_from_store", side_effect=lambda trip_id: store.get(trip_id)):
        assert [t["trip_id"] for t in alice.get("/api/trips").json()["trips"]] == ["TRIP-A"]
        assert [t["trip_id"] for t in bob.get("/api/trips").json()["trips"]] == ["TRIP-B"]
        assert alice.get("/api/trips/TRIP-B").status_code == 404
        assert bob.get("/api/trips/TRIP-B").status_code == 200


@needs_integration
def test_an_approved_trip_is_saved_for_the_signed_in_user_never_the_shared_traveller():
    memory_sessions.clear()
    make_pending_trip("s-alice")
    alice = TestClient(real_app())
    sign_in(alice, "alice")
    with patch("app.main.save_trip_to_store", return_value={"trip_id": "TRIP-9"}) as save:
        r = alice.post("/api/approve", json={"session_id": "s-alice", "action_id": "correct-id", "approved": True},
                       headers=ORIGIN)
    assert r.status_code == 200, r.text
    assert save.call_args.kwargs["traveller_id"] == sessions.traveller_id_for("alice", PROJECT)


def test_install_auth_is_idempotent():
    app = FastAPI()
    install_auth(app)
    install_auth(app)
    assert len(app.user_middleware) == 1 and len(app.router.routes) == len(install_auth(FastAPI()).router.routes)
    assert TestClient(app).get("/api/auth/me").status_code == 401
