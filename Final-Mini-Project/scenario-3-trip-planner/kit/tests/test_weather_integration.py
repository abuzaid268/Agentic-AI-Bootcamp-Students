"""GET /api/weather is registered in the real app (app.main.app), and a weather failure never blocks trip planning.

The provider is mocked (httpx.MockTransport) with the real Open-Meteo answer recorded for tests/test_weather.py: no
network. The chat orchestrator is replaced by a recorder: no LLM.
"""
import re
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.weather import OpenMeteoProvider, WeatherService
from tests.test_weather import AMMAN, NOW, OpenMeteo

ROOT = Path(__file__).resolve().parents[1]
# What the destination box gives for Jerusalem: the weather box asks about these coordinates and the trip's days.
JERUSALEM = {"latitude": "31.76904", "longitude": "35.21633", "start_date": "2026-11-03", "end_date": "2026-11-05"}
TRIP = {"destination": "Amman, Amman Governorate, Jordan", "start_date": "2026-12-01", "end_date": "2026-12-03",
        "travellers": 2, "budget": 900}


@pytest.fixture()
def client():
    return TestClient(app)


def use_weather(monkeypatch, meteo, **kwargs):
    provider = OpenMeteoProvider(client=httpx.Client(transport=httpx.MockTransport(meteo)))
    service = WeatherService(provider, environment="development", clock=lambda: NOW, monotonic=lambda: 0.0, **kwargs)
    monkeypatch.setattr(app.state, "weather_service", service, raising=False)
    return service


def chat(client, session):
    with patch("app.main.orchestrate_trip", return_value={"status": "needs_clarification", "message": "recorded"}) as run:
        response = client.post("/api/chat", json={"session_id": session, "message": "Plan my trip", "trip": TRIP})
    return response, run


# ------------------------------------------------------------------ registered
def test_the_weather_routes_are_in_the_real_app_and_read_only():
    paths = {path: set(methods) for path, methods in app.openapi()["paths"].items()}
    assert paths["/api/weather"] == {"get"} and paths["/api/weather/status"] == {"get"}
    assert not [p for p in paths if p.startswith("/api/weather") and p not in ("/api/weather", "/api/weather/status")]


def test_it_is_registered_once_even_if_installed_again():
    from app.weather import install_weather
    before = len(app.openapi()["paths"])
    app.openapi_schema = None
    install_weather(app)
    app.openapi_schema = None
    assert len(app.openapi()["paths"]) == before


def test_it_needs_no_sign_in_and_answers_for_a_chosen_places_coordinates(client, monkeypatch):
    meteo = OpenMeteo(AMMAN)
    use_weather(monkeypatch, meteo)
    r = client.get("/api/weather", params=JERUSALEM)  # no cookie, no token
    body = r.json()
    assert r.status_code == 200 and body["data_status"] == "LIVE" and body["source"]["provider"] == "Open-Meteo"
    assert [d["date"] for d in body["days"]] == ["2026-11-03", "2026-11-04", "2026-11-05"]
    asked = meteo.requests[0].url.params
    # the chosen place, to 4 decimals (about 10 m: the service's own forecast-cell rounding), never another place
    assert (asked["latitude"], asked["longitude"]) == ("31.7690", "35.2163")
    assert client.get("/api/weather/status").json()["available"] is True


def test_what_the_trip_page_sends_is_accepted_and_what_it_must_not_send_is_refused(client, monkeypatch):
    meteo = OpenMeteo(AMMAN)
    use_weather(monkeypatch, meteo)
    assert client.get("/api/weather", params={**JERUSALEM, "latitude": "91"}).status_code == 422
    assert client.get("/api/weather", params={**JERUSALEM, "end_date": "2026-12-30"}).json()["error"]["code"] == "beyond_forecast_horizon"
    assert meteo.requests == []  # refused before any provider call


# ------------------------------------------------------------------ failures are contained
FAILURES = [httpx.ConnectError("down"), httpx.ReadTimeout("slow"), httpx.Response(500), httpx.Response(429),
            httpx.Response(200, text="<html>not json</html>")]


@pytest.mark.parametrize("failure", FAILURES, ids=lambda f: type(f).__name__ if isinstance(f, Exception) else str(f.status_code))
def test_a_weather_failure_is_a_clear_error_for_weather_only_and_the_trip_request_still_works(client, monkeypatch, failure):
    use_weather(monkeypatch, OpenMeteo(failure))
    r = client.get("/api/weather", params=JERUSALEM)
    body = r.json()
    assert r.status_code in (429, 502, 503, 504) and body["data_status"] == "UNAVAILABLE"
    assert "days" not in body and body["error"]["code"]  # nothing is invented in its place
    reply, run = chat(client, "weather-isolation")
    assert reply.status_code == 200 and reply.json()["status"] == "needs_clarification" and run.call_count == 1


def test_with_no_provider_allowed_the_answer_is_unavailable_and_planning_is_unaffected(client, monkeypatch):
    for name in ("RIHLA_OPEN_METEO_API_KEY", "RIHLA_OPEN_METEO_NONCOMMERCIAL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app.state, "weather_service", WeatherService(environment="production"), raising=False)
    assert client.get("/api/weather/status").json()["available"] is False
    r = client.get("/api/weather", params=JERUSALEM)
    assert r.status_code == 503 and r.json()["data_status"] == "UNAVAILABLE"
    assert chat(client, "weather-unavailable")[0].status_code == 200


def test_the_chat_contract_has_no_weather_field_and_the_plan_builders_do_not_use_the_weather_route():
    from app.schemas import ChatRequest, ChatResponse, TripForm
    names = set(TripForm.model_fields) | set(ChatRequest.model_fields) | set(ChatResponse.model_fields)
    assert not [n for n in names if re.search(r"weather|forecast", n, re.I)]
    for path in ("app/orchestrator.py", "app/schemas.py", "planning/itinerary_planner.py", "planning/research.py"):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+app\.weather", source, re.M), path
