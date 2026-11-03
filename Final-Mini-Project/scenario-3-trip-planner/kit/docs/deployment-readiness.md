# Deployment readiness and budget plan

**What this document is:**
- A draft by Member 3, written 2026-11-03.
- **Nothing was deployed publicly.** No cloud account, billing or paid API was created or used.
- **What was tested is local Docker only,** as recorded below.

**The target budget** is **$0–10 a month**. It is a planning constraint, not a promise: no free tier is unlimited, and **an app-level cap is not a financial hard cap** unless the provider itself enforces it.

## 1. What is ready, and the evidence

| Check (2026-11-03, Docker 29.8.2, Compose v5.6.0) | Result |
|---|---|
| `docker compose config --quiet` | Valid. Three services: `travel-api`, `app`, `web`. |
| `docker compose up -d --build --wait --wait-timeout 180` | All three **healthy** in 47 s |
| `GET :5173/` (nginx and the React build) | 200 |
| `GET :5173/health` (proxied) and `:8000/health` | 200 `{"status":"ok"}` |
| `GET :5173/api/flights/status` and `/api/airports?q=TLV` | **404**, as expected: `app/main.py` doesn't install Member 3's routers yet |
| Inside the app image, with `RIHLA_ENV=production` and no provider credentials | See below |
| `docker compose down` | Clean, no containers left. Volumes were not touched. |

**Inside the app image, in production with no credentials:**
- The modules import, and the airport dataset is packaged (`TLV` found, data date 2026-11-02).
- Flights: `503 flights_unavailable`, with no "DEMO" text in the answer.
- Weather: `503 weather_unavailable`.

The Docker setup itself is described in `DOCKER.md`, which covers the images, healthchecks, nginx, and keeping `.env` out of images.

**Docker working locally does not mean Rihla is ready for a public deployment.** The blockers are below.

## 2. Blockers before any public deployment

| # | Blocker | Owner | Why it matters |
|---|---|---|---|
| 1 | **Saved trips live only in memory.** `services/travel_api.py` appends saved trips to `STATE["trips"]`, filled at start-up from `services/data/trips.json`. | Member 1 (and the kit) | Every restart, redeploy or free-tier sleep loses every saved trip. A public app needs real storage, for example SQLite on a persistent disk, or a hosted database. |
| 2 | **Session memory is in process.** `app/memory.py` holds `sessions: dict`. | Member 1 | It needs a single worker, and is lost on restart. Several workers or instances would each see different sessions. |
| 3 | **The replay cache knows only the recorded cities**, Istanbul and Amman (`services/cache`). | Member 1 and the team | A public app needs `TRAVEL_MODE=live`. Then each upstream's policy applies: OpenStreetMap Nominatim allows about one request per second and needs a contact (`TRAVEL_CONTACT`); Open-Meteo's free API is non-commercial; and so on. |
| 4 | **Member 3's routers and components aren't wired in.** | Members 1 and 2 | The handoffs are in `docs/destinations.md`, `airports.md`, `flights.md` and `weather.md` |
| 5 | **This branch (`feature/destinations-flights`) isn't merged into `main`.** WHAT IF itself is on `main` since PR #15 (`6df209d`). | The team | Merge it through a reviewed PR first (a trial merge had no conflicts), then run the full test suite on the result |
| 6 | **The AI cost per plan isn't measured.** | Member 1 | See §4 |
| 7 | **Licensing decisions** | The team | Open-Meteo is free only for non-commercial use (Duffel LIVE costs money; see §4). Decide whether the deployment is non-commercial (`RIHLA_OPEN_METEO_NONCOMMERCIAL=true`), and keep Duffel LIVE off. |
| 8 | **HTTPS and cookie settings** | Member 2 and the team | `RIHLA_COOKIE_SECURE=true`, `RIHLA_ALLOWED_ORIGINS=<the public origin>`, a strong `RIHLA_SESSION_SECRET`, and the Firebase authorised domains |

## 3. Configuration for a public deployment

### Always deploy with the production overlay

The server can't tell by itself whether it is a laptop or a public launch, so **production is set by the deployment command, not guessed.**

```sh
cd kit
# TRAVEL_API_KEY must hold a private key (in kit/.env or the shell); compose refuses to start without one.
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet      # check first
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
```

**What `docker-compose.prod.yml` does:**
- It sets `RIHLA_ENV=production` **literally** in the `app` service. It can't be left out, defaulted, or overridden from `.env` or the shell (`environment` takes precedence over `env_file`).
- It requires `TRAVEL_API_KEY` (`${TRAVEL_API_KEY:?…}`), so the kit's public default key is not used.
- It publishes only the web port: `app` (8000) and `travel-api` (8103) stay inside Docker. This uses Compose's `!reset` tag, so it needs Docker Compose 2.24 or newer.

**Checked on 2026-11-03** with `docker compose … config`, printing only `RIHLA_ENV` and the ports:

| Case | Result |
|---|---|
| Without `TRAVEL_API_KEY` | Compose refuses: "required variable TRAVEL_API_KEY is missing a value" |
| With the overlay | `app` has `RIHLA_ENV=production`; `app` and `travel-api` publish no ports; `web` keeps 5173 |
| `RIHLA_ENV=development` in the shell, with the overlay | Still `production` |
| The base file alone (local use) | `RIHLA_ENV=development`, with ports 8000, 8103 and 5173 |

**What still depends on people:**
- **Running the base file alone** on a public host would be development. The server then logs a warning at start-up ("RIHLA_ENV is not set …"), and flights stay DEMO-labelled.
- **Any other deployment tool** (a PaaS, systemd, Kubernetes) must set `RIHLA_ENV=production` itself.
- **Unknown values** (`prod`, `staging`, typos) already count as production.

The variables are listed below by name only; every secret stays in the host's secret store or in `kit/.env`, never in Git or in an image.

| Variable | Production value | Notes |
|---|---|---|
| `RIHLA_ENV` | `production` | **Required.** Set by `docker-compose.prod.yml`. Without it the server counts as development: it shows DEMO flights (labelled) and logs a warning. |
| `OPENROUTER_API_KEY` | secret | The crew's LLM |
| `OPENROUTER_MODEL` / `MODEL`, `RESEARCHER_MODEL` | as chosen | Cost depends on the model |
| `RIHLA_LLM_TIMEOUT_SECONDS`, `RIHLA_LLM_MAX_RETRIES` | small | Fewer retries means a lower worst-case cost |
| `TRAVEL_API_URL`, `TRAVEL_API_KEY` | the internal URL, and a secret that isn't `dev-key-change-me` | The kit's default key is public |
| `TRAVEL_MODE`, `TRAVEL_CONTACT` | `live`, plus a real contact | See blocker 3 |
| `TRAVEL_TRAVELLER_ID` | — | The kit's single-traveller store, kept until per-user storage exists |
| `RIHLA_SESSION_SECRET`, `RIHLA_COOKIE_SECURE=true`, `RIHLA_ALLOWED_ORIGINS`, `RIHLA_FIREBASE_PROJECT_ID`, `RIHLA_SESSION_TTL_HOURS` | — | Sign-in (Member 2) |
| `VITE_FIREBASE_*` | — | Built into the frontend. These are public Firebase web config values, not secrets. |
| `VITE_ENABLE_LIVE_AI` | as Member 2 decides | Read by `App.jsx` |
| `DUFFEL_ACCESS_TOKEN`, `RIHLA_FLIGHTS_ALLOW_LIVE` | **not set** | Production then says flights are unavailable, and never shows sample prices |
| `RIHLA_FLIGHTS_MAX_PER_MINUTE` / `_PER_DAY` | `10` / `60` if LIVE is ever approved | Per process |
| `RIHLA_OPEN_METEO_NONCOMMERCIAL` *or* `RIHLA_OPEN_METEO_API_KEY` | per the licensing decision | One decision covers weather and city search (`app/open_meteo.py`). Without either, both are unavailable in production (`503 weather_unavailable` and `503 destinations_unavailable`). |
| `RIHLA_WEATHER_MAX_PER_DAY`, `RIHLA_DESTINATIONS_MAX_PER_MINUTE` | defaults | Per process |

**Security checks done in Member 3's code:**
- Secrets are read only on the server, and none is returned in an answer.
- Tokens are never logged. Open-Meteo's `apikey` is redacted from httpx's request logs, and a test checks it.
- `/api/flights` and `/api/weather` answer `Cache-Control: no-store` or `private`.
- All of Member 3's endpoints are GET only: nothing books, orders or pays.

**Not reviewed here:** the sign-in implementation (Member 2's), and the kit's travel API exposure. In production `travel-api` should not be reachable from the internet. For local use, `docker-compose.yml` publishes `travel-api` on 8103, `app` on 8000 and `web` on 5173. On a public host, only the web port should be open; the others should be firewalled or left unpublished.

## 4. Running cost, and what can go over

| Item | Cost basis (source) | Risk |
|---|---|---|
| **LLM (OpenRouter)** | `gpt-4.1-mini` is about **$0.40 per million input tokens and $1.60 per million output tokens** (third-party trackers; **check openrouter.ai**) | **The biggest risk.** A plan runs several agents, a revision runs more, and retries multiply both. **Tokens per plan have not been measured.** |
| Duffel LIVE flights | $0.005 per search beyond 1,500 searches per order; $3 per order (duffel.com/pricing, checked 2026-11-02) | **Off by default.** With no bookings, 60 searches a day would be about $9 a month. **Keep it off.** |
| Open-Meteo | Free and non-commercial: under 10,000 calls a day per IP. The paid plan's price isn't published. | Licence rather than cost. A commercial Rihla needs a paid plan. |
| Open-Meteo Geocoding, OurAirports | Free or bundled | — |
| Firebase Auth (Google sign-in) | Not reviewed in this pass | Check Firebase's pricing before launch |
| Hosting | §5 | Sleep, limits, and overage when a payment method is attached |

### The LLM cost per plan

**The formula:** `cost = input_tokens × $0.40 / 1,000,000 + output_tokens × $1.60 / 1,000,000`.

**An illustrative example, with tokens that were not measured:**
- Suppose a plan used **60,000 input and 12,000 output tokens** across all its agents.
- It would cost about **$0.024 + $0.019 ≈ $0.04**.
- $8 of LLM budget would then cover about 200 plans a month.

**Measure it before planning on it.**
- `POST /api/chat` returns `performance`: the LLM calls and tokens of each stage.
- Record it for the sample cases, then put the real numbers here.

**Capping it:**
- OpenRouter works on prepaid credits, and keys can have credit limits. If that holds, it is a cap enforced by the provider itself, which our code can't give. **This is unverified here.**
- Our own per-process limits are useful, but are not a financial cap.

## 5. Hosting options

These were checked from official pages where shown, on 2026-11-03. **Nothing was activated.**

| Option | Facts | Fits Rihla? |
|---|---|---|
| **Cloudflare Pages** (frontend) | Official limits: 500 builds a month, 1 build at a time, 20-minute build timeout, 20,000 files and 25 MiB per file, 100 custom domains a project. The limits page states no bandwidth or static-request limit. Commercial use on Free is stated by third-party sources only (**unverified**). | **Good** for the static React build. The `/api/*` calls must then go to the backend's origin, which means changing `RIHLA_ALLOWED_ORIGINS` and the cookies. |
| **Render, free web service** (backend) | Official: spins down after 15 minutes idle, about 1 minute to wake, 750 free hours per workspace a month, all free services suspended when the hours run out. Bandwidth overage is billed if a payment method is on file, otherwise the services are suspended. Render says **"don't use free instances for production"**. | **No, for real use.** Sleeping loses in-memory sessions and trips (blockers 1 and 2). Two always-on services would need about 1,488 hours, more than the 750 free. |
| **Google Cloud Run** | Free tier: about 2 million requests and 180,000 vCPU-seconds a month (third-party summaries of the pricing page). **A billing account is required.** | Poor fit today. Instances are stateless and scale to zero, while Rihla keeps state in process. And a billing account is a spending risk. |
| **One small VPS running this `docker compose`** | Prices **not checked in this pass** | **The best fit for the current architecture:** one machine, one worker, the travel API not exposed. Add HTTPS with Caddy or a Cloudflare proxy, and a persistent disk once trips are stored on it. |

### Proposed plan

This is a proposal; nothing is activated.

1. **First, fix blockers 1 and 2** (persistent trips, and single-worker sessions), and **measure the LLM cost** (blocker 6).
2. **Frontend:** the `web` container on the same VPS (simplest, with same-origin cookies), or Cloudflare Pages.
3. **Backend:** one small VPS (price to be confirmed) running `travel-api` and `app` through `docker compose -f docker-compose.yml -f docker-compose.prod.yml`, with only the web port public.
4. **Feature switches:**
   - `RIHLA_ENV=production`, set by the overlay;
   - flights unavailable (no `DUFFEL_ACCESS_TOKEN`);
   - weather and destinations only after the non-commercial decision.
5. **LLM:** prepaid OpenRouter credits with a key limit (to verify). Lower the retries. Consider a per-user daily plan limit, which Member 1 would add.
6. **Expected month:** the VPS (to be confirmed) plus LLM credits, up to the remaining budget. **With a public audience, usage can't be guaranteed under $10.** When the credits run out, planning stops, which is the intended failure.

## 6. Pre-deployment checklist

- [ ] Trips are stored persistently, and survive a `docker compose restart travel-api`.
- [ ] A single app worker, or shared session storage.
- [ ] Deployed with `-f docker-compose.yml -f docker-compose.prod.yml`, or `RIHLA_ENV=production` set by the hosting tool. The start-up log shows no "RIHLA_ENV is not set" warning.
  - [ ] `/api/flights/status` shows `available: false`, or LIVE has been explicitly approved.
  - [ ] `/api/weather/status` and `/api/destinations/status` match the Open-Meteo licensing decision.
- [ ] `TRAVEL_API_KEY` is not `dev-key-change-me`, `RIHLA_SESSION_SECRET` is strong, and `RIHLA_COOKIE_SECURE=true` is set.
- [ ] Only the web port is public. 8103 (`travel-api`) and 8000 (`app`) are closed.
- [ ] HTTPS is on, and `RIHLA_ALLOWED_ORIGINS` is the public origin only.
- [ ] The LLM cost per plan has been measured, and the credit limit is set at the provider.
- [ ] `git ls-files | grep -i '\.env$'` is empty, and the images are built without `.env` (`.dockerignore`).
- [ ] Member 3's handoffs are done, and the four routes answer through the proxy.
