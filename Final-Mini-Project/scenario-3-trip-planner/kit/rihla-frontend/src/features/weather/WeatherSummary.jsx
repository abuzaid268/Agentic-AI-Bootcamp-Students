import { useEffect, useId, useState } from 'react'
import {
  Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Droplets, Sun, Wind,
} from 'lucide-react'
import { fetchWeather } from './weatherApi.js'
import {
  SHOWN_STATUSES, conditionIcon, describeDay, formatDay, formatTemperature, rainLabel,
} from './weatherState.js'

const ICONS = { Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Sun }

const isCoordinate = (value, bound) => value !== null && value !== undefined && value !== ''
  && Number.isFinite(Number(value)) && Math.abs(Number(value)) <= bound

// Answers that mean "no forecast here", not a failure: shown as a calm note, not an alert.
const QUIET_ERRORS = ['beyond_forecast_horizon', 'weather_unavailable', 'not_available']

function Unavailable({ children }) {
  return <p role="status" className="rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#456774]">{children}</p>
}

/**
 * The daily forecast for a place and dates (GET /api/weather, Open-Meteo). Shows only real forecasts, says when
 * there is none, and never fills a gap.
 *
 * Props: latitude, longitude (required to load), startDate, endDate ("YYYY-MM-DD"; default today, at most 16 days
 * ahead), locationName (e.g. "Amman"), temperatureUnit ("celsius" | "fahrenheit"), fetchImpl (tests).
 */
export default function WeatherSummary({
  latitude, longitude, startDate, endDate, locationName, temperatureUnit = 'celsius', fetchImpl,
}) {
  const ids = useId()
  const hasPlace = isCoordinate(latitude, 90) && isCoordinate(longitude, 180)
  const key = JSON.stringify([latitude, longitude, startDate, endDate, temperatureUnit])
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ key: null, attempt: -1 }) // { key, attempt, forecast } or { …, error }

  useEffect(() => {
    if (!hasPlace) return undefined
    const controller = new AbortController()
    fetchWeather({ latitude, longitude, startDate, endDate, temperatureUnit }, { signal: controller.signal, fetchImpl })
      .then((forecast) => setResult({ key, attempt, forecast }))
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ key, attempt, error })
      })
    return () => controller.abort()
  }, [hasPlace, latitude, longitude, startDate, endDate, temperatureUnit, fetchImpl, key, attempt])

  const loading = hasPlace && (result.key !== key || result.attempt !== attempt)
  const { forecast, error } = loading ? {} : result
  const title = locationName ? `Weather in ${locationName}` : 'Weather'

  return (
    <section
      aria-labelledby={`${ids}-title`}
      aria-busy={loading}
      className="rounded-3xl border border-[#d5e6e9] bg-white p-4 shadow-sm sm:p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`${ids}-title`} className="font-semibold text-[#1c3544]">{title}</h3>
        {forecast && (
          <span
            className="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-800"
            title={SHOWN_STATUSES[forecast.status].detail}
          >
            {SHOWN_STATUSES[forecast.status].label}
          </span>
        )}
      </div>

      <div className="mt-3" aria-live="polite">
        {!hasPlace && <Unavailable>Choose a place to see its weather.</Unavailable>}

        {loading && (
          <p role="status" className="animate-pulse rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#6b8791]">Loading the weather…</p>
        )}

        {error && error.code === 'beyond_forecast_horizon' && (
          <Unavailable>
            No forecast yet: forecasts reach only 16 days ahead
            {error.availableUntil ? ` (to ${formatDay(error.availableUntil)})` : ''}. Check again closer to the date.
          </Unavailable>
        )}
        {error && error.code === 'weather_unavailable' && (
          <Unavailable>Weather forecasts are not available on this service right now.</Unavailable>
        )}
        {error && error.code === 'not_available' && (
          <Unavailable>Weather is not connected on this server yet. The rest of your trip is not affected.</Unavailable>
        )}
        {error && !QUIET_ERRORS.includes(error.code) && (
          <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error.message}
            {error.retryable && (
              <button type="button" onClick={() => setAttempt((n) => n + 1)} className="ml-2 font-semibold underline">
                Try again
              </button>
            )}
          </div>
        )}

        {forecast && forecast.days.length === 0 && <Unavailable>The weather service gave no forecast for these dates.</Unavailable>}

        {forecast && forecast.days.length > 0 && (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {forecast.days.map((day) => {
              const Icon = ICONS[conditionIcon(day.weatherCode)]
              return (
                <li key={day.date} className="rounded-2xl bg-[#f7fbfb] p-3">
                  <span className="sr-only">{describeDay(day, forecast.temperatureUnit)}</span>
                  <div aria-hidden="true">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold text-[#456774]">{formatDay(day.date)}</p>
                      <Icon size={20} className="text-[#3c8992]" />
                    </div>
                    <p className="mt-1 text-lg font-semibold text-[#1c3544]">
                      {formatTemperature(day.temperatureMax, forecast.temperatureUnit)}
                      <span className="ml-1 text-sm font-normal text-[#6b8791]">
                        / {formatTemperature(day.temperatureMin, forecast.temperatureUnit)}
                      </span>
                    </p>
                    <p className="text-xs capitalize text-[#456774]">{day.condition || 'Conditions not given'}</p>
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-[#456774]">
                      <Droplets size={13} /> {rainLabel(day)}
                    </p>
                    {day.windSpeedMax !== null && (
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-[#456774]">
                        <Wind size={13} /> Wind up to {Math.round(day.windSpeedMax)} km/h
                      </p>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}

        {forecast && forecast.missingDates.length > 0 && (
          <p className="mt-2 text-xs text-[#6b8791]">No forecast was given for {forecast.missingDates.map(formatDay).join(', ')}.</p>
        )}
      </div>

      {forecast && (
        <p className="mt-3 text-[11px] text-[#8297a0]">
          Forecasts change: check again closer to the date.
          {forecast.retrievedAt && ` Updated ${forecast.retrievedAt.slice(11, 16)} UTC.`}
          {forecast.timezone && ` Dates in ${forecast.timezone} time.`}{' '}
          {forecast.sourceUrl ? (
            <a href={forecast.sourceUrl} target="_blank" rel="noreferrer" className="underline">{forecast.attribution}</a>
          ) : forecast.attribution}
        </p>
      )}
    </section>
  )
}
