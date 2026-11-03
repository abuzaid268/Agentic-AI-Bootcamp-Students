# WHAT IF: scenario fixtures and external data (Member 3)

WHAT IF tries a hypothetical change on the plan on screen, previews it, and keeps it only if the traveller applies it.

**Who owns what:**
- **Member 1** owns the simulation: `app/whatif.py` and `app/revision.py`.
- **Member 2** owns the WHAT IF screen: `rihla-frontend/src/services/whatIf.js` and its UI.
- **This part (Member 3)** supplies only:
  - deterministic **scenario fixtures**, built from real recorded data;
  - **checks** that measure any WHAT IF result against a fixture;
  - a **weather adapter**, so the rain scenario can use `app/weather`'s real forecasts.

**Nothing here simulates, revises, approves or saves a plan.**

| Part | File |
|---|---|
| Fixtures: A budget −30%, B 3-hour delay, C rain, D closed attraction | `tests/fixtures/whatif/*.json` |
| Scenario validation and arithmetic | `app/whatif_support/scenarios.py` |
| Result checks: budget, hours, overlaps, travel, unchanged days, no automatic save | `app/whatif_support/checks.py` |
| Weather adapter for the rain scenario | `app/whatif_support/weather_adapter.py` |
| Tests | `tests/test_whatif_support.py`: 59 passed on `main` after PR #16, the compatibility test with the real `forecast_rain` included (2026-11-03) |

## Integration status (2026-11-03)

| What | Where it stands |
|---|---|
| Member 1's WHAT IF simulation (`app/whatif.py`, `/api/whatif`, `/api/whatif/apply`) and Member 2's `services/whatIf.js` | **Merged into `main`**: PR #15, `main` at `6df209d` |
| This part (`app/whatif_support/`, the fixtures) | **Merged into `main`**: PR #16 (merge commit `12513aa`) |
| Fixtures run through the real simulation, end to end | **Not done yet.** It needs a `PlanState` built from each fixture (Member 1's test helpers) and the LLM-backed Revision Agent. |
| `main`'s WHAT IF using this weather adapter | **Not wired.** It's optional: `main` reads the kit's `get_weather`. |
| `main` after PR #16 | **Checked 2026-11-03:** backend 1418 passed, 10 skipped, 0 failed; frontend 246 passed, lint and build pass; the real `forecast_rain()` reads this adapter as a live forecast with the right rainy dates, and answers `available: false` past 16 days. |

**What *was* verified:**
- On 2026-11-03, the real `forecast_rain()` was run on this adapter's output, with four inputs.
- It was taken read-only from `backup/rihla-integration-wip`. **`main` now has the same file:** `app/whatif.py` is the same Git blob `f16019b` on both, so the result applies to `main` as it is.

The four inputs and their results:

  | Input | Result |
  |---|---|
  | A real forecast with rain | `live: true`, rain on the right date |
  | A real dry forecast | `live: true`, no rain |
  | Simulated weather | `live: false` |
  | A date past the forecast horizon | `available: false` |

- The same check is in the tests, and runs on `main` (it skips only where `app/whatif.py` is absent).

**The contract used** is the one in `main`'s `app/whatif.py`:

| Scenario | Request |
|---|---|
| Budget cut | `{"type": "budget_cut", "percent": 1-90 (default 30)}` |
| Delay | `{"type": "delay", "hours": 1-12 whole hours (default 3)}` |
| Rain | `{"type": "rain", "date": optional}` |
| Closure | `{"type": "closure", "place_id", "date"}` |

- **Results:**
  - `preview()` returns `status: "whatif_preview"` with the revised `itinerary` in the README `save_trip` schema and a `whatif` block.
  - When a scenario can't be applied, the status is `"whatif_not_feasible"` or `"needs_clarification"`, with a reason.
- `scenarios.py` mirrors those bounds. **If they ever disagree, `app/whatif.py` is the authority.**

## The fixtures

All four share one realistic original plan: **Istanbul, 2026-11-02 (Mon) to 11-04 (Wed), 1 traveller, budget 230 USD.**

| Day | Activities (start time, estimated USD) |
|---|---|
| Mon 2 Nov | Hagia Sophia 09:00 (27.98) · Basilica Cistern 11:00 (30.16) · Museum of Archaeology 13:30 (16.79) · Grand Bazaar 15:30 (*price not listed*) |
| Tue 3 Nov | Galata Tower 10:00 (13.07) · Pera Museum 11:45 (0.40) |
| Wed 4 Nov | Topkapı Palace 09:00 (55.29), which is closed on Tuesdays, hence Wednesday · Dolmabahçe Palace 14:00 (24.13) |

**Known total: 167.82 USD.** The Grand Bazaar's price is unknown, and is never counted as 0.

### What is real and what is assumed

Each fixture's `data_basis` says the same.

- **Real, recorded:**
  - Every place's id, name, opening hours, price text, coordinates and link.
  - They are Wikivoyage listings from the kit's replay cache (`services/cache/wikivoyage`), read through the kit's travel API with `TRAVEL_MODE=replay`.
- **Real, recorded:** the exchange rates, from the ECB reference rates of 2026-10-23 in the kit's replay cache: TRY→USD 0.020105 and EUR→USD 1.1193.
- **Computed:** `estimated_cost` is the listed price for a **foreign adult** times that rate.
  - For Pera Museum that is 20 TL, not the 10 TL concession price.
  - For Dolmabahçe it is 1200 TL "for foreigners", not the 170 TL domestic price.
- **Fixture assumptions**, not data:
  - `travel_minutes` is the straight-line distance × 1.3 at 4.5 km/h, rounded up to 5 minutes. It is not from a routing service.
  - `day_start` 09:00 and `day_end` 21:00 stand in for the plan's rules.
- **Hypothetical:** every triggering event. Nothing claims that a budget changed, a flight was late, it rained, or a museum closed.

### The four scenarios

| Fixture | Scenario | Expected |
|---|---|---|
| **A** `A_budget_cut_30.json` (high priority) | `{"type": "budget_cut", "percent": 30}` | The budget becomes 230 → **161.00**, below the known 167.82, so the plan must change or be refused. If revised: the known total ≤ 161, `budget_total` 161, the same dates, hours respected. Never count the unknown Grand Bazaar price as 0, and never invent a cheaper price. |
| **B** `B_delay_3h.json` (high) | `{"type": "delay", "hours": 3}` | Monday starts at **12:00** instead of 09:00. If revised: nothing on Monday before 12:00, Tuesday and Wednesday unchanged, hours respected. Variants: 12 h is not feasible (21:00 is the end of the day); 0, 13, 2.5 and `true` are invalid. |
| **C** `C_rain_day.json` | `{"type": "rain", "date": "2026-11-03"}` | If revised: Galata Tower (outdoor) is gone from Tuesday, and Monday and Wednesday are unchanged. **The weather inputs** are a simulated forecast and a recorded copy; neither may confirm rain (`expected_live: false`). |
| **D** `D_closed_attraction.json` | `{"type": "closure", "place_id": "wv-istanbul-pera-museum", "date": "2026-11-03"}` | If revised: Pera Museum is gone from Tuesday, and the other days are unchanged. Its listing says Tue–Sun 10:00–19:00, so the closure is **not** real (`claims_real_closure: false`). |

**Every fixture:**
- `approval.requires_user_approval: true`;
- a preview never changes or saves the plan;
- applying a proposal doesn't save it either; the usual `save_trip` approval (`POST /api/approve`) is still needed.

## Checks

```python
from app.whatif_support import check_against_fixture
problems = check_against_fixture(fixture, result)   # [] = acceptable
```

**It checks:**
- **Opening hours:** the listed hours for that weekday, including days the listing says it is closed. An unparsable window such as `?-20:00` is not judged.
- **Overlaps.**
- **Travel time:** the gap must be at least the stated `travel_minutes`.
- **Budget:** the known costs must not exceed the cap.
- **The fixture's expectations:**
  - `same_dates`;
  - `unchanged_dates`;
  - `absent_on`;
  - `first_start_not_before`;
  - `budget_total`.
- **A refusal must say why.**
- **No result may be `saved` or `approved`, or carry a `trip_id`.** A `pending_action` that *asks* for approval is fine.

The checker reads only the result. It doesn't decide what the plan should become.

## Weather for the rain scenario

**Today:** `forecast_rain()` asks the kit's `get_weather` by city. Locally that is `replay`, a recorded cache, so rain is never "live".

**With the adapter**, it can use `app/weather`'s real forecast for the destination's coordinates instead:

```python
from app.weather import WeatherService
from app.whatif_support import make_weather_read_tool

read_tool = make_weather_read_tool(WeatherService(), latitude, longitude)
weather = forecast_rain(destination, dates, read_tool)          # Member 1's function, unchanged
```

**What the adapter returns:**
- **A real forecast** (`data_status` LIVE, or CACHED, which is the same answer fetched minutes ago) becomes the `get_weather` shape with `mode: "live"`.
- **Simulated weather** (`simulated_weather()`, used by fixtures) is `mode: "simulated"`, so it is never confirmation.
- **No forecast** (an error, or a date past 16 days) is `{"ok": false, "error": …}`, so the rain stays hypothetical.
- `rainy_dates()` uses the same thresholds as `app/whatif.py`: at least 1 mm, or a 60% chance.

## Handoffs

### Member 1

1. **Optional, to get live rain:**
   - pass `read_tool=make_weather_read_tool(WeatherService(), lat, lon)` to `whatif.preview(...)`;
   - the coordinates: `main`'s session has no destination coordinates, but each researched place has `lat` and `lon`
     (`planning/research.py`). One option is the first place in `state.bundle.places` that has both; without one,
     keep the default `read_tool`.
   - Past the 16-day horizon the adapter answers `ok: false`, and `forecast_rain()` then says "No weather data could
     be read". A clearer message for that case ("too far ahead for a forecast") would be Member 1's choice.
3. **Optional, to use the fixtures in evals:** load a fixture, build a `PlanState` from its `original_itinerary` and places, call `preview()`, and check `check_against_fixture(fixture, result) == []`.

Building that `PlanState` belongs in Member 1's test helpers, because it depends on `planning/`.

### Member 2

**Nothing is required.** If the WHAT IF screen shows the rain scenario's `whatif.weather`, show `note` as it is, because it already says whether the rain is live or hypothetical. Never call the rain "forecast" when `live` is false.

## Limitations

- **No end-to-end run:** see the integration status above.
- **Only plans like the fixture's:** the fixtures cover one city and one plan shape. The checker works on any plan in the README schema, but only for places it is given.
- **Indoor or outdoor:** `outdoor_place_ids` in C is a fixture assumption. At run time `planning/setting.py` decides.
