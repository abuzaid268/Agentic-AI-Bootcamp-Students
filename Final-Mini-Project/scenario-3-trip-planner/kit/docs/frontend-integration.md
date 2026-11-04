# Frontend integration: destinations, FROM → TO, weather, flights and sources

**Audience:** Member 1 (backend owner) and Member 2 (frontend owner).
**Status:** Member 3's modules are ready on branch `feature/member3-ui-integration`, based on `main` at `a26c63e`.
The shared files below (`app/main.py`, `App.jsx`, `TripDashboard.jsx`, `savedTrips.js`) are **not** changed by
Member 3. Each step here is a copy-ready change for its owner.

## What already works, and what is missing

Checked on 2026-11-04, on `main` at `a26c63e`, over real HTTP on a local server. Only free GET routes were called.

| Capability | API on `main` | In the website today |
|---|---|---|
| City search (`DestinationSearch`) | `GET /api/destinations` registered | Shown on the home page. Only the text is kept: the chosen place and its coordinates are dropped. |
| Airports and departure countries | `GET /api/airports`, `GET /api/airports/countries` registered | Not shown: only `FlightSearch` uses them. |
| Flight prices (`FlightSearch`) | `GET /api/flights`, `/status` registered; DEMO data without a Duffel token | Not shown. |
| Weather (`WeatherSummary`) | **`GET /api/weather` is not registered: 404** | Not shown. |
| Sources (`citations` in `/api/chat`) | Sent in every answer | Not shown; each activity only has its own "Source" link. |

## The design

```
Home page (App.jsx)
  FROM (optional, for flights only): DestinationSearch     -> originPlace      (never sent to /api/chat)
  TO: DestinationSearch                                     -> destination text (sent, as today)
                                                            -> destinationPlace (coordinates, kept for the dashboard)
  Dates · Travellers · Budget · Interests                   (unchanged)

Trip page (TripDashboard.jsx)
  … itinerary …
  TripTravelInfo  (Member 3: features/trip-travel)
    FROM → TO summary, dates, travellers
    WeatherSummary for TO's coordinates and the trip days that have a forecast
    "Compare flights (optional)": FlightSearch, closed until opened
      departure country (from FROM) → departure airport (the traveller picks)
      arrival airport (the box starts with TO's city name; the traveller picks)
      dates and adults from the trip; DEMO / TEST / LIVE badge; cheapest offer marked
  Sources (aiResult.citations)
```

**Rules this design keeps:**
- **The official contract is unchanged.** `buildTripForm` and `buildTripMessage` (`services/tripApi.js`) send only
  the existing fields, so a place object added to the trip state never reaches `/api/chat`.
- **A city is never confused with an airport.** FROM and TO are cities (`DestinationSearch`). Airports are only
  chosen inside the flight form (`AirportSearch`). A city name only fills an airport box's text, which then lists
  matching airports. No airport is ever chosen for the traveller.
- **Flights are optional and stay out of the budget.** The flight form is closed until the traveller opens it, so
  nothing is requested for a trip without flights. Its prices are never added to `budget_total`, `estimated_cost`
  or the "Budget overview".
- **No stale state.**
  - The flight form reads the trip's values once.
  - What the traveller changes afterwards is kept.
  - A different trip (another place, other dates or party size) remounts the form empty (`flightsKey`).
  - Old results are hidden as soon as the search changes (unchanged).
- **Never invented.**
  - Weather appears only for a place chosen from the suggestions, which carries coordinates; a typed name is never
    geocoded here.
  - Forecasts appear only for the days the provider covers.
  - DEMO prices carry the violet "DEMO: not real flights, schedules or prices" label.

## Member 1: register the weather router (`app/main.py`)

Add the import with the other feature imports, and the call with the other `install_*` calls:

```python
from app.weather import install_weather
```

```python
install_destinations(app)
install_flights(app)
install_airports(app)
install_weather(app)   # GET /api/weather, GET /api/weather/status (docs/weather.md)
```

`install_weather` does nothing if it is called twice. The route needs no sign-in. In production it answers 503
`weather_unavailable` until the team records the Open-Meteo licence decision (`app/open_meteo.py`): the same rule
as city search.

**Verify:**

```sh
python -m pytest -q tests/test_weather.py
curl "http://localhost:8000/api/weather/status"          # 200, "available": true in development
curl "http://localhost:8000/api/weather?latitude=31.95&longitude=35.93"   # 200, "data_status": "LIVE"
```

Until this is done, `TripTravelInfo` shows a quiet note, "Weather is not connected on this server yet. The rest of
your trip is not affected.", instead of an error.

## Member 2: the home page (`src/App.jsx`)

### 1. Keep the chosen places

Next to the existing `const [destination, setDestination] = useState('')`:

```jsx
const [destinationPlace, setDestinationPlace] = useState(null) // the chosen city: coordinates for the weather
const [originPlace, setOriginPlace] = useState(null)           // optional FROM: only starts the flight form
```

### 2. TO: pass `onSelect` to the existing destination box

```jsx
<DestinationSearch
  label="Destination"
  tone="dark"
  placeholder="City, Country (e.g. Paris, France)"
  defaultValue={destination}
  onTextChange={setDestination}
  onSelect={setDestinationPlace}
  required
/>
```

`onSelect` receives `null` as soon as the text no longer matches the chosen city, so the place can never belong to
a different text.

### 3. FROM: add an optional box above TO

```jsx
<DestinationSearch
  label="Departing from (optional, for flights)"
  tone="dark"
  placeholder="City, e.g. London"
  onSelect={setOriginPlace}
/>
```

- It is not `required`, and it has no `onTextChange`: the planner never sees it.
- If it would make the home card too tall, it can live on the trip page instead. In that case, pass no `origin`
  (see below).

### 4. Carry both places to the trip page

In `handleSubmit`, add them to the `trip` object (they are not sent to the planner, see "The design"):

```jsx
const trip = {
  destination,
  departureDate: startDate,
  returnDate: endDate,
  travellers,
  budget,
  interests,
  customPreferences,
  destinationPlace, // not sent to /api/chat: buildTripForm and buildTripMessage pick their own fields
  originPlace,
}
```

`generateTrip` already spreads `trip` into the `/trip` route state.

### 5. Single-letter suggestions: nothing to do

`DestinationSearch` now searches from the first letter:
- **1 or 2 letters:** the server answers from its bundled list of 224 popular destinations, and the box says
  "Keep typing to search every city".
- **3 letters or more:** the worldwide search, as before.

## Member 2: the trip page (`src/pages/TripDashboard.jsx`)

### 1. Import

```jsx
import { TripTravelInfo } from '../features/trip-travel'
```

### 2. Render it under the day-by-day itinerary

Place it in the left column, right after the itinerary `</section>` (before the `</div>` that precedes
`<aside className="space-y-6">`). Show it only for a real trip, not the sample:

```jsx
{isReal && !sampleEntry && (
  <div className="mt-7">
    <TripTravelInfo
      destination={trip.destinationPlace || null}
      destinationText={trip.destination || view.destination}
      origin={trip.originPlace || null}
      startDate={trip.departureDate}
      endDate={trip.returnDate}
      travellers={Number(trip.travellers) || 1}
    />
  </div>
)}
```

`TripTravelInfo` is responsive: one column on a phone, and the FROM → TO bar in one row from `sm` up. The airport
lists open below their box (`z-30`) inside the white card, which has no `overflow-hidden`, so the lists are not
cut off.

### 3. Sources (`citations`)

The backend sends `citations: [{id, title, url}]`, one per source URL behind the itinerary
(`app/contract.py build_citations`). Add a list, for example in the `<aside>` under "Budget overview":

```jsx
{isReal && Array.isArray(aiResult.citations) && aiResult.citations.length > 0 && (
  <section className="rounded-[28px] border border-[#e0ebed] bg-white p-6 shadow-sm">
    <h2 className="mb-4 text-xl font-bold">Sources</h2>
    <ol className="space-y-2 text-sm">
      {aiResult.citations
        .filter((c) => typeof c?.url === 'string' && /^https?:\/\//.test(c.url))
        .map((c) => (
          <li key={c.id || c.url}>
            <a href={c.url} target="_blank" rel="noreferrer" className="text-[#2e7b87] underline">
              {c.title || c.url}
            </a>
          </li>
        ))}
    </ol>
  </section>
)}
```

### 4. Keep the places when a trip is saved (optional, `src/services/savedTrips.js`)

`requestFields` keeps only the form fields, so a trip reopened from My Trips has no `destinationPlace`. It then
shows "choose … from the destination suggestions" instead of the forecast. To keep the weather for saved trips, add
both places to what `requestFields` returns, copying only plain values:

```js
destinationPlace: placeFrom(request.destinationPlace), // import { placeFrom } from '../features/trip-travel'
originPlace: placeFrom(request.originPlace),
```

`placeFrom` returns `null` for anything that is not a usable place.

## Member 2: verify in the browser

1. Type `A` in Destination. Eight popular places, largest first (Alexandria, Addis Ababa, Ankara, …), appear with
   region and country, and the status says "Keep typing to search every city".
2. Type `Am`. Amman and Amsterdam appear first. Choose "Amman, Amman Governorate, Jordan".
3. Type `London` in "Departing from" and choose "London, England, United Kingdom".
4. Plan the trip. On the trip page, the card shows "London … → Amman …", the dates and the travellers.
5. Weather:
   - with Member 1's route, and dates within 16 days: a "Live forecast" with one card per day;
   - without the route: the quiet "not connected" note.
6. Open "Compare flights (optional)":
   - the departure country is United Kingdom;
   - "From" starts with London airports listed, and "To" with Amman's (AMM, ADJ);
   - neither is selected until you choose one.
7. Choose LHR and AMM, then press Search. The violet DEMO banner, cards sorted by price and "Cheapest in USD" appear.
   The Budget overview does not change.
8. Change the return date. The offers are hidden and "Your search changed" is shown.
9. Check at phone width (about 375 px): no horizontal scroll, and the airport lists are not cut off.

## Tests

| Where | What |
|---|---|
| `tests/test_destinations.py` | short queries never reach the provider and use the bundled list; ranking; accent-insensitive matching; the dataset is real provider records with attribution; the licence gate still comes first |
| `features/destinations/destinations.test.js` | from the first letter; `scope`; the "popular destinations" messages |
| `features/airports/airports.test.js` | airport search still needs 2 characters (its own rule) |
| `features/flights/flights.test.js` | `initialFlightForm`: starting values from the trip, cleaned, never a chosen airport |
| `features/weather/weather.test.js` | a 404 (route not registered) is a quiet note, not an alert |
| `features/trip-travel/tripTravel.test.js` | the forecast window (full, partial, later, past); FROM → TO; flight hints; `flightsKey` |

## Data and licences

- **Popular destinations** (`app/destinations/data/popular_destinations.json`):
  - 224 GeoNames records as Open-Meteo's Geocoding API serves them (CC BY 4.0, attribution in the file and in
    every answer's `source`);
  - rebuilt by `python -m app.destinations.build_popular`;
  - the script names destinations only, keeps the provider's own record, and leaves out any name the provider does
    not confirm or that matches only a village (under 5,000 people).
- Airports: OurAirports, public domain (unchanged).
- Weather: Open-Meteo, CC BY 4.0 (unchanged).
