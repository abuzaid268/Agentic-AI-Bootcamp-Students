"""Server-side verification of Firebase ID tokens (Google sign-in), without a service account.

It follows Firebase's documented procedure for third-party JWT libraries: an RS256 signature by one of Google's
`securetoken` keys, audience = the project ID, issuer = https://securetoken.google.com/<project ID>, a non-empty
`sub` (the stable Firebase user ID), and iat / auth_time / exp in the right order. Rihla also requires the
sign-in to be Google's and recent, so an old leaked ID token cannot open a new session.
"""
import re
import ssl
import threading
import time
from collections.abc import Callable
from typing import Any

import certifi
import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate

CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
CLOCK_SKEW_S = 60
MAX_SIGN_IN_AGE_S = 5 * 60  # a session is opened only from a sign-in made in the last five minutes


class TokenError(Exception):
    """The ID token is not a valid, recent Google sign-in for this Firebase project. The message is safe to show."""


def _tls_context() -> ssl.SSLContext:
    """TLS verification against the operating system's trusted roots and certifi's. The OS store matters on
    Windows machines whose antivirus scans HTTPS with its own root (certifi alone rejects Google there);
    certifi covers Python builds that ship an empty system store. Certificates are always verified."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


class GoogleCertificates:
    """Google's current public keys by key ID, cached for as long as Google's Cache-Control allows."""

    def __init__(self, url: str = CERTS_URL, timeout: float = 10.0):
        self._url = url
        self._timeout = timeout
        self._keys: dict[str, Any] = {}
        self._expires = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> dict[str, Any]:
        with self._lock:
            if time.time() < self._expires and self._keys:
                return self._keys
            try:
                response = httpx.get(self._url, timeout=self._timeout, verify=_tls_context())
                response.raise_for_status()
                certs = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                if self._keys:  # Google unreachable: keep using the keys we have
                    return self._keys
                raise TokenError("Google's sign-in keys could not be loaded. Please try again.") from exc
            self._keys = {
                kid: load_pem_x509_certificate(pem.encode()).public_key() for kid, pem in certs.items()
            }
            match = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
            self._expires = time.time() + (int(match.group(1)) if match else 3600)
            return self._keys


class FirebaseTokenVerifier:
    def __init__(self, project_id: str, keys: Callable[[], dict[str, Any]] | None = None,
                 clock: Callable[[], float] = time.time):
        self.project_id = project_id
        self._keys = keys or GoogleCertificates()
        self._clock = clock

    def verify(self, token: str) -> dict[str, Any]:
        """The token's claims, or TokenError."""
        if not self.project_id:
            raise TokenError("Sign-in is not configured on the server.")
        if not isinstance(token, str) or token.count(".") != 2 or len(token) > 8192:
            raise TokenError("The sign-in token is malformed.")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenError("The sign-in token is malformed.") from exc
        if header.get("alg") != "RS256":
            raise TokenError("The sign-in token is not signed the way Firebase signs ID tokens.")
        key = self._keys().get(str(header.get("kid") or ""))
        if key is None:
            raise TokenError("The sign-in token was not signed by Google.")

        # PyJWT checks the signature, audience and issuer; the times are checked below against self._clock.
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self.project_id,
                issuer=f"https://securetoken.google.com/{self.project_id}",
                options={"require": ["exp", "iat", "aud", "iss", "sub"], "verify_exp": False, "verify_iat": False,
                         "verify_nbf": False},
            )
        except jwt.PyJWTError as exc:
            raise TokenError("The sign-in token is not valid for Rihla.") from exc

        now = self._clock()
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)) or exp < now - CLOCK_SKEW_S:
            raise TokenError("The sign-in has expired. Please sign in again.")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub or len(sub) > 128:
            raise TokenError("The sign-in token has no user ID.")
        iat, auth_time = claims.get("iat"), claims.get("auth_time")
        if not isinstance(iat, (int, float)) or iat > now + CLOCK_SKEW_S:
            raise TokenError("The sign-in token was issued in the future.")
        if not isinstance(auth_time, (int, float)) or auth_time > now + CLOCK_SKEW_S:
            raise TokenError("The sign-in token has no valid sign-in time.")
        if now - auth_time > MAX_SIGN_IN_AGE_S:
            raise TokenError("That sign-in is too old to open a session. Please sign in again.")
        if (claims.get("firebase") or {}).get("sign_in_provider") != "google.com":
            raise TokenError("Only Google sign-in is accepted.")
        return claims
