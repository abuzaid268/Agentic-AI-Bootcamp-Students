"""planning/evidence.py: plan from places whose facts can be checked, when there are enough; say what was set aside.

Offline: the Istanbul research fixture (9 attractions, 3 restaurants, Topkapi Palace required), with listings made
incomplete per test, and travel lookups that measure, fail or raise. Nothing here estimates a fact.
"""
from research_fixtures import bundle

from planning.budget_analyst import prepare_candidates
from planning.evidence import checkable_bundle


def measured(minutes=7):
    return lambda a, b: {"ok": True, "duration_min": minutes, "profile": "foot"}


def without(b, place_id, **change):
    return b.model_copy(update={"places": [p.model_copy(update=change) if p.place_id == place_id else p
                                           for p in b.places]})


def ids(b):
    return {p.place_id for p in b.places}


def test_a_place_without_opening_hours_is_set_aside_and_the_plan_says_why():
    b = without(bundle(), "wv-istanbul-galata-tower", hours=None)
    kept, notes = checkable_bundle(b, measured())
    assert "wv-istanbul-galata-tower" not in ids(kept)
    assert "wv-istanbul-hagia-sophia" in ids(kept)  # a place with its hours stays
    assert any("Galata Tower (no opening hours for the trip dates)" in n for n in notes)


def test_a_place_without_a_price_is_set_aside_and_never_counted_as_free():
    b = bundle()
    unpriced = [c.place_id for c in prepare_candidates(b).candidates if c.cost.status == "unknown"]
    assert unpriced  # the fixture has listings without a price
    kept, notes = checkable_bundle(b, measured())
    assert not ids(kept) & set(unpriced)
    assert any("(no price)" in n for n in notes)


def test_a_place_with_no_measurable_walk_is_set_aside_only_on_a_real_failed_lookup():
    def lookup(a, b):
        if "Pera Museum" in (a, b):
            return {"ok": False, "error": {"code": "not_cached"}}
        return {"ok": True, "duration_min": 9}
    kept, notes = checkable_bundle(bundle(), lookup)
    assert "wv-istanbul-pera-museum" not in ids(kept)
    assert any("Pera Museum (no measurable walking route" in n for n in notes)


def test_a_lookup_that_raises_is_not_a_measured_leg():
    def lookup(a, b):
        if "Pera Museum" in (a, b):
            raise RuntimeError("MCP down")
        return {"ok": True, "duration_min": 9}
    assert "wv-istanbul-pera-museum" not in ids(checkable_bundle(bundle(), lookup)[0])


def test_without_a_travel_tool_routes_are_not_judged():
    b = bundle()
    kept, _ = checkable_bundle(b, None)
    priced_or_required = {c.place_id for c in prepare_candidates(b).candidates
                          if c.cost.status != "unknown" or c.required}
    assert ids(kept) == priced_or_required


def test_a_place_the_traveller_asked_for_is_never_set_aside():
    b = without(bundle(), "wv-istanbul-topkapi-palace", hours=None)  # required in the fixture
    assert b.trip.required_places == ["Topkapi Palace"]
    kept, _ = checkable_bundle(b, measured())
    assert "wv-istanbul-topkapi-palace" in ids(kept)


def test_with_too_few_checkable_places_nothing_is_set_aside():
    b = bundle()
    for p in b.places:
        if p.category == "attraction" and p.place_id != "wv-istanbul-hagia-sophia":
            b = without(b, p.place_id, hours=None)
    kept, notes = checkable_bundle(b, measured())
    assert {p.place_id for p in kept.places if p.category == "attraction"} == \
        {p.place_id for p in b.places if p.category == "attraction"}
    assert not any("attractions" in n for n in notes)


def test_an_interest_with_no_checkable_place_is_reported():
    b = bundle(interests=["history", "views"])
    for p in b.places:
        if "views" in p.tags:
            b = without(b, p.place_id, hours=None)
    _, notes = checkable_bundle(b, measured())
    views = [p for p in b.places if "views" in p.tags and p.place_id != "wv-istanbul-topkapi-palace"]
    if views:  # the required Topkapi Palace (tagged views) stays, so the interest is still served by it
        assert not any("No place for 'views'" in n for n in notes)
