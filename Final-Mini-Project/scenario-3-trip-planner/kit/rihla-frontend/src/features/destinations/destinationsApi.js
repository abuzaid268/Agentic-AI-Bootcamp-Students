// Client for GET /api/destinations (app/destinations): worldwide city search for the destination box.
import { normalizeQuery, sanitizeDestination } from './searchState.js'

export class DestinationSearchError extends Error {
  constructor(message, { code = 'search_failed', retryable = false, status = null } = {}) {
    super(message)
    this.name = 'DestinationSearchError'
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

const FALLBACK_MESSAGES = {
  404: 'City search is not available on this server yet. You can still type the destination yourself.',
  429: 'Too many city searches right now. Please wait a moment.',
}

// Resolves to { query, results, ambiguous, source }. Throws DestinationSearchError with a message safe to show;
// an aborted request rethrows the AbortError so the caller can ignore it.
export async function searchDestinations(query, { signal, limit = 8, fetchImpl = globalThis.fetch } = {}) {
  const q = normalizeQuery(query)
  const url = `/api/destinations?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`

  let response
  try {
    response = await fetchImpl(url, { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    throw new DestinationSearchError('Could not reach the Rihla server for city search.', {
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
    throw new DestinationSearchError(
      (error && typeof error.message === 'string' && error.message)
        || FALLBACK_MESSAGES[response.status]
        || `City search failed (${response.status}).`,
      {
        code: (error && error.code) || (response.status === 404 ? 'not_available' : 'search_failed'),
        retryable: error ? error.retryable === true : response.status >= 500 || response.status === 429,
        status: response.status,
      },
    )
  }

  if (!body || !Array.isArray(body.results)) {
    throw new DestinationSearchError('The server sent an unexpected city search answer.', { code: 'bad_response' })
  }

  const results = body.results.map(sanitizeDestination).filter(Boolean)
  return {
    query: typeof body.query === 'string' ? body.query : q,
    results,
    ambiguous: body.ambiguous === true && results.length > 1,
    source: body.source && typeof body.source === 'object' ? body.source : null,
  }
}
