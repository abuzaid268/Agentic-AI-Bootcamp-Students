"""Deployment configuration: RIHLA_ENV (app/deployment_env.py) and the production Docker overlay.

The compose files are read as YAML here (no Docker needed, and no environment value can end up in test output).
`docker compose -f docker-compose.yml -f docker-compose.prod.yml config` was also checked by hand: see
docs/deployment-readiness.md.
"""
import logging
from pathlib import Path

import pytest
import yaml

import app.deployment_env as deployment
from app.flights import FlightSearch, UnavailableProvider, provider_from_env
from app.weather import WeatherService

KIT = Path(__file__).resolve().parent.parent


class _ComposeLoader(yaml.SafeLoader):
    """Understands compose's !reset tag (it resets a value to empty in an overlay)."""


_ComposeLoader.add_constructor("!reset", lambda loader, node: {"__reset__": loader.construct_sequence(node)
                                                                 if isinstance(node, yaml.SequenceNode) else None})


def compose(name):
    return yaml.load((KIT / name).read_text(encoding="utf-8"), Loader=_ComposeLoader)


@pytest.fixture()
def env(monkeypatch):
    for name in ("RIHLA_ENV", "DUFFEL_ACCESS_TOKEN", "RIHLA_FLIGHTS_ALLOW_LIVE", "RIHLA_OPEN_METEO_API_KEY",
                 "RIHLA_OPEN_METEO_NONCOMMERCIAL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(deployment, "_warned", set())
    return monkeypatch


# ------------------------------------------------------------------ RIHLA_ENV
@pytest.mark.parametrize("raw, expected", [
    (None, "development"), ("", "development"), ("   ", "development"),
    ("development", "development"), ("test", "test"), ("production", "production"),
    (" Production\n", "production"), ("PRODUCTION", "production"),
    ("prod", "production"), ("staging", "production"), ("dev", "production"), ("1", "production"),
])
def test_missing_malformed_and_explicit_values(env, raw, expected):
    if raw is not None:
        env.setenv("RIHLA_ENV", raw)
    assert deployment.deployment_env() == expected


def test_a_missing_value_is_logged_once_as_a_warning(env, caplog):
    caplog.set_level(logging.WARNING, logger="rihla.deployment")
    deployment.deployment_env()
    deployment.deployment_env()
    warnings = [r for r in caplog.records if r.name == "rihla.deployment"]
    assert len(warnings) == 1 and "RIHLA_ENV is not set" in warnings[0].getMessage()
    assert "docker-compose.prod.yml" in warnings[0].getMessage()


def test_an_unknown_value_is_logged_and_treated_as_production(env, caplog):
    caplog.set_level(logging.WARNING, logger="rihla.deployment")
    env.setenv("RIHLA_ENV", "prodution")  # a typo
    assert deployment.deployment_env() == "production"
    assert "treated as production" in caplog.text


@pytest.mark.parametrize("raw", ["production", "prod", "staging", "PRODUCTION"])
def test_in_production_or_on_a_typo_no_demo_or_test_flights_and_no_unlicensed_open_meteo(env, raw):
    env.setenv("RIHLA_ENV", raw)
    env.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_not-real")
    assert isinstance(provider_from_env(), UnavailableProvider)
    status = FlightSearch().status()
    assert status["available"] is False and status["data_mode"] is None
    assert WeatherService().status()["available"] is False


def test_development_stays_easy(env):
    status = FlightSearch().status()
    assert status["environment"] == "development" and status["data_mode"] == "DEMO"
    assert WeatherService().status()["available"] is True


# ------------------------------------------------------------------ Docker
def test_the_base_compose_file_is_local_development_and_says_so():
    app = compose("docker-compose.yml")["services"]["app"]
    assert app["environment"]["RIHLA_ENV"] == "${RIHLA_ENV:-development}"


def test_the_production_overlay_sets_production_literally_and_closes_internal_ports():
    services = compose("docker-compose.prod.yml")["services"]
    assert services["app"]["environment"]["RIHLA_ENV"] == "production"  # literal: no ${...} default to fall back on
    assert services["app"]["ports"] == {"__reset__": []} and services["travel-api"]["ports"] == {"__reset__": []}
    assert "web" not in services  # the web port stays published
    for name in ("app", "travel-api"):
        key = services[name]["environment"]["TRAVEL_API_KEY"]
        assert key.startswith("${TRAVEL_API_KEY:?")  # compose refuses to start without a private key
        assert "dev-key-change-me" not in key.split("?")[0]


def test_the_production_overlay_only_touches_known_services():
    base = set(compose("docker-compose.yml")["services"])
    assert set(compose("docker-compose.prod.yml")["services"]) <= base
