# DESIGN.md: Rihla, the trip planning crew

> Follows `Final-Mini-Project/common/DESIGN-DOC-TEMPLATE.md`. Written on 2026-11-03 from the code on `main`
> (after PR #16), so it records the decisions **as built**, not a Day 1 plan. Details and the live feature status are
> in [`docs/architecture.md`](docs/architecture.md).

**Team:**
- **Member 1:** agents, orchestration, WHAT IF, approval, memory, MCP.
- **Member 2:** sign-in and the main pages, including the WHAT IF UI and PDF.
- **Member 3:** external data integrations, WHAT IF fixtures, Docker, and the docs and demo.

**Brief:** 3 Trip Planning Crew. **Repo:** `demadabbagh/Agentic-AI-Bootcamp-Students`, folder `Final-Mini-Project/scenario-3-trip-planner/kit`.

---

## 1. The job, in one sentence

A traveller gets a day-by-day plan for a city, dates and a budget, in which every place, opening time and price has a
source, and **no trip is saved until the traveller approves it**. We know it worked when the eval cases pass and
`/api/approve` is the only path that ever writes a trip.

## 2. Architecture sketch

The final diagram, as Mermaid, is in [`docs/architecture.md` §3](docs/architecture.md#3-system-architecture). In short:

**React UI** → **FastAPI** `app.auth_app` (`/api/chat`, `/api/approve`, `/api/whatif`, `/api/trips`) → **orchestrator**
→ **CrewAI crew** (OpenRouter LLM) → **MCP stdio client** → **kit MCP server** `services.travel_mcp` → **travel API**
(open travel data via a replay cache, and the simulated Trip Store).

- **Memory:**
  - session state is in process (`app/memory.py`);
  - lasting preferences live in the Trip Store, through MCP (`app/traveller_memory.py`).
- **Approval gate:** `POST /api/approve` (`app/main.py`, with eligibility rules in `app/approval_policy.py`).
- **Guardrails:** see §6.
- **Member 3's read-only side services:** `/api/destinations`, `/api/airports`, `/api/flights` and `/api/weather`. They are on `main` but not installed in `app/main.py` yet.

## 3. Roles

| Role | Its one job | Tools it may call | It is done when |
|---|---|---|---|
| Coordinator (`app/coordinator.py`) | Read the free-text preferences into the trip request | none (form fields are taken as given) | The request is complete, or a clarification is asked |
| Researcher (`researcher/`) | Find real places with sources | Read-only MCP tools: `geocode`, `find_attractions`, `find_restaurants`, `get_opening_hours`, `travel_time`, `get_weather`, `convert_currency` | `researcher/validate.py` has built a ResearchBundle from the tool log |
| Budget Analyst (`planning/budget_analyst.py`) | Decide what to spend on | none (Python `planning/budget.py` does every sum) | The plan fits the budget, or says by how much it does not |
| Itinerary Planner (`planning/itinerary_planner.py`) | Choose the day and order of places | none (`planning/schedule.py` checks hours, durations, travel) | Every day is schedulable |
| Verifier (`planning/verification.py`, `verifier_agent.py`) | Check the plan before anything can be saved | none (deterministic checks; the LLM explains them) | A PASS, UNKNOWN or FAIL report with evidence |
| Revision Agent (`planning/revision_agent.py`, `app/revision.py`) | Apply a change request or a WHAT IF to the days it touches | none (it chooses among alternatives Python found) | A revised, re-verified plan, or a reason why not |

**The write tool `save_trip` is called by our code in `/api/approve`, never by an LLM.** ☑ agreed. The agents' MCP
client allows only `READ_ONLY_TOOLS` (`researcher/mcp_client.py`), so `save_trip` and `save_preferences` raise
`ToolNotAllowed` if an agent asks for them.

## 4. State

**Session (in process, `app/memory.py`):**
- the trip details;
- the `plan_state` (itinerary, budget report, research bundle, version);
- the `pending_action` waiting for approval;
- WHAT IF proposals, at most 5;
- the session's preferences.

It is lost on restart, so the app needs a single worker. See `docs/deployment-readiness.md`, blocker 2.

## 5. Persistent memory

Lasting preferences are stored per `traveller_id` in the Trip Store, through MCP.

| When | What happens |
|---|---|
| Read | Once at the start of a session, for that traveller only |
| Written | Only when the traveller asks to keep something ("remember that I'm vegetarian"). Lists are merged, and nothing is erased by an empty value. |

Saved trips are also in the Trip Store, which the kit keeps **in memory**, so they don't survive a restart (blocker 1).

## 6. Guardrails

| Risk in our brief | Our check (in code) | Where it runs |
|---|---|---|
| An invented place, hour or price | Only places from the tool log get into the plan, each with a `source_url` | `researcher/validate.py`, after research |
| A plan that breaks hours, budget or walking time | Deterministic verification; approval only on PASS | `planning/verification.py`, `app/approval_policy.py` |
| Saving without consent | `save_trip` only in `/api/approve`, with the exact proposed payload; a trip ID is shown only when the store's answer carries a valid one | `app/main.py`, `app/trip_store.py` |
| Instructions hidden in a listing | A place whose listing text gives instructions to AI agents is dropped, with the reason recorded (`looks_like_injection`) | `researcher/validate.py`, after research |
| A tool or source is down | The reply says so, and nothing is proposed for saving (eval S3-07) | Orchestrator |
| Made-up flight prices or weather | DEMO, TEST and LIVE labels; production refuses anything but LIVE (`503 flights_unavailable`); weather is never filled in | `app/flights`, `app/weather` |
| Unlicensed use of a free API, or a public default key | Open-Meteo is used in production only after the licence decision; `prod-guard` refuses `dev-key-change-me` | `app/open_meteo.py`, `docker-compose.prod.yml` |

## 7. The first 10 test cases (`evals/cases.sample.jsonl`)

1. **S3-01 happy_path:** a 3-day Istanbul plan within budget, with sources, proposed for approval; nothing saved yet.
2. **S3-02 happy_path:** approve: exactly one trip is saved, and its ID is shown.
3. **S3-03 rejection:** reject: nothing is saved, and no trip ID is shown.
4. **S3-04 revision:** cut the budget by 20% in the same session.
5. **S3-05 conflict:** Topkapı is closed on Tuesdays, so it isn't scheduled then.
6. **S3-06 conflict:** two sources disagree on a ticket price, and the plan shows it.
7. **S3-07 tool_failure:** the attractions source is down (503): the crew says so and proposes nothing.
8. **S3-08 memory:** a returning traveller's saved preferences are used.
9. **S3-09 guardrail:** a prompt injection in a listing is ignored.
10. **S3-10 clarification:** no dates and no budget: the crew asks and proposes nothing.

**Not done yet:** the scorecard (`evals/scorecard.md`) from `python evals/run_evals.py`. It needs real OpenRouter calls.

## 8. The walking skeleton

`POST /api/chat` with the Istanbul request goes to the Researcher, which calls MCP `find_attractions`
(travel API, replay cache). The answer is a `proposed` plan with sources and a `pending_action` for `save_trip`.

## 9. Risks and how we cut scope

| Risk | How we handle it |
|---|---|
| **LLM cost and latency** | Python does arithmetic, scheduling and verification; the LLM only chooses. The cost per plan is not measured yet. |
| **Replay cache coverage** | Only Istanbul and Amman are recorded; other cities need `TRAVEL_MODE=live` |
| **Cut first** | Flights stay informational: no booking, and DEMO data without a provider account |
| **Public deployment** | Not done: persistence, the Open-Meteo licence, HTTPS and cookie settings first (`docs/deployment-readiness.md`) |
