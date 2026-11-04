"""Time limits of the travel data's upstream calls (services/travel_data.py http_get) and of the MCP tool waiting for
the travel API (services/travel_mcp.py): connection timeouts are retried a bounded number of times, every upstream
call has a deadline, every API request a budget, and the limits fit inside each other. A simulated clock stands in
for real time and httpx.MockTransport for the network: nothing waits, nothing is called.
"""
import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

import services.travel_data as td


class Clock:
    """Simulated time: sleeping and every simulated network delay move it forward."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def time(self):
        return 1_700_000_000.0 + self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += max(seconds, 0)


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setenv("TRAVEL_MODE", "live")
    monkeypatch.setattr(td.time, "monotonic", c.monotonic)
    monkeypatch.setattr(td.time, "time", c.time)
    monkeypatch.setattr(td.time, "sleep", c.sleep)
    monkeypatch.setattr(td, "_MEM", {})
    monkeypatch.setattr(td, "_last_call", {})
    return c


def use(monkeypatch, handler):
    monkeypatch.setattr(td, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    return handler


def script(clock, *steps):
    """A handler playing `steps` in order (the last one repeats). A step is a Response, or an exception class from
    httpx raised after spending the attempt's whole connect (ConnectTimeout) or read (ReadTimeout) timeout."""
    calls = []

    def handler(request):
        calls.append(dict(request.extensions["timeout"]))
        step = steps[min(len(calls), len(steps)) - 1]
        if isinstance(step, httpx.Response):
            clock.now += 0.2
            return step
        spent = request.extensions["timeout"]["connect" if step is httpx.ConnectTimeout else "read"]
        clock.now += spent
        raise step("simulated", request=request)
    handler.calls = calls
    return handler


# ------------------------------------------------------------------ connection timeouts: retried, bounded
def test_a_connection_timeout_is_retried_then_succeeds(clock, monkeypatch):
    handler = use(monkeypatch, script(clock, httpx.ConnectTimeout, httpx.Response(200, json={"ok": True})))
    r, _ = td.http_get("https://api.open-meteo.com/v1/forecast")
    assert r.status_code == 200 and r.json() == {"ok": True} and len(handler.calls) == 2


def test_connection_timeouts_stop_at_the_call_deadline(clock, monkeypatch):
    handler = use(monkeypatch, script(clock, httpx.ConnectTimeout))
    start = clock.now
    with pytest.raises(httpx.ConnectTimeout):
        td.http_get("https://en.wikivoyage.org/w/api.php")
    assert len(handler.calls) <= td.MAX_ATTEMPTS
    assert clock.now - start <= td.HTTP_CALL_DEADLINE_S  # every attempt, wait and pause included


def test_each_attempt_gets_only_the_time_that_is_left(clock, monkeypatch):
    handler = use(monkeypatch, script(clock, httpx.ConnectTimeout))
    with pytest.raises(httpx.ConnectTimeout):
        td.http_get("https://en.wikivoyage.org/w/api.php")
    # 20 s deadline: 8 s + 0.5 s pause, 8 s + 1.5 s pause, then only the 2 s that are left
    assert [(c["connect"], c["read"]) for c in handler.calls] == [(8.0, 15.0), (8.0, 11.5), (2.0, 2.0)]
    assert clock.sleeps == [0.5, 1.5]


def test_a_read_timeout_is_not_retried(clock, monkeypatch):
    handler = use(monkeypatch, script(clock, httpx.ReadTimeout))
    with pytest.raises(httpx.ReadTimeout):
        td.http_get("https://en.wikivoyage.org/w/api.php")
    assert len(handler.calls) == 1


def test_a_rate_limit_longer_than_the_time_left_is_answered_not_waited_for(clock, monkeypatch):
    slow = httpx.Response(429, headers={"Retry-After": "5"})
    handler = use(monkeypatch, script(clock, slow))
    with td.request_budget(4):
        r, _ = td.http_get("https://nominatim.openstreetmap.org/search")
    assert r.status_code == 429 and len(handler.calls) == 1 and 5 not in clock.sleeps


# ------------------------------------------------------------------ a response that never finishes arriving
def test_a_body_still_arriving_at_the_deadline_is_dropped(clock, monkeypatch):
    def trickle():
        while True:  # one byte every 3 s, each within the read timeout: only the deadline can end it
            clock.now += 3
            yield b" "

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=trickle())
    use(monkeypatch, handler)
    start = clock.now
    with pytest.raises(td.DeadlineExceeded):
        td.http_get("https://en.wikivoyage.org/w/api.php")
    assert clock.now - start <= td.HTTP_CALL_DEADLINE_S + 3
    assert len(calls) == 1  # a deadline is final: no further attempt


def test_a_decoded_body_is_returned_whole(clock, monkeypatch):
    use(monkeypatch, lambda request: httpx.Response(200, json={"query": {"pages": [1, 2]}}))
    r, url = td.http_get("https://en.wikivoyage.org/w/api.php", {"action": "query"})
    assert r.json() == {"query": {"pages": [1, 2]}} and "action=query" in url


# ------------------------------------------------------------------ one budget for a whole API request
def test_calls_after_the_request_budget_is_spent_fail_at_once_without_a_request(clock, monkeypatch):
    handler = use(monkeypatch, script(clock, httpx.ReadTimeout, httpx.Response(200)))
    with td.request_budget(10):
        with pytest.raises(httpx.ReadTimeout):
            td.http_get("https://en.wikivoyage.org/w/api.php")  # spends the 10 s
        with pytest.raises(td.DeadlineExceeded):
            td.http_get("https://api.open-meteo.com/v1/forecast")
    assert len(handler.calls) == 1
    assert handler.calls[0]["read"] == 10  # the first call was given only the budget, not its own 15 s


def test_the_budget_ends_with_its_block(clock, monkeypatch):
    use(monkeypatch, script(clock, httpx.Response(200)))
    with td.request_budget(0):
        with pytest.raises(td.DeadlineExceeded):
            td.http_get("https://en.wikivoyage.org/w/api.php")
    assert td.http_get("https://en.wikivoyage.org/w/api.php")[0].status_code == 200


def test_waiting_for_a_busy_lock_counts_against_the_deadline(clock, monkeypatch):
    class Busy:
        def acquire(self, timeout):
            clock.now += timeout
            return False
    monkeypatch.setattr(td, "_LOCK", Busy())
    with pytest.raises(td.DeadlineExceeded):
        td.http_get("https://en.wikivoyage.org/w/api.php")


# ------------------------------------------------------------------ the travel API: a clear error, in time
@pytest.fixture()
def api(monkeypatch):
    from services import travel_api
    monkeypatch.setenv("TRAVEL_API_KEY", "test-key")
    return TestClient(travel_api.app, headers={"X-API-Key": "test-key"})


def test_an_unreachable_source_is_a_clear_503_not_data(clock, monkeypatch, api):
    handler = use(monkeypatch, script(clock, httpx.ConnectTimeout))
    r = api.get("/api/attractions", params={"city": "Paris"})
    body = r.json()
    assert r.status_code == 503 and body["error"]["code"] == "upstream_unavailable"
    assert "ConnectTimeout" in body["error"]["message"] and "attractions" not in body
    assert len(handler.calls) <= td.MAX_ATTEMPTS


def test_the_request_budget_reaches_the_endpoint(clock, monkeypatch, api):
    handler = use(monkeypatch, script(clock, httpx.Response(200)))
    monkeypatch.setattr(td, "REQUEST_BUDGET_S", 0.5)  # less than one attempt needs: nothing may be sent
    r = api.get("/api/weather", params={"city": "Paris, Texas, United States", "start": "2026-11-10"})
    assert r.status_code == 503 and handler.calls == []
    assert r.json()["error"]["code"] == "upstream_unavailable" and "DeadlineExceeded" in r.json()["error"]["message"]


# ------------------------------------------------------------------ the limits fit inside each other
@pytest.fixture()
def mcp_modules():
    """services.travel_mcp and researcher.mcp_client, imported without leaving their logging set-up behind
    (FastMCP sets the httpx logger to WARNING when it is created, which other tests' log checks rely on)."""
    root = logging.getLogger()
    levels = {name: lg.level for name, lg in logging.root.manager.loggerDict.items() if isinstance(lg, logging.Logger)}
    handlers, root_level = list(root.handlers), root.level
    from researcher import mcp_client
    from services import travel_mcp
    yield travel_mcp, mcp_client
    for name, lg in list(logging.root.manager.loggerDict.items()):
        if isinstance(lg, logging.Logger):
            lg.setLevel(levels.get(name, logging.NOTSET))
    root.handlers[:] = handlers
    root.setLevel(root_level)


def test_the_limits_fit_inside_each_other(mcp_modules):
    travel_mcp, mcp_client = mcp_modules
    assert td.HTTP_CALL_DEADLINE_S <= td.REQUEST_BUDGET_S
    worst_request = td.REQUEST_BUDGET_S + td.READ_TIMEOUT_S  # a body still arriving at the budget's end
    assert worst_request < travel_mcp.TRAVEL_API_TIMEOUT_S < mcp_client.CALL_TIMEOUT
    assert travel_mcp.TRAVEL_API_TIMEOUT_S == 60


def test_the_mcp_tool_reports_a_timeout_with_its_real_limit(monkeypatch, mcp_modules):
    travel_mcp = mcp_modules[0]

    class Slow:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == travel_mcp.TRAVEL_API_TIMEOUT_S

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, *args, **kwargs):
            raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(travel_mcp.httpx, "AsyncClient", Slow)
    out = asyncio.run(travel_mcp.call("GET", "/api/attractions", {"city": "Tokyo, Japan"}))
    assert out == {"ok": False, "error": {"code": "timeout", "status": None,
                                          "message": "The travel API did not answer in 60 s."}}
