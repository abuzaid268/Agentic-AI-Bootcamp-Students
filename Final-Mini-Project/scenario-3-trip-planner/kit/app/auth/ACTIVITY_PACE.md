# Preferred activity pace: integration

Owner of this note: Developer 2 (auth & frontend). Branch `feature/activity-pace-integration` (worktree
`Agentic-AI-Bootcamp-Students-pace`, based on `main` at 3d9fd86) holds the whole feature, applied and tested
together. Nothing on it is committed yet.

```
activity_pace: "relaxed" | "balanced" | "packed"     (absent = balanced: today's behaviour)
```

A preference for how full each day is, **never a quota**. It cannot override the budget, opening hours, the
walking limit, verified travel times or the verifier: those still decide what is actually planned.

## How it flows

```
My Profile ──PUT /api/profile/preferences──▶ app/auth/profile.py ──PUT /api/travellers/{own id}/preferences──▶ Trip Store
                                              (saved only when the store's /health lists "activity_pace")
/api/chat ──MCP get_preferences(own id)──▶ app/traveller_memory.py ──apply_preferences──▶ trip_info["activity_pace"]
          ──▶ TripRequest.activity_pace ──▶ plan_quality targets ──▶ Budget Analyst, day balance, planner prompt
```

`own id` is always `traveller_id_for_request()`: the signed-in user's traveller. A traveller ID in the request
body is ignored for a signed-in user. An anonymous call to the open contract uses the body's `user.traveller_id`
(CONTRACT §5), and without one loads no preferences at all, so evaluations behave as before.

## What the branch contains, by owner

| Owner | Files | Change |
|---|---|---|
| Developer 2 | `app/auth/profile.py`, `app/auth/__init__.py`, `rihla-frontend/src/...` (Profile page, profileApi, profileForm, nav/login) | pace in GET/PUT; cards clickable only when the store supports it |
| Developer 3 | `services/travel_api.py`, `services/travel_mcp.py` | `patches/activity_pace_travel_api.patch`, unchanged |
| Developer 1 | `planning/*`, `app/research_adapter.py`, `app/coverage.py` | `patches/activity_pace_planner.patch`, unchanged |
| Developer 1 | `app/traveller_memory.py`, `app/mcp_app_client.py`, `researcher/mcp_client.py` | taken **verbatim** from `feature/global-data-frontend` (2b7c2bb); `traveller_memory.py` then gains the pace (3 places, marked by `ACTIVITY_PACES`) |
| Developer 1 | `app/main.py`, `app/orchestrator.py`, `app/schemas.py` | auth wiring (`main_integration.patch`) and the memory step, written to match `feature/global-data-frontend` (same `preferences=` parameter, `_orchestrate_trip` wrapper, STEP 6b, `ChatRequest.user`) |
| tests | `tests/conftest.py`, `tests/test_activity_pace_memory.py`, `tests/planning/test_activity_pace.py`, `tests/test_profile.py` | |

`feature/global-data-frontend` itself was **not** merged: against `main` it conflicts in 12 files owned by
Developer 1 (main.py, orchestrator.py, schemas.py, trip_store.py, App.jsx, MyTrips.jsx, TripDashboard.jsx, ...).
That merge is theirs to make.

## Safest order to integrate

1. Developer 1 merges `feature/global-data-frontend` into `main` (their conflicts, their call).
2. Developer 3 applies `patches/activity_pace_travel_api.patch` (or takes the two service files from this branch).
3. Rebase this branch on the new `main`. `traveller_memory.py`, `mcp_app_client.py` and `mcp_client.py` then
   differ only by the pace lines; in `main.py`/`orchestrator.py` keep Developer 1's version and re-add only:
   `base_version`/`revision_request` (if still missing), and the traveller line in `chat()`:
   `traveller_id_for_request() if current_user() is not None else traveller_id_from(request.user)`.
4. Run the suite (`tests/test_activity_pace_memory.py` checks the per-user loading) and open one PR.
