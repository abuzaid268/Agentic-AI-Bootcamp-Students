import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { describe, it } from 'node:test'

import { sanitizeAirport } from '../airports/airportState.js'
import {
  FlightSearchError, fetchFlightStatus, flightSearchUrl, isFlightsUnavailable, searchFlights,
} from './flightsApi.js'
import {
  baggageLabel, cheapestByCurrency, dayShift, formatDuration, formatPrice, initialFlightForm, latestOnly, resultState,
  sanitizeFlightAnswer, sanitizeOffer, searchKey, sortOffers, stopsLabel, validateFlightForm,
} from './flightState.js'

// A real answer from the backend's DEMO provider (app/flights): TLV -> LHR round trip, 2 adults.
const DEMO = JSON.parse(readFileSync(new URL('./fixtures/demo_tlv_lhr_round_trip.json', import.meta.url), 'utf8'))

// A TEST-mode offer as the backend normalizes Duffel's sandbox answers (synthetic values).
const slice = (origin, destination, departing, arriving, extra = {}) => ({
  origin, destination, departing_at: departing, arriving_at: arriving, duration_minutes: 310, stops: 0,
  connections: [], segments: [{ flight_number: 'ZZ101' }], ...extra,
})
const offer = (id, amount, currency = 'USD', extra = {}) => ({
  id, provider_offer_id: id, airline: { name: 'Duffel Airways', iata_code: 'ZZ' }, total_amount: amount, currency,
  passengers: 1, cabin_class: 'economy', slices: [slice('TLV', 'LHR', '2026-12-01T08:00', '2026-12-01T11:10')],
  baggage: { checked: 1, carry_on: 1 }, expires_at: '2026-11-02T12:30:00Z', time_basis: 'local', data_mode: 'TEST',
  provider: 'Duffel', ...extra,
})
const answer = (offers, extra = {}) => ({
  query: {}, data_mode: 'TEST', provider: 'Duffel', retrieved_at: '2026-11-02T12:00:00Z', count: offers.length,
  total_offers: offers.length, offers, notices: ['TEST data from the provider\'s sandbox.'], ...extra,
})

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

const TLV = { iata: 'TLV' }
const LHR = { iata: 'LHR' }
const FORM = { origin: TLV, destination: LHR, departureDate: '2026-12-01', returnDate: '2026-12-08', roundTrip: true, adults: 1 }

describe('the search form', () => {
  it('accepts a complete one-way or round-trip search', () => {
    assert.deepEqual(validateFlightForm(FORM, '2026-11-02'), {})
    assert.deepEqual(validateFlightForm({ ...FORM, roundTrip: false, returnDate: '' }, '2026-11-02'), {})
  })

  it('names every missing or invalid field', () => {
    const errors = validateFlightForm({ roundTrip: true, adults: 0 }, '2026-11-02')
    assert.deepEqual(Object.keys(errors).sort(), ['adults', 'departureDate', 'destination', 'origin', 'returnDate'])
    assert.match(validateFlightForm({ ...FORM, destination: TLV }, '2026-11-02').destination, /different airports/)
    assert.match(validateFlightForm({ ...FORM, departureDate: '2026-11-01' }, '2026-11-02').departureDate, /past/)
    assert.match(validateFlightForm({ ...FORM, returnDate: '2026-11-30' }, '2026-11-02').returnDate, /before/)
    assert.match(validateFlightForm({ ...FORM, adults: 10 }, '2026-11-02').adults, /1 to 9/)
  })

  it('refuses an airport without an IATA code instead of sending its ICAO code', () => {
    const errors = validateFlightForm({ ...FORM, origin: { iata: null, icao: 'OJKF' } }, '2026-11-02')
    assert.match(errors.origin, /no IATA code/)
  })

  it('builds the request for one way, round trip and several passengers', () => {
    assert.equal(flightSearchUrl({ origin: 'TLV', destination: 'LHR', departureDate: '2026-12-01', adults: 1 }),
      '/api/flights?origin=TLV&destination=LHR&departure_date=2026-12-01&adults=1&cabin_class=economy')
    assert.equal(flightSearchUrl({ origin: 'TLV', destination: 'LHR', departureDate: '2026-12-01',
      returnDate: '2026-12-08', adults: 3, cabinClass: 'business' }),
    '/api/flights?origin=TLV&destination=LHR&departure_date=2026-12-01&adults=3&cabin_class=business&return_date=2026-12-08')
  })
})

describe('searchFlights', () => {
  it('reads a real DEMO answer and keeps DEMO on every offer', async () => {
    const result = await searchFlights({ origin: 'TLV', destination: 'LHR', departureDate: '2026-12-01' },
      { fetchImpl: fakeFetch(200, DEMO).impl })
    assert.equal(result.dataMode, 'DEMO')
    assert.match(result.notices[0], /^DEMO data/)
    assert.equal(result.offers.length, 4)
    for (const o of result.offers) {
      assert.equal(o.dataMode, 'DEMO')
      assert.equal(o.passengers, 2)
      assert.equal(o.slices.length, 2) // round trip
      assert.equal(o.timeBasis, 'utc')
    }
  })

  it('finds the cheapest returned offer', async () => {
    const body = answer([offer('a', '500.00'), offer('b', '99.99'), offer('c', '250.50')])
    const result = await searchFlights({}, { fetchImpl: fakeFetch(200, body).impl })
    assert.deepEqual(sortOffers(result.offers).map((o) => o.id), ['b', 'c', 'a'])
    assert.equal(cheapestByCurrency(result.offers).USD.id, 'b')
    assert.deepEqual(sortOffers(result.offers, 'price-desc').map((o) => o.id), ['a', 'c', 'b'])
  })

  it('never compares prices in different currencies', async () => {
    const body = answer([offer('usd-high', '400.00'), offer('eur-low', '100.00', 'EUR'), offer('usd-low', '300.00')])
    const result = await searchFlights({}, { fetchImpl: fakeFetch(200, body).impl })
    assert.equal(result.comparable, false)
    assert.deepEqual(sortOffers(result.offers).map((o) => o.id), ['usd-low', 'usd-high', 'eur-low'])
    const cheapest = cheapestByCurrency(result.offers)
    assert.deepEqual(Object.keys(cheapest), ['USD', 'EUR'])
  })

  it('treats no available flights as an empty answer', async () => {
    const result = await searchFlights({}, { fetchImpl: fakeFetch(200, answer([])).impl })
    assert.deepEqual(result.offers, [])
  })

  it('shows invalid airport codes on the right field', async () => {
    const body = { error: { code: 'unknown_airport', message: 'No airport with the code QQQ was found.', retryable: false, field: 'destination' } }
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(422, body).impl }), (err) => (
      err instanceof FlightSearchError && err.field === 'destination' && err.code === 'unknown_airport' && !err.retryable))
  })

  it('reports provider errors and timeouts with a retry', async () => {
    const timeout = { error: { code: 'provider_timeout', message: 'The flight search service did not answer in time. Please try again.', retryable: true } }
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(504, timeout).impl }),
      (err) => err.code === 'provider_timeout' && err.retryable)
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(502, null, { json: false }).impl }),
      (err) => /Flight search failed \(502\)/.test(err.message) && err.retryable)
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(404, { detail: 'Not Found' }).impl }),
      (err) => err.code === 'not_available')
    const offline = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(searchFlights({}, { fetchImpl: offline }), (err) => err.code === 'network')
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(200, { offers: [] }).impl }),
      (err) => err.code === 'bad_response') // no data_mode: never shown as if it were real
  })
})

describe('offers as the traveller sees them', () => {
  it('drops offers without a usable price or data mode, never fills them in', () => {
    assert.equal(sanitizeOffer(offer('x', null)), null)
    assert.equal(sanitizeOffer(offer('x', '0')), null)
    assert.equal(sanitizeOffer(offer('x', '10.00', 'usd')), null)
    assert.equal(sanitizeOffer(offer('x', '10.00', 'USD', { data_mode: 'REAL' })), null)
    assert.equal(sanitizeOffer(offer('x', '10.00', 'USD', { slices: [] })), null)
    assert.equal(sanitizeFlightAnswer(answer([offer('ok', '1.00'), offer('bad', '-1')])).offers.length, 1)
  })

  it('says when baggage is not known', () => {
    assert.equal(baggageLabel({ checked: null, carryOn: null }), 'Baggage not stated: check with the airline')
    assert.equal(baggageLabel({ checked: 1, carryOn: 1 }), '1 checked bag, 1 carry-on bag per passenger')
    assert.equal(baggageLabel({ checked: 0, carryOn: null }), 'no checked bag per passenger (other allowance not stated)')
    assert.deepEqual(sanitizeOffer(offer('x', '1.00', 'USD', { baggage: {} })).baggage, { checked: null, carryOn: null })
  })

  it('formats price, duration, stops and overnight arrival', () => {
    assert.equal(formatPrice('1070.00', 'USD'), '$1,070.00')
    assert.equal(formatPrice('350', 'EUR'), '€350.00')
    assert.equal(formatDuration(310), '5h 10m')
    assert.equal(formatDuration(45), '45m')
    assert.equal(formatDuration(null), 'Duration not given')
    assert.equal(stopsLabel({ stops: 0, connections: [] }), 'Direct')
    assert.equal(stopsLabel({ stops: 1, connections: ['ATH'] }), '1 stop via ATH')
    assert.equal(dayShift('2026-12-08T19:45', '2026-12-09T00:55'), '+1')
    assert.equal(dayShift('2026-12-08T08:00', '2026-12-08T11:00'), '')
  })
})

describe('production: no real prices, no made-up ones', () => {
  it('reads the server status, and ignores a server that does not have it', async () => {
    const off = { environment: 'production', available: false, data_mode: null, provider: null, notice: 'No approved live flight provider is configured.' }
    assert.deepEqual(await fetchFlightStatus({ fetchImpl: fakeFetch(200, off).impl }),
      { available: false, environment: 'production', dataMode: null, notice: 'No approved live flight provider is configured.' })
    const demo = { environment: 'development', available: true, data_mode: 'DEMO' }
    assert.equal((await fetchFlightStatus({ fetchImpl: fakeFetch(200, demo).impl })).dataMode, 'DEMO')
    assert.equal(await fetchFlightStatus({ fetchImpl: fakeFetch(404, { detail: 'Not Found' }).impl }), null)
    assert.equal(await fetchFlightStatus({ fetchImpl: fakeFetch(200, { available: 'yes' }).impl }), null)
    const offline = async () => { throw new TypeError('Failed to fetch') }
    assert.equal(await fetchFlightStatus({ fetchImpl: offline }), null)
  })

  it('recognizes the unavailable answer, which is not retried', async () => {
    const body = { error: { code: 'flights_unavailable', message: 'Real-time flight prices are not available on this service right now.', retryable: false } }
    await assert.rejects(searchFlights({}, { fetchImpl: fakeFetch(503, body).impl }),
      (err) => isFlightsUnavailable(err) && err.retryable === false)
    assert.equal(isFlightsUnavailable(new FlightSearchError('x', { code: 'provider_timeout' })), false)
  })
})

describe('works with AirportSearch', () => {
  it('takes the airport AirportSearch hands over and sends its IATA code', () => {
    const tlv = sanitizeAirport({ id: 'ourairports:4411', name: 'Ben Gurion International Airport', city: 'Tel Aviv', country: 'Israel', iata: 'TLV', icao: 'LLBG' })
    const lhr = sanitizeAirport({ id: 'ourairports:2434', name: 'London Heathrow Airport', city: 'London', country: 'United Kingdom', iata: 'LHR', icao: 'EGLL' })
    const noIata = sanitizeAirport({ id: 'ourairports:30599', name: 'King Feisal Air Base', iata: null, icao: 'OJKF' })
    assert.deepEqual(validateFlightForm({ ...FORM, origin: tlv, destination: lhr }, '2026-11-02'), {})
    assert.match(validateFlightForm({ ...FORM, origin: noIata, destination: lhr }, '2026-11-02').origin, /no IATA code/)
    assert.match(flightSearchUrl({ origin: tlv.iata, destination: lhr.iata, departureDate: '2026-12-01' }), /origin=TLV&destination=LHR/)
  })
})

describe('informational only', () => {
  it('has no booking, order or payment code', () => {
    const dir = new URL('./', import.meta.url)
    const source = readdirSync(dir).filter((f) => /\.(js|jsx)$/.test(f) && !f.endsWith('.test.js'))
      .map((f) => readFileSync(new URL(f, dir), 'utf8')).join('\n')
    assert.doesNotMatch(source, /method:\s*['"](POST|PUT|PATCH|DELETE)/i)
    assert.doesNotMatch(source, /\/orders|\/payments|payment_intent|>\s*Book\b|Buy now/i)
  })
})

describe('results always match the search on screen', () => {
  const TLV = { iata: 'TLV' }
  const LHR = { iata: 'LHR' }
  const form = { origin: TLV, destination: LHR, departureDate: '2026-12-01', returnDate: '2026-12-08', roundTrip: true,
    adults: 2, cabinClass: 'economy' }

  it('changing any search input makes the shown offers (or error) stale', () => {
    const searched = searchKey(form)
    assert.equal(resultState('ready', searched, searchKey({ ...form })), 'ready')
    for (const change of [{ origin: { iata: 'AMM' } }, { destination: { iata: 'CDG' } }, { departureDate: '2026-12-02' },
      { returnDate: '2026-12-09' }, { roundTrip: false }, { adults: 3 }, { cabinClass: 'business' }, { origin: null }]) {
      assert.equal(resultState('ready', searched, searchKey({ ...form, ...change })), 'stale', JSON.stringify(change))
      assert.equal(resultState('error', searched, searchKey({ ...form, ...change })), 'stale', JSON.stringify(change))
    }
    // Loading, idle and the same search again are not stale; a one-way search ignores the hidden return date.
    assert.equal(resultState('loading', searched, searchKey({ ...form, adults: 3 })), 'loading')
    assert.equal(resultState('idle', null, searchKey(form)), 'idle')
    const oneWay = searchKey({ ...form, roundTrip: false })
    assert.equal(resultState('ready', oneWay, searchKey({ ...form, roundTrip: false, returnDate: '2026-12-20' })), 'ready')
  })

  it('an older search that answers late cannot replace a newer one', async () => {
    const searches = latestOnly()
    const shown = []
    const later = (value, ms) => new Promise((resolve) => setTimeout(() => resolve(value), ms))
    const run = async (value, ms) => {
      const ticket = searches.start()
      const answer = await later(value, ms)
      if (searches.isCurrent(ticket)) shown.push(answer)
    }
    await Promise.all([run('TLV-LHR (old, slow)', 30), run('AMM-LHR (new, fast)', 5)])
    assert.deepEqual(shown, ['AMM-LHR (new, fast)'])
  })

  it('keeps the data mode label of each answer (DEMO, TEST, LIVE)', () => {
    assert.equal(sanitizeFlightAnswer(DEMO).dataMode, 'DEMO')
    for (const mode of ['TEST', 'LIVE']) {
      assert.equal(sanitizeFlightAnswer({ ...DEMO, data_mode: mode, offers: [] }).dataMode, mode)
    }
  })
})

describe('starting values from the trip', () => {
  it('fills the form from the trip without choosing an airport', () => {
    const start = initialFlightForm({ departureHint: ' London ', departureCountry: 'gb', arrivalHint: 'Amman',
      departureDate: '2026-12-01', returnDate: '2026-12-08', adults: 2 })
    assert.deepEqual(start, { departureHint: 'London', departureCountry: 'GB', arrivalHint: 'Amman',
      departureDate: '2026-12-01', returnDate: '2026-12-08', roundTrip: true, adults: 2, adultsCapped: false })
    // only text for the airport boxes: the search form still has no airport until the traveller picks one
    assert.deepEqual(Object.keys(validateFlightForm({ origin: null, destination: null, departureDate: start.departureDate,
      returnDate: start.returnDate, roundTrip: true, adults: start.adults }, '2026-11-04')), ['origin', 'destination'])
  })

  it('starts empty, as before, without a trip', () => {
    assert.deepEqual(initialFlightForm(), { departureHint: '', departureCountry: '', arrivalHint: '', departureDate: '',
      returnDate: '', roundTrip: true, adults: 1, adultsCapped: false })
  })

  it('leaves unusable values empty instead of guessing', () => {
    const start = initialFlightForm({ departureCountry: 'GBR', departureDate: '01/12/2026', returnDate: '2026-12-08',
      adults: 'two', arrivalHint: 42 })
    assert.equal(start.departureCountry, '')
    assert.equal(start.departureDate, '')
    assert.equal(start.adults, 1)
    assert.equal(start.arrivalHint, '')
    assert.equal(initialFlightForm({ departureDate: '2026-12-08', returnDate: '2026-12-01' }).returnDate, '') // before departure
    assert.equal(initialFlightForm({ arrivalHint: 'x'.repeat(150) }).arrivalHint.length, 100)
  })

  it('a trip with only a start date is searched one way; a large party is capped and says so', () => {
    assert.equal(initialFlightForm({ departureDate: '2026-12-01' }).roundTrip, false)
    assert.deepEqual(initialFlightForm({ adults: 12 }), { ...initialFlightForm(), adults: 9, adultsCapped: true })
  })

  it('reads the starting values once, and never selects an airport from a hint', () => {
    const source = readFileSync(new URL('./FlightSearch.jsx', import.meta.url), 'utf8')
    assert.match(source, /const \[start\] = useState\(\(\) => initialFlightForm\(initial\)\)/)
    assert.match(source, /useState\(null\)[^\n]*\n\s*const \[destination, setDestination\] = useState\(null\)/)
    assert.match(source, /defaultValue=\{start\.arrivalHint\}/)
    assert.doesNotMatch(source, /setOrigin\(\s*\{|setDestination\(\s*\{/) // only AirportSearch's onSelect sets them
  })
})
