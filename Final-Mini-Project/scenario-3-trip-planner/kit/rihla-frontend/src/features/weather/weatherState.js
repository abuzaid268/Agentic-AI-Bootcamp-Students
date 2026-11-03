// Pure helpers for WeatherSummary: the answer from GET /api/weather, and how a day is shown and read out.

// Only real provider data is shown as a forecast: anything else (SIMULATED, UNAVAILABLE, unknown) is refused.
export const SHOWN_STATUSES = {
  LIVE: { label: 'Live forecast', detail: 'Fetched from the weather service just now.' },
  CACHED: { label: 'Forecast', detail: 'From the weather service, saved for a few minutes.' },
}

const num = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null)
const text = (value) => (typeof value === 'string' && value.trim() ? value.trim() : null)

function sanitizeDay(raw) {
  if (!raw || typeof raw !== 'object' || !/^\d{4}-\d{2}-\d{2}$/.test(raw.date || '')) return null
  const probability = num(raw.precipitation_probability_max_pct)
  return {
    date: raw.date,
    weatherCode: Number.isInteger(raw.weather_code) ? raw.weather_code : null,
    condition: text(raw.condition),
    temperatureMax: num(raw.temperature_max),
    temperatureMin: num(raw.temperature_min),
    precipitationMm: num(raw.precipitation_sum_mm),
    rainProbability: probability !== null && probability >= 0 && probability <= 100 ? probability : null,
    windSpeedMax: num(raw.wind_speed_max_kmh),
    wet: typeof raw.wet === 'boolean' ? raw.wet : null,
  }
}

// The answer, cleaned. Throws when it is not a real forecast, so it is never shown as one.
export function sanitizeWeather(body) {
  if (!body || typeof body !== 'object' || !SHOWN_STATUSES[body.data_status] || !Array.isArray(body.days)) {
    throw new Error('The server sent an unexpected weather answer.')
  }
  return {
    status: body.data_status,
    days: body.days.map(sanitizeDay).filter(Boolean),
    temperatureUnit: text(body.units?.temperature) || '°C',
    timezone: text(body.location?.timezone),
    retrievedAt: text(body.retrieved_at),
    missingDates: Array.isArray(body.missing_dates) ? body.missing_dates.filter((d) => typeof d === 'string') : [],
    attribution: text(body.source?.attribution) || 'Weather data by Open-Meteo.com (CC BY 4.0)',
    sourceUrl: text(body.source?.url),
  }
}

// Which icon to draw for a WMO weather code (the names match lucide-react icons).
export function conditionIcon(code) {
  if (code === null || code === undefined) return 'Cloud'
  if (code <= 1) return 'Sun'
  if (code === 2) return 'CloudSun'
  if (code === 3) return 'Cloud' // overcast: no sun
  if (code === 45 || code === 48) return 'CloudFog'
  if (code >= 51 && code <= 57) return 'CloudDrizzle'
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return 'CloudRain'
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return 'CloudSnow'
  if (code >= 95) return 'CloudLightning'
  return 'Cloud'
}

export const formatTemperature = (value, unit) => (value === null ? '—' : `${Math.round(value)}${unit}`)

// "2026-11-03" -> "Tue 3 Nov": the place's own calendar date, never shifted by the viewer's time zone.
export function formatDay(date) {
  const day = new Date(`${date}T12:00:00Z`)
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(day)
}

export function rainLabel(day) {
  return day.rainProbability === null ? 'Rain chance not given' : `${Math.round(day.rainProbability)}% chance of rain`
}

// One sentence a screen reader can say for a day.
export function describeDay(day, unit) {
  const parts = [formatDay(day.date), day.condition || 'conditions not given']
  if (day.temperatureMax !== null || day.temperatureMin !== null) {
    parts.push(`high ${formatTemperature(day.temperatureMax, unit)}, low ${formatTemperature(day.temperatureMin, unit)}`)
  }
  parts.push(rainLabel(day))
  if (day.windSpeedMax !== null) parts.push(`wind up to ${Math.round(day.windSpeedMax)} km/h`)
  return parts.join(', ')
}
