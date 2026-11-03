"""Which kind of deployment this server is: RIHLA_ENV = development (default) | test | production.

Used by Member 3's external-data integrations (app/flights, app/weather) to decide what data they may show:
- development: sample (DEMO / SIMULATED) data is allowed, always labelled as such;
- test: as development, plus provider sandboxes; never live paid calls;
- production: real provider data only; when there is none, the feature says it is unavailable.

An unrecognised value counts as production, so a typo fails closed (no sample data reaches real users).
"""
from __future__ import annotations

import os

ENVIRONMENTS = ("development", "test", "production")


def deployment_env() -> str:
    raw = (os.getenv("RIHLA_ENV") or "").strip().lower()
    if not raw:
        return "development"
    return raw if raw in ENVIRONMENTS else "production"


def is_production() -> bool:
    return deployment_env() == "production"
