# Worldwide destination search

Search-as-you-type for the trip form's destination box. Owner: Member 3. **Not yet wired into the app.** That is
two small handoffs, at the end of this file.

| Part | File |
|---|---|
| Service: validation, provider client, normalization, cache, rate limit | `app/destinations/service.py` |
| Route `GET /api/destinations` | `app/destinations/routes.py` |
| `install_destinations(app)` | `app/destinations/__init__.py` |
| React component | `rihla-frontend/src/features/destinations/DestinationSearch.jsx` |
| API client and pure helpers | `rihla-frontend/src/features/destinations/destinationsApi.js`, `searchState.js` |
| Tests | `tests/test_destinations.py` (58), `rihla-frontend/src/features/destinations/destinations.test.js` (16) |
| Open-Meteo licence decision, shared with weather | `app/open_meteo.py` |
| Recorded provider answer used by the tests | `tests/fixtures/open_meteo_geocoding_pari.json` |

## Provider

**Open-Meteo Geocoding API** (`https://geocoding-api.open-meteo.com/v1/search`), built on **GeoNames**. It is free,
needs no key, and is made for search as you type:
- three or more characters match by prefix (fuzzy);
- two characters match exactly;
- one character returns nothing.

**One or two letters: popular destinations.** The provider alone cannot suggest "Amman" for "Am", and it returns
nothing for "A". So a query of one or two letters is answered from a bundled list, without calling the provider:
- the list is `app/destinations/data/popular_destinations.json`, 224 popular destinations;
- each record is the provider's own GeoNames record, so it has the same id, coordinates and label as in the
  worldwide search;
- results are places whose name starts with the query, then places with a later word that does ("Yo" gives
  Yogyakarta, then New York), largest population first, ignoring case and accents;
- the answer says `"scope": "popular"`, and the box shows "Keep typing to search every city";
- three letters or more always use the worldwide search (`"scope": "worldwide"`), as before;
- the licence gate below still comes first: in production without a decision, short queries answer 503 too.

**Countries, regions and shared names need an explicit choice.** Rihla plans a city. For "Italy", the provider's
first result is the country itself (GeoNames `PCLI`), then towns that share the name ("Italy, Texas").
- `app/destinations/areas.py` knows every country and first-level region of the world (`data/areas.json`, 252
  countries and 3,865 states, provinces and governorates from GeoNames, CC BY 4.0, rebuilt by
  `python -m app.destinations.build_areas --source <GeoNames export folder>`), matched by whole name only.
- The answer carries `"areas": [{"kind": "country" | "region", "name", "country_code", "country", "suggestions"}]`:
  "Italy" is a country (suggestions Rome, Milan, …); "Georgia" is a country and a US state; "Texas" is a region.
  The provider's country records are never returned as places.
- The box shows "Italy is a country. Choose a city:" above the suggestions, then "Other places with this name",
  and highlights nothing, so Enter cannot pick "Italy, Texas" for the traveller. The same applies to a name
  several places share (`"ambiguous": true`: London, Paris, Tokyo).
- A required box stops the trip form (the browser's own validation) while it holds an area or a shared name and
  nothing is chosen, and while the text is still being checked. A failed search never blocks it.

**The chosen place travels with the trip.** `POST /api/chat` accepts an optional `trip.place` (GeoNames id,
`kind: "city"`, name, region, country, ISO `country_code`, coordinates, label); `app/destinations/identity.py`
checks it on the server: a known country code, real coordinates, not a country sent as a city, and a destination
text that names that same place. A shorter text ("Paris") is researched by the place's full label ("Paris, Texas,
United States"). Without a place (older clients, saved trips), a destination that is only a country's name is
refused with a request for a city (city-states such as Singapore excepted); everything else is planned as before.

**The travel data looks up that very place** (`services/travel_data.py`). A qualified name is never cut to its
first word any more:
- live and record modes: the city's coordinates come from Open-Meteo (the same GeoNames place the box showed),
  and the Wikivoyage page used is the one nearest to them within 40 km among Wikivoyage's own titles ("Paris
  (Texas)", "London (Ontario)", "Washington, D.C.", "New York City") and the pages near that point. None: error
  `no_guide`, never a namesake's page;
- replay mode: the recorded cities only, under any name that places them where they are ("Amman, Jordan",
  "Istanbul, Republic of Türkiye"); "Amman, Texas" is `not_cached`;
- refused or dropped connections, 429 and 5xx answers are retried at most 3 times (Retry-After honoured up to
  5 s), and so is a connection not made in time (the request was never sent); a read timeout is not retried.
  Every upstream call has a 20 s deadline (all its attempts and waits) and every travel API request a 40 s budget
  for all its upstream calls, so a request ends within 55 s at worst, under the MCP tool's 60 s
  (`services/travel_mcp.py`).

The list is rebuilt by hand with `python -m app.destinations.build_popular`:
- it names destinations only (city name and country code) and keeps the provider's own record;
- it leaves out any name the provider does not confirm, or that matches only a village (under 5,000 people);
- it makes about 230 free provider calls, so run it in development.

Every result has a stable GeoNames id, coordinates, country, region, population and time zone. Licence: CC BY 4.0.
The component shows the attribution ("City data: GeoNames (CC BY 4.0) via Open-Meteo") and every API answer carries
`source`.

**Licence and production.** These terms were checked on 2026-11-03 at https://open-meteo.com/en/terms and
https://open-meteo.com/en/docs/geocoding-api.

What the terms say:
- Open-Meteo's free API is for **non-commercial use only**.
- Commercial use needs a paid plan, whose `apikey` goes to the `customer-` server
  (`https://customer-geocoding-api.open-meteo.com/v1/search`).
- The price isn't published on the page.

A public deployment is not automatically non-commercial, so **production calls Open-Meteo only after an explicit
decision**. It is the same decision as for weather, and lives in `app/open_meteo.py`:

| Environment | City search |
|---|---|
| `development` or `test` | The free API |
| `production` with `RIHLA_OPEN_METEO_API_KEY` | The customer server, with the key |
| `production` with `RIHLA_OPEN_METEO_NONCOMMERCIAL=true` | The free API (the team states the deployment is non-commercial) |
| `production` with neither | **The provider is never called.** Every search answers `503 destinations_unavailable`: "City search is not available on this service right now. You can still type the destination yourself." The component shows that message, and the traveller can still type. |

**Keeping the key secret:** it is never in an answer or in `repr`, and it is redacted from httpx's request logs.
Tests check all of this.

**Why not the kit's `geocode` tool?**
- It calls Nominatim, which is an exact single-place lookup, not a prefix search.
- Nominatim's usage policy forbids building autocomplete on its public API.
- It is throttled to about one request per second.
- In replay mode it answers only recorded queries.

The kit tool stays as it is, for resolving one known place.

**Reliability:**
- Only populated places are returned: GeoNames `PPL*` codes, minus historical (`PPLH`), abandoned (`PPLQ`), destroyed (`PPLW`), "section of" (`PPLX`) and historical capital (`PPLCH`) places.
- A result with an invalid id, an empty name, or impossible or `0,0` coordinates is dropped, never repaired.
- An impossible population or country code becomes `null`.
- No results is a normal, empty answer.
- A provider failure is reported as an error and never filled in.
- Names come in English (`lang=en`). Another language can be requested with `lang=xx`.

## API

`GET /api/destinations?q=<text>&limit=<1-10, default 8>&lang=<2 letters, default en>`. Read-only, and it needs no
sign-in (it is not in `app/auth/middleware.py` `PROTECTED_PREFIXES`).

```http
GET /api/destinations?q=Pari&limit=3
200 OK
Cache-Control: private, max-age=300
```
```json
{
  "query": "Pari",
  "count": 3,
  "results": [
    {"id": "geonames:2988507", "provider_id": 2988507, "name": "Paris", "region": "Île-de-France Region",
     "country": "France", "country_code": "FR", "latitude": 48.85341, "longitude": 2.3488,
     "population": 2138551, "timezone": "Europe/Paris", "feature_code": "PPLC",
     "label": "Paris, Île-de-France Region, France", "ambiguous_name": true},
    {"id": "geonames:4717560", "name": "Paris", "region": "Texas", "country": "United States",
     "label": "Paris, Texas, United States", "ambiguous_name": true, "...": "..."},
    {"id": "geonames:4647963", "name": "Paris", "region": "Tennessee", "label": "Paris, Tennessee, United States", "...": "..."}
  ],
  "ambiguous": true,
  "cached": false,
  "source": {"provider": "Open-Meteo Geocoding API (GeoNames)", "url": "https://open-meteo.com/en/docs/geocoding-api",
             "licence": "CC BY 4.0", "attribution": "City data from GeoNames (geonames.org), CC BY 4.0, via Open-Meteo.com"}
}
```

`ambiguous` is true when the best match shares its name with another result. The UI then asks the traveller to
check region and country. `ambiguous_name` marks each result that shares its name.

No match: `200 {"query": "zzqxqz", "count": 0, "results": [], "ambiguous": false, ...}`

Errors: `{"error": {"code", "message", "retryable", "retry_after"?}}`

| Status | `code` | When |
|---|---|---|
| 503 | `destinations_unavailable` | Production without the Open-Meteo licence decision (see above). Checked before anything else, and not retryable. |
| 422 | `missing_query`, `invalid_query`, `query_too_long` | empty, no letters or control characters, over 80 characters; the provider is not called. One or two letters are answered from the popular list (above), not refused. |
| 422 | FastAPI validation | `limit` outside 1–10, `lang` not 2 letters |
| 429 | `rate_limited` | this server's provider-call cap was reached (header `Retry-After`) |
| 503 | `provider_rate_limited` | the provider answered 429 (`Retry-After` passed on) |
| 503 | `provider_unavailable` | cannot connect |
| 504 | `provider_timeout` | no answer within the timeout |
| 502 | `provider_error`, `provider_rejected`, `provider_bad_response` | provider 5xx, provider refused the request, or an unreadable answer |

## Limits and settings

**Cache.** In memory, per server process, at most 512 queries.
- Results are kept 6 h; an empty answer only 10 min.
- The cache key ignores case and accents ("pari" equals "Pari").
- Failures are never cached.

**Outbound cap.** At most `RIHLA_DESTINATIONS_MAX_PER_MINUTE` (default 60) provider calls per minute for the whole
server, in a sliding window. Cached queries never count. The frontend also waits 300 ms after typing (debounce) and
cancels an outdated request.

| Variable | Default | |
|---|---|---|
| `RIHLA_DESTINATIONS_URL` | the Open-Meteo search URL | e.g. a self-hosted Open-Meteo |
| `RIHLA_DESTINATIONS_TIMEOUT_S` | `4` | 0.5–30 |
| `RIHLA_DESTINATIONS_MAX_PER_MINUTE` | `60` | 1–600 |
| `TRAVEL_CONTACT` | — | already used by the kit; added to the User-Agent when set |
| `RIHLA_ENV` | `development` | `production` turns on the licence gate (`docker-compose.prod.yml` sets it) |
| `RIHLA_OPEN_METEO_API_KEY` | — | Secret. A paid plan's key: commercial use, customer server. |
| `RIHLA_OPEN_METEO_NONCOMMERCIAL` | — | `true` lets production use the free API for a non-commercial deployment |

No key is needed in development. `GET /api/destinations/status` says whether search is available here, and why
not.

## Component

```jsx
import { DestinationSearch } from './features/destinations'

<DestinationSearch
  label="Destination"
  tone="dark"                         // "dark" for the home page's glass form, "light" for white panels
  defaultValue={destination}
  onTextChange={setDestination}       // every change of the text, and the chosen city's label (at most 100 characters)
  onSelect={setDestinationPlace}      // the chosen city object, or null when the text changes again
  required
/>
```

**Accessibility.** It follows the WAI-ARIA combobox pattern:
- an input with `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`, `aria-controls` and `aria-activedescendant`;
- a `listbox` of `option`s;
- a real `<label>`;
- a polite live region for "Searching…", "3 cities found. Several places share this name…", "No cities found…", or the error.

**Keyboard.**
- ↓ and ↑ move through the list, and it wraps around; Home and End jump to the ends.
- Enter chooses the highlighted city. With no list open, Enter submits the form as usual.
- Esc closes the list; Tab moves on.

**Keeping the parent in step (for whoever places it).** The box keeps its own text after it mounts: `defaultValue` is read once, like an uncontrolled `<input>`. Every change reaches the parent through `onTextChange` and `onSelect`, and `onSelect(null)` means the text no longer names a chosen place. A parent that resets or replaces the value from outside (for example clearing the form, or loading another trip) must remount the box with a new `key`, e.g. `<DestinationSearch key={formVersion} defaultValue={destination} … />`. Changing `defaultValue` alone does not change the text. `App.jsx` on `main` (2026-11-03) sets the destination only from the input, so it needs nothing more today.

**Errors.** A retryable error shows "Try again". If the backend does not have the route yet (404), the box says city
search is not available, and the traveller can still type the destination.

## Handoffs (not done here: these files belong to other members)

**Member 1 (backend owner): install the route.** One line in the app setup, the same pattern as `install_auth`:

```python
# app/main.py, after `app = FastAPI(...)`
from app.destinations import install_destinations
install_destinations(app)
```

`app.auth_app` imports `app.main`'s app, so the web app and the eval runner both get the route. No other backend
change is needed, and the API contract (`/api/chat`, `/api/approve`) is unchanged.

**Verify:**
- `curl "http://localhost:8000/api/destinations?q=Pari"` returns three "Paris" results.
- `python -m pytest -q tests/test_destinations.py` passes.

**Member 2 (frontend owner): use the component in the trip form.** In `rihla-frontend/src/App.jsx`, replace the
destination `<label>…<input …/></label>` block (the one with `placeholder="City, Country (e.g. Paris, France)"`) with:

```jsx
import { DestinationSearch } from './features/destinations'
// …
<DestinationSearch
  label="Destination"
  tone="dark"
  defaultValue={destination}
  onTextChange={setDestination}
  required
/>
```

`destination` stays the plain text the form already sends (`buildTripForm` in `services/tripApi.js` is unchanged),
so nothing downstream changes. Two optional extras:
- keep the chosen place in a new state from `onSelect`, to show "Paris, France" with its coordinates;
- prefer the chosen `label` as the destination text, so that "Paris, Texas" is not planned as Paris, France.

**Verify:** type "Pari" on the home page and three Paris entries appear; ↓ then Enter fills in "Paris, Île-de-France
Region, France".

**Local frontend environment (anyone):** after updating to `main`, run `npm ci` in `rihla-frontend/`. `main` added
`firebase@12.19.0`, and an older `node_modules` fails `npm run build` with "failed to resolve import firebase/app".
The Docker image build is not affected.
