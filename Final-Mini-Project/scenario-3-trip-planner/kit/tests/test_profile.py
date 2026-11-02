"""The profile endpoints (app/auth/profile.py): always private, the signed-in user's own Trip Store preferences
only, validated, and honest about the store being unavailable. A fake Trip Store keeps the real one's rules."""
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import install_auth
from app.auth import sessions
from app.auth.profile import StoreUnavailable, forget_store_support
from test_auth import ORIGIN, PROJECT, auth_env, sign_in, verifier  # noqa: F401  (auth_env: autouse env)

PREF_FIELDS = {"budget_style", "interests", "dietary", "walking_tolerance", "max_walk_minutes", "home_currency",
               "travel_party", "notes"}


class FakeTripStore:
    """services/travel_api.py's preference endpoints: 404 until something is saved, PUT merges, unknown -> 422.
    pace=True is the store after Developer 3's patch (app/auth/patches/activity_pace_travel_api.patch)."""

    def __init__(self, pace=False):
        self.travellers = {}
        self.calls = []
        self.fields = PREF_FIELDS | ({"activity_pace"} if pace else set())
        self.pace = pace

    def __call__(self, method, path, body=None):
        if path == "/health":
            return httpx.Response(200, json={"status": "ok", **({"preference_fields": sorted(self.fields)}
                                                                 if self.pace else {})})
        self.calls.append((method, path))
        tid = path.split("/")[3]
        if method == "GET":
            t = self.travellers.get(tid)
            if t is None:
                return httpx.Response(404, json={"error": {"code": "traveller_not_found"}})
            return httpx.Response(200, json=t)
        unknown = set(body) - self.fields
        if unknown:
            return httpx.Response(422, json={"error": {"code": "unknown_field", "message": f"Unknown: {sorted(unknown)}"}})
        t = self.travellers.setdefault(tid, {"traveller_id": tid, "preferences": {}, "updated_at": None})
        t["preferences"].update(body)
        t["updated_at"] = "2026-11-02T12:00:00Z"
        return httpx.Response(200, json=t)


@pytest.fixture(autouse=True)
def fresh_support_check():
    forget_store_support()
    yield
    forget_store_support()


@pytest.fixture
def store():
    fake = FakeTripStore()
    with patch("app.auth.profile._store", side_effect=fake):
        yield fake


@pytest.fixture
def pace_store():
    fake = FakeTripStore(pace=True)
    with patch("app.auth.profile._store", side_effect=fake):
        yield fake


def profile_app():
    app = FastAPI()
    install_auth(app)
    app.state.rihla_token_verifier = verifier()
    return app


def signed_in(sub):
    client = TestClient(profile_app())
    sign_in(client, sub)
    return client


@pytest.mark.parametrize("required", ["true", "false"])
def test_a_profile_is_private_whatever_the_access_mode(monkeypatch, store, required):
    monkeypatch.setenv("RIHLA_AUTH_REQUIRED", required)
    guest = TestClient(profile_app())
    assert guest.get("/api/profile").status_code == 401
    r = guest.put("/api/profile/preferences", json={"budget_style": "budget"}, headers=ORIGIN)
    assert r.status_code == 401
    assert store.calls == []


def test_a_new_user_sees_their_google_identity_and_no_saved_preferences(store):
    r = signed_in("alice").get("/api/profile")
    body = r.json()
    assert r.status_code == 200
    assert body["user"]["name"] == "User alice" and body["user"]["email"] == "alice@example.com"
    assert body["preferences"] == {} and body["saved"] is False
    assert "traveller_id" not in body["user"]


def test_saved_preferences_come_back_and_are_merged(store):
    alice = signed_in("alice")
    r = alice.put("/api/profile/preferences", headers=ORIGIN, json={
        "home_currency": "EUR", "budget_style": "mid-range", "interests": ["History", "food", "history"],
        "walking_tolerance": "low", "max_walk_minutes": 20})
    assert r.status_code == 200 and r.json()["saved"] is True
    assert r.json()["preferences"]["interests"] == ["history", "food"]  # lower-cased, de-duplicated
    alice.put("/api/profile/preferences", headers=ORIGIN, json={"budget_style": "splurge"})
    prefs = alice.get("/api/profile").json()["preferences"]
    assert prefs == {"home_currency": "EUR", "budget_style": "splurge", "interests": ["history", "food"],
                     "walking_tolerance": "low", "max_walk_minutes": 20}


def test_each_user_reads_and_writes_only_their_own_traveller(store):
    alice, bob = signed_in("alice"), signed_in("bob")
    alice.put("/api/profile/preferences", headers=ORIGIN, json={"budget_style": "budget"})
    assert bob.get("/api/profile").json()["preferences"] == {}
    bob.put("/api/profile/preferences", headers=ORIGIN, json={"budget_style": "splurge"})
    assert alice.get("/api/profile").json()["preferences"] == {"budget_style": "budget"}
    paths = {path for _, path in store.calls}
    assert paths == {f"/api/travellers/{sessions.traveller_id_for(u, PROJECT)}/preferences" for u in ("alice", "bob")}


def test_preferences_other_rihla_parts_saved_are_kept_but_not_shown(store):
    alice = signed_in("alice")
    tid = sessions.traveller_id_for("alice", PROJECT)
    store.travellers[tid] = {"traveller_id": tid, "updated_at": "x",
                             "preferences": {"dietary": ["vegetarian"], "notes": "early riser", "budget_style": "budget"}}
    assert alice.get("/api/profile").json()["preferences"] == {"budget_style": "budget"}
    alice.put("/api/profile/preferences", headers=ORIGIN, json={"walking_tolerance": "high"})
    assert store.travellers[tid]["preferences"]["dietary"] == ["vegetarian"]  # the memory's own fields survive


def test_saving_currency_and_walking_keeps_the_stored_budget_style_and_interests(store):
    # The profile page no longer edits budget style or interests (chosen per trip); saving must not erase them.
    alice = signed_in("alice")
    tid = sessions.traveller_id_for("alice", PROJECT)
    store.travellers[tid] = {"traveller_id": tid, "updated_at": "x",
                             "preferences": {"budget_style": "budget", "interests": ["history", "local food"]}}
    r = alice.put("/api/profile/preferences", headers=ORIGIN,
                  json={"home_currency": "JOD", "walking_tolerance": "high", "max_walk_minutes": 45})
    assert r.status_code == 200
    assert store.travellers[tid]["preferences"] == {
        "budget_style": "budget", "interests": ["history", "local food"],
        "home_currency": "JOD", "walking_tolerance": "high", "max_walk_minutes": 45}
    after = alice.get("/api/profile").json()["preferences"]  # what a refresh shows
    assert after["home_currency"] == "JOD" and after["budget_style"] == "budget"


@pytest.mark.parametrize("body", [
    {"home_currency": "euro"},
    {"budget_style": "cheap"},
    {"walking_tolerance": "extreme"},
    {"max_walk_minutes": 2},
    {"max_walk_minutes": 999},
    {"interests": ["x"] * 21},
    {"traveller_id": "TRV-101", "budget_style": "budget"},  # never choose whose profile to write
    {"pace": "relaxed"},  # the Trip Store has no pace field yet
])
def test_invalid_or_unsupported_preferences_are_refused_and_nothing_is_saved(store, body):
    r = signed_in("alice").put("/api/profile/preferences", headers=ORIGIN, json=body)
    assert r.status_code == 422
    assert not [c for c in store.calls if c[0] == "PUT"]


def test_an_empty_update_is_refused(store):
    r = signed_in("alice").put("/api/profile/preferences", headers=ORIGIN, json={})
    assert r.status_code == 422 and r.json()["code"] == "nothing_to_save"


def test_an_unreachable_store_is_reported_never_a_pretend_save():
    alice = signed_in("alice")
    with patch("app.auth.profile._store", side_effect=StoreUnavailable("The Trip Store could not be reached.")):
        assert alice.get("/api/profile").status_code == 503
        r = alice.put("/api/profile/preferences", headers=ORIGIN, json={"budget_style": "budget"})
    assert r.status_code == 503 and "not saved" in r.json()["detail"]


def test_saving_needs_the_rihla_origin_and_logout_ends_access(store):
    alice = signed_in("alice")
    r = alice.put("/api/profile/preferences", json={"budget_style": "budget"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    alice.post("/api/auth/logout", headers=ORIGIN)
    assert alice.get("/api/profile").status_code == 401


# --- Activity pace ------------------------------------------------------------------------------------------

def test_todays_trip_store_does_not_support_pace_and_saving_it_is_refused_not_pretended(store):
    alice = signed_in("alice")
    assert alice.get("/api/profile").json()["supports"] == {"activity_pace": False}
    r = alice.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "relaxed", "home_currency": "EUR"})
    assert r.status_code == 422 and r.json()["code"] == "field_not_supported" and "Nothing was saved" in r.json()["detail"]
    assert not [c for c in store.calls if c[0] == "PUT"]  # not even the currency: one save is all or nothing
    assert "activity_pace" not in str(store.travellers)  # and never put into another field


def test_a_store_that_rejects_pace_after_all_is_reported_the_same_way(pace_store):
    alice = signed_in("alice")
    assert alice.get("/api/profile").json()["supports"]["activity_pace"] is True
    pace_store.fields = PREF_FIELDS  # the store was swapped for an older one since the check
    r = alice.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "packed"})
    assert r.status_code == 422 and r.json()["code"] == "field_not_supported"


def test_with_the_patched_store_pace_is_saved_merged_and_reloaded(pace_store):
    alice = signed_in("alice")
    assert alice.get("/api/profile").json()["supports"] == {"activity_pace": True}
    alice.put("/api/profile/preferences", headers=ORIGIN,
              json={"home_currency": "EUR", "walking_tolerance": "low", "max_walk_minutes": 20})
    r = alice.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "relaxed"})
    assert r.status_code == 200 and r.json()["preferences"]["activity_pace"] == "relaxed"
    prefs = alice.get("/api/profile").json()["preferences"]  # a refresh
    assert prefs == {"home_currency": "EUR", "walking_tolerance": "low", "max_walk_minutes": 20, "activity_pace": "relaxed"}
    alice.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "packed"})
    assert alice.get("/api/profile").json()["preferences"]["activity_pace"] == "packed"  # one value at a time


def test_pace_comes_back_after_logout_and_is_independent_per_user(pace_store):
    alice, bob = signed_in("alice"), signed_in("bob")
    alice.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "relaxed"})
    bob.put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": "packed"})
    alice.post("/api/auth/logout", headers=ORIGIN)
    again = signed_in("alice")
    assert again.get("/api/profile").json()["preferences"]["activity_pace"] == "relaxed"
    assert bob.get("/api/profile").json()["preferences"]["activity_pace"] == "packed"


@pytest.mark.parametrize("value", ["fast", "", "Relaxed", 3])
def test_only_the_three_paces_are_accepted(pace_store, value):
    r = signed_in("alice").put("/api/profile/preferences", headers=ORIGIN, json={"activity_pace": value})
    assert r.status_code == 422
    assert not [c for c in pace_store.calls if c[0] == "PUT"]
