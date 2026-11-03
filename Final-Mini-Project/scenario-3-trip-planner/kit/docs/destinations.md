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
| Tests | `tests/test_destinations.py` (49), `rihla-frontend/src/features/destinations/destinations.test.js` (29) |
| Recorded provider answer used by the tests | `tests/fixtures/open_meteo_geocoding_pari.json` |

## Provider

**Open-Meteo Geocoding API** (`https://geocoding-api.open-meteo.com/v1/search`), built on **GeoNames**. It is free,
needs no key, and is made for search as you type:
- three or more characters match by prefix (fuzzy);
- two characters match exactly;
- one character returns nothing.

Every result has a stable GeoNames id, coordinates, country, region, population and time zone. Licence: CC BY 4.0.
The component shows the attribution ("City data: GeoNames (CC BY 4.0) via Open-Meteo") and every API answer carries
`source`. Open-Meteo's free service is for non-commercial use; check its terms before any commercial deployment.

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
| 422 | `missing_query`, `query_too_short`, `invalid_query`, `query_too_long` | empty, 1 character, no letters or control characters, over 80 characters; the provider is not called |
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

All are optional. No key is needed.

## Component

```jsx
import { DestinationSearch } from './features/destinations'

<DestinationSearch
  label="Destination"
  tone="dark"                         // "dark" for the home page's glass form, "light" for white panels
  defaultValue={destination}
  onTextChange={setDestination}       // every change of the text, and the chosen city's label
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
