"""The Rihla session: an HttpOnly cookie holding a signed (HS256) token, opened only from a verified sign-in.

The browser's JavaScript never sees it, so a script injected into the page cannot steal it. Logging out revokes
the session's ID on this server, not just in the browser. Revocations are kept in memory: a server restart forgets
them, so sessions are also short (RIHLA_SESSION_TTL_HOURS).
"""
import hashlib
import secrets
import threading
import time
from typing import Any

import jwt

from app.auth.config import AuthSettings

COOKIE_NAME = "rihla_session"
ISSUER = "rihla-api"
AUDIENCE = "rihla-web"

_revoked: dict[str, float] = {}  # session ID -> when the session would have expired
_revoked_lock = threading.Lock()


def traveller_id_for(uid: str, project_id: str) -> str:
    """The user's own Trip Store traveller ID: stable for one Google account, never chosen by the browser, and
    free of personal data. It fits the Trip Store's pattern (letters, digits, - _ . ; 2-40 characters)."""
    digest = hashlib.sha256(f"{project_id}:{uid}".encode()).hexdigest()
    return f"RIHLA-{digest[:24]}"


def user_from_claims(claims: dict[str, Any], project_id: str) -> dict[str, Any]:
    """The identity Rihla keeps from a verified Firebase ID token."""
    uid = str(claims["sub"])
    email = claims.get("email") if claims.get("email_verified") else None
    return {
        "uid": uid,
        "name": str(claims.get("name") or "").strip()[:120] or (email.split("@")[0] if email else "Traveller"),
        "email": email,
        "picture": str(claims.get("picture") or "")[:500] or None,
        "traveller_id": traveller_id_for(uid, project_id),
    }


def issue(user: dict[str, Any], s: AuthSettings, now: float | None = None) -> tuple[str, int]:
    """A signed session token for the user and when it expires (Unix seconds)."""
    now = int(now if now is not None else time.time())
    exp = now + s.session_ttl_s
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": exp, "sid": secrets.token_urlsafe(18),
        "sub": user["uid"], "name": user["name"], "email": user["email"], "picture": user["picture"],
        "tid": user["traveller_id"],
    }
    return jwt.encode(claims, s.session_secret, algorithm="HS256"), exp


def read(token: str | None, s: AuthSettings, now: float | None = None) -> dict[str, Any] | None:
    """The signed-in user of a session token, or None when it is missing, forged, expired or logged out."""
    if not token or not s.configured or len(token) > 4096:
        return None
    try:
        claims = jwt.decode(token, s.session_secret, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                            options={"require": ["exp", "iat", "sid", "sub"], "verify_exp": False})
    except jwt.PyJWTError:
        return None
    now = now if now is not None else time.time()
    if claims["exp"] <= now or is_revoked(claims["sid"], now):
        return None
    return {
        "uid": claims["sub"], "name": claims.get("name") or "Traveller", "email": claims.get("email"),
        "picture": claims.get("picture"), "traveller_id": claims.get("tid"), "session_id": claims["sid"],
        "expires_at": int(claims["exp"]),
    }


def revoke(session_id: str, expires_at: float) -> None:
    with _revoked_lock:
        now = time.time()
        for sid in [sid for sid, exp in _revoked.items() if exp <= now]:
            del _revoked[sid]
        _revoked[session_id] = expires_at


def is_revoked(session_id: str, now: float | None = None) -> bool:
    with _revoked_lock:
        exp = _revoked.get(session_id)
    return exp is not None and exp > (now if now is not None else time.time())


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """What the browser is told about the signed-in user."""
    return {key: user.get(key) for key in ("uid", "name", "email", "picture", "expires_at")}
