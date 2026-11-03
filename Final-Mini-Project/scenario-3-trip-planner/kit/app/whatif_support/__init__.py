"""External data and checks for WHAT IF (Member 3). See docs/whatif.md.

Member 1 owns the simulation (app/whatif.py and app/revision.py, on main since PR #15). This
package only supplies: scenario validation and arithmetic (scenarios.py), a weather adapter in the shape the
rain scenario reads (weather_adapter.py), and checks of a result against tests/fixtures/whatif/ (checks.py).
Nothing here revises, approves or saves a plan.
"""
from .checks import check_against_fixture, check_itinerary, check_no_automatic_save
from .scenarios import ScenarioError, budget_after, delayed_start, validate_scenario
from .weather_adapter import make_weather_read_tool, rainy_dates, simulated_weather, to_get_weather_result

__all__ = ["ScenarioError", "budget_after", "check_against_fixture", "check_itinerary", "check_no_automatic_save",
           "delayed_start", "make_weather_read_tool", "rainy_dates", "simulated_weather", "to_get_weather_result",
           "validate_scenario"]
