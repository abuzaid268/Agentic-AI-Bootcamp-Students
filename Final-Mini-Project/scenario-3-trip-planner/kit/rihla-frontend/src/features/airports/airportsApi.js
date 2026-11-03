// Client for GET /api/airports (app/airports): airport search for the departure and arrival boxes.
import { normalizeQuery, sanitizeAirport, sanitizeCountries } from './airportState.js'

export class AirportSearchError extends Error {
  constructor(message, { code = 'search_failed', retryable = false, status = null } = {}) {
    super(message)
    this.name = 'AirportSearchError'
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

const FALLBACK_MESSAGES = {
  404: 'Airport search is not available on this server yet. You can still type the airport or city yourself.',
}

// Resolves to { query, results, ambiguous, source }. Throws AirportSearchError with a message safe to show;
// an aborted request rethrows the AbortError so the caller can ignore it.
export async function searchAirports(query, {
  signal, limit = 8, scheduledOnly = false, country = '', fetchImpl = globalThis.fetch,
} = {}) {
  const params = new URLSearchParams({ q: normalizeQuery(query), limit: String(limit) })
  if (scheduledOnly) params.set('scheduled_only', 'true')
  if (/^[A-Z]{2}$/.test(country || '')) params.set('country', country)
  const url = `/api/airports?${params.toString().replace(/\+/g, '%20')}`

  let response
  try {
    response = await fetchImpl(url, { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    throw new AirportSearchError('Could not reach the Rihla server for airport search.', {
      code: 'network', retryable: true,
    })
  }

  let body = null
  try {
    body = await response.json()
  } catch {
    // handled below
  }

  if (!response.ok) {
    const error = body && typeof body.error === 'object' ? body.error : null
    throw new AirportSearchError(
      (error && typeof error.message === 'string' && error.message)
        || FALLBACK_MESSAGES[response.status]
        || `Airport search failed (${response.status}).`,
      {
        code: (error && error.code) || (response.status === 404 ? 'not_available' : 'search_failed'),
        retryable: error ? error.retryable === true : response.status >= 500 || response.status === 429,
        status: response.status,
      },
    )
  }

  if (!body || !Array.isArray(body.results)) {
    throw new AirportSearchError('The server sent an unexpected airport search answer.', { code: 'bad_response' })
  }

  const results = body.results.map(sanitizeAirport).filter(Boolean)
  return {
    query: typeof body.query === 'string' ? body.query : normalizeQuery(query),
    results,
    ambiguous: body.ambiguous === true && results.length > 1,
    source: body.source && typeof body.source === 'object' ? body.source : null,
  }
}

// GET /api/airports/countries: the countries that have airports, for the departure country picker. Resolves to []
// when the server cannot say (an older server, or the data is unavailable): the picker is then simply not offered.
export async function fetchAirportCountries({ signal, fetchImpl = globalThis.fetch } = {}) {
  try {
    const response = await fetchImpl('/api/airports/countries', { signal, headers: { Accept: 'application/json' } })
    if (!response.ok) return []
    return sanitizeCountries(await response.json())
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    return []
  }
}
