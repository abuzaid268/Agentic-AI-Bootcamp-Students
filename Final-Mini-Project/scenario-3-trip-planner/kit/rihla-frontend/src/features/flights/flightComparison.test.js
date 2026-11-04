import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import {
  DATA_MODES, cheapestByCurrency, compareOffers, fastestByCurrency, initialFlightForm, journeyMinutes,
  sanitizeFlightAnswer, searchSummary, sortOffers, tripTypeLabel,
} from './flightState.js'

// A real answer from the backend's DEMO provider (app/flights): TLV -> LHR round trip, 2 adults. Its four offers:
//   -2 Example Airlines    1070.00 USD  485 + 470 = 955 min (1 stop each way)
//   -3 Placeholder Jet     1136.00 USD  510 + 415 = 925 min (1 stop each way)
//   -1 Sample Skyways      1172.00 USD  310 + 310 = 620 min (direct)
//   -0 Rihla Demo Air      1416.00 USD  310 + 310 = 620 min (direct)
const DEMO = sanitizeFlightAnswer(JSON.parse(readFileSync(new URL('./fixtures/demo_tlv_lhr_round_trip.json', import.meta.url), 'utf8')))
const idOf = (offer) => offer.id.slice(-2)

// A minimal offer for the cases the fixture does not have.
const offer = (id, amount, minutes, { currency = 'USD', slices = 1 } = {}) => ({
  id, airline: 'A', airlineCode: null, totalAmount: amount, currency, passengers: 1, cabinClass: 'economy',
  slices: Array.from({ length: slices }, () => ({
    origin: 'AAA', destination: 'BBB', departingAt: '2026-12-01T08:00', arrivingAt: '2026-12-01T12:00',
    durationMinutes: Array.isArray(minutes) ? minutes.shift() : minutes, stops: 0, connections: [], flightNumbers: [],
  })),
  baggage: { checked: null, carryOn: null }, expiresAt: null, timeBasis: 'local', dataMode: 'DEMO', provider: 'x',
})

describe('the fastest offer', () => {
  it('is the shortest whole journey, the cheaper one when two tie', () => {
    const fastest = fastestByCurrency(DEMO.offers)
    assert.equal(idOf(fastest.USD), '-1') // 620 min, tied with -0 at 1416.00: the cheaper wins
    assert.equal(journeyMinutes(fastest.USD), 620)
    assert.equal(idOf(cheapestByCurrency(DEMO.offers).USD), '-2') // 1070.00
  })

  it('adds both directions of a round trip', () => {
    assert.deepEqual(DEMO.offers.map(journeyMinutes), [955, 925, 620, 620])
    assert.equal(journeyMinutes(offer('x', '10.00', 90, { slices: 1 })), 90)
  })

  it('never calls an offer fastest when a part of its journey has no duration', () => {
    assert.equal(journeyMinutes(offer('x', '10.00', null)), null)
    const unknown = offer('unknown', '5.00', null)
    const known = offer('known', '99.00', 300)
    assert.equal(fastestByCurrency([unknown, known]).USD.id, 'known')
    assert.deepEqual(fastestByCurrency([unknown]), {}) // none known: nothing is labelled
    assert.deepEqual(compareOffers([unknown]), [])
    const half = offer('half', '5.00', [100, null], { slices: 2 })
    assert.equal(journeyMinutes(half), null)
  })

  it('is chosen within each currency, never across currencies', () => {
    const fastest = fastestByCurrency([offer('usd-slow', '100.00', 600), offer('eur-fast', '90.00', 120, { currency: 'EUR' }),
      offer('usd-fast', '300.00', 200)])
    assert.deepEqual(Object.fromEntries(Object.entries(fastest).map(([c, o]) => [c, o.id])),
      { USD: 'usd-fast', EUR: 'eur-fast' })
  })
})

describe('cheapest versus fastest', () => {
  it('compares the real DEMO answer', () => {
    const [entry, ...others] = compareOffers(DEMO.offers)
    assert.equal(others.length, 0)
    assert.equal(entry.currency, 'USD')
    assert.equal(idOf(entry.cheapest), '-2')
    assert.equal(idOf(entry.fastest), '-1')
    assert.equal(entry.same, false)
    assert.equal(entry.extra, '102.00') // 1172.00 - 1070.00
    assert.equal(entry.saved, 335) // 955 - 620 minutes
  })

  it('says so when the cheapest offer is also the fastest', () => {
    const [entry] = compareOffers([offer('a', '100.00', 300), offer('b', '150.00', 400)])
    assert.equal(entry.same, true)
    assert.equal(entry.extra, null)
    assert.equal(entry.saved, null)
  })

  it('a faster offer at the same price costs nothing extra', () => {
    const [entry] = compareOffers([offer('slow', '100.00', 500), offer('quick', '100.00', 300)])
    assert.equal(entry.same, false)
    assert.equal(entry.extra, '0.00')
    assert.equal(entry.saved, 200)
  })

  it('keeps one comparison per currency and never mixes their prices', () => {
    const entries = compareOffers([offer('u1', '100.00', 500), offer('u2', '200.00', 300), offer('e1', '90.00', 400, { currency: 'EUR' })])
    assert.deepEqual(entries.map((e) => e.currency).sort(), ['EUR', 'USD'])
    const usd = entries.find((e) => e.currency === 'USD')
    assert.equal(usd.extra, '100.00')
    assert.equal(entries.find((e) => e.currency === 'EUR').same, true)
  })

  it('does not say how much time is saved when the cheapest offer has no known duration', () => {
    const [entry] = compareOffers([offer('cheap', '50.00', null), offer('quick', '80.00', 200)])
    assert.equal(entry.cheapest.id, 'cheap')
    assert.equal(entry.fastest.id, 'quick')
    assert.equal(entry.saved, null)
    assert.equal(entry.extra, '30.00')
  })
})

describe('sorting by price and duration', () => {
  const ids = (order) => sortOffers(DEMO.offers, order).map(idOf)

  it('lowest and highest price', () => {
    assert.deepEqual(ids('price-asc'), ['-2', '-3', '-1', '-0'])
    assert.deepEqual(ids('price-desc'), ['-0', '-1', '-3', '-2'])
  })

  it('shortest travel time, the cheaper first on a tie', () => {
    assert.deepEqual(ids('duration'), ['-1', '-0', '-3', '-2'])
  })

  it('puts offers with an unknown duration last and sorts each currency on its own', () => {
    const sorted = sortOffers([offer('unknown', '10.00', null), offer('long', '20.00', 900), offer('short', '30.00', 100),
      offer('eur', '5.00', 50, { currency: 'EUR' })], 'duration').map((o) => o.id)
    assert.deepEqual(sorted, ['short', 'long', 'unknown', 'eur'])
  })
})

describe('one way or round trip', () => {
  it('is named on every offer from its own journey', () => {
    assert.deepEqual(DEMO.offers.map(tripTypeLabel), ['Round trip', 'Round trip', 'Round trip', 'Round trip'])
    assert.equal(tripTypeLabel(offer('x', '1.00', 60, { slices: 1 })), 'One way')
  })

  it('is kept from the server\'s own description of the search', () => {
    assert.deepEqual(DEMO.query, { origin: 'TLV', destination: 'LHR', tripType: 'round_trip', departureDate: '2026-12-01',
      returnDate: '2026-12-08', adults: 2 })
    assert.equal(searchSummary(DEMO.query), 'Round trip · TLV ⇄ LHR · 2 adults · 2026-12-01 to 2026-12-08')
    assert.equal(searchSummary({ origin: 'AMM', destination: 'IST', tripType: 'one_way', departureDate: '2026-12-01', returnDate: null, adults: 1 }),
      'One way · AMM → IST · 1 adult · 2026-12-01')
  })

  it('shows nothing rather than guessing when the answer does not say', () => {
    assert.equal(searchSummary(null), '')
    assert.equal(searchSummary({ origin: 'AMM', destination: 'IST', tripType: null }), '')
    const q = sanitizeFlightAnswer({ data_mode: 'DEMO', offers: [], query: { origin: 'amman', trip_type: 'weekly', adults: '2' } }).query
    assert.deepEqual(q, { origin: null, destination: null, tripType: null, departureDate: null, returnDate: null, adults: null })
  })
})

describe('simulated prices are labelled where the price is', () => {
  it('every data mode has a price line that says it is not bookable', () => {
    for (const [mode, info] of Object.entries(DATA_MODES)) assert.match(info.price, /not bookable/i, mode)
  })

  it('DEMO and TEST say the price is not a real fare, and DEMO says simulated', () => {
    assert.match(DATA_MODES.DEMO.price, /^Simulated price/)
    assert.match(DATA_MODES.DEMO.price, /not a real fare/)
    assert.match(DATA_MODES.TEST.price, /not a real fare/)
    assert.doesNotMatch(DATA_MODES.LIVE.price, /simulated|test/i)
  })

  it('the offer card prints that line with the price, and names the fastest and the trip type', () => {
    const card = readFileSync(new URL('./FlightOfferCard.jsx', import.meta.url), 'utf8')
    assert.match(card, /\{mode\.price\}/)
    assert.match(card, /MODE_STYLES\[offer\.dataMode\]/)
    assert.match(card, /Fastest in \{offer\.currency\}/)
    assert.match(card, /tripTypeLabel\(offer\)/)
    assert.match(card, /both directions/)
    assert.match(card, /outbound only/)
  })

  it('the results say what is compared, and the comparison repeats that the data is simulated', () => {
    const search = readFileSync(new URL('./FlightSearch.jsx', import.meta.url), 'utf8')
    assert.match(search, /Cheapest vs fastest/)
    assert.match(search, /data: simulated, not bookable/)
    assert.match(search, /searchSummary\(answer\.query\)/)
    assert.match(search, /Round trip: one price for the outbound and the return flight together/)
    assert.match(search, /One way: the outbound flight only/)
  })
})

describe('the form starts from the chosen cities', () => {
  const AMMAN = { name: 'Amman', region: 'Amman Governorate', country: 'Jordan', countryCode: 'JO', latitude: 31.95522, longitude: 35.94503 }
  const PARIS_TX = { name: 'Paris', region: 'Texas', country: 'United States', countryCode: 'US', latitude: 33.66094, longitude: -95.55551 }

  it('takes each side\'s country from its place, so Paris in Texas is searched among American airports', () => {
    const start = initialFlightForm({ departurePlace: PARIS_TX, arrivalPlace: AMMAN, arrivalHint: 'Amman', departureHint: 'Paris' })
    assert.equal(start.departureCountry, 'US')
    assert.equal(start.arrivalCountry, 'JO')
    assert.equal(start.departurePlace.countryCode, 'US')
    assert.equal(start.arrivalPlace.name, 'Amman')
  })

  it('an explicit country wins, and an unusable one falls back to the place or to nothing', () => {
    assert.equal(initialFlightForm({ arrivalCountry: 'gb', arrivalPlace: AMMAN }).arrivalCountry, 'GB')
    assert.equal(initialFlightForm({ arrivalCountry: 'GBR', arrivalPlace: AMMAN }).arrivalCountry, 'JO')
    assert.equal(initialFlightForm({ arrivalCountry: 'GBR' }).arrivalCountry, '')
  })

  it('drops a place that cannot be asked about instead of guessing its coordinates or country', () => {
    for (const bad of [{ name: 'Amman', countryCode: 'JO' }, { ...AMMAN, countryCode: null }, { ...AMMAN, latitude: 95 },
      { ...AMMAN, longitude: Number.NaN }, { ...AMMAN, name: '  ' }, 'Amman', 42, [], null]) {
      const start = initialFlightForm({ arrivalPlace: bad })
      assert.equal(start.arrivalPlace, null, JSON.stringify(bad))
      assert.equal(start.arrivalCountry, '')
    }
  })
})
