"""Which kind of deployment this server is: RIHLA_ENV = development | test | production.

Used by Member 3's external-data integrations (app/flights, app/weather, app/destinations) to decide what they may
show:
- development: sample (DEMO) data is allowed, always labelled as such;
- test: as development, plus provider sandboxes; never live paid calls;
- production: real, licensed provider data only; when there is none, the feature says it is unavailable.

Not set -> development, so a laptop run needs no setup. A server cannot tell by itself whether it is someone's
laptop or a public launch, so production is made explicit by the deployment tooling, not guessed here:
docker-compose.prod.yml sets RIHLA_ENV=production literally (see DOCKER.md / docs/deployment-readiness.md).
Not set, or set to an unknown value, is logged once as a warning. An unknown value counts as production, so a
typo fails closed (no sample data reaches real users).
"""
from __future__ import annotations

import logging
import os

ENVIRONMENTS = ("development", "test", "production")
log = logging.getLogger("rihla.deployment")
_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        log.warning(message)


def deployment_env() -> str:
    raw = (os.getenv("RIHLA_ENV") or "").strip().lower()
    if not raw:
        _warn_once("unset", "RIHLA_ENV is not set: running as development (labelled DEMO flight data allowed). "
                            "Any public deployment must set RIHLA_ENV=production (docker-compose.prod.yml does).")
        return "development"
    if raw not in ENVIRONMENTS:
        _warn_once(f"unknown:{raw}", f"RIHLA_ENV={raw!r} is not development, test or production: treated as "
                                     "production (no sample data).")
        return "production"
    return raw


def is_production() -> bool:
    return deployment_env() == "production"
