"""The Open-Meteo licence decision, shared by app/weather (forecast) and app/destinations (geocoding).

Open-Meteo's free API is for non-commercial use only (https://open-meteo.com/en/terms); commercial use needs a
paid plan, whose key ("apikey") goes to the customer- servers (https://open-meteo.com/en/docs/geocoding-api:
"requires the prefix customer-"). A public deployment is not automatically non-commercial, so production calls
Open-Meteo only when the team has decided, explicitly:
- RIHLA_OPEN_METEO_API_KEY: a paid plan's key (commercial use licensed), or
- RIHLA_OPEN_METEO_NONCOMMERCIAL=true: the deployment is non-commercial (no ads, no subscriptions).
Development and test may use the free API (a bootcamp project's development is non-commercial).
"""
from __future__ import annotations

import logging
import os
import re

NONCOMMERCIAL_FLAG = "RIHLA_OPEN_METEO_NONCOMMERCIAL"
API_KEY_VAR = "RIHLA_OPEN_METEO_API_KEY"


def api_key() -> str | None:
    return (os.getenv(API_KEY_VAR) or "").strip() or None


def licence_allows(environment: str) -> tuple[bool, str | None]:
    """Whether this deployment may call Open-Meteo, and why not."""
    if environment != "production":
        return True, None
    if api_key():
        return True, None
    if (os.getenv(NONCOMMERCIAL_FLAG) or "").strip().lower() in ("1", "true", "yes"):
        return True, None
    return False, (f"Open-Meteo's free API is for non-commercial use only. In production set {API_KEY_VAR} "
                   f"(paid plan) or, for a non-commercial deployment, {NONCOMMERCIAL_FLAG}=true.")


class _RedactApiKey(logging.Filter):
    """httpx logs every request URL at INFO; Open-Meteo's paid plan puts the key in the URL (&apikey=...)."""

    _pattern = re.compile(r"(apikey=)[^&\s\"']+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "apikey=" in message.lower():
            record.msg, record.args = self._pattern.sub(r"\1REDACTED", message), ()
        return True


def protect_httpx_logs() -> None:
    """Hide apikey values in httpx's request logs (idempotent)."""
    logger = logging.getLogger("httpx")
    if not any(isinstance(f, _RedactApiKey) for f in logger.filters):
        logger.addFilter(_RedactApiKey())
