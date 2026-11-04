// Pure helpers for FlightSearch: form checks, the answer from GET /api/flights, sorting and formatting.

export const CABIN_CLASSES = [
  ['economy', 'Economy'], ['premium_economy', 'Premium economy'], ['business', 'Business'], ['first', 'First'],
]
export const MAX_ADULTS = 9

export const DATA_MODES = {
  LIVE: { label: 'LIVE', title: 'Live prices', detail: 'Prices from the provider at the time shown. They change and expire.' },
  TEST: { label: 'TEST', title: 'Test data', detail: "From the provider's sandbox: not real flights, schedules or prices." },
  DEMO: { label: 'DEMO', title: 'Demo data', detail: 'Sample flights made up by Rihla. Not real flights, schedules or prices.' },
}

// Badge and banner colours: green for live, amber for the sandbox, violet for made-up demo data.
export const MODE_STYLES = {
  LIVE: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  TEST: 'border-amber-300 bg-amber-50 text-amber-900',
  DEMO: 'border-violet-300 bg-violet-50 text-violet-900',
}

export function isoToday(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// Field -> message for what the traveller still has to fix; {} when the search can run. The server checks
// the same things again (app/flights/service.py).
export function validateFlightForm({ origin, destination, departureDate, returnDate, roundTrip, adults }, today) {
  const errors = {}
  if (!origin?.iata) errors.origin = origin ? 'This airport has no IATA code, so flights cannot be searched.' : 'Choose a departure airport.'
  if (!destination?.iata) errors.destination = destination ? 'This airport has no IATA code, so flights cannot be searched.' : 'Choose an arrival airport.'
  if (origin?.iata && destination?.iata && origin.iata === destination.iata) {
    errors.destination = 'Departure and arrival must be different airports.'
  }
  if (!departureDate) errors.departureDate = 'Choose a departure date.'
  else if (departureDate < today) errors.departureDate = 'The departure date is in the past.'
  if (roundTrip) {
    if (!returnDate) errors.returnDate = 'Choose a return date, or switch to one way.'
    else if (departureDate && returnDate < departureDate) errors.returnDate = 'The return date is before the departure date.'
  }
  const count = Number(adults)
  if (!Number.isInteger(count) || count < 1 || count > MAX_ADULTS) errors.adults = `Choose 1 to ${MAX_ADULTS} adults.`
  return errors
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const hintText = (value) => (typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 100) : '')

// FlightSearch's starting values from optional props (a parent's trip), cleaned: anything unusable is left empty
// for the traveller to fill in, never guessed. Hints are only text for the airport boxes, never a chosen airport.
export function initialFlightForm({ departureHint, departureCountry, arrivalHint, departureDate, returnDate, adults } = {}) {
  const depart = typeof departureDate === 'string' && ISO_DATE.test(departureDate) ? departureDate : ''
  const back = typeof returnDate === 'string' && ISO_DATE.test(returnDate) && (!depart || returnDate >= depart)
    ? returnDate : ''
  const count = Number(adults)
  const wanted = Number.isInteger(count) && count >= 1 ? count : 1
  const country = typeof departureCountry === 'string' ? departureCountry.trim() : ''
  return {
    departureHint: hintText(departureHint),
    departureCountry: /^[A-Za-z]{2}$/.test(country) ? country.toUpperCase() : '',
    arrivalHint: hintText(arrivalHint),
    departureDate: depart,
    returnDate: back,
    roundTrip: !depart || Boolean(back), // a trip with a start date but no return date is searched one way
    adults: Math.min(wanted, MAX_ADULTS),
    adultsCapped: wanted > MAX_ADULTS,
  }
}

// What a search asks for. Offers (or an error) on screen belong to the key they were searched with: once the
// form no longer matches it, they are hidden instead of being shown as if they answered the new search.
export function searchKey({ origin, destination, departureDate, returnDate, roundTrip, adults, cabinClass }) {
  return JSON.stringify([
    origin?.iata ?? null, destination?.iata ?? null, departureDate || '', roundTrip ? returnDate || '' : '',
    Number(adults) || 0, cabinClass || 'economy',
  ])
}

// What to show: 'stale' when a finished search (ready or error) no longer matches the form; otherwise the status.
export function resultState(status, resultKey, currentKey) {
  return (status === 'ready' || status === 'error') && resultKey !== currentKey ? 'stale' : status
}

// Only the newest search may change the screen: an older one that answers late is ignored.
export function latestOnly() {
  let current = 0
  return { start: () => ++current, isCurrent: (ticket) => ticket === current }
}

const textOrNull = (value) => (typeof value === 'string' && value.trim() ? value.trim() : null)
const intOrNull = (value) => (Number.isInteger(value) && value >= 0 ? value : null)
const isAmount = (value) => typeof value === 'string' && /^\d+(\.\d+)?$/.test(value) && Number(value) > 0

function sanitizeSlice(raw) {
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.segments)) return null
  const origin = textOrNull(raw.origin)
  const destination = textOrNull(raw.destination)
  const departingAt = textOrNull(raw.departing_at)
  const arrivingAt = textOrNull(raw.arriving_at)
  if (!origin || !destination || !departingAt || !arrivingAt) return null
  return {
    origin,
    destination,
    departingAt,
    arrivingAt,
    durationMinutes: intOrNull(raw.duration_minutes),
    stops: intOrNull(raw.stops) ?? 0,
    connections: Array.isArray(raw.connections) ? raw.connections.filter((c) => typeof c === 'string') : [],
    flightNumbers: raw.segments.map((s) => textOrNull(s?.flight_number)).filter(Boolean),
  }
}

// One offer from the API, or null when it cannot be shown honestly (no price, no journey).
export function sanitizeOffer(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = textOrNull(raw.id)
  const currency = typeof raw.currency === 'string' && /^[A-Z]{3}$/.test(raw.currency) ? raw.currency : null
  if (!id || !isAmount(raw.total_amount) || !currency || !Array.isArray(raw.slices) || !raw.slices.length) return null
  const slices = raw.slices.map(sanitizeSlice)
  if (slices.some((s) => !s)) return null
  const mode = DATA_MODES[raw.data_mode] ? raw.data_mode : null
  if (!mode) return null
  return {
    id,
    airline: textOrNull(raw.airline?.name) || 'Airline not given',
    airlineCode: textOrNull(raw.airline?.iata_code),
    totalAmount: raw.total_amount,
    currency,
    passengers: intOrNull(raw.passengers) || 1,
    cabinClass: textOrNull(raw.cabin_class),
    slices,
    baggage: { checked: intOrNull(raw.baggage?.checked), carryOn: intOrNull(raw.baggage?.carry_on) },
    expiresAt: textOrNull(raw.expires_at),
    timeBasis: raw.time_basis === 'utc' ? 'utc' : 'local',
    dataMode: mode,
    provider: textOrNull(raw.provider),
  }
}

// The answer from GET /api/flights, cleaned. Throws when it is not a flight answer at all.
export function sanitizeFlightAnswer(body) {
  if (!body || typeof body !== 'object' || !Array.isArray(body.offers) || !DATA_MODES[body.data_mode]) {
    throw new Error('The server sent an unexpected flight search answer.')
  }
  const offers = body.offers.map(sanitizeOffer).filter(Boolean)
  return {
    offers,
    dataMode: body.data_mode,
    provider: textOrNull(body.provider),
    retrievedAt: textOrNull(body.retrieved_at),
    totalOffers: intOrNull(body.total_offers) ?? offers.length,
    comparable: new Set(offers.map((o) => o.currency)).size <= 1,
    notices: Array.isArray(body.notices) ? body.notices.filter((n) => typeof n === 'string') : [],
  }
}

const totalMinutes = (offer) => offer.slices.reduce((sum, s) => sum + (s.durationMinutes ?? 1e6), 0)

// Sorts within each currency only: prices in different currencies are never compared. Currency groups keep the
// server's order (the most common currency first).
export function sortOffers(offers, order = 'price-asc') {
  const groups = new Map()
  for (const offer of offers) {
    if (!groups.has(offer.currency)) groups.set(offer.currency, [])
    groups.get(offer.currency).push(offer)
  }
  const compare = {
    'price-asc': (a, b) => Number(a.totalAmount) - Number(b.totalAmount) || totalMinutes(a) - totalMinutes(b),
    'price-desc': (a, b) => Number(b.totalAmount) - Number(a.totalAmount) || totalMinutes(a) - totalMinutes(b),
    duration: (a, b) => totalMinutes(a) - totalMinutes(b) || Number(a.totalAmount) - Number(b.totalAmount),
  }[order] || (() => 0)
  return [...groups.values()].flatMap((group) => [...group].sort(compare))
}

// The cheapest offer per currency: { USD: offer, EUR: offer }.
export function cheapestByCurrency(offers) {
  const cheapest = {}
  for (const offer of offers) {
    const best = cheapest[offer.currency]
    if (!best || Number(offer.totalAmount) < Number(best.totalAmount)) cheapest[offer.currency] = offer
  }
  return cheapest
}

export function formatPrice(amount, currency) {
  try {
    return new Intl.NumberFormat('en', { style: 'currency', currency }).format(Number(amount))
  } catch {
    return `${amount} ${currency}`
  }
}

export function formatDuration(minutes) {
  if (!Number.isInteger(minutes)) return 'Duration not given'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? `${h}h${m ? ` ${String(m).padStart(2, '0')}m` : ''}` : `${m}m`
}

// "2026-12-01T08:10" -> "08:10"; the time is the airport's local time unless the offer says UTC.
export const formatClock = (value) => (typeof value === 'string' ? value.slice(11, 16) : '')

// "+1" when the flight lands on a later calendar day than it left.
export function dayShift(departingAt, arrivingAt) {
  const days = Math.round((Date.parse(`${arrivingAt.slice(0, 10)}T00:00Z`) - Date.parse(`${departingAt.slice(0, 10)}T00:00Z`)) / 86400000)
  return Number.isFinite(days) && days > 0 ? `+${days}` : ''
}

export function stopsLabel(slice) {
  if (!slice.stops) return 'Direct'
  const via = slice.connections.length ? ` via ${slice.connections.join(', ')}` : ''
  return `${slice.stops} ${slice.stops === 1 ? 'stop' : 'stops'}${via}`
}

export function baggageLabel({ checked, carryOn }) {
  const part = (count, noun) => {
    if (count === null) return null
    return count === 0 ? `no ${noun}` : `${count} ${noun}${count === 1 ? '' : 's'}`
  }
  const parts = [part(checked, 'checked bag'), part(carryOn, 'carry-on bag')].filter(Boolean)
  if (!parts.length) return 'Baggage not stated: check with the airline'
  return `${parts.join(', ')} per passenger${checked === null || carryOn === null ? ' (other allowance not stated)' : ''}`
}
