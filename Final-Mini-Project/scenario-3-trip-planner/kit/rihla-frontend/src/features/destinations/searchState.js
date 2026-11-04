// Pure helpers for DestinationSearch: what to search, keyboard movement in the list, and what to announce.

export const MIN_QUERY_LENGTH = 1
// Below this the server answers from its bundled list of popular destinations, not the worldwide search.
export const WORLDWIDE_MIN_LENGTH = 3
export const MAX_QUERY_LENGTH = 80

export function normalizeQuery(text) {
  return String(text ?? '').normalize('NFC').replace(/\s+/g, ' ').trim()
}

// The backend refuses the same cases (app/destinations/service.py): don't send a request it would refuse.
export function shouldSearch(text) {
  const query = normalizeQuery(text)
  return query.length >= MIN_QUERY_LENGTH && query.length <= MAX_QUERY_LENGTH && /\p{L}/u.test(query)
}

// The highlighted option after a key press; -1 means none. The list wraps around at both ends.
export function moveHighlight(index, key, count) {
  if (!count) return -1
  if (key === 'ArrowDown') return index < 0 || index >= count - 1 ? 0 : index + 1
  if (key === 'ArrowUp') return index <= 0 ? count - 1 : index - 1
  if (key === 'Home') return 0
  if (key === 'End') return count - 1
  return index
}

// Region and country under the city name, so places with the same name can be told apart.
export function placeDetails(destination) {
  const parts = [destination.region !== destination.name ? destination.region : null, destination.country]
  return parts.filter(Boolean).join(', ')
}

// The text a chosen city puts in the box: its label, shortened when needed to fit the trip form's limit
// (tripForm.js and the backend accept at most 100 characters): "name, country", then the name.
export const MAX_DESTINATION_TEXT = 100

export function destinationText(destination, max = MAX_DESTINATION_TEXT) {
  const options = [destination.label, [destination.name, destination.country].filter(Boolean).join(', '), destination.name]
  return options.find((text) => text && text.length <= max) || destination.name.slice(0, max)
}

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)
const textOrNull = (value) => (typeof value === 'string' && value.trim() ? value.trim() : null)

// One result from GET /api/destinations, or null when it is not a usable place (never guessed).
export function sanitizeDestination(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = textOrNull(raw.id)
  const name = textOrNull(raw.name)
  const { latitude, longitude } = raw
  if (!id || !name || !isFiniteNumber(latitude) || !isFiniteNumber(longitude)) return null
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null
  const destination = {
    id,
    name,
    region: textOrNull(raw.region),
    country: textOrNull(raw.country),
    countryCode: textOrNull(raw.country_code),
    latitude,
    longitude,
    population: Number.isInteger(raw.population) && raw.population >= 0 ? raw.population : null,
    timezone: textOrNull(raw.timezone),
    ambiguousName: raw.ambiguous_name === true,
  }
  return { ...destination, label: textOrNull(raw.label) || [name, placeDetails(destination)].filter(Boolean).join(', ') }
}

// The sentence for the screen reader's live region (and the visible status line).
export function statusMessage({ status, count, error, ambiguous, searchable, scope = 'worldwide' }) {
  if (status === 'loading') return 'Searching for cities…'
  if (status === 'error') return error || 'City search failed. Please try again.'
  if (status === 'ready' && searchable && scope === 'popular') {
    if (!count) return `No popular destination starts with that. Type ${WORLDWIDE_MIN_LENGTH} letters or more to search every city.`
    return `${count} popular ${count === 1 ? 'destination' : 'destinations'}. Keep typing to search every city.`
  }
  if (status === 'ready' && searchable) {
    if (!count) return 'No cities found. Check the spelling, or try the city name in English.'
    const found = `${count} ${count === 1 ? 'city' : 'cities'} found.`
    return ambiguous ? `${found} Several places share this name: check the region and country.` : found
  }
  return ''
}
