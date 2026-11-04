# Flight search and price comparison

**Owner:** Member 3. The feature is optional and for information only.

**What it never does:**
- Rihla never books flights, creates orders or takes payments.
- Flight prices are kept apart from the trip budget.

**Status:** wired into the app. The trip page's "Weather and flights" section (`TripTravelInfo`) offers it, closed until the traveller opens it, and a failure in that section cannot take the itinerary down with it (see "Isolation"). No Duffel token is configured on this project, so every search answers with **DEMO** data, clearly labelled; **no real Duffel call has ever been made**.

| Part | File |
|---|---|
| Validation, cache, rate limit, expiry filter, sorting, price summary | `app/flights/service.py` |
| Duffel adapter, DEMO provider, provider choice | `app/flights/providers.py` |
| Routes `GET /api/flights` and `GET /api/flights/status` (GET only) | `app/flights/routes.py` |
| `RIHLA_ENV`: development, test or production | `app/deployment_env.py` |
| `install_flights(app)` | `app/flights/__init__.py` |
| React: form and results | `rihla-frontend/src/features/flights/FlightSearch.jsx` |
| React: one offer | `rihla-frontend/src/features/flights/FlightOfferCard.jsx` |
| API client and pure helpers | `rihla-frontend/src/features/flights/flightsApi.js`, `flightState.js` |
| Airports near a chosen city (`GET /api/airports/near`) | `app/airports/service.py` (`AirportSearch.nearest`), `app/airports/routes.py` |
| React: the nearby-airports list | `rihla-frontend/src/features/airports/NearbyAirports.jsx`, `airportState.js` |
| React: error boundary around the trip page's weather and flights | `rihla-frontend/src/features/trip-travel/TravelInfoBoundary.js` |
| Tests, backend | `tests/test_flights.py`, `tests/test_flights_integration.py`, `tests/test_airports_near.py` |
| Tests, frontend | `features/flights/flights.test.js`, `flightComparison.test.js`, `features/airports/nearby.test.js`, `features/trip-travel/travelBoundary.test.js` |
| Real DEMO answer used by the frontend tests | `rihla-frontend/src/features/flights/fixtures/demo_tlv_lhr_round_trip.json` |
| Real nearby-airport answers used by the frontend tests | `rihla-frontend/src/features/airports/fixtures/near_*.json` |

## Provider selection

Both candidates were checked on 2026-11-02.

| | Amadeus Self-Service (Flight Offers Search) | Duffel Flights API |
|---|---|---|
| Access | The Self-Service portal was announced for decommissioning on 17 July 2026, and new registrations were paused. Today `test.api.amadeus.com` has no DNS address. Only Enterprise APIs remain, by contract. | Sign up, then create a test token in the dashboard (`duffel_test_…`). |
| Test data | — | "Duffel Airways" (`ZZ`). Duffel says test mode shows no realistic schedules or prices. |
| Cost | — | Test mode: "no danger of spending any money". Live mode: $3 per order, plus $0.005 per search beyond 1,500 searches per order. With no bookings, every live search can be billed. |
| Verdict | Not usable | **Selected:** Duffel, in **test mode** |

**Sources:**
- [Duffel test mode](https://duffel.com/docs/api/overview/test-mode)
- [Create an offer request](https://duffel.com/docs/api/v2/offer-requests/create-offer-request)
- [Offer schema](https://duffel.com/docs/api/v2/offers/schema)
- [Errors](https://duffel.com/docs/api/overview/errors)
- [Duffel pricing](https://duffel.com/pricing)
- [Report on the Amadeus Self-Service shutdown](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers)

### Environments and how the provider is chosen

`RIHLA_ENV` decides what data may be shown. It is read by `app/deployment_env.py`:

| `RIHLA_ENV` | Meaning |
|---|---|
| not set | `development`, and a warning is logged once ("RIHLA_ENV is not set …") |
| `test` | `test` |
| `production` | `production` |
| any other value, such as `prod` or `staging` | `production` (logged), so a typo fails closed |

**Unset means development.** A server can't tell a laptop from a public launch, so leaving the variable unset keeps
development easy. Production is made explicit by the deployment tooling: `docker-compose.prod.yml` sets
`RIHLA_ENV=production` literally. Deploy with
`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait`; see
`docs/deployment-readiness.md` §3.

The provider is chosen once, at start-up:

| Environment | `DUFFEL_ACCESS_TOKEN` | `RIHLA_FLIGHTS_ALLOW_LIVE` | Provider | `data_mode` |
|---|---|---|---|---|
| development or test | not set | — | Rihla DEMO data, with a notice | `DEMO` |
| development or test | `duffel_test_…` | — | Duffel sandbox | `TEST` |
| development | `duffel_live_…` | not `true` | DEMO, with a notice | `DEMO` |
| development | `duffel_live_…` | `true` | Duffel live (**may be billed**) | `LIVE` |
| test | `duffel_live_…` | any | DEMO. Live is never used in test. | `DEMO` |
| **production** | `duffel_live_…` | `true` | Duffel live (**may be billed**) | `LIVE` |
| **production** | anything else, including a test token or no token | any | **unavailable** | none |

**Production fails closed:**
- **Unavailable state:** every search answers `503 flights_unavailable`. This happens before the input is even checked.
- **The status endpoint** says `available: false`.
- **The page** explains that real-time prices aren't available here, and disables the search button.
- **What production never does:**
  - It never shows DEMO or TEST offers, even if such a provider were wired in by mistake. `FlightSearch` refuses any answer that isn't `LIVE` and drops any non-LIVE offer.
  - It never falls back to DEMO when the live provider fails; the error is shown instead.

A live token on its own never turns on live searches. Live searches need the explicit switch and the team's approval.

**No external flight-search link is offered.** No link was verified for behaviour and terms, so the page only says "check airline or travel websites directly".

## Real, test and demo data

| Mode | What it is | What the traveller sees |
|---|---|---|
| `LIVE` | Real offers from Duffel at the time shown. They expire, and `expires_at` is kept. | Green "LIVE" badge. "Prices change and expire." |
| `TEST` | Duffel's sandbox, mainly the made-up airline Duffel Airways | Amber "TEST" badge. "Not real flights, schedules or prices." |
| `DEMO` | Generated by Rihla. The same search always gives the same 4 offers. | Violet "DEMO" badge on the banner and on every card. "Sample flights made up by Rihla." |

**How DEMO data is built:**
- **Airlines:** "Rihla Demo Air", "Sample Skyways", "Example Airlines" and "Placeholder Jet". They have no IATA codes, so no real airline's code is used.
- **Flight numbers:** "DEMO 123".
- **Durations:** from the great-circle distance between the airports in the bundled airport data. One-stop routes connect through a hub such as FRA or DOH.
- **Prices:** made up from the distance and cabin class. They are not estimates of real fares.
- **Times:** in UTC, and every card says "times in UTC".
- **Baggage:** one of the 4 offers always has unknown baggage, so the UI's "not stated" case shows up in demos.

**No real Duffel call has been made yet,** because no token was available. The Duffel adapter is tested against synthetic answers built in the shape of Duffel's documented schema. The first real test-mode call should be made by the team member who creates the test token.

## Setup

1. **Without a token:** nothing to do. The feature runs in DEMO mode.
2. **For Duffel test mode:**
   1. Create a free Duffel account and switch the dashboard to "Developer test mode".
   2. Create an access token.
   3. Put it in `kit/.env`, which Git ignores and Docker never copies into an image:
      ```
      DUFFEL_ACCESS_TOKEN=duffel_test_...
      ```
   4. Restart the app. The response's `data_mode` should become `TEST`.
3. **Never commit the token.** If it leaks, revoke it in the Duffel dashboard.

### Environment variables

| Variable | Default | |
|---|---|---|
| `DUFFEL_ACCESS_TOKEN` | not set (DEMO) | A secret. `duffel_test_…` for TEST. |
| `RIHLA_FLIGHTS_ALLOW_LIVE` | not set | Must be `true` before a `duffel_live_…` token is used. Live searches may be billed. |
| `RIHLA_FLIGHTS_TIMEOUT_S` | `25` | How long to wait for Duffel, 3–70 s. Duffel's `supplier_timeout` is set 5 s shorter. |
| `RIHLA_ENV` | `development` | `development`, `test` or `production`. See the table above. |
| `RIHLA_FLIGHTS_MAX_PER_MINUTE` | `30` | The most provider calls per minute, per server process. Cached searches and DEMO searches don't count. |
| `RIHLA_FLIGHTS_MAX_PER_DAY` | `500` | The most provider calls per UTC day, per server process. Then `429 daily_limit_reached` until midnight UTC. |
| `RIHLA_FLIGHTS_URL` | `https://api.duffel.com` | For a proxy or a mock |

### Cost controls, and what they don't guarantee

**These caps aren't a financial hard cap:**
- The per-minute and per-day caps are counted **in the memory of one server process**.
- With several workers or instances, each one counts on its own.
- A restart resets the counts.
- Duffel itself doesn't enforce a spending limit for Rihla.

**Before turning LIVE on in production:**
- Run a single worker, or move the counters to a shared store.
- Agree a budget.
- Watch the Duffel dashboard.

**At the Duffel prices checked on 2026-11-02:** with no bookings, 500 live searches a day could cost about 500 × $0.005 = **$2.50 a day, or about $75 a month**, which is over a $10 budget. Keep LIVE off, or set `RIHLA_FLIGHTS_MAX_PER_DAY` to about 60 or less.

**Logging:** errors go to the `rihla.flights` logger with the error code and HTTP status only. The token, the request headers and the offers are never logged, and a test checks this.

## Endpoints

`GET /api/flights/status` says what the server can offer, without searching. The page reads it when it opens.

```json
{"environment": "production", "available": false, "data_mode": null, "provider": null,
 "notice": "No approved live flight provider is configured (production needs a live Duffel token and RIHLA_FLIGHTS_ALLOW_LIVE=true; it never shows test or demo flights).",
 "booking_supported": false, "limits": {"per_minute": 30, "per_day": 500, "scope": "per server process"}}
```

`GET /api/flights`

- **Read-only.** No sign-in is needed. Any other method returns 405.
- **Not cached by browsers:** every answer carries `Cache-Control: no-store`.

| Parameter | Required | |
|---|---|---|
| `origin`, `destination` | yes | IATA codes, case-insensitive. They must exist in the bundled airport data and must differ. |
| `departure_date` | yes | `YYYY-MM-DD`, from today up to 361 days ahead |
| `return_date` | no | Empty means one way. It must not be before `departure_date`. |
| `adults` | no (1) | 1–9 |
| `cabin_class` | no (`economy`) | `economy`, `premium_economy`, `business` or `first` |
| `limit` | no (20) | 1–50 offers in the answer |

**Duffel request:** Rihla sends `POST /air/offer_requests?return_offers=true&supplier_timeout=…` with:
- one slice for a one-way trip, or two for a round trip;
- one `{"type": "adult"}` entry per passenger;
- `max_connections: 1`.

That is the only Duffel endpoint Rihla calls. A test checks that the code contains no orders or payments path.

### Example: DEMO, a real answer from this server

`GET /api/flights?origin=TLV&destination=LHR&departure_date=2026-12-01&return_date=2026-12-08&adults=2` (shortened)

```json
{
  "query": {"origin": "TLV", "destination": "LHR", "departure_date": "2026-12-01", "return_date": "2026-12-08",
            "adults": 2, "cabin_class": "economy", "trip_type": "round_trip"},
  "data_mode": "DEMO",
  "provider": "Rihla demo data",
  "retrieved_at": "2026-11-02T12:00:00Z",
  "cached": false,
  "count": 4, "total_offers": 4,
  "offers": [{
    "id": "demo:dcd71c09cc-2", "provider_offer_id": null,
    "airline": {"name": "Example Airlines", "iata_code": null},
    "total_amount": "1070.00", "currency": "USD", "passengers": 2, "cabin_class": "economy",
    "slices": [
      {"origin": "TLV", "destination": "LHR", "departing_at": "2026-12-01T15:15", "arriving_at": "2026-12-01T23:20",
       "duration_minutes": 485, "stops": 1, "connections": ["FRA"], "segments": ["…"]},
      {"origin": "LHR", "destination": "TLV", "departing_at": "2026-12-08T12:00", "arriving_at": "2026-12-08T19:50",
       "duration_minutes": 470, "stops": 1, "connections": ["FRA"], "segments": ["…"]}],
    "baggage": {"checked": null, "carry_on": null},
    "expires_at": null, "time_basis": "utc", "data_mode": "DEMO", "provider": "Rihla demo data"
  }, "…3 more"],
  "currencies": ["USD"], "comparable": true,
  "cheapest": {"offer_id": "demo:dcd71c09cc-2", "total_amount": "1070.00", "currency": "USD"},
  "cheapest_by_currency": {"USD": {"offer_id": "demo:dcd71c09cc-2", "total_amount": "1070.00", "currency": "USD"}},
  "skipped_offers": {"unusable": 0, "expired": 0},
  "notices": [
    "DEMO data: sample flights made up by Rihla to show the feature. They are not real flights, schedules or prices.",
    "No flight provider is set up on this server (DUFFEL_ACCESS_TOKEN). Showing DEMO data.",
    "Flight prices are for information only and are not part of the trip budget. Rihla does not book flights or take payments."],
  "booking_supported": false
}
```

### What a TEST offer looks like

The values below are synthetic, in Duffel's documented shape:

```json
{"id": "duffel:off_1", "provider_offer_id": "off_1", "airline": {"name": "Duffel Airways", "iata_code": "ZZ"},
 "total_amount": "412.30", "currency": "USD", "passengers": 1, "cabin_class": "economy",
 "slices": [{"origin": "TLV", "destination": "LHR", "departing_at": "2026-12-01T08:00",
             "arriving_at": "2026-12-01T11:10", "duration_minutes": 310, "stops": 0, "connections": [],
             "segments": [{"flight_number": "ZZ101", "marketing_carrier": {"name": "Duffel Airways", "iata_code": "ZZ"}, "…": "…"}]}],
 "baggage": {"checked": 1, "carry_on": 1}, "expires_at": "2026-11-02T12:30:00Z", "time_basis": "local",
 "data_mode": "TEST", "provider": "Duffel"}
```

### Rules the answer follows

- **Prices are never invented.**
  - An offer without a positive price, with a currency code that isn't 3 capital letters, or without a usable journey is dropped, and counted in `skipped_offers.unusable`.
  - An offer whose `expires_at` has passed is dropped, also when it comes from the cache, and counted in `skipped_offers.expired`.
- **Sorting:** offers are sorted by `total_amount` (the total for every passenger) within one currency, then by travel time.
- **Several currencies:**
  - Offers are grouped by currency, with the most common currency first.
  - They are never compared across currencies, because there is no verified conversion.
  - `comparable` is `false`, `cheapest` is `null`, and `cheapest_by_currency` gives the cheapest offer for each currency.
- **Baggage:** `checked` and `carry_on` are the first passenger's allowance, the lowest over all segments. `null` means the provider didn't say; it is never assumed.
- **Times:** `time_basis` is `local` for Duffel (each airport's local time, as Duffel sends it) and `utc` for DEMO. `retrieved_at` and `expires_at` are UTC.
- **Stops:** `stops` counts connections plus technical stops. `connections` lists the airports where the traveller changes planes.
- **Caching:** each search is cached for 5 minutes. A cached answer keeps its original `retrieved_at`.

### Errors

Errors have the shape `{"error": {"code", "message", "retryable", "field"?, "retry_after"?}}`. `field` names the form field at fault.

| Status | `code` | When |
|---|---|---|
| 422 | `missing_airport`, `invalid_airport_code`, `unknown_airport`, `same_airport` | The airport is missing, is not 3 letters, is not in the airport data, or is the same at both ends |
| 422 | `invalid_date`, `date_in_past`, `date_too_far`, `return_before_departure` | The date is bad |
| 422 | `invalid_passengers`, `invalid_cabin_class` | Adults outside 1–9, or an unknown cabin class |
| 503 | `flights_unavailable` | No provider this deployment may use, for example production without approved LIVE. Not retryable. |
| 429 | `rate_limited` | This server's per-minute cap was reached (header `Retry-After`) |
| 429 | `daily_limit_reached` | This server's daily cap was reached (header `Retry-After`, until midnight UTC) |
| 503 | `provider_rate_limited` | Duffel answered 429. `retry_after` comes from `ratelimit-reset`. |
| 503 | `provider_unavailable`, `airports_unavailable` | Duffel can't be reached, or the airport data is missing |
| 504 | `provider_timeout` | No answer within `RIHLA_FLIGHTS_TIMEOUT_S` |
| 502 | `provider_auth_failed` | Duffel answered 401 or 403: an invalid or expired token. The token never appears in any answer. |
| 502 | `provider_error` | Duffel 5xx, including airline errors (`airline_internal` 502/504) |
| 502 | `provider_rejected`, `provider_bad_response` | Duffel refused the search, or sent an unreadable answer |

**No offers** is a normal `200` answer with an empty list and a notice; it is not an error.

**Failures are never cached and never replaced by DEMO data.** A traveller in TEST or LIVE mode sees the error, not made-up flights.

## Choosing the airports

Flights are searched between **airports**, and a city is not an airport: the trip's cities are used only to propose
airports, and the traveller chooses. Everything below is local data (OurAirports, public domain): no network, no key.

- `GET /api/airports/near?lat=…&lon=…&country=IL` lists the airports near a place, nearest first, each with its
  `distance_km` and `in_country`. Only airports a traveller can fly from are offered: an IATA code, coordinates and
  OurAirports' scheduled-service flag. That flag is data, **not a promise that an airline flies there today or that a
  route exists**; nothing here says which routes are served. Every parameter is validated (coordinates in range, a
  known two-letter country, 1–500 km, 1–10 airports) with the same error shape as the other airport routes.
- **The place's country decides.** Airports in the place's own country are listed up to 150 km; an airport across a
  border only when it is within 80 km, always marked `in_country: false` ("In Jordan, outside Israel", "Other
  country"). Paris, France and Paris, Texas are told apart by coordinates and country, never by name: Texas lists
  Tyler and Texarkana, 146 km away, and no French airport; France lists Orly and Charles de Gaulle.
- **A city without an airport** is handled honestly. Jerusalem lists Tel Aviv (41 km, same country) and Amman (74 km)
  and Amman Civil (77 km) marked as another country, with a reminder to check entry rules. Where nothing is within
  reach the list says so, and the traveller searches by name or code.
- **Ranked by distance only.** The list says so: the nearest airport is not always the best one for the route
  (Istanbul's nearest is Sabiha Gökçen, but Istanbul Airport is as real a choice).
- **Preselecting.** An airport is put into its box only when exactly one clearly qualifies: it is the only airport with
  scheduled service within 100 km in the place's own country, it is within 60 km, and none across the border is within
  80 km (`suggested` in the answer). Tbilisi, Cusco and Santiago qualify; London, Paris, Rome, Istanbul, Tokyo, Amman and
  Jerusalem do not, and the traveller chooses. The preselected airport is an ordinary, editable choice, it never
  replaces something the traveller already did in that box, and the list says it was preselected.
- Without a country, `in_country` is null and nothing is ever suggested.

## Isolation

- The "Weather and flights" section is wrapped in `TravelInfoBoundary`: if it throws while rendering, only a short
  notice ("Weather and flights could not be shown. Your itinerary is not affected.", with "Try again") replaces it.
  Event handlers and network failures are not caught by boundaries; `FlightSearch` handles its own in state.
- `GET /api/flights` is a separate route. A flight failure (Duffel down, slow, refusing) is a clear error for that route
  only; `POST /api/chat` does not call it and works the same. A test runs both in one app.
- The plan, the budget and the chat contract do not use flight search at all (a test checks every module that builds
  them, and `budget_analyst` lists "flights and intercity transport" as not priced).


## Component

```jsx
import { FlightSearch } from './features/flights'

<FlightSearch />
```

**Optional starting values from a trip.** These props only fill the form when it first appears; what the
traveller changes afterwards is kept. Remount with a new `key` for another trip (`TripTravelInfo` does this, see
`docs/frontend-integration.md`). A hint is text typed into an airport box, which then lists matching airports.

```jsx
<FlightSearch departureHint="London" departureCountry="GB" arrivalHint="Amman"
  departurePlace={fromCity} arrivalPlace={toCity}
  departureDate="2026-12-01" returnDate="2026-12-08" adults={2} title="Flights for this trip" />
```

- `departurePlace` and `arrivalPlace` are the cities chosen in the destination box (`name`, `region`, `country`,
  `countryCode`, `latitude`, `longitude`). A place without a name, a country code or real coordinates is dropped, never
  completed. With one, the form lists the airports near it (see "Choosing the airports"), and its country starts that
  side's country picker (`arrivalCountry` and `departureCountry` do the same by themselves).
- A country code that the countries list does not contain is dropped, not kept as a hidden filter.
- A party of more than 9 starts at 9 adults, and the form says so.
- A start date without a return date starts a one-way search.

**The form:**
- Optional **Departure country** and **Arrival country** pickers (from `GET /api/airports/countries`). Choosing a
  country empties that box and limits it to that country's airports; "Any country" searches worldwide. Without the
  countries route (an older server), the pickers are simply not shown.
- "From" and "To" are `AirportSearch` boxes from `features/airports`. They need an airport with an IATA code.
- Round trip or one way, with a line that says what it means: round trip is one price for the outbound and the
  return flight together, one way is the outbound flight only. Adults only (up to 9) and no multi-city trips.
- Departure and return dates. Past dates can't be picked.
- Adults, 1–9, and the cabin class.
- The form checks itself before sending. Server errors are shown next to the field they name.
- **Results always match the form.** Changing the route, a date, the trip type, the passengers or the cabin hides
  the offers (or the error) of the previous search and says "Your search changed. Search again". An older search
  that answers after a newer one started is ignored (`searchKey`, `resultState`, `latestOnly` in `flightState.js`).

**The results:**
- A banner with the data-mode badge, the provider, the notices and the retrieval time.
- **Cheapest vs fastest**, one line per currency: "The cheapest offer is also the fastest", or both offers with the
  extra cost of the fastest and the time it saves. On DEMO and TEST data the line repeats "simulated, not bookable".
  Prices in different currencies are never compared.
- What was searched, as the server ran it ("Round trip · TLV ⇄ LHR · 2 adults · 2026-12-01 to 2026-12-08").
- A sort control: lowest price, highest price, or shortest travel time (offers with an unknown duration last). Each
  currency is sorted on its own.
- A warning when the offers are in more than one currency.
- One card per offer, showing:
  - the airline;
  - a **Round trip** or **One way** tag, and "both directions" or "outbound only" beside the price;
  - the total price for all passengers, and **under it a line that says what the price is**: "Simulated price · not a
    real fare · not bookable" (DEMO), "Test price · not a real fare · not bookable" (TEST), or the provider price that
    changes and expires and is not bookable on Rihla (LIVE);
  - the outbound and return times and dates, with "+1" for an overnight arrival, and whether times are local or UTC;
  - the duration, the stops and the connection airports, and the total travel time of a round trip;
  - the flight numbers;
  - the baggage, or "not stated";
  - the cabin;
  - "Offer valid until".
- A "Cheapest in USD" tag and a "Fastest in USD" tag per currency. The fastest is the shortest whole journey (both
  directions), the cheaper one on a tie; an offer with any unknown duration is never called fastest.
- Loading, empty and error states. An error that can be retried shows "Try again".

**Accessibility:**
- Real `<label>`s, and a `fieldset` with a `legend` for the trip type.
- `aria-invalid` and `aria-describedby` on fields with errors.
- An `aria-live` results region, a `role="alert"` error, and an `article` with an accessible name on each card.

**Layout:** one column on a phone, a 2-column airport row and a 4-column details row on wider screens.

**No booking:** the component has no book, buy or pay button, and the frontend has no POST to flights. A test checks this.

## Wiring

Done. Kept here for the next person to deploy it.

- **Backend:** `app/main.py` calls `install_flights(app)` and `install_airports(app)` (on `main`, `a26c63e`).
- **Frontend:** `TripDashboard.jsx` renders `TripTravelInfo` for a generated trip (never the sample), inside
  `TravelInfoBoundary`. `TripTravelInfo` passes the FROM and TO cities as `departurePlace` and `arrivalPlace`.
- **Docker:** no change is needed. The `app` service loads `kit/.env`, so a `DUFFEL_ACCESS_TOKEN` in `.env` reaches the
  container at run time and is never part of an image. Without a token the container runs in DEMO mode.
- **For any public deployment** use `docker-compose.prod.yml`, which sets `RIHLA_ENV=production`, or set it in the
  hosting tool. Without it the server counts as development and shows DEMO flights, clearly labelled; with it and no
  approved LIVE provider, flight search says it is unavailable.

**Leave the crew alone.** Don't give flights to the crew, and don't add them to `estimated_cost` or `budget_total`.
`/api/chat`, `/api/approve` and the official contract stay unchanged.

**Verify:**
- `curl "http://localhost:8000/api/flights?origin=TLV&destination=LHR&departure_date=<a future date>"` returns
  `"data_mode": "DEMO"`, or `TEST` when a test token is set.
- `curl "http://localhost:8000/api/airports/near?lat=31.769&lon=35.216&country=IL"` lists Tel Aviv, with Amman marked
  `"in_country": false`.
- `python -m pytest -q tests/test_flights.py tests/test_flights_integration.py tests/test_airports_near.py` passes, and
  so does `npm test` in `rihla-frontend`.
- In the browser: finish a trip, open "Compare flights (optional)", choose airports, search. The violet DEMO banner, a
  "Simulated price · not bookable" line on every card, and the "Cheapest vs fastest" line appear.

## Known limitations

- **Duffel is untested against the real service.** The adapter has not called Duffel yet, because there was no token.
  It is tested against synthetic answers in Duffel's documented shape, including end to end with a mocked Duffel
  (`tests/test_flights_integration.py`). TEST data, even once connected, is Duffel Airways with unrealistic prices.
- **LIVE needs approval.** It is off unless explicitly allowed, and live searches may be billed by Duffel.
- **DEMO data is not an estimate.** Its prices and times are made up and must never be read as real fares.
- **Search options:** adults only, with no children or infants; at most one connection; no flexible dates; no multi-city trips.
- **Airport codes:** the bundled airport data decides which codes are known. A real airport missing from that data is
  refused with `unknown_airport`. "Scheduled service" is OurAirports' flag, not a list of routes.
- **Nearby airports** are straight-line distances: they say nothing about road or rail travel, border crossings, or
  which airport has the flights a traveller needs.
- **Times:** Duffel's times are local without a UTC offset, so cards can't compare times across time zones. Durations come from the provider.
- **Caching and limits:** the cache and the per-minute cap are per server process and in memory.
- **Currencies:** no currency conversion. The kit's ECB tool is for the itinerary budget, not for comparing flight prices.
- **Not tested in a real browser or DOM.** The components are checked as rendered HTML and through their pure logic;
  the error boundary is checked through its contract. See the test files above.
