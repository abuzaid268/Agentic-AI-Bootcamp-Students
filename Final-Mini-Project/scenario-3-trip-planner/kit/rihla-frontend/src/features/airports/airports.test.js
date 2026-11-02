import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { AirportSearchError, searchAirports } from './airportsApi.js'
import {
  airportCode, airportDetails, moveHighlight, routeError, sanitizeAirport, shouldSearch, statusMessage,
} from './airportState.js'

// The backend's answers (app/airports, from the bundled OurAirports data).
const TLV = {
  id: 'ourairports:4411', name: 'Ben Gurion International Airport', city: 'Tel Aviv', region: 'Central District',
  country: 'Israel', country_code: 'IL', iata: 'TLV', icao: 'LLBG', latitude: 32.0114, longitude: 34.8867,
  type: 'large_airport', scheduled_service: true, label: 'Ben Gurion International Airport (TLV), Tel Aviv, Israel',
  ambiguous_city: false,
}
const LHR = {
  id: 'ourairports:2434', name: 'London Heathrow Airport', city: 'London', region: 'England', country: 'United Kingdom',
  country_code: 'GB', iata: 'LHR', icao: 'EGLL', latitude: 51.47075, longitude: -0.45991, type: 'large_airport',
  scheduled_service: true, label: 'London Heathrow Airport (LHR), London, United Kingdom', ambiguous_city: true,
}
const YXU = {
  id: 'ourairports:1968', name: 'London International Airport', city: 'London', region: 'Ontario', country: 'Canada',
  country_code: 'CA', iata: 'YXU', icao: 'CYXU', latitude: 43.03285, longitude: -81.149, type: 'medium_airport',
  scheduled_service: true, label: 'London International Airport (YXU), London, Canada', ambiguous_city: true,
}
const OJKF = {
  id: 'ourairports:30599', name: 'King Feisal Air Base', city: 'Al-Jafr', region: "Ma'an Governorate",
  country: 'Jordan', country_code: 'JO', iata: null, icao: 'OJKF', latitude: 30.3435, longitude: 36.1477,
  type: 'medium_airport', scheduled_service: false, label: 'King Feisal Air Base (OJKF), Al-Jafr, Jordan',
  ambiguous_city: false,
}
const LONDON = { query: 'London', count: 2, results: [LHR, YXU], ambiguous: true, cached: false,
  source: { provider: 'OurAirports', licence: 'Public domain' } }

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
  it('searches codes, cities and names from 2 letters, never numbers or symbols only', () => {
    assert.equal(shouldSearch('TLV'), true)
    assert.equal(shouldSearch('Lo'), true)
    assert.equal(shouldSearch('T'), false)
    assert.equal(shouldSearch('123'), false)
    assert.equal(shouldSearch('x'.repeat(81)), false)
  })

  it('moves through the list with the keyboard, like the destination box', () => {
    assert.equal(moveHighlight(-1, 'ArrowDown', 2), 0)
    assert.equal(moveHighlight(1, 'ArrowDown', 2), 0)
    assert.equal(moveHighlight(0, 'ArrowUp', 2), 1)
  })
})

describe('searchAirports', () => {
  it('finds TLV and returns a clean airport', async () => {
    const { impl, calls } = fakeFetch(200, { ...LONDON, query: 'TLV', count: 1, results: [TLV], ambiguous: false })
    const answer = await searchAirports(' TLV ', { fetchImpl: impl })
    assert.equal(calls[0].url, '/api/airports?q=TLV&limit=8')
    assert.deepEqual(answer.results[0], {
      id: 'ourairports:4411', name: 'Ben Gurion International Airport', city: 'Tel Aviv', region: 'Central District',
      country: 'Israel', countryCode: 'IL', iata: 'TLV', icao: 'LLBG', latitude: 32.0114, longitude: 34.8867,
      type: 'large_airport', scheduledService: true, ambiguousCity: false,
      label: 'Ben Gurion International Airport (TLV), Tel Aviv, Israel',
    })
  })

  it('keeps London, England and London, Ontario apart', async () => {
    const answer = await searchAirports('London', { fetchImpl: fakeFetch(200, LONDON).impl })
    assert.equal(answer.ambiguous, true)
    assert.deepEqual(answer.results.map(airportDetails), ['London, England, United Kingdom', 'London, Ontario, Canada'])
  })

  it('encodes the query and asks for scheduled service only when told to', async () => {
    const { impl, calls } = fakeFetch(200, { ...LONDON, results: [] })
    await searchAirports('Tel Aviv & co', { fetchImpl: impl, limit: 5, scheduledOnly: true })
    assert.equal(calls[0].url, '/api/airports?q=Tel%20Aviv%20%26%20co&limit=5&scheduled_only=true')
  })

  it('drops results it cannot use instead of guessing', async () => {
    const bad = [null, 'LHR', { ...LHR, id: '' }, { ...LHR, name: ' ' }, LHR]
    const answer = await searchAirports('London', { fetchImpl: fakeFetch(200, { ...LONDON, results: bad }).impl })
    assert.equal(answer.results.length, 1)
    assert.equal(answer.ambiguous, false) // one usable result cannot be ambiguous
  })

  it('shows the backend error, an unavailable route and an unreachable server', async () => {
    const down = fakeFetch(503, { error: { code: 'data_unavailable', message: 'Airport search is not available on this server right now.', retryable: false } })
    await assert.rejects(searchAirports('TLV', { fetchImpl: down.impl }), (err) => (
      err instanceof AirportSearchError && err.code === 'data_unavailable' && err.retryable === false))
    await assert.rejects(searchAirports('TLV', { fetchImpl: fakeFetch(404, { detail: 'Not Found' }).impl }),
      (err) => err.code === 'not_available' && /not available on this server yet/.test(err.message))
    await assert.rejects(searchAirports('TLV', { fetchImpl: fakeFetch(500, null, { json: false }).impl }),
      (err) => /Airport search failed \(500\)/.test(err.message) && err.retryable)
    const offline = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(searchAirports('TLV', { fetchImpl: offline }), (err) => err.code === 'network')
    await assert.rejects(searchAirports('TLV', { fetchImpl: fakeFetch(200, { results: {} }).impl }),
      (err) => err.code === 'bad_response')
  })

  it('lets an abort through so a newer search can win', async () => {
    const controller = new AbortController()
    controller.abort()
    const aborted = async () => { throw new DOMException('aborted', 'AbortError') }
    await assert.rejects(searchAirports('TLV', { fetchImpl: aborted, signal: controller.signal }),
      (err) => err.name === 'AbortError')
  })
})

describe('airports without every detail', () => {
  it('keeps an airport without an IATA code and shows its ICAO code', () => {
    const airport = sanitizeAirport(OJKF)
    assert.equal(airport.iata, null)
    assert.equal(airportCode(airport), 'OJKF')
    assert.equal(airport.scheduledService, false)
  })

  it('shows no code when there is none, and never invents one', () => {
    const airport = sanitizeAirport({ ...OJKF, icao: null, label: '' })
    assert.equal(airportCode(airport), null)
    assert.equal(airport.label, 'King Feisal Air Base, Al-Jafr, Jordan')
  })

  it('turns malformed codes and coordinates into null', () => {
    const airport = sanitizeAirport({ ...TLV, iata: 'T1V', icao: 'LL', country_code: 'ISR', latitude: 'x' })
    assert.equal(airport.iata, null)
    assert.equal(airport.icao, null)
    assert.equal(airport.countryCode, null)
    assert.equal(airport.latitude, null)
    assert.equal(airport.longitude, null) // never half a position
  })
})

describe('what the traveller sees and hears', () => {
  it('announces loading, results, shared city names, no results and errors', () => {
    assert.match(statusMessage({ status: 'loading' }), /Searching for airports/)
    assert.equal(statusMessage({ status: 'ready', count: 1, searchable: true }), '1 airport found.')
    assert.match(statusMessage({ status: 'ready', count: 7, ambiguous: true, searchable: true }), /Several cities share this name/)
    assert.match(statusMessage({ status: 'ready', count: 0, searchable: true }), /No airports found/)
    assert.equal(statusMessage({ status: 'error', error: 'Down.' }), 'Down.')
    assert.equal(statusMessage({ status: 'ready', count: 2, searchable: false }), '') // after choosing
  })

  it('refuses the same airport for departure and arrival', () => {
    const tlv = sanitizeAirport(TLV)
    assert.match(routeError(tlv, sanitizeAirport(TLV)), /same airport/)
    assert.equal(routeError(tlv, sanitizeAirport(LHR)), '')
    assert.equal(routeError(tlv, null), '') // nothing to compare yet
  })
})
