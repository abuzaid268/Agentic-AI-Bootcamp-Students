"""Security of the signed-in web app, with two real accounts (Alice and Bob).

Real here: app.main's endpoints behind install_auth (RIHLA_AUTH_REQUIRED=true: verified Firebase ID tokens,
HttpOnly session cookies, CSRF origin checks, session ownership), the approval policy, MCP save_trip into a real
Trip Store process, and GET /api/trips. The identities are test Firebase ID tokens signed with a test key the
verifier is given (tests/test_auth.py): the same verification code a real Google sign-in goes through.
TEST FIXTURE (labelled): the planning pipeline's result (test_my_trips_journey.planned / test_accept_unverified).
"""
import time
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

from app.auth import sessions
from app.auth.config import settings
from test_accept_unverified import accept, unverified
from test_auth import ORIGIN, OTHER_KEY, PROJECT, auth_env, id_token, real_app, sign_in  # noqa: F401
from test_mcp_integration import api, travel_api  # noqa: F401  (a real Trip Store process)
from test_my_trips_journey import decide, plan, planned, store_trips, traveller, user

EVIL = {"Origin": "https://evil.example"}
PROTECTED = [("post", "/api/chat", {"session_id": "s", "message": "Plan 2 days in Istanbul"}),
             ("post", "/api/approve", {"session_id": "s", "action_id": "a", "approved": True}),
             ("post", "/api/accept", {"session_id": "s", "acceptance_id": "a", "acknowledged": True, "mode": "x"}),
             ("post", "/api/whatif", {"session_id": "s", "scenario": {"type": "rain"}}),
             ("post", "/api/whatif/options", {"session_id": "s"}),
             ("post", "/api/whatif/apply", {"session_id": "s", "proposal_id": "p"}),
             ("get", "/api/trips", None), ("get", "/api/trips/TRIP-3001", None), ("get", "/api/profile", None)]


def call(client, method, path, body, headers=ORIGIN):
    return client.get(path) if method == "get" else client.post(path, json=body, headers=headers)


def test_every_protected_endpoint_refuses_no_session_a_garbage_one_and_an_expired_one():
    s = settings()
    expired, _ = sessions.issue(sessions.user_from_claims({"sub": "u"}, PROJECT), s, now=time.time() - 10**6)
    for cookie in (None, "garbage", expired):
        client = TestClient(real_app())
        if cookie:
            client.cookies.set(sessions.COOKIE_NAME, cookie)
        for method, path, body in PROTECTED:
            r = call(client, method, path, body)
            assert r.status_code == 401, (cookie and cookie[:10], path, r.status_code)
            assert r.json()["code"] == "auth_required"


def test_sign_in_needs_a_valid_google_id_token_for_this_project():
    client = TestClient(real_app())
    now = int(time.time())
    bad = {
        "expired": id_token(exp=now - 60, iat=now - 4000, auth_time=now - 4000),
        "other project": id_token(aud="someone-elses-project", iss="https://securetoken.google.com/someone-elses-project"),
        "forged signature": id_token(key=OTHER_KEY),
        "unknown key": id_token(kid="k-unknown"),
        "no subject": id_token(sub=""),
        "not a token": "not-a-jwt",
    }
    for why, token in bad.items():
        r = client.post("/api/auth/session", json={"id_token": token}, headers=ORIGIN)
        # refused by the verifier (401), or before it by the request's own validation (422: not a JWT at all)
        assert r.status_code in (401, 422), why
        assert r.status_code == 422 or r.json()["code"] == "invalid_sign_in", why
        assert sessions.COOKIE_NAME not in r.cookies, why
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/session", json={"id_token": id_token()}, headers=EVIL)
    assert r.status_code == 403  # a sign-in started from another site is refused (CSRF)


def test_the_traveller_comes_from_the_verified_session_never_from_the_request(api):
    alice = user("alice")
    # Alice names Bob's traveller in the request body (the contract's optional `user`): ignored when signed in.
    with patch("app.main.orchestrate_trip", return_value=planned()):
        r = alice.post("/api/chat", headers=ORIGIN, json={"session_id": "s-a", "message": "Plan 2 days in Istanbul",
                                                          "user": {"traveller_id": traveller("bob")}})
    action = r.json()["pending_action"]
    assert action["payload"]["traveller_id"] == traveller("alice")
    assert decide(alice, "s-a", action["action_id"]).json()["status"] == "approved"
    [rec] = store_trips(api)
    assert rec["traveller_id"] == traveller("alice") != traveller("bob")
    assert user("bob").get("/api/trips").json()["count"] == 0


def test_bob_cannot_read_list_approve_accept_revise_or_whatif_alices_trips(api):
    alice, bob = user("alice"), user("bob")
    approved = plan(alice, "s-alice", planned())
    unsure = plan(alice, "s-alice-2", unverified())
    # Bob reuses Alice's planning sessions: refused before any endpoint runs
    for path, body in (("/api/approve", {"session_id": "s-alice", "action_id": approved["pending_action"]["action_id"],
                                         "approved": True}),
                       ("/api/accept", {"session_id": "s-alice-2", "acceptance_id":
                                        unsure["pending_acceptance"]["acceptance_id"], "acknowledged": True,
                                        "mode": unsure["pending_acceptance"]["mode"]}),
                       ("/api/chat", {"session_id": "s-alice", "message": "Cut the budget", "revision": True}),
                       ("/api/whatif", {"session_id": "s-alice", "scenario": {"type": "rain"}}),
                       ("/api/whatif/options", {"session_id": "s-alice"}),
                       ("/api/whatif/apply", {"session_id": "s-alice", "proposal_id": "p"})):
        r = bob.post(path, json=body, headers=ORIGIN)
        assert r.status_code == 403 and r.json()["code"] == "session_not_yours", path
    assert store_trips(api) == []  # nothing Bob did saved anything

    # Alice saves both; Bob cannot list or open them, by id or by guessing the next ids
    trip_a = decide(alice, "s-alice", approved["pending_action"]["action_id"]).json()["result"]["trip_id"]
    trip_b = accept(alice, "s-alice-2", unsure["pending_acceptance"]).json()["result"]["trip_id"]
    assert bob.get("/api/trips").json()["count"] == 0
    for trip_id in (trip_a, trip_b, "TRIP-3001", "TRIP-3002", "TRIP-9999", "../travellers"):
        assert bob.get(f"/api/trips/{trip_id}").status_code == 404, trip_id
    assert {t["trip_id"] for t in alice.get("/api/trips").json()["trips"]} == {trip_a, trip_b}

    # Bob manages his own trip
    mine = plan(bob, "s-bob", planned())
    trip_bob = decide(bob, "s-bob", mine["pending_action"]["action_id"]).json()["result"]["trip_id"]
    assert [t["trip_id"] for t in bob.get("/api/trips").json()["trips"]] == [trip_bob]
    assert alice.get(f"/api/trips/{trip_bob}").status_code == 404


def test_a_write_with_the_session_cookie_from_another_site_is_refused(api):
    alice = user("alice")
    data = plan(alice, "s-x", planned())
    for path, body in (("/api/approve", {"session_id": "s-x", "action_id": data["pending_action"]["action_id"],
                                         "approved": True}),
                       ("/api/chat", {"session_id": "s-x", "message": "hi"}),
                       ("/api/auth/logout", None)):
        r = alice.post(path, json=body, headers=EVIL)
        assert r.status_code == 403 and r.json()["code"] == "origin_not_allowed", path
    r = alice.post("/api/approve", json={"session_id": "s-x", "action_id": data["pending_action"]["action_id"],
                                         "approved": True})  # no Origin header at all
    assert r.status_code == 403
    assert store_trips(api) == []


def test_no_cross_origin_reads_are_granted():
    client = TestClient(real_app())
    r = client.options("/api/trips", headers={**EVIL, "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
    r = client.get("/api/auth/config", headers=EVIL)
    assert "access-control-allow-origin" not in r.headers


def test_logout_survives_a_backend_restart_with_a_revocation_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RIHLA_SESSION_DB_PATH", str(tmp_path / "sessions.sqlite3"))
    sessions.forget_revocations()
    client = TestClient(real_app())
    sign_in(client, "alice")
    stolen = client.cookies.get(sessions.COOKIE_NAME)
    assert client.post("/api/auth/logout", headers=ORIGIN).json() == {"status": "logged_out"}
    sessions.forget_revocations()  # what a restarted backend starts with: nothing in memory
    replay = TestClient(real_app())
    replay.cookies.set(sessions.COOKIE_NAME, stolen)
    assert replay.get("/api/auth/me").status_code == 401
    assert replay.get("/api/trips").status_code == 401
    monkeypatch.delenv("RIHLA_SESSION_DB_PATH")
    sessions.forget_revocations()


def test_a_session_cannot_be_forged_or_widened_by_the_browser():
    client = TestClient(real_app())
    sign_in(client, "alice")
    real = client.cookies.get(sessions.COOKIE_NAME)
    claims = jwt.decode(real, options={"verify_signature": False})
    # change the traveller to Bob's without the server's secret: the signature no longer matches
    tampered = jwt.encode({**claims, "tid": sessions.traveller_id_for("bob", PROJECT)}, "not-the-secret" * 4,
                          algorithm="HS256")
    other = TestClient(real_app())
    other.cookies.set(sessions.COOKIE_NAME, tampered)
    assert other.get("/api/auth/me").status_code == 401
    unsigned = jwt.encode({**claims}, None, algorithm="none") if "none" in jwt.algorithms.get_default_algorithms() \
        else real[:-4] + "AAAA"
    other.cookies.set(sessions.COOKIE_NAME, unsigned)
    assert other.get("/api/auth/me").status_code == 401


def test_responses_carry_no_secret_token_or_cookie_value():
    client = TestClient(real_app())
    signed = sign_in(client, "alice")
    cookie = client.cookies.get(sessions.COOKIE_NAME)
    set_cookie = signed.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/" in set_cookie
    for r in (signed, client.get("/api/auth/me"), client.get("/api/auth/config")):
        assert settings().session_secret not in r.text and cookie not in r.text
        assert r.headers.get("cache-control") == "no-store"
    assert "id_token" not in client.get("/api/auth/me").text
