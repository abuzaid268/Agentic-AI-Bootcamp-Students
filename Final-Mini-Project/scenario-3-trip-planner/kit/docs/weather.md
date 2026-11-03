# Weather forecast

Real daily forecasts for any place, by coordinates. Owner: Member 3.

**Status:** not yet wired into the app. Wiring it in is two small handoffs, described at the end of this file.

| Part | File |
|---|---|
| Validation, provider client, normalization, cache, limits, licensing gate | `app/weather/service.py` |
| Routes `GET /api/weather` and `GET /api/weather/status` (GET only) | `app/weather/routes.py` |
| `install_weather(app)` | `app/weather/__init__.py` |
| React component | `rihla-frontend/src/features/weather/WeatherSummary.jsx` |
| API client and pure helpers | `rihla-frontend/src/features/weather/weatherApi.js`, `weatherState.js` |
| Tests | `tests/test_weather.py` (46), `rihla-frontend/src/features/weather/weather.test.js` (9) |
| Recorded real provider answer (Amman, 2026-11-03..05) | `tests/fixtures/open_meteo_forecast_amman.json` |

## How this differs from the kit's weather tool

The kit's tool is `services/travel_api.py` `/api/weather`, exposed to the crew as the MCP tool `get_weather`:

- It is **real Open-Meteo data**. In `TRAVEL_MODE=replay`, the local default, it answers from a recorded cache and says `"mode": "replay"`.
- It takes a **city name**, which it geocodes through Nominatim.
- Beyond 16 days it gives last year's values, labelled `seasonal_normals`.
- It is the crew's tool, part of the official kit, and is left unchanged.

This feature is a separate, small service for the app and its pages:

- It takes **coordinates**, for example those of a chosen destination (`/api/destinations` gives them).
- It gives **only forecasts**. A date past the 16-day horizon is refused, not filled with old values.
- The `Dockerfile` app image doesn't contain `services/travel_data.py`, so this service doesn't import from it. The WMO code table is the same as the kit's.

## Provider, licence and limits

These were checked on 2026-11-03 on Open-Meteo's own pages: [terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing), [docs](https://open-meteo.com/en/docs).

| | Confirmed |
|---|---|
| Data licence | CC BY 4.0. Attribution "Weather data by Open-Meteo.com" is shown under every forecast. |
| Free API | **Non-commercial use only.** Private or non-profit sites and apps without subscriptions or ads, and educational content, count as non-commercial. A site or app with ads or subscriptions is commercial. |
| Free limits | Under 10,000 calls a day, 5,000 an hour and 600 a minute (300,000 a month), per IP address |
| Commercial | Paid plans ("API Standard" and above) give an API key for `customer-api.open-meteo.com`. **The price isn't published on the page;** it is shown in the customer portal. |
| Forecast horizon | Up to 16 days (`forecast_days` 0–16) |
| Errors | HTTP 400 with `{"error": true, "reason": "..."}` |

**Unverified:** whether a free, ad-free public Rihla counts as non-commercial is the team's call. If Rihla gets ads, subscriptions or a business behind it, it needs a paid plan.

### What each environment may do

`RIHLA_ENV` is read by `app/deployment_env.py`.

| Environment | Calls Open-Meteo? |
|---|---|
| `development` (the default) or `test` | Yes, the free API. Development of a bootcamp project is non-commercial. |
| `production` with `RIHLA_OPEN_METEO_API_KEY` | Yes, the customer endpoint (paid plan) |
| `production` with `RIHLA_WEATHER_NONCOMMERCIAL=true` | Yes, the free API. The team states that the deployment is non-commercial. |
| `production` with neither | **No.** `503 weather_unavailable`, and `/api/weather/status` says why. |

**The paid key is kept secret:**
- It is sent only as a URL parameter, which is the only way Open-Meteo accepts it.
- It never appears in answers or in `repr`.
- httpx logs request URLs, so a filter on the `httpx` logger replaces the key with `REDACTED`. A test checks this against real httpx logging.

## Endpoints

`GET /api/weather/status` says whether forecasts are available:

```json
{"environment": "development", "available": true, "provider": "Open-Meteo", "notice": null, "forecast_days": 16,
 "source": {"provider": "Open-Meteo", "url": "https://open-meteo.com/", "licence": "CC BY 4.0",
            "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)"},
 "limits": {"per_minute": 60, "per_day": 5000, "scope": "per server process"}}
```

`GET /api/weather?latitude=&longitude=&start_date=&end_date=&temperature_unit=`

| Parameter | |
|---|---|
| `latitude`, `longitude` | Required. −90 to 90 and −180 to 180. |
| `start_date` | Default today. Yesterday in UTC is also accepted, because in some time zones it is still that day. |
| `end_date` | Default `start_date`. At most `today + 15` (16 days). |
| `temperature_unit` | `celsius` (default) or `fahrenheit` |

Real answer (a live call on 2026-11-03, London, shortened):

```json
{
  "location": {"latitude": "…", "longitude": "…", "elevation_m": "…", "timezone": "Europe/London",
               "timezone_abbreviation": "…", "utc_offset_seconds": "…"},
  "requested": {"latitude": 51.5072, "longitude": -0.1276, "start_date": "2026-11-03", "end_date": "2026-11-04"},
  "kind": "forecast",
  "data_status": "LIVE",
  "units": {"temperature": "°C", "precipitation": "mm", "wind_speed": "km/h", "wind_direction": "°"},
  "days": [{"date": "2026-11-03", "weather_code": 53, "condition": "drizzle", "temperature_max": 12.5,
            "temperature_min": 8.3, "precipitation_sum_mm": 1.3, "precipitation_probability_max_pct": 29.0,
            "wind_speed_max_kmh": 18.4, "wind_gusts_max_kmh": 40.7, "wind_direction_dominant_deg": 29.0, "wet": true},
           "…"],
  "missing_dates": [],
  "retrieved_at": "2026-11-03T04:00:00Z",
  "cache_expires_at": "2026-11-03T04:30:00Z",
  "forecast_horizon_end": "2026-11-18",
  "source": {"provider": "Open-Meteo", "licence": "CC BY 4.0", "…": "…"},
  "environment": "development",
  "notices": ["Forecast: it changes, check again closer to the date."]
}
```

**Field notes:**
- **Dates and time zone:** dates are the place's own calendar days (`timezone=auto`).
- **`data_status`:**
  - `LIVE`: fetched just now.
  - `CACHED`: served from this server's cache, keeping its original `retrieved_at`.
  - This API never returns `SIMULATED`.
- **`wet`:** whether the day's weather code is drizzle, rain, showers or thunderstorm.
- **Missing values:** a value the provider didn't give is `null`. A requested date the provider left out is listed in `missing_dates`.

### Errors

Errors have the shape `{"error": {"code", "message", "retryable", "field"?, ...}, "data_status": "UNAVAILABLE"}`.

| Status | `code` | When |
|---|---|---|
| 422 | `invalid_coordinates`, `invalid_date`, `invalid_date_range`, `date_in_past`, `invalid_unit` | Bad input. The provider is not called. |
| 422 | `beyond_forecast_horizon` | `end_date` is past the 16-day horizon. The error includes `forecast_available_until`. |
| 429 | `rate_limited`, `daily_limit_reached` | This server's caps were reached |
| 503 | `weather_unavailable` | Production without permission (see above) |
| 503 | `provider_unavailable`, `provider_rate_limited` | Open-Meteo can't be reached, or answered 429 |
| 504 | `provider_timeout` | No answer within `RIHLA_WEATHER_TIMEOUT_S` |
| 502 | `provider_error`, `provider_rejected`, `provider_bad_response`, `provider_auth_failed` | Provider 5xx, provider 400 (`error: true`), an unreadable or unexpected answer, or a rejected key |

**Failures are never cached and never replaced by made-up weather.**

## Caching and limits

**Cache:**
- In memory, at most 256 forecasts, kept 30 minutes.
- Keyed by coordinates rounded to 0.01° (about 1 km), the dates and the unit.
- **Expired entries are never served**, not even when the provider is down.

**Caps:**
- `RIHLA_WEATHER_MAX_PER_MINUTE` (default 60) and `RIHLA_WEATHER_MAX_PER_DAY` (default 5,000) calls to Open-Meteo.
- Counted per server process, so they aren't global or financial limits.
- The free API's own limits apply per IP address, shared with any other process on that address. That includes the kit's travel API in `live` mode.

### Environment variables

| Variable | Default | |
|---|---|---|
| `RIHLA_ENV` | `development` | See above |
| `RIHLA_OPEN_METEO_API_KEY` | not set | Secret. A paid plan's key; switches to the customer endpoint. |
| `RIHLA_WEATHER_NONCOMMERCIAL` | not set | `true` allows the free API in production for a non-commercial deployment |
| `RIHLA_WEATHER_URL` | free or customer forecast URL | For a self-hosted Open-Meteo or a mock |
| `RIHLA_WEATHER_TIMEOUT_S` | `6` | 1–30 |
| `RIHLA_WEATHER_MAX_PER_MINUTE` / `_PER_DAY` | `60` / `5000` | Per process |

## Component

```jsx
import { WeatherSummary } from './features/weather'

<WeatherSummary latitude={31.9539} longitude={35.9106} startDate="2026-11-03" endDate="2026-11-05" locationName="Amman" />
```

**Each day card shows:**
- the date (the place's own calendar day);
- an icon for the condition;
- the high and low temperature;
- the condition in words;
- the chance of rain, or "Rain chance not given";
- the wind.

**The rest of the component:**
- A "Live forecast" or "Forecast" badge.
- The update time (UTC), the place's time zone and the Open-Meteo attribution link.
- Clear states for: no place chosen; loading; a date too far ahead ("forecasts reach only 16 days ahead"); unavailable on this service; an error with "Try again".

**Accessibility:**
- A `section` named by its heading, with `aria-busy` and a polite live region.
- A `role="status"` loading message.
- Each day is read out as one sentence, for example "Tue 3 Nov, overcast, high 25°C, low 15°C, 3% chance of rain, wind up to 16 km/h".

**Layout:** one day per row on a phone, two or three per row on wider screens.

**Tested:**
- the pure logic, in `weather.test.js`;
- the loading and no-place states, by server rendering.

**Not tested:** rendering the forecast cards in a real browser.

## Handoffs (not done here: these files belong to other members)

### Member 1 (backend owner): install the route

Add two lines to `app/main.py`, after `app = FastAPI(...)`:

```python
from app.weather import install_weather
install_weather(app)
```

**Verify:** `curl "http://localhost:8000/api/weather?latitude=31.95&longitude=35.91"` returns today's forecast for Amman with `"data_status": "LIVE"`.

**For WHAT IF rain:** `app/whatif.py`, on the `backup/rihla-integration-wip` branch, reads the kit's `get_weather` by city. This service can supply the same rain information by coordinates, with no replay cache. The adapter for that is documented with the WHAT IF fixtures.

### Member 2 (frontend owner): show the forecast

Render `<WeatherSummary>` where a trip's destination and dates are known, for example on the trip result, with the coordinates of the chosen destination:

- `DestinationSearch`'s `onSelect` gives `latitude` and `longitude`.
- Pass the trip's dates only when they are within 16 days. Otherwise the card shows the "no forecast yet" state, which is correct but less useful.

## Known limitations

- **Testing:** the live provider was called twice for verification on 2026-11-03: the recorded Amman fixture and a London smoke test through `app.auth_app`. Everything else is mocked.
- **Daily data only:** no hourly forecast, and no forecast beyond 16 days. Use the kit's `get_weather` seasonal values, clearly labelled, if a long-range indication is needed.
- **Production licensing** depends on the team's decision: non-commercial use, or a paid plan.
- **The cache and caps** are per process.
