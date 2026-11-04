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

// ------------------------------------------------------------------ airports near a chosen place (GET /api/airports/near)
// A place from the destination box ({ name, region, country, countryCode, latitude, longitude, ... }), kept only when
// it can be asked about: a name, real coordinates and a 2-letter country code. Nothing is guessed from a typed name.
export function cleanNearbyPlace(raw) {
  if (!raw || typeof raw !== 'object') return null
  const name = textOrNull(raw.name)
  const countryCode = codeOrNull(typeof raw.countryCode === 'string' ? raw.countryCode.toUpperCase() : null, /^[A-Z]{2}$/)
  const latitude = coordinate(raw.latitude, 90)
  const longitude = coordinate(raw.longitude, 180)
  if (!name || !countryCode || latitude === null || longitude === null) return null
  return {
    name, countryCode, latitude, longitude,
    region: textOrNull(raw.region),
    country: textOrNull(raw.country),
    label: textOrNull(raw.label) || [name, textOrNull(raw.country)].filter(Boolean).join(', '),
  }
}

// The same place asked about once: coordinates and country decide, never the name.
export const nearbyPlaceKey = (place) => (place ? `${place.countryCode}:${place.latitude.toFixed(4)},${place.longitude.toFixed(4)}` : '')

// The answer from GET /api/airports/near, cleaned. Airports without an IATA code or a distance are dropped (they
// cannot be searched as flights); `suggested` is kept only when it is in the list and in the place's own country.
export function sanitizeNearby(body) {
  if (!body || typeof body !== 'object' || !Array.isArray(body.airports)) {
    throw new Error('The server sent an unexpected nearby airports answer.')
  }
  const airports = body.airports.map((raw) => {
    const airport = sanitizeAirport(raw)
    const km = raw?.distance_km
    if (!airport || !airport.iata || typeof km !== 'number' || !Number.isFinite(km) || km < 0) return null
    return { ...airport, distanceKm: km, inCountry: raw.in_country === true ? true : raw.in_country === false ? false : null }
  }).filter(Boolean)
  const country = body.country && typeof body.country === 'object' && /^[A-Z]{2}$/.test(body.country.code || '')
    ? { code: body.country.code, name: textOrNull(body.country.name) } : null
  const wanted = typeof body.suggested === 'string' ? body.suggested : null
  const suggested = wanted ? airports.find((a) => a.id === wanted && a.inCountry === true) || null : null
  return {
    airports,
    suggested,
    country,
    maxKm: typeof body.max_km === 'number' && body.max_km > 0 ? body.max_km : null,
    note: textOrNull(body.note),
  }
}

export function distanceLabel(km) {
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`
}

// Where an airport is, relative to the place's country, so an airport across a border is never taken for a local one.
export function locationLabel(airport, country) {
  if (airport.inCountry === false) {
    return `In ${airport.country || 'another country'}${country?.name ? `, outside ${country.name}` : ''}`
  }
  return airport.country ? `In ${airport.country}` : ''
}

// The sentences that explain a list: what was searched, what is missing and what to watch for. Nothing here claims
// that an airport serves a route: only that it has scheduled service in the airport data.
export function nearbyNotes({ place, airports, country, maxKm }) {
  const notes = []
  const where = place.region && place.region !== place.name ? `${place.name}, ${place.region}` : place.name
  const home = country?.name || place.country || place.countryCode
  const inside = airports.filter((a) => a.inCountry !== false)
  const outside = airports.filter((a) => a.inCountry === false)
  if (!airports.length) {
    notes.push(`No airport with scheduled service was found within ${maxKm ?? 150} km of ${where}. Search for an airport by name or code.`)
    return notes
  }
  if (!inside.length) {
    notes.push(`There is no airport in ${home} within ${maxKm ?? 150} km of ${where}. The airports below are in another country.`)
  } else if (inside.every((a) => a.distanceKm > 60)) {
    notes.push(`${where} has no airport of its own nearby: the closest in ${home} are ${distanceLabel(inside[0].distanceKm)} away.`)
  }
  if (outside.length && inside.length) {
    notes.push(`Airports marked “outside ${home}” are in another country: check entry rules before choosing one.`)
  } else if (outside.length) {
    notes.push(`Check entry rules before choosing an airport outside ${home}.`)
  }
  return notes
}
