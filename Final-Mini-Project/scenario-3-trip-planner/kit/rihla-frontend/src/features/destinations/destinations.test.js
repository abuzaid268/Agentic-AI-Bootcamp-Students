import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { DestinationSearchError, searchDestinations } from './destinationsApi.js'
import {
  MAX_DESTINATION_TEXT, areaSentence, destinationText, destinationValidity, initialHighlight, listOptions, moveHighlight,
  normalizeQuery, placeDetails, sanitizeAreas, sanitizeDestination, shouldSearch,
  statusMessage,
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

  it('searches from the first letter, never for numbers or symbols only, never past 80 characters', () => {
    assert.equal(shouldSearch(''), false)
    assert.equal(shouldSearch('P'), true) // one or two letters: the server's popular destinations list
    assert.equal(shouldSearch(' P '), true)
    assert.equal(shouldSearch('Pa'), true)
    assert.equal(shouldSearch('1'), false)
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

  it('says city search is unavailable (no licence decision in production) and does not offer a retry', async () => {
    const body = { error: { code: 'destinations_unavailable', message: 'City search is not available on this service right now. You can still type the destination yourself.', retryable: false } }
    await assert.rejects(searchDestinations('Pari', { fetchImpl: fakeFetch(503, body).impl }), (err) => (
      err.code === 'destinations_unavailable' && err.retryable === false && /type the destination yourself/.test(err.message)))
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

describe('the text a chosen city puts in the trip form', () => {
  it('is the full label when it fits', () => {
    assert.equal(destinationText(sanitizeDestination(PARIS_TX)), 'Paris, Texas, United States')
  })

  it('never exceeds the trip form\'s 100-character limit (tripForm.js), shortest form last', () => {
    const region = 'R'.repeat(95)
    const long = sanitizeDestination({ ...PARIS, region, label: `Paris, ${region}, France` })
    assert.ok(long.label.length > MAX_DESTINATION_TEXT)
    assert.equal(destinationText(long), 'Paris, France')
    const longName = 'N'.repeat(120)
    assert.equal(destinationText({ name: longName, country: 'France', label: `${longName}, France` }).length,
      MAX_DESTINATION_TEXT)
  })
})

describe('one or two letters: popular destinations', () => {
  const AMMAN = {
    id: 'geonames:250441', provider_id: 250441, name: 'Amman', region: 'Amman Governorate', country: 'Jordan',
    country_code: 'JO', latitude: 31.95522, longitude: 35.94503, population: 1275857, timezone: 'Asia/Amman',
    feature_code: 'PPLC', label: 'Amman, Amman Governorate, Jordan', ambiguous_name: false,
  }

  it('passes on whether the answer came from the popular list', async () => {
    const popular = await searchDestinations('A', { fetchImpl: fakeFetch(200, { query: 'A', results: [AMMAN], scope: 'popular' }).impl })
    assert.equal(popular.scope, 'popular')
    assert.equal(popular.results[0].label, 'Amman, Amman Governorate, Jordan')
    const worldwide = await searchDestinations('Pari', { fetchImpl: fakeFetch(200, ANSWER).impl }) // an older server: no scope
    assert.equal(worldwide.scope, 'worldwide')
  })

  it('says the list is popular places only, and how to search every city', () => {
    assert.equal(statusMessage({ status: 'ready', count: 3, searchable: true, scope: 'popular' }),
      '3 popular destinations. Keep typing to search every city.')
    assert.match(statusMessage({ status: 'ready', count: 0, searchable: true, scope: 'popular' }),
      /No popular destination starts with that\. Type 3 letters or more to search every city\./)
    assert.equal(statusMessage({ status: 'ready', count: 1, searchable: true, scope: 'worldwide' }), '1 city found.')
  })

  it('keeps the scope in the component and shows its message', () => {
    const source = readFileSync(new URL('./DestinationSearch.jsx', import.meta.url), 'utf8')
    assert.match(source, /setScope\(answer\.scope\)/)
    assert.match(source, /statusMessage\(\{[^}]*scope, areas \}\)/)
  })
})

describe('countries, regions and shared names need an explicit choice', () => {
  // The backend's answers (app/destinations, from recorded Open-Meteo answers): "Italy" names a country, "Georgia" a
  // country and a US state; Italy, Texas and Paris, Texas are towns that share a name with something better known.
  const city = (id, name, region, country, cc, lat, lon, extra = {}) => ({ id: `geonames:${id}`, provider_id: id, name,
    region, country, country_code: cc, latitude: lat, longitude: lon,
    label: [name, region, country].filter(Boolean).join(', '), ...extra })
  const ROME = city(3169070, 'Rome', 'Lazio', 'Italy', 'IT', 41.89193, 12.51133)
  const MILAN = city(3173435, 'Milan', 'Lombardy', 'Italy', 'IT', 45.46427, 9.18951)
  const TBILISI = city(611717, 'Tbilisi', null, 'Georgia', 'GE', 41.69411, 44.83368)
  const TEXAS_TOWN = city(4703811, 'Italy', 'Texas', 'United States', 'US', 32.18404, -96.88472, { ambiguous_name: true })
  const ITALY = { query: 'Italy', count: 1, results: [TEXAS_TOWN], ambiguous: true, scope: 'worldwide',
    areas: [{ kind: 'country', name: 'Italy', country_code: 'IT', country: 'Italy', suggestions: [ROME, MILAN] }] }
  const GEORGIA = [{ kind: 'country', name: 'Georgia', country_code: 'GE', country: 'Georgia', suggestions: [TBILISI] },
    { kind: 'region', name: 'Georgia', country_code: 'US', country: 'United States', suggestions: [] }]

  it('reads the areas and the cities suggested in them', async () => {
    const answer = await searchDestinations('Italy', { fetchImpl: fakeFetch(200, ITALY).impl })
    assert.deepEqual(answer.areas.map((a) => [a.kind, a.name, a.countryCode]), [['country', 'Italy', 'IT']])
    assert.deepEqual(answer.areas[0].suggestions.map((d) => d.label), ['Rome, Lazio, Italy', 'Milan, Lombardy, Italy'])
    assert.deepEqual((await searchDestinations('Pari', { fetchImpl: fakeFetch(200, ANSWER).impl })).areas, []) // older answer
  })

  it('says what the name is: a country, a state or region, or both', () => {
    const areas = sanitizeAreas(GEORGIA)
    assert.equal(areaSentence(areas), 'Georgia is a country, and a state or region in United States')
    assert.equal(areaSentence(sanitizeAreas(ITALY.areas)), 'Italy is a country')
    assert.equal(statusMessage({ status: 'ready', count: 3, searchable: true, areas }),
      'Georgia is a country, and a state or region in United States: choose a city, such as Tbilisi.')
  })

  it('lists the suggested cities first, then the namesake places', () => {
    const italy = sanitizeAreas(ITALY.areas)
    assert.deepEqual(listOptions([sanitizeDestination(TEXAS_TOWN)], italy).map((d) => d.label),
      ['Rome, Lazio, Italy', 'Milan, Lombardy, Italy', 'Italy, Texas, United States'])
    assert.deepEqual(listOptions([sanitizeDestination(ROME)], italy).map((d) => d.name), ['Rome', 'Milan'])
  })

  it('highlights nothing for an area or a shared name, so Enter never picks a place for the traveller', () => {
    assert.equal(initialHighlight({ count: 3, ambiguous: true, areas: sanitizeAreas(ITALY.areas) }), -1)
    assert.equal(initialHighlight({ count: 3, ambiguous: false, areas: sanitizeAreas(GEORGIA) }), -1)
    assert.equal(initialHighlight({ count: 3, ambiguous: true }), -1) // London: England or Ontario
    assert.equal(initialHighlight({ count: 3, ambiguous: false }), 0) // one clear best match
  })

  it('keeps the form from being sent with a country, a region or a shared name', () => {
    assert.equal(destinationValidity({ text: 'Italy', answered: 'Italy', areas: sanitizeAreas(ITALY.areas) }),
      'Italy is a country. Choose a city, for example Rome, from the list.')
    assert.match(destinationValidity({ text: 'georgia', answered: 'Georgia', areas: sanitizeAreas(GEORGIA) }),
      /^Georgia is a country, and a state or region in United States\./)
    assert.equal(destinationValidity({ text: 'London', answered: 'London', ambiguous: true }),
      'Several places are called London. Choose the one you mean from the list.')
  })

  it('lets the form go once a city is chosen, or when the name is one clear place', () => {
    const rome = sanitizeDestination(ROME)
    assert.equal(destinationValidity({ text: 'Rome, Lazio, Italy', answered: 'Italy', areas: sanitizeAreas(ITALY.areas),
      selected: rome }), '')
    assert.equal(destinationValidity({ text: 'Paris, Texas', answered: 'Paris, Texas', ambiguous: false }), '')
    assert.equal(destinationValidity({ text: '', answered: '' }), '')
  })

  it('waits while the text is being checked, but never blocks when the search failed', () => {
    assert.equal(destinationValidity({ text: 'London', answered: 'Lond', searchable: true, status: 'loading' }),
      'Wait a moment: Rihla is checking this destination.')
    assert.equal(destinationValidity({ text: 'London', answered: '', searchable: true, status: 'error' }), '')
    assert.equal(destinationValidity({ text: '12', answered: '', searchable: false }), '') // nothing to search
  })

  it('drops unusable areas instead of guessing', () => {
    assert.deepEqual(sanitizeAreas([{ kind: 'continent', name: 'Europe', country_code: 'EU' },
      { kind: 'country', name: 'Italy', country_code: 'ITA' }, null]), [])
    assert.deepEqual(sanitizeAreas('Italy'), [])
    assert.deepEqual(sanitizeAreas([{ kind: 'country', name: 'Italy', country_code: 'IT', suggestions: [{ id: 'x' }] }])[0]
      .suggestions, [])
  })

  it('the box uses all of it: no auto-highlight, no form submit from an open list, browser validity', () => {
    const source = readFileSync(new URL('./DestinationSearch.jsx', import.meta.url), 'utf8')
    assert.match(source, /setHighlight\(initialHighlight\(\{/)
    assert.match(source, /key === 'Enter' && showList\) \{\s*event\.preventDefault\(\)/)
    assert.match(source, /destinationValidity\(\{\s*text, answered, areas, ambiguous, selected, searchable, status,\s*\}\)/)
    assert.match(source, /setCustomValidity\(validity\)/)
    assert.match(source, /setAnswered\(text\)/)
  })
})
