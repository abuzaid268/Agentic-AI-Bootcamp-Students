import { useEffect, useId, useRef, useState } from 'react'
import { Info, MapPin } from 'lucide-react'
import { fetchNearbyAirports } from './airportsApi.js'
import { airportCode, distanceLabel, locationLabel, nearbyNotes, nearbyPlaceKey } from './airportState.js'

/**
 * The airports near a place chosen in the destination box (GET /api/airports/near), nearest first, to pick from.
 *
 * It only suggests. Nothing is chosen for the traveller except when the server says exactly one airport clearly
 * qualifies (the only one in the place's own country within reach, with none across the border close by): then
 * `onSuggested` is called once. Every choice stays editable in the airport box above. The list is ranked by
 * straight-line distance only, and says so: the nearest airport is not necessarily the best one for a route.
 *
 * Props:
 *  - place: { name, region, country, countryCode, latitude, longitude } (airportState.cleanNearbyPlace); without one
 *    the component shows nothing
 *  - kind: "departure" | "arrival" (wording only)
 *  - selectedId: the id of the airport now chosen in the box, to mark it
 *  - onChoose(airport): the traveller picked a suggestion
 *  - onSuggested(airport): called once with the sole qualifying airport, if there is one
 *  - fetchImpl (tests)
 */
export default function NearbyAirports({ place, kind = 'departure', selectedId = null, onChoose, onSuggested, fetchImpl }) {
  const [attempt, setAttempt] = useState(0)
  // The answer (or error) belongs to the request it was made for; until it matches the current one, we are loading.
  const [result, setResult] = useState({ request: '', answer: null, message: '' })
  const announced = useRef('')
  const key = nearbyPlaceKey(place)
  const request = `${key}#${attempt}`

  useEffect(() => {
    if (!place) return undefined
    const controller = new AbortController()
    fetchNearbyAirports(place, { signal: controller.signal, fetchImpl })
      .then((answer) => {
        if (controller.signal.aborted) return
        setResult({ request, answer, message: '' })
        if (answer.suggested && announced.current !== key) {
          announced.current = key // once per place: a later re-render never overrides the traveller's choice
          onSuggested?.(answer.suggested)
        }
      })
      .catch((err) => {
        if (controller.signal.aborted || err?.name === 'AbortError') return
        setResult({ request, answer: null, message: err instanceof Error ? err.message : 'Nearby airports failed.' })
      })
    return () => controller.abort()
    // The place's coordinates decide (key), not the object's identity; a callback change must not search again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, fetchImpl, attempt])

  const state = {
    status: !place ? 'idle' : result.request !== request ? 'loading'
      : result.message ? 'error' : result.answer?.unavailable ? 'unavailable' : 'ready',
    answer: result.answer,
    message: result.message,
  }
  if (!place || state.status === 'unavailable') return null

  if (state.status === 'loading') {
    return <p role="status" className="mt-2 text-xs text-[#6b8791]">Looking for airports near {place.name}…</p>
  }
  if (state.status === 'error') {
    return (
      <p role="status" className="mt-2 text-xs text-[#6b8791]">
        {state.message} You can still search for an airport above.{' '}
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="font-semibold underline">Try again</button>
      </p>
    )
  }

  return (
    <NearbyList place={place} answer={state.answer} kind={kind} selectedId={selectedId} onChoose={onChoose} />
  )
}

/** The list itself (a pure view of one GET /api/airports/near answer), separate so it can be rendered on its own. */
export function NearbyList({ place, answer, kind = 'departure', selectedId = null, onChoose }) {
  const ids = useId()
  const noun = kind === 'arrival' ? 'arrival' : 'departure'
  const heading = `Airports near ${place.label}`

  const { airports, suggested, country, maxKm } = answer
  const notes = nearbyNotes({ place, airports, country, maxKm })
  const onlyOne = suggested && selectedId === suggested.id

  return (
    <div role="group" aria-labelledby={`${ids}-title`} className="mt-3 rounded-2xl border border-[#d5e6e9] bg-white p-3">
      <p id={`${ids}-title`} className="flex items-center gap-1.5 text-xs font-semibold text-[#456774]">
        <MapPin size={13} aria-hidden="true" /> {heading}
      </p>
      {airports.length > 0 && (
        <ol className="mt-2 space-y-1.5">
          {airports.map((airport) => {
            const chosen = airport.id === selectedId
            return (
              <li key={airport.id}>
                <button
                  type="button"
                  aria-pressed={chosen}
                  onClick={() => onChoose?.(airport)}
                  className={`flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-0.5 rounded-xl border px-3 py-2 text-left text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a9d7dc] ${
                    chosen ? 'border-[#245c6a] bg-[#e5f4f4]' : 'border-[#e3eef0] hover:bg-[#f7fbfb]'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="font-semibold text-[#1c3544]">{airportCode(airport)}</span>
                    <span className="text-[#456774]"> · {airport.name}</span>
                    <span className="block text-[#6b8791]">
                      {airport.city ? `${airport.city} · ` : ''}{locationLabel(airport, country)}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="font-semibold text-[#245c6a]">{distanceLabel(airport.distanceKm)}</span>
                    {airport.inCountry === false && (
                      <span className="ml-2 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                        Other country
                      </span>
                    )}
                    {chosen && <span className="sr-only"> (selected {noun} airport)</span>}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
      {onlyOne && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-emerald-800">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>Only one airport clearly qualifies near {place.name}, so it is preselected. You can change it.</span>
        </p>
      )}
      {notes.map((note) => (
        <p key={note} className="mt-2 flex items-start gap-1.5 text-xs text-[#6b8791]">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" /> <span>{note}</span>
        </p>
      ))}
      {airports.length > 0 && (
        <p className="mt-2 text-[11px] text-[#8297a0]">
          Ranked by straight-line distance only. The nearest airport is not always the best one for your route.
        </p>
      )}
    </div>
  )
}
