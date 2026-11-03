# Airport search (departure and arrival)

Search as you type for the trip form's "From" and "To" airport boxes. Owner: Member 3.

**Status:** not yet wired into the app. Wiring it in is two small handoffs, described at the end of this file.

| Part | File |
|---|---|
| Service: data loading, validation, ranking, cache | `app/airports/service.py` |
| Route `GET /api/airports` | `app/airports/routes.py` |
| `install_airports(app)` | `app/airports/__init__.py` |
| Bundled data and its metadata | `app/airports/data/airports.csv`, `app/airports/data/airports.meta.json` |
| Data rebuild script | `app/airports/build_dataset.py` |
| React component | `rihla-frontend/src/features/airports/AirportSearch.jsx` |
| API client and pure helpers | `rihla-frontend/src/features/airports/airportsApi.js`, `airportState.js` |
| Tests | `tests/test_airports.py` (50), `rihla-frontend/src/features/airports/airports.test.js` (13) |

## Data source and licence

**[OurAirports](https://ourairports.com/data/)**, from the daily files at
`https://davidmegginson.github.io/ourairports-data/`: `airports.csv`, `countries.csv` and `regions.csv`.

- **Licence:** public domain. Credit is not required, but it is given anyway.
  - The component shows "Airport data: OurAirports (public domain)".
  - Every API answer carries `source`.
- **No runtime calls:** the data is bundled in the repository. Search makes no network call, needs no key and costs nothing.
- **Docker:** `Dockerfile` already copies `app/`, so the data reaches the image with no Docker change.

**What the bundle keeps (built 2026-11-02):**

| Kept | Count |
|---|---|
| Large airports | 1,175 |
| Medium airports | 4,105 |
| Small airports with an IATA code or scheduled service | 4,331 |
| **Total** | **9,611** |
| With an IATA code | 8,799 |
| Marked with scheduled service | 4,134 |

Left out: about 77,000 other rows, such as heliports, seaplane bases, balloon ports, closed airports, and small airfields with neither an IATA code nor scheduled service. `airports.meta.json` records the counts and the build date.

**Cleaning:**
- **Rows dropped:** a row without an id, a name or an airport type is dropped.
- **Values set to null:**
  - An IATA code that is not 3 letters becomes `null`.
  - An ICAO code that is not 4 letters becomes `null`.
  - A country code that is not 2 letters becomes `null`.
  - Missing, impossible or `0,0` coordinates become `null`, and both coordinates are dropped together.
- **Shared codes:** if the data gives one code to several airports, only the most likely one keeps it.
- **City names:** a repeated part is removed, so "Luton, Luton" becomes "Luton".
- **Checked twice:** at build time and again when the server loads the file.

### Limitations

- **`scheduled_service` is OurAirports' flag, not a timetable.** It ranks likely passenger airports higher. It does not promise that any airline flies there today, and the UI says "No scheduled service listed" rather than "no flights".
- **Accuracy:** OurAirports is community-maintained and is not an official aviation source. It can be out of date, so do not use it for navigation.
- **Script:** names are in English and Latin script. Searching in Arabic ("عمان") finds nothing, while "Amman" or "AMM" works. A few airports have local names in their keywords.
- **Prefix matching:** a word can match a longer word. For example, "Paris" also matches "Saint James *Parish*", but those results rank last.
- **Refreshing the data is manual**, as shown below.

### Refresh the data

1. Download the three files into an empty folder:
   ```sh
   for f in airports countries regions; do curl -fsSLO "https://davidmegginson.github.io/ourairports-data/$f.csv"; done
   ```
2. Rebuild the bundle:
   ```sh
   python -m app.airports.build_dataset --source <that folder>
   ```
3. Run `python -m pytest -q tests/test_airports.py`. A few tests use real codes such as TLV, LHR, YXU and OJKF, so a large change in the data shows up there.
4. Commit `airports.csv` and `airports.meta.json`. Rows are sorted by id, so the diff stays readable.

## API

`GET /api/airports?q=<text>&limit=<1-10, default 8>&scheduled_only=<true|false, default false>&country=<2 letters, optional>`

- `country` keeps only airports in that country (ISO 3166-1 alpha-2, any case: `jo` = `JO`). Empty means every
  country. With it, "London" and `country=CA` gives London, Ontario (YXU), never Heathrow.
- `GET /api/airports/countries` lists the countries in the bundled data, sorted by name:
  `{"count", "countries": [{"code": "JO", "name": "Jordan", "airports": 6}, ...], "source"}`. The flight form's
  optional **Departure country** picker uses it.

- Read-only, and no sign-in is needed. The route is not in `app/auth/middleware.py` `PROTECTED_PREFIXES`.
- `q` can be any of these:
  - an airport name, such as "Heathrow" or "ben gurion";
  - a city, such as "Tel Aviv" or "London";
  - a country, such as "Jordan";
  - an IATA code ("TLV") or an ICAO code ("LLBG");
  - an alternative name from OurAirports' keywords, such as "NYC".
- Every word of the query must start a word of the airport's details. Case and accents are ignored: "zurich" finds "Zürich Airport".

```http
GET /api/airports?q=TLV&limit=1
200 OK
Cache-Control: public, max-age=3600
```
```json
{
  "query": "TLV",
  "count": 1,
  "results": [{
    "id": "ourairports:4411", "name": "Ben Gurion International Airport", "city": "Tel Aviv",
    "region": "Central District", "country": "Israel", "country_code": "IL", "iata": "TLV", "icao": "LLBG",
    "latitude": 32.0114, "longitude": 34.8867, "type": "large_airport", "scheduled_service": true,
    "label": "Ben Gurion International Airport (TLV), Tel Aviv, Israel", "ambiguous_city": false
  }],
  "ambiguous": false,
  "cached": false,
  "source": {"provider": "OurAirports", "url": "https://ourairports.com/data/", "licence": "Public domain",
             "attribution": "Airport data from OurAirports (ourairports.com), released to the public domain.",
             "data_date": "2026-11-02"}
}
```

**Field notes:**
- `id` is OurAirports' own numeric id. It stays stable across data refreshes.
- `iata`, `icao`, `latitude` and `longitude` can be `null`. For example, `q=OJKF` returns King Feisal Air Base with `"iata": null, "icao": "OJKF"`, and its label shows the ICAO code.

**Ranking:**
1. An exact IATA or ICAO code.
2. A city that is, or starts with, the query; or a name that starts with the query; or a country with that exact name.
3. Scheduled service, then airport size, then whether the airport has an IATA code.

**Same city name in different places:** `ambiguous_city` marks a result whose city name also appears in the list in another country or region. The UI then shows the region. `ambiguous` is true when the first result is such an airport. Real results:

| Query | First results |
|---|---|
| `London` | LGW, LHR, STN, LCY (England), then YXU London (Ontario, Canada), all `ambiguous_city: true`. Then LTN and SEN, which are not marked because their city is Luton and Southend-on-Sea. |
| `Portland` | PDX (Oregon) and PWM (Maine), both marked |
| `Paris` | CDG and ORY first, then Le Bourget, then Paris, Texas and Paris, Tennessee |

**No match:** `200 {"query": "zzqxqz", "count": 0, "results": [], "ambiguous": false, ...}`

**Errors:** `{"error": {"code", "message", "retryable"}}`

| Status | `code` | When |
|---|---|---|
| 422 | `missing_query`, `query_too_short`, `invalid_query`, `query_too_long` | The query is empty, 1 character long, has no letters or contains control characters, or is over 80 characters |
| 422 | `invalid_country` | `country` is not 2 letters |
| 422 | FastAPI validation | `limit` is outside 1–10, `scheduled_only` is not a boolean, or `country` is longer than 2 characters |
| 503 | `data_unavailable` | The bundled file is missing, has no rows, or lacks required columns. This is never an empty answer. The next search tries to load the file again. |

## Performance and limits

**Loading:**
- The data loads into memory on the first search, once per process. It takes about 0.6 s and is thread-safe.
- A prefix index then answers a search in about 1 ms.

**Caching:**
- Up to 512 recent queries are cached in memory, ignoring case and spaces.
- Responses carry `Cache-Control: public, max-age=3600`, because the data is the same for everyone.

**No rate limit:** there is no outbound call, so there is no provider to protect. The frontend still waits 300 ms after typing before it searches (debounce), and cancels an outdated request.

## Component

```jsx
import { AirportSearch, routeError } from './features/airports'

<AirportSearch kind="departure" tone="dark" onSelect={setFromAirport} required />
<AirportSearch kind="arrival" tone="dark" onSelect={setToAirport} required />
{routeError(fromAirport, toAirport) && <p role="alert">{routeError(fromAirport, toAirport)}</p>}
```

**Props:**

| Prop | Meaning |
|---|---|
| `kind` | `"departure"` or `"arrival"`. Sets the icon (PlaneTakeoff / PlaneLanding), the default label ("From" / "To") and the clear button's name. |
| `label`, `placeholder`, `name`, `id`, `required`, `disabled` | The usual input settings |
| `defaultValue` | The starting text, read once. To reset the box from outside, remount it with a new `key` (see "Keeping the parent in step" in `docs/destinations.md`). |
| `onTextChange(text)` | Called on every change of the text, and with the chosen airport's label |
| `onSelect(airport \| null)` | Called with the chosen airport, or `null` when the text changes again. The airport is `{ id, name, city, region, country, countryCode, iata, icao, latitude, longitude, type, scheduledService, label }`. |
| `scheduledOnly` | Show only airports with scheduled service. Default `false`. |
| `country` | Show only airports in this country (`"JO"`). Default `''`, every country. |
| `limit` | Number of results. Default 8. |
| `debounceMs` | Wait after typing. Default 300. |
| `tone` | `"dark"` or `"light"` |

**Each option** shows:
- the code (IATA, else ICAO, else "—");
- the name;
- the city and country, plus the region when the city name is ambiguous;
- "No scheduled service listed" when that applies.

**Route check:** `routeError(departure, arrival)` returns a message when both boxes hold the same airport, and `''` otherwise.

**Accessibility and keyboard** are the same as the destination box (see `docs/destinations.md`):
- the WAI-ARIA combobox pattern, with `listbox` and `option`s;
- a real `<label>` and a polite live region;
- ↑ and ↓ wrap around the list, Home and End jump to the ends, Enter chooses, and Esc closes the list.

## Handoffs (not done here: these files belong to other members)

### Member 1 (backend owner): install the route

Add two lines to `app/main.py`, after `app = FastAPI(...)`, using the same pattern as `install_auth` and `install_destinations`:

```python
from app.airports import install_airports
install_airports(app)
```

No other backend change is needed. The `/api/chat` and `/api/approve` contracts are unchanged.

**Verify:**
- `curl "http://localhost:8000/api/airports?q=TLV"` returns Ben Gurion (TLV).
- `curl "http://localhost:8000/api/airports?q=London"` lists LHR, LGW, STN and LCY first.
- `python -m pytest -q tests/test_airports.py` passes.

### Member 2 (frontend owner): place the boxes where the trip needs an origin and destination airport

The current trip form (`App.jsx`) has no airport field, so this belongs with the Flights work.

1. Add two states, `fromAirport` and `toAirport`.
2. Render:
   ```jsx
   import { AirportSearch, routeError } from './features/airports'
   // …
   <AirportSearch kind="departure" tone="dark" onSelect={setFromAirport} required />
   <AirportSearch kind="arrival" tone="dark" onSelect={setToAirport} required />
   ```
3. Block submit while `routeError(fromAirport, toAirport)` is not empty.
4. Send `airport.iata`. When it is `null`, warn the traveller that flight search needs an IATA code; never send the ICAO code in its place.

**Verify:** type "TLV" and press Enter. The box shows "Ben Gurion International Airport (TLV), Tel Aviv, Israel".
