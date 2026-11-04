import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { addDays, cityFromText, placeFrom, travelInfoPlan, weatherWindow } from './tripTravelState.js'

// Places as DestinationSearch's onSelect hands them over (sanitizeDestination), from the backend's real answers.
const AMMAN = { id: 'geonames:250441', name: 'Amman', region: 'Amman Governorate', country: 'Jordan', countryCode: 'JO',
  latitude: 31.95522, longitude: 35.94503, label: 'Amman, Amman Governorate, Jordan' }
const LONDON = { id: 'geonames:2643743', name: 'London', region: 'England', country: 'United Kingdom', countryCode: 'GB',
  latitude: 51.50853, longitude: -0.12574, label: 'London, England, United Kingdom' }
const TODAY = '2026-11-04'

describe('the forecast window', () => {
  it('asks for the trip days that have a forecast (16 days, today included)', () => {
    assert.equal(addDays(TODAY, 15), '2026-11-19')
    assert.deepEqual(weatherWindow('2026-11-06', '2026-11-08', TODAY),
      { status: 'full', startDate: '2026-11-06', endDate: '2026-11-08', horizon: '2026-11-19' })
  })

  it('cuts a trip that runs past the horizon instead of getting no forecast at all', () => {
    assert.deepEqual(weatherWindow('2026-11-10', '2026-11-30', TODAY),
      { status: 'partial', startDate: '2026-11-10', endDate: '2026-11-19', horizon: '2026-11-19' })
  })

  it('does not ask for a trip that starts after the horizon, or one that is over', () => {
    assert.deepEqual(weatherWindow('2026-12-20', '2026-12-25', TODAY), { status: 'later', horizon: '2026-11-19' })
    assert.deepEqual(weatherWindow('2026-10-01', '2026-10-05', TODAY), { status: 'past' })
  })

  it('starts today for a trip under way, and needs real dates', () => {
    assert.equal(weatherWindow('2026-11-01', '2026-11-06', TODAY).startDate, TODAY)
    assert.equal(weatherWindow('', '', TODAY).status, 'no_dates')
    assert.equal(weatherWindow('next week', '', TODAY).status, 'no_dates')
    assert.equal(weatherWindow('2026-11-06', '2026-11-01', TODAY).endDate, '2026-11-06') // end before start: one day
  })
})

describe('FROM -> TO', () => {
  const trip = { destination: AMMAN, origin: LONDON, startDate: '2026-11-06', endDate: '2026-11-09', travellers: '2', today: TODAY }

  it('gives the weather the chosen place and dates', () => {
    const plan = travelInfoPlan(trip)
    assert.deepEqual(plan.weather, { latitude: 31.95522, longitude: 35.94503, startDate: '2026-11-06',
      endDate: '2026-11-09', locationName: 'Amman' })
    assert.equal(plan.weatherStatus, 'full')
    assert.equal(plan.fromLabel, 'London, England, United Kingdom')
    assert.equal(plan.toLabel, 'Amman, Amman Governorate, Jordan')
  })

  it('starts the flight form from the trip: city names as hints, never airports', () => {
    assert.deepEqual(travelInfoPlan(trip).flights, { departureHint: 'London', departureCountry: 'GB', arrivalHint: 'Amman',
      departureDate: '2026-11-06', returnDate: '2026-11-09', adults: 2 })
  })

  it('works without FROM: flights stay optional and start empty on that side', () => {
    const plan = travelInfoPlan({ ...trip, origin: null })
    assert.equal(plan.fromLabel, null)
    assert.equal(plan.flights.departureHint, '')
    assert.equal(plan.flights.departureCountry, '')
    assert.equal(plan.flights.arrivalHint, 'Amman')
  })

  it('a typed destination without a chosen place gets no weather (never geocoded here) but still a flight hint', () => {
    const plan = travelInfoPlan({ ...trip, destination: null, destinationText: 'Paris, France' })
    assert.equal(plan.weather, null)
    assert.equal(plan.weatherStatus, 'no_coordinates')
    assert.equal(plan.toLabel, 'Paris, France')
    assert.equal(plan.flights.arrivalHint, 'Paris')
    assert.equal(cityFromText('  Tel Aviv ,  Israel'), 'Tel Aviv')
    assert.equal(travelInfoPlan({ today: TODAY }).weatherStatus, 'no_destination')
  })

  it('drops past dates from the flight form and unusable places', () => {
    const past = travelInfoPlan({ ...trip, startDate: '2026-10-01', endDate: '2026-10-05' })
    assert.equal(past.flights.departureDate, '')
    assert.equal(past.flights.returnDate, '')
    assert.equal(past.weatherStatus, 'past')
    assert.equal(placeFrom({ name: '' }), null)
    assert.deepEqual(placeFrom({ name: 'X', latitude: 'north', longitude: 500, countryCode: 'GBR' }),
      { name: 'X', country: null, countryCode: null, latitude: null, longitude: null, label: 'X' })
  })

  it('a new trip starts the flight form over; the same trip keeps it', () => {
    const key = travelInfoPlan(trip).flightsKey
    assert.equal(travelInfoPlan({ ...trip }).flightsKey, key)
    for (const change of [{ destination: LONDON }, { origin: AMMAN }, { startDate: '2026-11-07' }, { endDate: '2026-11-10' },
      { travellers: 3 }]) {
      assert.notEqual(travelInfoPlan({ ...trip, ...change }).flightsKey, key, JSON.stringify(Object.keys(change)))
    }
  })
})

describe('TripTravelInfo', () => {
  const source = readFileSync(new URL('./TripTravelInfo.jsx', import.meta.url), 'utf8')

  it('composes the existing components instead of calling APIs itself', () => {
    assert.match(source, /import FlightSearch from '\.\.\/flights\/FlightSearch\.jsx'/)
    assert.match(source, /import WeatherSummary from '\.\.\/weather\/WeatherSummary\.jsx'/)
    assert.doesNotMatch(source, /fetch\(|\/api\//)
  })

  it('keeps flights optional: closed until asked for, remounted for a new trip, never in the budget', () => {
    assert.match(source, /useState\(false\)/)
    assert.match(source, /aria-expanded=\{flightsOpen\}/)
    assert.match(source, /\{flightsOpen && \(\s*<FlightSearch key=\{plan\.flightsKey\}/)
    assert.match(source, /not part of your trip budget/)
    assert.doesNotMatch(source, /budget\s*[+=]|onBudget|setBudget/)
  })
})
