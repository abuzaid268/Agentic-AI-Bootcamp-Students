// Client for GET /api/weather (app/weather): the daily forecast for coordinates and dates (Open-Meteo).
import { sanitizeWeather } from './weatherState.js'

export class WeatherFetchError extends Error {
  constructor(message, { code = 'weather_failed', retryable = false, status = null, availableUntil = null } = {}) {
    super(message)
    this.name = 'WeatherFetchError'
    this.code = code
    this.retryable = retryable
    this.status = status
    this.availableUntil = availableUntil // for beyond_forecast_horizon: the last date with a forecast
  }
}

export function weatherUrl({ latitude, longitude, startDate, endDate, temperatureUnit }) {
  const params = new URLSearchParams({ latitude: String(latitude ?? ''), longitude: String(longitude ?? '') })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (temperatureUnit) params.set('temperature_unit', temperatureUnit)
  return `/api/weather?${params.toString()}`
}

export async function fetchWeather(request, { signal, fetchImpl = globalThis.fetch } = {}) {
  let response
  try {
    response = await fetchImpl(weatherUrl(request), { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (signal?.aborted || err?.name === 'AbortError') throw err
    throw new WeatherFetchError('Could not reach the Rihla server for the weather.', { code: 'network', retryable: true })
  }
  let body = null
  try {
    body = await response.json()
  } catch {
    // handled below
  }
  if (!response.ok) {
    const error = body && typeof body.error === 'object' ? body.error : null
    throw new WeatherFetchError(
      (error && typeof error.message === 'string' && error.message)
        || (response.status === 404 ? 'Weather is not available on this server yet.' : `Weather failed (${response.status}).`),
      {
        code: (error && error.code) || (response.status === 404 ? 'not_available' : 'weather_failed'),
        retryable: error ? error.retryable === true : response.status >= 500,
        status: response.status,
        availableUntil: (error && typeof error.forecast_available_until === 'string' && error.forecast_available_until) || null,
      },
    )
  }
  try {
    return sanitizeWeather(body)
  } catch (err) {
    throw new WeatherFetchError(err.message, { code: 'bad_response' })
  }
}
