import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { travelInfoPlan } from '../features/trip-travel/tripTravelState.js'
import { STORAGE_KEY, getSavedTrip, saveTrip } from './savedTrips.js'
import { buildTripForm, createTrip } from './tripApi.js'
import { validateTripForm } from './tripForm.js'

// FROM -> TO from the home page to the trip page: the chosen places travel in the page state and the local saved
// copy, never in the /api/chat request.

function memoryStorage(initial = {}) {
  const data = { ...initial }
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v) }, data }
}

// Places as DestinationSearch's onSelect hands them over (sanitizeDestination of the backend's real answers).
const AMMAN = { id: 'geonames:250441', name: 'Amman', region: 'Amman Governorate', country: 'Jordan', countryCode: 'JO',
  latitude: 31.95522, longitude: 35.94503, population: 1275857, timezone: 'Asia/Amman', ambiguousName: false,
  label: 'Amman, Amman Governorate, Jordan' }
const LONDON = { id: 'geonames:2643743', name: 'London', region: 'England', country: 'United Kingdom', countryCode: 'GB',
  latitude: 51.50853, longitude: -0.12574, population: 8961989, timezone: 'Europe/London', ambiguousName: false,
  label: 'London, England, United Kingdom' }

const TRIP = { destination: 'Amman, Amman Governorate, Jordan', departureDate: '2026-12-01', returnDate: '2026-12-03',
  travellers: '2', budget: '900', interests: ['History & Culture'], customPreferences: '',
  destinationPlace: AMMAN, originPlace: LONDON }

const RESULT = {
  session_id: 'sess-amman', status: 'pending_approval', message: 'Ready.',
  itinerary: { destination: 'Amman', currency: 'USD', travellers: 2, budget_total: 900, estimated_total: 20,
    days: [{ date: '2026-12-01', activities: [{ name: 'Citadel', estimated_cost: 20 }] }] },
}

describe('the /api/chat contract is unchanged', () => {
  it('the trip form sends the same fields as before, without the places', () => {
    const form = buildTripForm(TRIP)
    assert.deepEqual(Object.keys(form).sort(),
      ['budget', 'currency', 'destination', 'end_date', 'interests', 'preferences', 'start_date', 'travellers'])
    assert.equal(JSON.stringify(form).includes('London'), false)
  })

  it('the request body carries no place: not in the form, not in the message', async () => {
    let sent = null
    const realFetch = globalThis.fetch
    globalThis.fetch = async (url, init) => {
      sent = { url, body: JSON.parse(init.body) }
      return { ok: false, status: 503, json: async () => ({ detail: 'test stops here' }) }
    }
    try {
      await assert.rejects(createTrip(TRIP, 'sess-1', 1000))
    } finally {
      globalThis.fetch = realFetch
    }
    assert.equal(sent.url, '/api/chat')
    assert.deepEqual(Object.keys(sent.body).sort(), ['message', 'session_id', 'trip'])
    const text = JSON.stringify(sent.body)
    for (const leak of ['London', 'originPlace', 'destinationPlace', 'latitude', '51.50853']) {
      assert.equal(text.includes(leak), false, leak)
    }
  })

  it('validation is the same with or without places', () => {
    const now = new Date('2026-11-04T10:00:00Z')
    const { destinationPlace, originPlace, ...plain } = TRIP
    assert.ok(destinationPlace && originPlace)
    assert.deepEqual(validateTripForm(TRIP, now), validateTripForm(plain, now))
  })
})

describe('saved trips keep the places', () => {
  it('a saved trip reopens with its FROM and TO, as plain values', () => {
    const storage = memoryStorage()
    saveTrip(RESULT, { ...TRIP, sessionId: 'sess-amman' }, storage)
    const { request } = getSavedTrip('sess-amman', storage)
    assert.deepEqual(request.destinationPlace, { name: 'Amman', country: 'Jordan', countryCode: 'JO',
      latitude: 31.95522, longitude: 35.94503, label: 'Amman, Amman Governorate, Jordan' })
    assert.equal(request.originPlace.label, 'London, England, United Kingdom')
    // My Trips opens it with { ...request }: the trip page then has the forecast and the flight hints again
    const plan = travelInfoPlan({ destination: request.destinationPlace, origin: request.originPlace,
      startDate: request.departureDate, endDate: request.returnDate, travellers: request.travellers, today: '2026-11-25' })
    assert.equal(plan.weatherStatus, 'full')
    assert.equal(plan.flights.departureCountry, 'GB')
  })

  it('a trip typed without choosing a suggestion saves null places', () => {
    const entry = saveTrip(RESULT, { ...TRIP, destinationPlace: null, originPlace: undefined }, memoryStorage())
    assert.equal(entry.request.destinationPlace, null)
    assert.equal(entry.request.originPlace, null)
  })

  it('an older saved trip, without the places, still opens and shows the typed destination', () => {
    const old = [{ id: 'sess-old', savedAt: '2026-10-01T10:00:00Z', aiResult: RESULT,
      request: { destination: 'Paris, France', departureDate: '2026-12-01', returnDate: '2026-12-03', travellers: 2,
        budget: 900, interests: [], customPreferences: '' } }]
    const storage = memoryStorage({ [STORAGE_KEY]: JSON.stringify(old) })
    const { request } = getSavedTrip('sess-old', storage)
    assert.equal(request.destination, 'Paris, France')
    assert.equal(request.destinationPlace, undefined)
    const plan = travelInfoPlan({ destination: request.destinationPlace || null, destinationText: request.destination,
      origin: request.originPlace || null, startDate: request.departureDate, endDate: request.returnDate,
      travellers: request.travellers, today: '2026-11-25' })
    assert.equal(plan.weather, null) // never geocoded from the typed name
    assert.equal(plan.weatherStatus, 'no_coordinates')
    assert.equal(plan.flights.arrivalHint, 'Paris')
  })

  it('a hand-edited place is cleaned, not trusted', () => {
    const entry = saveTrip(RESULT, { ...TRIP, destinationPlace: { name: 'X', latitude: 'north', token: 'secret' } },
      memoryStorage())
    assert.deepEqual(entry.request.destinationPlace, { name: 'X', country: null, countryCode: null, latitude: null,
      longitude: null, label: 'X' })
  })
})

describe('the pages are wired', () => {
  const app = readFileSync(new URL('../App.jsx', import.meta.url), 'utf8')
  const dashboard = readFileSync(new URL('../pages/TripDashboard.jsx', import.meta.url), 'utf8')

  it('the home page has FROM (optional) and TO, each keeping the chosen place', () => {
    assert.match(app, /label="From \(optional, for flights\)"[\s\S]*?onSelect=\{setOriginPlace\}/)
    assert.match(app, /label="To"[\s\S]*?onTextChange=\{setDestination\}[\s\S]*?onSelect=\{setDestinationPlace\}[\s\S]*?required/)
    assert.match(app, /customPreferences,\s*\/\/[^\n]*\n\s*destinationPlace,\s*originPlace,\s*\}/)
    assert.doesNotMatch(app, /geolocation/) // no location permission is asked for
  })

  it('the trip page shows TripTravelInfo with the trip\'s places, and the sources', () => {
    assert.match(dashboard, /import \{ TripTravelInfo \} from '\.\.\/features\/trip-travel'/)
    assert.match(dashboard, /\{isReal && !sampleEntry && \(\s*<div className="mt-7">\s*<TripTravelInfo/)
    assert.match(dashboard, /destination=\{trip\.destinationPlace \|\| null\}/)
    assert.match(dashboard, /origin=\{trip\.originPlace \|\| null\}/)
    assert.match(dashboard, /const sources = isReal \? sourceLinks\(aiResult\.citations\) : \[\]/)
  })

  it('a revision keeps the places: the new page state spreads the old one', () => {
    assert.match(dashboard, /const request = \{ \.\.\.trip, aiResult: result,/)
  })
})
