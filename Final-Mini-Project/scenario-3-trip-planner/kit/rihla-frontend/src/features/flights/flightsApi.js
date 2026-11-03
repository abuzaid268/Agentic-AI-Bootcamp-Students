// Client for GET /api/flights (app/flights): flight offers for a route and dates. Read-only: nothing books or pays.
import { sanitizeFlightAnswer } from './flightState.js'

export class FlightSearchError extends Error {
  constructor(message, { code = 'search_failed', field = null, retryable = false, status = null } = {}) {
    super(message)
    this.name = 'FlightSearchError'
    this.code = code
    this.field = field
    this.retryable = retryable
    this.status = status
  }
}

const FALLBACK_MESSAGES = {
  404: 'Flight search is not available on this server yet.',
  429: 'Too many flight searches right now. Please wait a moment.',
}

// GET /api/flights/status: whether this server can show flight prices, and as which data mode. Resolves to null
// when the server does not say (an older server without the route): the form then simply works as usual.
export async function fetchFlightStatus({ signal, fetchImpl = globalThis.fetch } = {}) {
  try {
    const response = await fetchImpl('/api/flights/status', { signal, headers: { Accept: 'application/json' } })
    if (!response.ok) return null
    const body = await response.json()
    if (!body || typeof body.available !== 'boolean') return null
    return {
      available: body.available,
      environment: typeof body.environment === 'string' ? body.environment : null,
      dataMode: ['LIVE', 'TEST', 'DEMO'].includes(body.data_mode) ? body.data_mode : null,
      notice: typeof body.notice === 'string' ? body.notice : null,
    }
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    return null
  }
}

// True for the server's "no real prices here" answer (production without an approved live provider).
export const isFlightsUnavailable = (err) => err?.code === 'flights_unavailable'

export function flightSearchUrl({ origin, destination, departureDate, returnDate, adults, cabinClass }) {
  const params = new URLSearchParams({
    origin: origin || '',
    destination: destination || '',
    departure_date: departureDate || '',
    adults: String(adults || 1),
    cabin_class: cabinClass || 'economy',
  })
  if (returnDate) params.set('return_date', returnDate)
  return `/api/flights?${params.toString()}`
}

// Resolves to the cleaned answer (see sanitizeFlightAnswer). Throws FlightSearchError with a message safe to show
// and, for a form mistake, the field at fault; an aborted request rethrows the AbortError.
export async function searchFlights(search, { signal, fetchImpl = globalThis.fetch } = {}) {
  let response
  try {
    response = await fetchImpl(flightSearchUrl(search), { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    throw new FlightSearchError('Could not reach the Rihla server for flight search.', { code: 'network', retryable: true })
  }

  let body = null
  try {
    body = await response.json()
  } catch {
    // handled below
  }

  if (!response.ok) {
    const error = body && typeof body.error === 'object' ? body.error : null
    throw new FlightSearchError(
      (error && typeof error.message === 'string' && error.message)
        || FALLBACK_MESSAGES[response.status]
        || `Flight search failed (${response.status}).`,
      {
        code: (error && error.code) || (response.status === 404 ? 'not_available' : 'search_failed'),
        field: (error && typeof error.field === 'string' && error.field) || null,
        retryable: error ? error.retryable === true : response.status >= 500 || response.status === 429,
        status: response.status,
      },
    )
  }

  try {
    return sanitizeFlightAnswer(body)
  } catch (err) {
    throw new FlightSearchError(err.message, { code: 'bad_response' })
  }
}
