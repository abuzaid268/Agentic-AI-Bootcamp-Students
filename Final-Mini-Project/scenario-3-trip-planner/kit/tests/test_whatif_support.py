"""WHAT IF scenario fixtures (tests/fixtures/whatif/) and the external-data support in app/whatif_support.

This does NOT test the simulation: that is Member 1's app/whatif.py (on main since PR #15; not yet merged into
this branch). The "revised" results below are hand-made from the fixtures to exercise the checks; they are not
outputs of the Revision Agent. No network: the weather service is mocked with a real recorded Open-Meteo answer.
"""
import copy
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.weather import OpenMeteoProvider, WeatherService
from app.whatif_support import (
    ScenarioError, budget_after, check_against_fixture, check_itinerary, check_no_automatic_save, delayed_start,
    make_weather_read_tool, rainy_dates, simulated_weather, to_get_weather_result, validate_scenario,
)

FIXTURES = Path(__file__).parent / "fixtures" / "whatif"
NAMES = ["A_budget_cut_30.json", "B_delay_3h.json", "C_rain_day.json", "D_closed_attraction.json"]
AMMAN = json.loads((Path(__file__).parent / "fixtures" / "open_meteo_forecast_amman.json").read_text(encoding="utf-8"))
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc).timestamp()


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


A, B, C, D = (load(n) for n in NAMES)


def preview(itinerary, **extra):
    """A result shaped like app/whatif.py preview() (status, itinerary, whatif block)."""
    return {"status": "whatif_preview", "itinerary": itinerary, "message": "Preview.",
            "whatif": {"hypothetical": True, "proposal_id": "abc123", "outcome": "revised"}, **extra}


def day(itinerary, date):
    return next(d for d in itinerary["days"] if d["date"] == date)


def weather_service(meteo_reply=AMMAN):
    provider = OpenMeteoProvider(client=httpx.Client(transport=httpx.MockTransport(
        lambda r: meteo_reply if isinstance(meteo_reply, httpx.Response) else httpx.Response(200, json=meteo_reply))))
    return WeatherService(provider, environment="development", clock=lambda: NOW)


# ------------------------------------------------------------------ the fixtures themselves
@pytest.mark.parametrize("fixture", [A, B, C, D], ids=NAMES)
def test_each_fixture_is_complete_and_its_scenario_is_valid(fixture):
    for key in ("id", "data_basis", "places", "travel_minutes", "original_itinerary", "constraints", "approval",
                "scenario", "trigger", "expected"):
        assert key in fixture
    assert validate_scenario(fixture["scenario"])["type"] == fixture["trigger"]["kind"]
    assert fixture["trigger"]["hypothetical"] is True and "HYPOTHETICAL" in fixture["data_basis"]["event"]
    assert fixture["approval"] == {**fixture["approval"], "requires_user_approval": True, "preview_saves": False,
                                   "apply_saves": False, "preview_changes_plan": False}
    assert set(fixture["expected"]["outcome_one_of"]) <= {"revised", "not_feasible"}


@pytest.mark.parametrize("fixture", [A, B, C, D], ids=NAMES)
def test_the_original_itinerary_is_itself_valid(fixture):
    itinerary = fixture["original_itinerary"]
    places = {p["place_id"]: p for p in fixture["places"]}
    assert check_itinerary(itinerary, places=places, travel_minutes=fixture["travel_minutes"]) == []
    # the README save_trip schema: days[].date and activities[].name are required
    assert all(d["date"] and all(a["name"] for a in d["activities"]) for d in itinerary["days"])
    known = sum(Decimal(str(a["estimated_cost"])) for d in itinerary["days"] for a in d["activities"]
                if a["estimated_cost"] is not None)
    assert Decimal(str(itinerary["estimated_total"])) == known == Decimal("167.82")
    for a in (a for d in itinerary["days"] for a in d["activities"]):
        assert a["source_url"] == places[a["place_id"]]["source_url"].split("#")[0] + "#" + \
            places[a["place_id"]]["source_url"].split("#")[1]


def test_unknown_prices_stay_unknown_and_are_said():
    grand_bazaar = next(a for d in A["original_itinerary"]["days"] for a in d["activities"]
                        if a["place_id"] == "wv-istanbul-grand-bazaar")
    assert grand_bazaar["estimated_cost"] is None and "not counted as free" in grand_bazaar["notes"]


def test_prices_are_the_foreign_adult_price_times_the_recorded_rate():
    costs = {a["place_id"]: a["estimated_cost"] for d in A["original_itinerary"]["days"] for a in d["activities"]}
    assert costs["wv-istanbul-pera-museum"] == round(20 * 0.020105, 2)            # not the 10 TL concession
    assert costs["wv-istanbul-dolmabahce-palace"] == round(1200 * 0.020105, 2)    # not the 170 TL domestic price
    assert costs["wv-istanbul-hagia-sophia"] == round(25 * 1.1193, 2)             # EUR listing


def test_the_fixtures_are_deterministic():
    for name in NAMES:
        assert load(name) == load(name)
    assert A["original_itinerary"] == B["original_itinerary"] == C["original_itinerary"] == D["original_itinerary"]
    assert validate_scenario(validate_scenario(B["scenario"])) == validate_scenario(B["scenario"])


def test_scenarios_use_member_1s_request_shape_only():
    allowed = {"budget_cut": {"type", "percent"}, "delay": {"type", "hours"}, "rain": {"type", "date"},
               "closure": {"type", "place_id", "date"}}
    for fixture in (A, B, C, D):
        assert set(fixture["scenario"]) <= allowed[fixture["scenario"]["type"]]


# ------------------------------------------------------------------ arithmetic
def test_budget_arithmetic():
    assert budget_after(230, 30) == Decimal("161.00") == Decimal(A["expected"]["budget_after"])
    assert budget_after("700", 30) == Decimal("490.00")  # Member 1's own test case
    for variant in A["variants"]["valid"]:
        percent = validate_scenario(variant["scenario"])["percent"]
        assert budget_after(230, percent) == Decimal(variant["budget_after"])
    assert budget_after("0.05", 50) == Decimal("0.03")  # ROUND_HALF_UP to the cent
    assert Decimal(A["expected"]["budget_after"]) < Decimal(str(A["expected"]["known_total_before"]))  # a real cut


def test_delay_arithmetic():
    assert delayed_start("09:00", 3, "21:00") == "12:00" == B["expected"]["start_after"]
    for variant in B["variants"]["valid"]:
        hours = validate_scenario(variant["scenario"])["hours"]
        assert delayed_start("09:00", hours, "21:00") == variant["start_after"]
    with pytest.raises(ScenarioError, match="no planning time"):
        delayed_start("09:00", B["variants"]["not_feasible"][0]["scenario"]["hours"], "21:00")
    with pytest.raises(ScenarioError):
        delayed_start("15:00", 9, "23:59")  # past midnight


@pytest.mark.parametrize("scenario", [
    *A["variants"]["invalid"], *B["variants"]["invalid"], *D["variants"]["invalid"],
    None, "budget_cut", {}, {"type": "earthquake"}, {"type": "rain", "date": "tomorrow"},
])
def test_invalid_scenario_parameters_are_refused(scenario):
    with pytest.raises(ScenarioError):
        validate_scenario(scenario)


def test_defaults_match_member_1s():
    assert validate_scenario({"type": "budget_cut"}) == {"type": "budget_cut", "percent": 30}
    assert validate_scenario({"type": "delay"}) == {"type": "delay", "hours": 3}
    assert validate_scenario({"type": "rain"}) == {"type": "rain", "date": None}


# ------------------------------------------------------------------ closure and rain inputs
def test_the_closure_is_hypothetical_the_listing_says_open():
    place = next(p for p in D["places"] if p["place_id"] == D["scenario"]["place_id"])
    weekday = dt.date.fromisoformat(D["scenario"]["date"]).strftime("%a")
    assert place["weekly"].get(weekday), "the fixture must not pick a day the place is really closed"
    assert D["trigger"]["claims_real_closure"] is False
    assert D["scenario"]["place_id"] in [a["place_id"] for a in day(D["original_itinerary"], D["scenario"]["date"])["activities"]]


def test_simulated_or_recorded_rain_never_counts_as_a_live_forecast():
    for case in C["weather_inputs"].values():
        assert case["expected_live"] is False and rainy_dates(case["result"]) == []
    built = simulated_weather(C["weather_inputs"]["simulated"]["result"]["days"], "fixture")
    assert built["mode"] == "simulated" and built["data_status"] == "SIMULATED" and rainy_dates(built) == []


def test_a_real_forecast_becomes_a_get_weather_result_forecast_rain_can_read():
    answer = weather_service().forecast(latitude="31.9539", longitude="35.9106", start_date="2026-11-03",
                                        end_date="2026-11-05")
    result = to_get_weather_result(answer)
    assert result["ok"] is True and result["kind"] == "forecast" and result["mode"] == "live"
    assert result["stale"] is False and result["data_status"] == "LIVE" and result["source"] == "Open-Meteo forecast API"
    assert result["days"][0] == {"date": "2026-11-03", "weather_code": 3, "summary": "overcast", "precip_mm": 0.0,
                                 "precip_probability_pct": 3.0, "temp_max_c": 24.5, "temp_min_c": 14.7}
    assert rainy_dates(result) == []  # the recorded Amman forecast is dry


def test_rainy_dates_use_member_1s_thresholds():
    wet = to_get_weather_result({"data_status": "LIVE", "units": {"temperature": "°C"}, "days": [
        {"date": "2026-11-03", "precipitation_sum_mm": 1.0, "precipitation_probability_max_pct": 10},
        {"date": "2026-11-04", "precipitation_sum_mm": 0.0, "precipitation_probability_max_pct": 60},
        {"date": "2026-11-05", "precipitation_sum_mm": 0.9, "precipitation_probability_max_pct": 59},
        {"date": "2026-11-06", "precipitation_sum_mm": None, "precipitation_probability_max_pct": None}]})
    assert rainy_dates(wet) == ["2026-11-03", "2026-11-04"]  # at or above 1 mm or 60 %; unknown is not rain


def test_the_read_tool_serves_get_weather_by_coordinates():
    read_tool = make_weather_read_tool(weather_service(), 31.9539, 35.9106)
    result = read_tool("get_weather", {"city": "Amman", "start_date": "2026-11-03", "end_date": "2026-11-05"})
    assert result["ok"] is True and [d["date"] for d in result["days"]] == ["2026-11-03", "2026-11-04", "2026-11-05"]


@pytest.mark.parametrize("name, args, code", [
    ("get_weather", {"start_date": "2026-11-20", "end_date": "2026-11-22"}, "beyond_forecast_horizon"),
    ("get_weather", {"start_date": "yesterday"}, "invalid_date"),
    ("get_attractions", {}, "unsupported_tool"),
])
def test_missing_external_data_is_an_explicit_no_never_invented(name, args, code):
    result = make_weather_read_tool(weather_service(), 31.9539, 35.9106)(name, args)
    assert result["ok"] is False and result["error"]["code"] == code and "days" not in result
    assert rainy_dates(result) == []


def test_a_provider_outage_is_an_explicit_no():
    read_tool = make_weather_read_tool(weather_service(httpx.Response(500)), 31.9539, 35.9106)
    result = read_tool("get_weather", {"start_date": "2026-11-03"})
    assert result == {"ok": False, "error": {"code": "provider_error", "message": result["error"]["message"]}}


@pytest.mark.parametrize("answer", [None, {}, {"data_status": "SIMULATED", "days": []},
                                    {"data_status": "UNAVAILABLE"}, {"data_status": "LIVE", "days": "x"}])
def test_anything_but_a_real_forecast_is_not_passed_on(answer):
    assert to_get_weather_result(answer)["ok"] is False


def test_member_1s_forecast_rain_reads_the_adapter_when_it_is_merged():
    """Skipped on this branch alone; runs once it is combined with main, which has app/whatif.py (PR #15), and
    then checks the real function. (Run on this branch merged with main 6df209d on 2026-11-03: passed.)"""
    whatif = pytest.importorskip("app.whatif")
    wet = {**AMMAN, "daily": {**AMMAN["daily"], "precipitation_sum": [0.0, 6.5, 0.0],
                              "precipitation_probability_max": [5, 85, 10]}}
    dates = [dt.date(2026, 11, 3), dt.date(2026, 11, 4), dt.date(2026, 11, 5)]
    live = whatif.forecast_rain("Amman", dates, make_weather_read_tool(weather_service(wet), 31.9539, 35.9106))
    assert live["live"] is True and live["rainy_dates"] == ["2026-11-04"]
    dry = whatif.forecast_rain("Amman", dates, make_weather_read_tool(weather_service(), 31.9539, 35.9106))
    assert dry["live"] is True and dry["rainy_dates"] == []
    sim = simulated_weather([{"date": "2026-11-04", "precip_mm": 9.0, "precip_probability_pct": 95}], "fixture")
    assert whatif.forecast_rain("Amman", dates, lambda name, args: sim)["live"] is False
    far = whatif.forecast_rain("Amman", [dt.date(2026, 11, 30)],
                               make_weather_read_tool(weather_service(), 31.9539, 35.9106))
    assert far["available"] is False and far["live"] is False


# ------------------------------------------------------------------ checks of a result against a fixture
def good_budget_cut():
    it = copy.deepcopy(A["original_itinerary"])
    day(it, "2026-11-02")["activities"] = [a for a in day(it, "2026-11-02")["activities"]
                                           if a["place_id"] != "wv-istanbul-basilica-cistern"]  # -30.16
    it["budget_total"], it["estimated_total"] = 161.0, 137.66
    return it


def test_a_valid_budget_cut_passes():
    assert check_against_fixture(A, preview(good_budget_cut())) == []


def test_a_budget_cut_still_over_budget_fails():
    it = copy.deepcopy(A["original_itinerary"])
    it["budget_total"] = 161.0
    assert any("exceed 161.0" in p for p in check_against_fixture(A, preview(it)))


def test_a_valid_delay_passes_and_an_early_start_or_another_day_changed_fails():
    it = copy.deepcopy(B["original_itinerary"])
    day(it, "2026-11-02")["activities"] = [
        {**day(it, "2026-11-02")["activities"][0], "start_time": "12:00", "end_time": "13:30"},
        {**day(it, "2026-11-02")["activities"][2], "start_time": "14:00", "end_time": "15:30"},
        {**day(it, "2026-11-02")["activities"][3], "start_time": "16:00", "end_time": "17:30"}]
    assert check_against_fixture(B, preview(it)) == []
    early = copy.deepcopy(B["original_itinerary"])
    assert any("before 12:00" in p for p in check_against_fixture(B, preview(early)))
    moved = copy.deepcopy(it)
    day(moved, "2026-11-03")["activities"].pop()
    assert any("2026-11-03 should be unchanged" in p for p in check_against_fixture(B, preview(moved)))


def test_rain_and_closure_must_remove_the_place_on_that_day_only():
    rained = copy.deepcopy(C["original_itinerary"])
    day(rained, "2026-11-03")["activities"] = day(rained, "2026-11-03")["activities"][1:]
    assert check_against_fixture(C, preview(rained)) == []
    assert any("still has ['wv-istanbul-galata-tower']" in p
               for p in check_against_fixture(C, preview(copy.deepcopy(C["original_itinerary"]))))
    closed = copy.deepcopy(D["original_itinerary"])
    day(closed, "2026-11-03")["activities"] = day(closed, "2026-11-03")["activities"][:1]
    assert check_against_fixture(D, preview(closed)) == []
    assert check_against_fixture(D, preview(copy.deepcopy(D["original_itinerary"])))


def test_opening_hours_overlaps_and_travel_times_are_checked():
    places = {p["place_id"]: p for p in A["places"]}
    it = copy.deepcopy(A["original_itinerary"])
    topkapi = day(it, "2026-11-04")["activities"].pop(0)
    day(it, "2026-11-03")["activities"].append({**topkapi, "start_time": "14:00", "end_time": "15:00"})  # Tuesday
    day(it, "2026-11-02")["activities"][1].update(start_time="10:00", end_time="11:00")  # overlaps Hagia Sophia
    day(it, "2026-11-04")["activities"][0].update(start_time="18:00", end_time="19:00")  # Dolmabahce shuts at 17:00
    problems = check_itinerary(it, places=places, travel_minutes=A["travel_minutes"])
    assert any("closed on Tue" in p for p in problems)
    assert any("starts before Hagia Sophia ends" in p for p in problems)
    assert any("outside the listed hours" in p for p in problems)
    tight = copy.deepcopy(A["original_itinerary"])
    day(tight, "2026-11-02")["activities"][3].update(start_time="15:05", end_time="16:30")  # 5 min, 20 needed
    assert any("20 min needed" in p for p in check_itinerary(tight, places=places, travel_minutes=A["travel_minutes"]))


def test_not_feasible_is_accepted_only_with_a_reason():
    refused = {"status": "whatif_not_feasible", "message": "The budget is too low for the required places.",
               "whatif": {"outcome": "not_feasible", "reason": "too low"}}
    assert check_against_fixture(A, refused) == []
    assert check_against_fixture(A, {**refused, "message": "", "whatif": {}}) == [
        "A scenario that cannot be applied must say why."]


# ------------------------------------------------------------------ never approve or save by itself
@pytest.mark.parametrize("result, ok", [
    (preview({"days": []}), True),
    (preview({"days": []}, pending_action={"type": "save_trip", "action_id": "act-1"}), True),  # asking is fine
    ({"status": "saved", "itinerary": {"days": []}}, False),
    ({"status": "approved"}, False),
    (preview({"days": []}, result={"trip_id": "TRIP-3001"}), False),
])
def test_a_what_if_never_approves_or_saves_by_itself(result, ok):
    assert (check_no_automatic_save(result) == []) is ok


def test_the_support_code_cannot_save_approve_or_call_anything():
    """Read the code itself (not its comments): what it imports and which functions it calls."""
    import ast
    imported, called = set(), set()
    for path in Path("app/whatif_support").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Call):
                func = node.func
                called.add(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    assert not {m for m in imported if m.split(".")[0] in ("httpx", "requests", "urllib")}
    assert not {m for m in imported if m in ("app.trip_store", "app.revision", "app.whatif", "app.orchestrator")}
    assert not called & {"save_trip", "approve", "run_trip_revision", "apply_proposal", "preview", "post", "put"}
    assert imported & {"app.weather.service"}  # it only reads the weather service
