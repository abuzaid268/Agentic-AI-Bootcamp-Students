"""The traveller's activity pace scales the daily targets: a preference, never a quota, never past the rules."""
import pytest

from planning.plan_quality import daily_targets, full_day_words, target_range
from planning.research import TripRequest
from planning.verification import MAX_SIGHTS_PER_DAY

TRIP = {"destination": "Amman", "currency": "USD", "travellers": 2, "start_date": "2026-11-05",
        "end_date": "2026-11-09"}


def test_balanced_and_no_pace_are_todays_targets():
    assert daily_targets(5) == daily_targets(5, "balanced") == daily_targets(5, None) == [1, 2, 2, 2, 1]
    assert target_range(5) == target_range(5, "balanced")


def test_relaxed_plans_fewer_and_packed_more_on_full_days():
    assert daily_targets(5, "relaxed") == [1, 1, 1, 1, 1]
    assert daily_targets(5, "packed") == [1, 3, 3, 3, 1]  # arrival and departure days stay light
    assert target_range(5, "relaxed")[0] < target_range(5, "balanced")[0] < target_range(5, "packed")[0]


@pytest.mark.parametrize("pace", ["relaxed", "balanced", "packed"])
def test_no_pace_asks_for_more_than_the_verifier_allows_in_a_day(pace):
    low, high = target_range(7, pace)
    assert max(daily_targets(7, pace)) + 1 <= MAX_SIGHTS_PER_DAY  # target plus the one extra that may fit
    assert high <= 7 * MAX_SIGHTS_PER_DAY


def test_the_trip_request_carries_the_saved_pace_and_refuses_other_values():
    assert TripRequest.model_validate({**TRIP, "activity_pace": "packed"}).activity_pace == "packed"
    assert TripRequest.model_validate(TRIP).activity_pace is None
    with pytest.raises(ValueError):
        TripRequest.model_validate({**TRIP, "activity_pace": "turbo"})


def test_the_messages_describe_a_full_day_at_the_travellers_pace():
    assert full_day_words() == full_day_words("balanced") == "two or three"  # today's wording
    assert full_day_words("relaxed") == "one or two"
    assert full_day_words("packed") == "three or four"
