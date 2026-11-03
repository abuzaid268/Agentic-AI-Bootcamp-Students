# Demo preparation

**What this document is:** a draft by Member 3, written 2026-11-03. Re-check §4 on the day: anything wired in or merged after this date changes it.

## 1. Short demo script (about 5 minutes, for a general audience)

1. **The problem.** A single chatbot invents opening hours and prices. Rihla's rule is: every place, hour and price has a source, and nothing is saved without your approval.
2. **Plan a trip.**
   - Sign in with Google.
   - Fill in the form, for example Istanbul, 3 days, 700 USD, history and food.
   - Show the itinerary, with each activity's source link and an *estimate* price, then the budget and the verification summary.
3. **Revise.** "Make day 2 cheaper": show that only day 2 changed.
4. **Approve.** Click Approve, show the `TRIP-…` ID, then **My Trips** and the PDF export.
5. **Honesty.**
   - Point to a price labelled as an estimate, and to a place whose price is unknown, which is not counted as 0.
   - If flights are shown, point to the **DEMO** badge and say plainly: "these are sample flights, not real prices".

## 2. Technical demo script (about 10 minutes, for reviewers)

1. **Architecture:** `docs/architecture.md`, with the diagram and the status table. Be explicit about which parts are wired in.
2. **The crew:**
   - the Coordinator, then the Researcher (MCP tools only), the Budget Analyst, the Itinerary Planner and the Verifier;
   - the point is that the LLM decides and Python calculates;
   - show `tool_calls` and `performance` in the `/api/chat` answer.
3. **The approval gate:** `pending_action` goes to `POST /api/approve`, and a trip ID appears only after the store answers 201.
4. **Member 3's integrations, as APIs.** They aren't wired into `app/main.py` yet; use §3.
   - `/api/destinations?q=Pari`: Paris (France), Paris (Texas) and Paris (Tennessee), with `ambiguous: true`.
   - `/api/airports?q=London`: LHR, LGW, STN and LCY, then YXU (Ontario), flagged.
   - `/api/flights?origin=TLV&destination=LHR&departure_date=…`: `data_mode: DEMO`, with every offer labelled.
   - The same request with `RIHLA_ENV=production`: `503 flights_unavailable`. Production never shows made-up prices. `/api/destinations` answers `503 destinations_unavailable` too, until the Open-Meteo licence is decided.
   - `/api/weather?latitude=41.01&longitude=28.98`: a real Open-Meteo forecast, `data_status: LIVE`. Call it again: `CACHED`.
5. **Tests:** `python -m pytest -q` (about 1 minute) and `cd rihla-frontend && npm test`. Mention the one known failure, which is Member 1's.
6. **Docker:** `docker compose up -d --build --wait`. All three containers become healthy. Then `docker compose down`.

## 3. Reliable demo paths

**Main journey, on `main`:**
- **Destinations:** Istanbul or Amman. These are the cities in the kit's replay cache (`TRAVEL_MODE=replay`).
- **Dates** within the recorded weather window (`TRAVEL_TODAY`, see `.env.example`).
- **Each plan makes real OpenRouter calls,** which cost money. Plan one trip before the demo, and keep it open.

**Member 3's APIs before the handoffs are done.**

This installs the routers into the running app from the command line, without editing any file:

```sh
cd kit
python -c "from app.auth_app import app; from app.destinations import install_destinations; from app.airports import install_airports; from app.flights import install_flights; from app.weather import install_weather; [f(app) for f in (install_destinations, install_airports, install_flights, install_weather)]; import uvicorn; uvicorn.run(app, port=8000)"
```

**What each needs:**
- **Destinations and weather** call Open-Meteo live: free, non-commercial, and they need the internet.
- **Airports** are offline.
- **Flights** are DEMO unless a `duffel_test_…` token is set.

**Offline fallback:** `python -m pytest -q tests/test_destinations.py tests/test_airports.py tests/test_flights.py tests/test_weather.py tests/test_whatif_support.py`

## 4. Feature status for the demo (2026-11-03)

| Feature | Show as | Note |
|---|---|---|
| Planning, verification, revision, approval, My Trips, PDF | **Working** (on `main`) | Real LLM calls |
| Google sign-in | **Working** (on `main`) | Needs the Firebase configuration |
| Destination autocomplete | **API working, not in the UI yet** | It is on the UI only after Member 2's handoff |
| Airport search | **API working, not in the UI yet** | |
| Flight comparison | **DEMO data only** | Duffel was never called with a real token |
| Weather | **API working with live data, not in the UI yet** | |
| WHAT IF (Member 1 and 2) | **On `main`** (PR #15) | Try it on `main` before the demo; it was not re-run in this review. Call each result **hypothetical**. |
| WHAT IF fixtures and weather adapter (Member 3) | **Tests only** | On `feature/destinations-flights`, not yet merged into `main`, and not run end to end |
| Public deployment | **None** | Local Docker only |

## 5. Do NOT present as live or real

- **Flight prices or schedules.** They are DEMO (Rihla's samples) or TEST (Duffel's sandbox). Never "real-time prices".
- **The replay cache's weather and places.** These are real data, recorded on the cache date. Say "recorded", not "live", when `mode` is `replay`.
- **WHAT IF results.** They are hypothetical by design. A WHAT IF rain is "confirmed" only when the live forecast says so.
- **The WHAT IF fixtures.** They are test data: real places, with hypothetical events.
- **Cost or capacity claims.** The LLM cost per plan has not been measured, and the free tiers have limits.
- **"Deployed" or "production-ready".** Rihla runs locally in Docker and has the blockers listed in `docs/deployment-readiness.md`.

## 6. Pre-presentation checklist

- [ ] `git status` is clean on the branch being demoed, and the pulled commit hash is noted.
- [ ] `python -m pytest -q` passes, apart from the known Member 1 failure.
- [ ] `npm ci && npm test && npm run lint && npm run build` pass in `rihla-frontend`.
- [ ] `docker compose up -d --build --wait` shows three healthy containers, and `http://localhost:5173/health` is ok.
- [ ] `.env` has `OPENROUTER_API_KEY`, the Firebase settings and `TRAVEL_TRAVELLER_ID`, and there is credit left on OpenRouter.
- [ ] One trip has been planned beforehand as a fallback, in case the LLM is slow during the demo.
- [ ] Know which environment is on:
  - `RIHLA_ENV` unset means development, with DEMO flights and a warning in the server log;
  - `RIHLA_ENV=production` shows the fail-closed answers for flights, and for weather and city search without a licence decision.
- [ ] Never demo with `docker-compose.prod.yml` unless you mean to show production behaviour.
- [ ] Internet is available for the live weather and destination calls. Otherwise use the tests.
- [ ] Nobody says "real-time flight prices", "deployed" or "live" for recorded data.
