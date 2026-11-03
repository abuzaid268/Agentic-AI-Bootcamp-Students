"""Start-up checks for a production deployment: python -m app.deployment_check  (exit 0 = may start).

docker-compose.prod.yml runs this once, as the prod-guard service, and starts travel-api and app only when it
succeeds. Compose's own ${TRAVEL_API_KEY:?} refuses an unset or empty key but cannot compare values, so the kit's
public default key (services/travel_api.py falls back to it) would otherwise be accepted.

Never prints a secret: only which check failed.
"""
from __future__ import annotations

import os
import sys

KNOWN_DEV_KEYS = frozenset({"dev-key-change-me"})  # the kit's public default (services/travel_api.py)


def problems(environ: dict | None = None) -> list[str]:
    """What stops this deployment from starting; [] when it may start."""
    env = os.environ if environ is None else environ
    key = (env.get("TRAVEL_API_KEY") or "").strip()
    if not key:
        return ["TRAVEL_API_KEY is missing or empty: set a private key for production."]
    if key.lower() in KNOWN_DEV_KEYS:
        return ["TRAVEL_API_KEY is the kit's public development key: set a private key for production."]
    return []


def main() -> int:
    found = problems()
    for problem in found:
        print(f"Refusing to start: {problem}", file=sys.stderr)
    if not found:
        print("Production start-up checks passed.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
