"""The signed-in user's profile: their Google identity (read-only) and their travel preferences.

GET /api/profile                 {"user": {...}, "preferences": {...}, "updated_at": ..., "saved": bool,
                                  "supports": {"activity_pace": bool}}
PUT /api/profile/preferences     {home_currency?, budget_style?, interests?, walking_tolerance?, max_walk_minutes?,
                                  activity_pace?}

Persistence contract: the preferences ARE the Trip Store traveller preferences, the same record the travel MCP
tools get_preferences / save_preferences read and write (persistent memory). The traveller is always the
signed-in user's own (traveller_id_for_request()): no endpoint takes a traveller ID, so nobody can read or write
another user's profile. Fields and values are the Trip Store's (services/travel_api.py PREF_FIELDS); interests
use the planner's tags (app/research_adapter.py INTEREST_WORDS: history, art, markets, nature, food, ...).
The Trip Store merges a PUT into what is stored. It is the kit's simulated store: it keeps preferences while the
travel API runs and resets when that service restarts or is reset.

activity_pace (relaxed | balanced | packed) is newer than the kit's Trip Store: it is saved only when the store
says it accepts it (its /health lists "preference_fields", app/auth/ACTIVITY_PACE.md). Until then GET reports
supports.activity_pace = false and a PUT with it is refused (422 field_not_supported, nothing saved), never
stored somewhere else or pretended.
"""
import os
import threading
import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import sessions
from app.auth.identity import current_user, traveller_id_for_request

router = APIRouter(prefix="/api/profile", tags=["profile"])
NO_STORE = {"Cache-Control": "no-store"}
EDITABLE = ("home_currency", "budget_style", "interests", "walking_tolerance", "max_walk_minutes", "activity_pace")
NEWER_FIELDS = ("activity_pace",)  # saved only when the Trip Store lists them in its preference_fields
SUPPORT_TTL_S = 30


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    budget_style: Literal["budget", "mid-range", "splurge"] | None = None
    interests: list[str] | None = Field(default=None, max_length=20)
    walking_tolerance: Literal["low", "medium", "high"] | None = None
    max_walk_minutes: int | None = Field(default=None, ge=5, le=240)
    activity_pace: Literal["relaxed", "balanced", "packed"] | None = None


class StoreUnavailable(Exception):
    pass


def _store(method: str, path: str, body: dict | None = None) -> httpx.Response:
    url = (os.getenv("TRAVEL_API_URL") or "http://localhost:8103").rstrip("/")
    key = os.getenv("TRAVEL_API_KEY")
    if not key:
        raise StoreUnavailable("Travel API key is not configured.")
    try:
        with httpx.Client(timeout=15.0) as client:
            return client.request(method, f"{url}{path}", json=body, headers={"X-API-Key": key})
    except httpx.HTTPError as exc:
        raise StoreUnavailable("The Trip Store could not be reached.") from exc


_support_cache: dict[str, Any] = {"at": 0.0, "fields": None}
_support_lock = threading.Lock()


def store_supports() -> dict[str, bool]:
    """Which NEWER_FIELDS the Trip Store accepts, from its own /health ("preference_fields"); cached briefly.
    An older store (no list), or one that cannot be reached, supports none of them."""
    with _support_lock:
        if time.monotonic() - _support_cache["at"] > SUPPORT_TTL_S or _support_cache["fields"] is None:
            try:
                fields = _json(_store("GET", "/health")).get("preference_fields")
            except StoreUnavailable:
                fields = None
            _support_cache.update(at=time.monotonic(), fields=set(fields) if isinstance(fields, list) else set())
        fields = _support_cache["fields"]
    return {name: name in fields for name in NEWER_FIELDS}


def forget_store_support() -> None:
    """Tests only: check the Trip Store again on the next request."""
    with _support_lock:
        _support_cache.update(at=0.0, fields=None)


def _json(r: httpx.Response) -> dict[str, Any]:
    try:
        body = r.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail, "code": code}, status_code=status, headers=NO_STORE)


def _not_signed_in() -> JSONResponse:
    return _error(401, "auth_required", "Please log in to see your profile.")


def _not_supported() -> JSONResponse:
    return _error(422, "field_not_supported", "Activity pace cannot be saved yet: Rihla's Trip Store does not "
                  "support it so far. Nothing was saved.")


def _editable(preferences: Any) -> dict[str, Any]:
    """The stored preferences the profile edits (other fields, e.g. dietary or notes, are kept but not shown)."""
    prefs = preferences if isinstance(preferences, dict) else {}
    return {k: prefs[k] for k in EDITABLE if k in prefs}


@router.get("")
def get_profile():
    user = current_user()
    if user is None:
        return _not_signed_in()  # whatever RIHLA_AUTH_REQUIRED says: a profile is always private
    try:
        r = _store("GET", f"/api/travellers/{traveller_id_for_request()}/preferences")
    except StoreUnavailable as exc:
        return _error(503, "profile_store_unavailable", f"{exc} Your preferences could not be loaded.")
    if r.status_code == 404:  # nothing saved yet for this traveller
        record: dict[str, Any] = {}
    elif r.is_success:
        record = _json(r)
    else:
        return _error(503, "profile_store_unavailable", "The Trip Store refused the request. Please try again.")
    return JSONResponse({
        "user": sessions.public_user(user),
        "preferences": _editable(record.get("preferences")),
        "updated_at": record.get("updated_at"),
        "saved": bool(record),
        "supports": store_supports(),
    }, headers=NO_STORE)


@router.put("/preferences")
def save_preferences(body: PreferencesUpdate):
    if current_user() is None:
        return _not_signed_in()
    update = body.model_dump(exclude_none=True)
    if "interests" in update:
        update["interests"] = list(dict.fromkeys(i.strip().lower()[:40] for i in update["interests"] if i.strip()))
    if not update:
        return _error(422, "nothing_to_save", "Choose at least one preference to save.")
    supports = store_supports()
    unsupported = [f for f in NEWER_FIELDS if f in update and not supports[f]]
    if unsupported:
        return _not_supported()
    try:
        r = _store("PUT", f"/api/travellers/{traveller_id_for_request()}/preferences", update)
    except StoreUnavailable as exc:
        return _error(503, "profile_store_unavailable", f"{exc} Your preferences were not saved.")
    if r.status_code == 422:  # the store's own validation (it lists what is allowed)
        error = _json(r).get("error") or {}
        if error.get("code") == "unknown_field" and any(f in update for f in NEWER_FIELDS):
            forget_store_support()
            return _not_supported()
        detail = error.get("message")
        return _error(422, "invalid_preferences", detail or "The Trip Store did not accept these preferences.")
    if not r.is_success:
        return _error(503, "profile_store_unavailable", "The Trip Store could not save your preferences. Please try again.")
    record = _json(r)
    return JSONResponse({"preferences": _editable(record.get("preferences")), "updated_at": record.get("updated_at"),
                         "saved": True}, headers=NO_STORE)
