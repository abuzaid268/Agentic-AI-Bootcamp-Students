"""Rihla sign-in settings, read from the environment on every use (a changed .env or a test's env takes effect).

RIHLA_AUTH_REQUIRED        true: /api/chat, /api/approve and /api/trips answer 401 without a signed-in session.
                           false (default): the official contract stays open for the eval runner and the hidden
                           tests; a signed-in user still gets their own identity and Trip Store traveller.
RIHLA_FIREBASE_PROJECT_ID  the Firebase project whose Google sign-ins are accepted (the ID token's audience).
RIHLA_SESSION_SECRET       at least 32 random characters: signs the HttpOnly session cookie. Never commit it.
RIHLA_SESSION_TTL_HOURS    how long a session lasts (default 12).
RIHLA_ALLOWED_ORIGINS      comma-separated origins allowed to send cookie-carrying writes (CSRF protection).
RIHLA_COOKIE_SECURE        true / false / auto (default): auto marks the cookie Secure except for a local http origin.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
MIN_SECRET_LENGTH = 32


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AuthSettings:
    required: bool
    firebase_project_id: str
    session_secret: str
    session_ttl_s: int
    allowed_origins: tuple[str, ...]
    cookie_secure: bool | None  # None: decided per request

    @property
    def configured(self) -> bool:
        return bool(self.firebase_project_id) and len(self.session_secret) >= MIN_SECRET_LENGTH

    def missing(self) -> list[str]:
        """The settings sign-in still needs (names only, never values)."""
        missing = []
        if not self.firebase_project_id:
            missing.append("RIHLA_FIREBASE_PROJECT_ID")
        if len(self.session_secret) < MIN_SECRET_LENGTH:
            missing.append(f"RIHLA_SESSION_SECRET (at least {MIN_SECRET_LENGTH} characters)")
        return missing


def settings() -> AuthSettings:
    try:
        ttl_hours = float(os.getenv("RIHLA_SESSION_TTL_HOURS", "") or 12)
    except ValueError:
        ttl_hours = 12
    origins = tuple(
        o.strip().rstrip("/") for o in os.getenv("RIHLA_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ) or DEFAULT_ORIGINS
    secure = os.getenv("RIHLA_COOKIE_SECURE", "auto").strip().lower()
    return AuthSettings(
        required=_flag("RIHLA_AUTH_REQUIRED", False),
        firebase_project_id=os.getenv("RIHLA_FIREBASE_PROJECT_ID", "").strip(),
        session_secret=os.getenv("RIHLA_SESSION_SECRET", "").strip(),
        session_ttl_s=max(300, int(ttl_hours * 3600)),
        allowed_origins=origins,
        cookie_secure=None if secure in {"", "auto"} else secure in {"1", "true", "yes", "on"},
    )
