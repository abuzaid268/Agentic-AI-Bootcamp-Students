// Pure helpers for AirportSearch: one airport from the API, how it is shown, what to announce, and route checks.
// Keyboard movement and query cleaning are the same as the destination box.
import { MAX_QUERY_LENGTH, normalizeQuery } from '../destinations/searchState.js'

export { moveHighlight, normalizeQuery } from '../destinations/searchState.js'

// The airport search needs 2 characters (app/airports MIN_QUERY_LENGTH): unlike city search, it has no list for
// a single letter, so one is never sent.
export const MIN_QUERY_LENGTH = 2

export function shouldSearch(text) {
  const query = normalizeQuery(text)
  return query.length >= MIN_QUERY_LENGTH && query.length <= MAX_QUERY_LENGTH && /\p{L}/u.test(query)
}

const textOrNull = (value) => (typeof value === 'string' && value.trim() ? value.trim() : null)
const codeOrNull = (value, pattern) => {
  const text = textOrNull(value)
  return text && pattern.test(text) ? text : null
}
const coordinate = (value, bound) => (typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= bound
  ? value : null)

// The code to show: IATA when the airport has one, else ICAO, else nothing.
export function airportCode(airport) {
  return airport?.iata || airport?.icao || null
}

// City and country under the airport name, so airports in cities that share a name can be told apart.
export function airportDetails(airport) {
  const region = airport.ambiguousCity ? airport.region : null
  return [airport.city, region, airport.country].filter(Boolean).join(', ')
}

// One result from GET /api/airports, or null when it is not usable (never guessed). Codes and coordinates the
// server does not have stay null.
export function sanitizeAirport(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = textOrNull(raw.id)
  const name = textOrNull(raw.name)
  if (!id || !name) return null
  let latitude = coordinate(raw.latitude, 90)
  let longitude = coordinate(raw.longitude, 180)
  if (latitude === null || longitude === null) latitude = longitude = null
  const airport = {
    id,
    name,
    city: textOrNull(raw.city),
    region: textOrNull(raw.region),
    country: textOrNull(raw.country),
    countryCode: codeOrNull(raw.country_code, /^[A-Z]{2}$/),
    iata: codeOrNull(raw.iata, /^[A-Z]{3}$/),
    icao: codeOrNull(raw.icao, /^[A-Z]{4}$/),
    latitude,
    longitude,
    type: textOrNull(raw.type),
    scheduledService: raw.scheduled_service === true,
    ambiguousCity: raw.ambiguous_city === true,
  }
  const code = airportCode(airport)
  const fallback = [code ? `${name} (${code})` : name, airport.city, airport.country].filter(Boolean).join(', ')
  return { ...airport, label: textOrNull(raw.label) || fallback }
}

// The sentence for the screen reader's live region (and the visible status line).
export function statusMessage({ status, count, error, ambiguous, searchable }) {
  if (status === 'loading') return 'Searching for airports…'
  if (status === 'error') return error || 'Airport search failed. Please try again.'
  if (status === 'ready' && searchable) {
    if (!count) return 'No airports found. Try the city name in English, or a 3-letter code such as LHR.'
    const found = `${count} ${count === 1 ? 'airport' : 'airports'} found.`
    return ambiguous ? `${found} Several cities share this name: check the country.` : found
  }
  return ''
}

// The countries list from GET /api/airports/countries, cleaned: [{ code, name, airports }] sorted as the server
// sent them. Entries without a 2-letter code or a name are dropped, never guessed.
export function sanitizeCountries(body) {
  if (!body || !Array.isArray(body.countries)) throw new Error('The server sent an unexpected countries answer.')
  return body.countries
    .filter((c) => c && /^[A-Z]{2}$/.test(c.code || '') && textOrNull(c.name))
    .map((c) => ({ code: c.code, name: c.name.trim(), airports: Number.isInteger(c.airports) ? c.airports : null }))
}

// Why a departure and arrival pair cannot be searched as a flight, or '' when it can.
export function routeError(departure, arrival) {
  if (!departure || !arrival) return ''
  if (departure.id === arrival.id) return 'Departure and arrival are the same airport. Choose a different one.'
  return ''
}
