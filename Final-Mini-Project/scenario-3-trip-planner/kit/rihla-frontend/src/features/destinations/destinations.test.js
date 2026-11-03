import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { DestinationSearchError, searchDestinations } from './destinationsApi.js'
import {
  moveHighlight, normalizeQuery, placeDetails, sanitizeDestination, shouldSearch, statusMessage,
} from './searchState.js'

// The backend's answer for "Pari" (app/destinations, from a recorded Open-Meteo response).
const PARIS = {
  id: 'geonames:2988507', provider_id: 2988507, name: 'Paris', region: 'Île-de-France Region', country: 'France',
  country_code: 'FR', latitude: 48.85341, longitude: 2.3488, population: 2138551, timezone: 'Europe/Paris',
  feature_code: 'PPLC', label: 'Paris, Île-de-France Region, France', ambiguous_name: true,
}
const PARIS_TX = { ...PARIS, id: 'geonames:4717560', provider_id: 4717560, region: 'Texas', country: 'United States',
  country_code: 'US', latitude: 33.66, longitude: -95.55, label: 'Paris, Texas, United States' }
const ANSWER = { query: 'Pari', count: 2, results: [PARIS, PARIS_TX], ambiguous: true, cached: false,
  source: { provider: 'Open-Meteo Geocoding API (GeoNames)', licence: 'CC BY 4.0' } }

function fakeFetch(status, body, { json = true } = {}) {
  const calls = []
  const impl = async (url, init) => {
    calls.push({ url, init })
    return { ok: status >= 200 && status < 300, status, json: async () => {
      if (!json) throw new SyntaxError('not JSON')
      return body
    } }
  }
  return { impl, calls }
}

describe('what is searched', () => {
  it('normalizes spaces and Unicode', () => {
    assert.equal(normalizeQuery('  New   York '), 'New York')
    assert.equal(normalizeQuery('São Paulo'), 'São Paulo')
    assert.equal(normalizeQuery(null), '')
  })

  it('searches from 2 letters, never for numbers or symbols only, never past 80 characters', () => {
    assert.equal(shouldSearch('P'), false)
    assert.equal(shouldSearch('Pa'), true)
    assert.equal(shouldSearch(' P '), false)
    assert.equal(shouldSearch('12'), false)
    assert.equal(shouldSearch('عمّان'), true) // any script's letters
    assert.equal(shouldSearch('x'.repeat(81)), false)
  })
})

describe('keyboard movement in the list', () => {
  it('moves down and up and wraps around', () => {
    assert.equal(moveHighlight(-1, 'ArrowDown', 3), 0)
    assert.equal(moveHighlight(0, 'ArrowDown', 3), 1)
    assert.equal(moveHighlight(2, 'ArrowDown', 3), 0)
    assert.equal(moveHighlight(0, 'ArrowUp', 3), 2)
    assert.equal(moveHighlight(-1, 'ArrowUp', 3), 2)
    assert.equal(moveHighlight(1, 'Home', 3), 0)
    assert.equal(moveHighlight(0, 'End', 3), 2)
    assert.equal(moveHighlight(1, 'a', 3), 1)
  })

  it('highlights nothing in an empty list', () => {
    assert.equal(moveHighlight(0, 'ArrowDown', 0), -1)
  })
})

describe('searchDestinations', () => {
  it('asks the backend and returns clean results', async () => {
    const { impl, calls } = fakeFetch(200, ANSWER)
    const answer = await searchDestinations('  Pari ', { fetchImpl: impl, limit: 5 })
    assert.equal(calls[0].url, '/api/destinations?q=Pari&limit=5')
    assert.equal(answer.ambiguous, true)
    assert.deepEqual(answer.results.map((d) => d.label), ['Paris, Île-de-France Region, France', 'Paris, Texas, United States'])
    assert.equal(answer.results[0].countryCode, 'FR')
    assert.equal(answer.results[0].timezone, 'Europe/Paris')
  })

  it('encodes the query', async () => {
    const { impl, calls } = fakeFetch(200, { ...ANSWER, results: [] })
    await searchDestinations('São & Co', { fetchImpl: impl })
    assert.equal(calls[0].url, '/api/destinations?q=S%C3%A3o%20%26%20Co&limit=8')
  })

  it('drops results it cannot use instead of guessing', async () => {
    const bad = [{ ...PARIS, latitude: 'x' }, { ...PARIS, id: '' }, { ...PARIS, longitude: 200 }, null, PARIS]
    const { impl } = fakeFetch(200, { ...ANSWER, results: bad })
    const answer = await searchDestinations('Pari', { fetchImpl: impl })
    assert.equal(answer.results.length, 1)
    assert.equal(answer.ambiguous, false) // one usable result cannot be ambiguous
  })

  it('shows the backend error message and whether a retry helps', async () => {
    const { impl } = fakeFetch(504, { error: { code: 'provider_timeout', message: 'The city search service did not answer in time.', retryable: true } })
    await assert.rejects(searchDestinations('Pari', { fetchImpl: impl }), (err) => (
      err instanceof DestinationSearchError && err.code === 'provider_timeout' && err.retryable === true
      && /did not answer in time/.test(err.message)))
  })

  it('explains when the server does not offer city search yet (404)', async () => {
    const { impl } = fakeFetch(404, { detail: 'Not Found' })
    await assert.rejects(searchDestinations('Pari', { fetchImpl: impl }), (err) => (
      err.code === 'not_available' && /not available on this server yet/.test(err.message) && err.retryable === false))
  })

  it('explains a rate limit and an unreadable error page', async () => {
    await assert.rejects(searchDestinations('Pari', { fetchImpl: fakeFetch(429, null, { json: false }).impl }),
      (err) => /Too many city searches/.test(err.message) && err.retryable === true)
    await assert.rejects(searchDestinations('Pari', { fetchImpl: fakeFetch(502, null, { json: false }).impl }),
      (err) => /City search failed \(502\)/.test(err.message))
  })

  it('reports an unreachable server, an odd answer, and lets an abort through', async () => {
    const down = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(searchDestinations('Pari', { fetchImpl: down }), (err) => err.code === 'network' && err.retryable)
    await assert.rejects(searchDestinations('Pari', { fetchImpl: fakeFetch(200, { results: 'x' }).impl }),
      (err) => err.code === 'bad_response')
    const controller = new AbortController()
    controller.abort()
    const aborted = async () => { throw new DOMException('aborted', 'AbortError') }
    await assert.rejects(searchDestinations('Pari', { fetchImpl: aborted, signal: controller.signal }),
      (err) => err.name === 'AbortError')
  })
})

describe('what the traveller sees and hears', () => {
  it('describes a place by region and country, without repeating the city', () => {
    assert.equal(placeDetails({ name: 'Paris', region: 'Texas', country: 'United States' }), 'Texas, United States')
    assert.equal(placeDetails({ name: 'Amman', region: 'Amman', country: 'Jordan' }), 'Jordan')
    assert.equal(sanitizeDestination({ ...PARIS, label: '' }).label, 'Paris, Île-de-France Region, France')
  })

  it('announces loading, results, ambiguity, no results and errors', () => {
    assert.match(statusMessage({ status: 'loading' }), /Searching/)
    assert.equal(statusMessage({ status: 'ready', count: 1, searchable: true }), '1 city found.')
    assert.match(statusMessage({ status: 'ready', count: 3, ambiguous: true, searchable: true }), /Several places share this name/)
    assert.match(statusMessage({ status: 'ready', count: 0, searchable: true }), /No cities found/)
    assert.equal(statusMessage({ status: 'error', error: 'Down.' }), 'Down.')
    assert.equal(statusMessage({ status: 'ready', count: 2, searchable: false }), '') // after choosing a city
  })
})
