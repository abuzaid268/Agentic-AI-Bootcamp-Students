import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { WeatherFetchError, fetchWeather, weatherUrl } from './weatherApi.js'
import {
  conditionIcon, describeDay, formatDay, formatTemperature, rainLabel, sanitizeWeather,
} from './weatherState.js'

// The backend's answer (app/weather) built from a real Open-Meteo forecast for Amman, 2026-11-03..05.
const AMMAN = JSON.parse(readFileSync(new URL('./fixtures/amman_forecast.json', import.meta.url), 'utf8'))

function fakeFetch(status, body, { json = true } = {}) {
  const calls = []
  const impl = async (url) => {
    calls.push(url)
    return { ok: status >= 200 && status < 300, status, json: async () => {
      if (!json) throw new SyntaxError('not JSON')
      return body
    } }
  }
  return { impl, calls }
}

describe('fetchWeather', () => {
  it('asks for the place and dates, and reads a real forecast', async () => {
    const { impl, calls } = fakeFetch(200, AMMAN)
    const forecast = await fetchWeather({ latitude: 31.9539, longitude: 35.9106, startDate: '2026-11-03', endDate: '2026-11-05' }, { fetchImpl: impl })
    assert.equal(calls[0], '/api/weather?latitude=31.9539&longitude=35.9106&start_date=2026-11-03&end_date=2026-11-05')
    assert.equal(forecast.status, 'LIVE')
    assert.equal(forecast.timezone, 'Asia/Amman')
    assert.equal(forecast.days.length, 3)
    assert.deepEqual(forecast.days[0], {
      date: '2026-11-03', weatherCode: 3, condition: 'overcast', temperatureMax: 24.5, temperatureMin: 14.7,
      precipitationMm: 0, rainProbability: 3, windSpeedMax: 15.5, wet: false,
    })
    assert.match(forecast.attribution, /Open-Meteo/)
  })

  it('passes the temperature unit only when asked', () => {
    assert.equal(weatherUrl({ latitude: 1, longitude: 2, temperatureUnit: 'fahrenheit' }),
      '/api/weather?latitude=1&longitude=2&temperature_unit=fahrenheit')
  })

  it('refuses simulated or unavailable data, so it is never shown as a forecast', async () => {
    for (const status of ['SIMULATED', 'UNAVAILABLE', undefined]) {
      await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: fakeFetch(200, { ...AMMAN, data_status: status }).impl }),
        (err) => err.code === 'bad_response')
    }
  })

  it('explains invalid coordinates, the forecast horizon and an unavailable service', async () => {
    const bad = { error: { code: 'invalid_coordinates', message: 'Latitude must be a number between -90 and 90.', retryable: false, field: 'latitude' }, data_status: 'UNAVAILABLE' }
    await assert.rejects(fetchWeather({ latitude: 91, longitude: 0 }, { fetchImpl: fakeFetch(422, bad).impl }),
      (err) => err instanceof WeatherFetchError && err.code === 'invalid_coordinates' && !err.retryable)
    const far = { error: { code: 'beyond_forecast_horizon', message: 'Forecasts reach only 16 days ahead.', retryable: false, forecast_available_until: '2026-11-18' }, data_status: 'UNAVAILABLE' }
    await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: fakeFetch(422, far).impl }),
      (err) => err.code === 'beyond_forecast_horizon' && err.availableUntil === '2026-11-18')
    const off = { error: { code: 'weather_unavailable', message: 'Weather forecasts are not available on this service right now.', retryable: false }, data_status: 'UNAVAILABLE' }
    await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: fakeFetch(503, off).impl }),
      (err) => err.code === 'weather_unavailable')
  })

  it('reports provider outages and timeouts with a retry', async () => {
    const timeout = { error: { code: 'provider_timeout', message: 'The weather service did not answer in time. Please try again.', retryable: true }, data_status: 'UNAVAILABLE' }
    await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: fakeFetch(504, timeout).impl }),
      (err) => err.code === 'provider_timeout' && err.retryable)
    await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: fakeFetch(502, null, { json: false }).impl }),
      (err) => /Weather failed \(502\)/.test(err.message) && err.retryable)
    const offline = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(fetchWeather({ latitude: 1, longitude: 2 }, { fetchImpl: offline }), (err) => err.code === 'network')
  })
})

describe('missing values are shown as missing', () => {
  it('keeps nulls, and drops days without a date', () => {
    const body = { ...AMMAN, days: [{ date: '2026-11-03', weather_code: null, temperature_max: null, precipitation_probability_max_pct: 140 }, { date: 'soon' }] }
    const forecast = sanitizeWeather(body)
    assert.equal(forecast.days.length, 1)
    const [day] = forecast.days
    assert.equal(day.temperatureMax, null)
    assert.equal(day.rainProbability, null)
    assert.equal(formatTemperature(day.temperatureMax, '°C'), '—')
    assert.equal(rainLabel(day), 'Rain chance not given')
    assert.equal(conditionIcon(day.weatherCode), 'Cloud')
  })
})

describe('what the traveller sees and hears', () => {
  it('formats the place\'s own date, whatever the viewer\'s time zone', () => {
    assert.equal(formatDay('2026-11-03'), 'Tue 3 Nov')
    assert.equal(formatDay('2026-12-31'), 'Thu 31 Dec')
  })

  it('picks an icon for each kind of weather', () => {
    assert.deepEqual([0, 2, 45, 53, 63, 81, 73, 95].map(conditionIcon),
      ['Sun', 'CloudSun', 'CloudFog', 'CloudDrizzle', 'CloudRain', 'CloudRain', 'CloudSnow', 'CloudLightning'])
  })

  it('reads a whole day out in one sentence', () => {
    const day = sanitizeWeather(AMMAN).days[0]
    assert.equal(describeDay(day, '°C'), 'Tue 3 Nov, overcast, high 25°C, low 15°C, 3% chance of rain, wind up to 16 km/h')
  })
})
