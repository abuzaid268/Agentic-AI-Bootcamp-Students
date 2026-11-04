import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { AirportSearchError, fetchNearbyAirports } from './airportsApi.js'
import {
  cleanNearbyPlace, distanceLabel, locationLabel, nearbyNotes, nearbyPlaceKey, sanitizeNearby,
} from './airportState.js'

// Real answers from GET /api/airports/near (the bundled OurAirports data, no network), saved by the backend's own
// code for these places: see tests/test_airports_near.py.
const fixture = (name) => JSON.parse(readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url), 'utf8'))
const JERUSALEM = fixture('near_jerusalem')
const PARIS_TX = fixture('near_paris_texas')
const PARIS_FR = fixture('near_paris_france')
const TBILISI = fixture('near_tbilisi')

const place = (over = {}) => ({
  name: 'Jerusalem', region: 'Jerusalem', country: 'Israel', countryCode: 'IL', latitude: 31.76904, longitude: 35.21633,
  label: 'Jerusalem, Jerusalem, Israel', ...over,
})
const codes = (answer) => answer.airports.map((a) => a.iata)
const ok = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })

describe('the place the nearby airports are asked about', () => {
  it('needs a name, real coordinates and a country code, and normalises the code', () => {
    assert.deepEqual(cleanNearbyPlace(place({ countryCode: 'il' })), {
      name: 'Jerusalem', countryCode: 'IL', latitude: 31.76904, longitude: 35.21633, region: 'Jerusalem', country: 'Israel',
      label: 'Jerusalem, Jerusalem, Israel',
    })
  })

  it('refuses anything it would have to guess', () => {
    for (const bad of [null, undefined, 'Jerusalem', 7, [], {}, place({ name: '' }), place({ countryCode: null }),
      place({ countryCode: 'ISR' }), place({ latitude: null }), place({ latitude: 91 }), place({ longitude: -181 }),
      place({ longitude: Number.NaN }), place({ latitude: '31.7' })]) {
      assert.equal(cleanNearbyPlace(bad), null, JSON.stringify(bad))
    }
  })

  it('is the same place when the coordinates and country are, whatever the name', () => {
    const a = cleanNearbyPlace(place())
    assert.equal(nearbyPlaceKey(a), nearbyPlaceKey(cleanNearbyPlace(place({ name: 'Yerushalayim' }))))
    assert.notEqual(nearbyPlaceKey(a), nearbyPlaceKey(cleanNearbyPlace(place({ countryCode: 'JO' }))))
    assert.equal(nearbyPlaceKey(null), '')
  })
})

describe('Jerusalem: a city with no airport of its own', () => {
  const answer = sanitizeNearby(JERUSALEM)

  it('lists the nearest airports, nearest first, with their distance', () => {
    assert.deepEqual(codes(answer), ['TLV', 'AMM', 'ADJ', 'HFA'])
    const km = answer.airports.map((a) => a.distanceKm)
    assert.deepEqual(km, [...km].sort((a, b) => a - b))
    assert.equal(distanceLabel(answer.airports[0].distanceKm), '41 km')
  })

  it('marks the airports in Jordan as outside Israel, and says so', () => {
    const by = Object.fromEntries(answer.airports.map((a) => [a.iata, a]))
    assert.equal(by.TLV.inCountry, true)
    assert.equal(by.AMM.inCountry, false)
    assert.equal(by.ADJ.inCountry, false)
    assert.equal(locationLabel(by.TLV, answer.country), 'In Israel')
    assert.equal(locationLabel(by.AMM, answer.country), 'In Jordan, outside Israel')
  })

  it('preselects nothing: two airports in Jordan are about as near as Tel Aviv', () => {
    assert.equal(answer.suggested, null)
  })

  it('explains the border and does not claim any route', () => {
    const notes = nearbyNotes({ place: cleanNearbyPlace(place()), ...answer })
    assert.ok(notes.some((n) => /outside Israel/.test(n) && /entry rules/.test(n)), notes.join(' | '))
    assert.ok(!notes.some((n) => /flight|route|direct|serve/i.test(n)), notes.join(' | '))
    assert.match(answer.note, /not always the best one for your route/)
  })
})

describe('Paris in Texas and Paris in France never share an airport', () => {
  const texas = sanitizeNearby(PARIS_TX)
  const france = sanitizeNearby(PARIS_FR)

  it('Texas lists only American airports, far away, and none of the French ones', () => {
    assert.deepEqual(codes(texas), ['TYR', 'TXK'])
    assert.ok(texas.airports.every((a) => a.countryCode === 'US' && a.inCountry === true && a.distanceKm > 100))
    assert.ok(!codes(texas).some((c) => ['CDG', 'ORY', 'LBG', 'BVA'].includes(c)))
  })

  it('France lists only French airports, and none of the Texan ones', () => {
    assert.deepEqual(codes(france), ['ORY', 'CDG', 'BVA', 'XCR'])
    assert.ok(france.airports.every((a) => a.countryCode === 'FR'))
    assert.ok(!codes(france).some((c) => ['TYR', 'TXK', 'PRX', 'DFW'].includes(c)))
  })

  it('Texas says the city has no airport of its own, with the real distance, and nothing is preselected', () => {
    const notes = nearbyNotes({ place: cleanNearbyPlace(place({ name: 'Paris', region: 'Texas', country: 'United States',
      countryCode: 'US' })), ...texas })
    assert.match(notes[0], /Paris, Texas has no airport of its own nearby/)
    assert.match(notes[0], /146 km/)
    assert.equal(texas.suggested, null)
    assert.equal(france.suggested, null)
  })
})

describe('preselecting only when exactly one airport clearly qualifies', () => {
  it('keeps the suggestion the server made for Tbilisi', () => {
    const answer = sanitizeNearby(TBILISI)
    assert.deepEqual(codes(answer), ['TBS'])
    assert.equal(answer.suggested.iata, 'TBS')
    assert.equal(answer.suggested.id, answer.airports[0].id)
  })

  it('never keeps a suggestion that is not in the list or is across a border', () => {
    assert.equal(sanitizeNearby({ ...TBILISI, suggested: 'ourairports:1' }).suggested, null)
    assert.equal(sanitizeNearby({ ...TBILISI, suggested: null }).suggested, null)
    assert.equal(sanitizeNearby({ ...TBILISI, suggested: 42 }).suggested, null)
    const amm = JERUSALEM.airports.find((a) => a.iata === 'AMM')
    assert.equal(sanitizeNearby({ ...JERUSALEM, suggested: amm.id }).suggested, null) // Jordan, not Israel
    const across = { ...TBILISI, airports: [{ ...TBILISI.airports[0], in_country: false }], suggested: TBILISI.suggested }
    assert.equal(sanitizeNearby(across).suggested, null)
    const unknown = { ...TBILISI, airports: [{ ...TBILISI.airports[0], in_country: null }], suggested: TBILISI.suggested }
    assert.equal(sanitizeNearby(unknown).suggested, null)
  })
})

describe('what is dropped, and what is said when there is nothing', () => {
  it('drops airports it cannot search as flights or place on the map', () => {
    const base = TBILISI.airports[0]
    const answer = sanitizeNearby({ ...TBILISI, suggested: null, airports: [
      { ...base, iata: null }, { ...base, id: 'ourairports:2', distance_km: null }, { ...base, id: 'ourairports:3', distance_km: -1 },
      { ...base, id: 'ourairports:4', distance_km: '5' }, { ...base, id: 'ourairports:5', name: '' }, null, 'TBS',
      { ...base, id: 'ourairports:6' }] })
    assert.deepEqual(answer.airports.map((a) => a.id), ['ourairports:6'])
  })

  it('says there is no airport, honestly, when there are none', () => {
    const notes = nearbyNotes({ place: cleanNearbyPlace(place({ name: 'Nowhere', region: null })), airports: [], country: { code: 'IL', name: 'Israel' }, maxKm: 150 })
    assert.deepEqual(notes, ['No airport with scheduled service was found within 150 km of Nowhere. Search for an airport by name or code.'])
  })

  it('says so when the only airports are in another country', () => {
    const other = sanitizeNearby({ ...JERUSALEM, airports: JERUSALEM.airports.filter((a) => a.country_code === 'JO') })
    const notes = nearbyNotes({ place: cleanNearbyPlace(place()), ...other })
    assert.match(notes[0], /There is no airport in Israel within 150 km of Jerusalem/)
    assert.match(notes[0], /in another country/)
  })

  it('rejects an answer that is not a list of airports', () => {
    for (const bad of [null, {}, { airports: 'TLV' }, 'x', 3]) assert.throws(() => sanitizeNearby(bad), /unexpected nearby airports answer/)
  })
})

describe('asking the server', () => {
  it('sends the coordinates and the country, never the name, and reads the answer', async () => {
    const seen = []
    const answer = await fetchNearbyAirports(place({ name: 'Anything at all' }), {
      fetchImpl: async (url, init) => { seen.push([url, init]); return ok(JERUSALEM) } })
    assert.equal(seen[0][0], '/api/airports/near?lat=31.76904&lon=35.21633&country=IL&limit=6')
    assert.ok(!seen[0][1].method || seen[0][1].method === 'GET')
    assert.deepEqual(codes(answer), ['TLV', 'AMM', 'ADJ', 'HFA'])
    assert.equal(answer.unavailable, false)
  })

  it('does not call the server for a place it cannot ask about', async () => {
    let called = 0
    await assert.rejects(fetchNearbyAirports(place({ countryCode: null }), { fetchImpl: async () => { called += 1 } }),
      (err) => err instanceof AirportSearchError && err.code === 'no_place')
    assert.equal(called, 0)
  })

  it('treats a server without the route as unavailable, so typing still works', async () => {
    const answer = await fetchNearbyAirports(place(), { fetchImpl: async () => ok({}, 404) })
    assert.deepEqual(answer, { unavailable: true, airports: [], suggested: null, country: null, maxKm: null, note: null })
  })

  it('reports the server\'s own message and whether to retry', async () => {
    const bad = { error: { code: 'invalid_coordinates', message: 'The latitude must be a number.', retryable: false } }
    await assert.rejects(fetchNearbyAirports(place(), { fetchImpl: async () => ok(bad, 422) }),
      (err) => err.code === 'invalid_coordinates' && err.message === 'The latitude must be a number.' && err.retryable === false)
    await assert.rejects(fetchNearbyAirports(place(), { fetchImpl: async () => ok({}, 503) }),
      (err) => err.retryable === true && err.status === 503)
  })

  it('reports a network failure as retryable, and rethrows an abort', async () => {
    await assert.rejects(fetchNearbyAirports(place(), { fetchImpl: async () => { throw new TypeError('failed') } }),
      (err) => err.code === 'network' && err.retryable === true)
    const controller = new AbortController()
    controller.abort()
    await assert.rejects(fetchNearbyAirports(place(), { signal: controller.signal,
      fetchImpl: async () => { throw Object.assign(new Error('x'), { name: 'AbortError' }) } }), (err) => err.name === 'AbortError')
  })

  it('refuses an answer that is not airports', async () => {
    await assert.rejects(fetchNearbyAirports(place(), { fetchImpl: async () => ok({ airports: 'none' }) }),
      (err) => err.code === 'bad_response')
  })
})

describe('the lists and boxes behave as promised', () => {
  const near = readFileSync(new URL('./NearbyAirports.jsx', import.meta.url), 'utf8')
  const search = readFileSync(new URL('../flights/FlightSearch.jsx', import.meta.url), 'utf8')

  it('the list says it is ranked by distance only and that the nearest is not always the best', () => {
    assert.match(near, /Ranked by straight-line distance only/)
    assert.match(near, /not always the best one for your route/)
    assert.match(near, /Other country/)
  })

  it('choosing is a button press on a suggestion; the only automatic choice is the sole qualifying airport', () => {
    assert.match(near, /onClick=\{\(\) => onChoose\?\.\(airport\)\}/)
    assert.equal((near.match(/onSuggested\?\.\(/g) || []).length, 1) // called in one place only
    assert.match(near, /announced\.current !== key/) // once per place
    assert.match(near, /answer\.suggested/) // only what the server proved
  })

  it('the preselection never overrides the traveller, and every box stays editable', () => {
    assert.match(search, /if \(touched\.current\[side\]\) return\s*\n\s*putAirport\(side, airport\)/)
    assert.match(search, /onTextChange=\{\(\) => \{ touched\.current\.origin = true \}\}/)
    assert.match(search, /onTextChange=\{\(\) => \{ touched\.current\.destination = true \}\}/)
    assert.match(search, /initialAirport=\{originSeed\}/)
    assert.match(search, /initialAirport=\{destinationSeed\}/)
    // a new country empties the box: the seeded airport does not survive a filter it does not match
    assert.match(search, /setOriginSeed\(null\)/)
    assert.match(search, /setDestinationSeed\(null\)/)
  })

  it('a place in one country is searched among that country\'s airports, and both countries are pickable', () => {
    assert.match(search, /country=\{arrivalCountry\}/)
    assert.match(search, /country=\{departureCountry\}/)
    assert.match(search, /Arrival country \(optional\)/)
    assert.match(search, /Departure country \(optional\)/)
  })

  it('lists only read-only requests', () => {
    const api = readFileSync(new URL('./airportsApi.js', import.meta.url), 'utf8')
    assert.doesNotMatch(api + near, /method:\s*['"](POST|PUT|PATCH|DELETE)/i)
  })
})
