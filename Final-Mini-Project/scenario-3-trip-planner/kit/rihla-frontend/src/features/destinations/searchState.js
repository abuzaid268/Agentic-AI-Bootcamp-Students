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
export function statusMessage({ status, count, error, ambiguous, searchable, scope = 'worldwide', areas = [] }) {
  if (status === 'loading') return 'Searching for cities…'
  if (status === 'error') return error || 'City search failed. Please try again.'
  if (status === 'ready' && searchable && areas.length) {
    const examples = suggestionsOf(areas).slice(0, 3).map((d) => d.name)
    return `${areaSentence(areas)}: choose a city${examples.length ? `, such as ${examples.join(', ')}` : ' in it'}.`
  }
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

const fold = (text) => normalizeQuery(text).normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()

// The answer's `areas` (the query is the whole name of countries or regions: "Italy", "Georgia", "Texas"), cleaned:
// [{ kind: 'country' | 'region', name, countryCode, country, suggestions }], suggestions being cities there.
export function sanitizeAreas(raw) {
  if (!Array.isArray(raw)) return []
  return raw.map((area) => {
    if (!area || typeof area !== 'object' || !['country', 'region'].includes(area.kind)) return null
    const name = textOrNull(area.name)
    const countryCode = typeof area.country_code === 'string' && /^[A-Z]{2}$/.test(area.country_code) ? area.country_code : null
    if (!name || !countryCode) return null
    const suggestions = Array.isArray(area.suggestions) ? area.suggestions.map(sanitizeDestination).filter(Boolean) : []
    return { kind: area.kind, name, countryCode, country: textOrNull(area.country) || name, suggestions }
  }).filter(Boolean)
}

const suggestionsOf = (areas) => areas.flatMap((area) => area.suggestions)

// "Italy is a country", "Texas is a state or region in United States", "Georgia is a country, and a state or region
// in United States".
export function areaSentence(areas) {
  const what = areas.map((a) => (a.kind === 'country' ? 'a country' : `a state or region in ${a.country}`))
  const list = what.length > 1 ? `${what.slice(0, -1).join(', ')}, and ${what[what.length - 1]}` : what[0]
  return `${areas[0].name} is ${list}`
}

// Every choice in the list, in order: the cities suggested for the areas first, then the places found (no repeats).
export function listOptions(results, areas = []) {
  const seen = new Set()
  return [...suggestionsOf(areas), ...results].filter((d) => !seen.has(d.id) && seen.add(d.id))
}

// Which option is highlighted when an answer arrives. None when the traveller must look before choosing: the text
// names a country or region (its namesake towns are not it) or the best match shares its name with other places
// (Paris: France or Texas). Then Enter does not pick anything for them.
export function initialHighlight({ count, ambiguous, areas = [] }) {
  return count > 0 && !ambiguous && !areas.length ? 0 : -1
}

// The message that stops the trip form (the browser's own validation) while the box holds a name that is not one
// clear city and nothing was chosen: a country or a region, or a name several places share. '' when the form may go.
// `answered` is the text the answer on screen belongs to: a stale answer never blocks or allows a newer text. While
// the text is still being checked (`searchable`, no answer for it yet), the form waits; a failed search never blocks
// it (`status` 'error': the server checks the destination too).
export function destinationValidity({
  text, answered, areas = [], ambiguous = false, selected = null, searchable = false, status = 'idle',
}) {
  if (selected || !text) return ''
  if (fold(text) !== fold(answered)) {
    return searchable && status !== 'error' ? 'Wait a moment: Rihla is checking this destination.' : ''
  }
  if (areas.length) {
    const example = suggestionsOf(areas)[0]?.name
    return `${areaSentence(areas)}. Choose a city${example ? `, for example ${example},` : ''} from the list.`
  }
  if (ambiguous) return `Several places are called ${normalizeQuery(text)}. Choose the one you mean from the list.`
  return ''
}
