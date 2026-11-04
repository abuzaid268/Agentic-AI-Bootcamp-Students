<!--
  DRAFT of the portfolio README (Final-Mini-Project/common/PORTFOLIO-README-TEMPLATE.md), by Member 3, 2026-11-03.
  The template says to copy it to README.md at the repo root. In this kit that file is the official kit README,
  which the team and graders use, so replacing it is a TEAM decision. Until then, the draft lives here.
  Items marked TODO need things that don't exist yet (the scorecard, the video, a screenshot).
-->

# Rihla: a trip planning crew that cites its sources and asks before it saves

<!-- TODO: a 10–20 s GIF of the happy path, saved as docs/demo.gif -->

**Planning a city trip means checking opening hours, prices and travel times across many sites. A single chatbot
answers fast, but it invents hours and prices. Rihla gives the job to a crew of specialised agents:**
- the agents research real places through MCP tools;
- Python does every sum and schedule check;
- a verifier checks the plan;
- **nothing is saved until the traveller approves it.**

▶ **3-minute demo video:** TODO · 🧪 **Eval pass rate:** TODO (`evals/scorecard.md` not generated yet) · 🧰 **Stack:** CrewAI · MCP · FastAPI · React · OpenRouter

---

## What it does

- **Plans a day-by-day trip** from a destination, dates, a budget and interests. Every place, opening time and price has a source.
- **Revises on request** ("make day 2 cheaper"), and only the days that need it change.
- **Previews WHAT IF scenarios:** a budget cut, rain, a closure or a delay. Each is labelled hypothetical.
- **Remembers lasting preferences** per traveller ("remember that I'm vegetarian").
- **Asks before it acts:** a trip is proposed first, and written only after you approve it.
  - Saved trips appear in **My Trips** and export to PDF.
- **Side services, on `main` but not yet wired into the UI:**
  - worldwide city search, airport search with a departure country;
  - flight price comparison, labelled DEMO, TEST or LIVE;
  - real weather forecasts.

## Architecture

The diagram (Mermaid) is in [`architecture.md` §3](architecture.md#3-system-architecture); the decisions are in [`DESIGN.md`](../DESIGN.md).

- **Crew** (CrewAI, OpenRouter): Coordinator, Researcher, Budget Analyst, Itinerary Planner, Verifier, Revision Agent. The LLM decides; Python calculates and checks.
- **Data access:** the Researcher calls only read-only MCP tools (`researcher/mcp_client.py` → `services.travel_mcp` → travel API).
- **Memory:**
  - session state is in process;
  - lasting preferences live in the Trip Store, through MCP.
- **Approval gate:** `POST /api/approve` is the only code that calls `save_trip`.

| Component | Real or simulated? | Notes |
|---|---|---|
| LLM via OpenRouter | **Real** | Paid per call |
| Travel data: Wikivoyage, OpenStreetMap, OSRM routing, Open-Meteo, ECB rates | **Real** | Through the kit's travel API. Replay mode serves recorded real answers (Istanbul and Amman); live mode calls the sources |
| Trip Store and traveller preferences | **Simulated** | The kit's REST API + MCP server, with fault injection; kept in memory |
| Google sign-in | **Real** | Firebase; needs the project settings |
| City search (`/api/destinations`) | **Real** | Open-Meteo Geocoding (GeoNames). In production only after the licence decision |
| Airport search (`/api/airports`) | **Real data, offline snapshot** | OurAirports, public domain, built 2026-11-02. It is metadata, not live flight availability |
| Flight prices (`/api/flights`) | **Simulated by default** | DEMO sample flights, labelled. Duffel TEST is a sandbox. LIVE is never verified or enabled. Production shows no prices without an approved live provider |
| Weather (`/api/weather`) | **Real** | Open-Meteo forecasts, up to 16 days, never filled in |

## Run it

```bash
cd Final-Mini-Project/scenario-3-trip-planner/kit
cp .env.example .env          # add OPENROUTER_API_KEY (and the Firebase settings for sign-in)
docker compose up --build     # travel API + backend + web app
# open http://localhost:5173
```

Details and the production overlay: [`DOCKER.md`](../DOCKER.md).

## How it behaves: the approval gate

The plan comes back as a proposal with a `pending_action`. **Approve** calls `save_trip` with exactly that payload. A
`TRIP-…` ID is shown only when the Trip Store returns one. **Reject** saves nothing.

## Evaluation

TODO: paste `evals/scorecard.md` here after `python evals/run_evals.py`, which makes real LLM calls.

There are 10 cases in `evals/cases.sample.jsonl`:

| Category | Cases |
|---|---|
| happy_path | 2 |
| rejection | 1 |
| revision | 1 |
| conflict | 2 |
| tool_failure | 1 |
| memory | 1 |
| guardrail | 1 |
| clarification | 1 |

**The failure we fixed:** TODO (cause, change, before and after).

## Guardrails and safety

- **Places:** only places from the tool log, each with a `source_url`. A listing that addresses AI agents is dropped (`researcher/validate.py`).
- **Approval:** only on a PASS from deterministic verification (`planning/verification.py`, `app/approval_policy.py`).
- **Writes:** `save_trip` only from `/api/approve`. Agents can call read tools only.
- **When a source is down,** the reply says so, and nothing is proposed for saving.
- **Production (`docker-compose.prod.yml`):**
  - no DEMO or TEST flight prices;
  - Open-Meteo only after the licence decision;
  - the kit's public development key is refused at start-up.

## Cost and latency

TODO: from the scorecard (`usage`). The LLM cost per plan has not been measured yet.

## What we'd fix next

- **Persistence:** move saved trips and sessions to real storage. Both are in memory now, which blocks a public deployment.
- **Wiring:** install Member 3's routers in `app/main.py`, place the components in the UI, and test them in a browser.
- **Measurement:** the LLM cost per plan, the scorecard, and one fixed failure with before and after.
- **Licence:** decide on Open-Meteo for a public deployment.

## Team

| | Built |
|---|---|
| **Member 1** | Agents and orchestration, revision and WHAT IF, approval, memory, MCP |
| **Member 2** | Google sign-in, the main pages, the WHAT IF UI, My Trips and the PDF export |
| **Member 3** ([SHAHDmu8](https://github.com/SHAHDmu8)) | City, airport, flight and weather integrations, WHAT IF fixtures, Docker, architecture and deployment docs, demo |

## Acknowledgements

Built during the **Agentic AI Bootcamp**, organized by Jerusalem High-Tech Foundry (JHF), in partnership with COMCEC.

**Data** (the lines from the kit README, "Licences and attribution", plus Member 3's sources):
- "Travel information from Wikivoyage (en.wikivoyage.org), CC BY-SA 4.0", with each listing's `source_url`
- "© OpenStreetMap contributors" (ODbL 1.0): Nominatim geocoding and FOSSGIS OSRM routing
- "Weather data by Open-Meteo.com" (CC BY 4.0)
- "Euro foreign exchange reference rates of the European Central Bank, via frankfurter.dev"
- "City data from GeoNames (geonames.org), CC BY 4.0, via Open-Meteo.com"
- "Airport data from OurAirports (ourairports.com), released to the public domain."
