import { useId, useState } from 'react'
import { ArrowRight, CalendarDays, ChevronDown, Info, MapPin, PlaneTakeoff, Users } from 'lucide-react'
import FlightSearch from '../flights/FlightSearch.jsx'
import { isoToday } from '../flights/flightState.js'
import WeatherSummary from '../weather/WeatherSummary.jsx'
import { formatDay } from '../weather/weatherState.js'
import { travelInfoPlan } from './tripTravelState.js'

function Note({ children }) {
  return (
    <p role="status" className="flex items-start gap-2 rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#456774]">
      <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}

function RoutePoint({ icon: Icon, caption, value, placeholder }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#e5f4f4] text-[#3c8992]">
        <Icon size={18} aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-[#7b969f]">{caption}</span>
        <span className={`block truncate text-sm font-semibold ${value ? 'text-[#1c3544]' : 'font-normal text-[#8297a0]'}`}>
          {value || placeholder}
        </span>
      </span>
    </div>
  )
}

/**
 * The trip's weather and optional flight prices, side by side with its route (FROM -> TO). It only composes
 * WeatherSummary and FlightSearch: no new API, nothing booked, and flight prices never enter the trip budget.
 *
 * Props (all from the parent page; see docs/frontend-integration.md):
 *  - destination: the place DestinationSearch's onSelect gave for TO (its coordinates give the weather), or null
 *  - destinationText: the typed destination, used when no place was chosen (no weather then: never geocoded here)
 *  - origin: the optional FROM place (DestinationSearch's onSelect), used only to start the flight form
 *  - startDate, endDate ("YYYY-MM-DD"), travellers (number)
 *  - fetchImpl, today: tests only
 */
export default function TripTravelInfo({
  destination = null, destinationText = '', origin = null, startDate = '', endDate = '', travellers = 1,
  fetchImpl, today = isoToday(),
}) {
  const ids = useId()
  const [flightsOpen, setFlightsOpen] = useState(false)
  const plan = travelInfoPlan({ destination, destinationText, origin, startDate, endDate, travellers, today })
  const dates = startDate ? `${formatDay(startDate)}${endDate && endDate !== startDate ? ` – ${formatDay(endDate)}` : ''}` : null

  return (
    <section aria-labelledby={`${ids}-title`} className="rounded-[28px] border border-[#dbe8eb] bg-white p-5 shadow-sm sm:p-7">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#69b7bf]">Before you go</p>
          <h2 id={`${ids}-title`} className="mt-1 text-xl font-bold text-[#1c3544]">Weather and flights</h2>
        </div>
        <p className="text-xs text-[#6b8791]">For information only: nothing here is booked or added to your budget.</p>
      </div>

      <div className="mt-5 grid gap-4 rounded-3xl border border-[#d5e6e9] bg-[#f7fbfb] p-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
        <RoutePoint icon={PlaneTakeoff} caption="From" value={plan.fromLabel} placeholder="Not set (optional)" />
        <ArrowRight size={18} className="hidden text-[#69b7bf] sm:block" aria-hidden="true" />
        <RoutePoint icon={MapPin} caption="To" value={plan.toLabel} placeholder="Choose a destination" />
        <p className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#456774] sm:col-span-3">
          {dates && <span className="flex items-center gap-1.5"><CalendarDays size={14} aria-hidden="true" /> {dates}</span>}
          <span className="flex items-center gap-1.5">
            <Users size={14} aria-hidden="true" /> {plan.flights.adults} {plan.flights.adults === 1 ? 'traveller' : 'travellers'}
          </span>
        </p>
      </div>

      <div className="mt-6 space-y-3">
        {plan.weatherStatus === 'no_destination' && <Note>Choose a destination to see its weather.</Note>}
        {plan.weatherStatus === 'no_coordinates' && (
          <Note>Weather needs the exact place: choose {plan.toLabel} from the destination suggestions to see its forecast.</Note>
        )}
        {plan.weatherStatus === 'no_dates' && <Note>Choose your travel dates to see the forecast.</Note>}
        {plan.weatherStatus === 'past' && <Note>These dates have passed, so there is no forecast for them.</Note>}
        {plan.weatherStatus === 'later' && (
          <Note>
            No forecast yet: forecasts reach only 16 days ahead (to {formatDay(plan.weatherHorizon)}). Check again closer to
            your trip.
          </Note>
        )}
        {plan.weather && (
          <>
            <WeatherSummary {...plan.weather} fetchImpl={fetchImpl} />
            {plan.weatherStatus === 'partial' && (
              <p className="text-xs text-[#6b8791]">
                Forecasts reach only 16 days ahead: the days after {formatDay(plan.weatherHorizon)} have no forecast yet.
              </p>
            )}
          </>
        )}
      </div>

      <div className="mt-6 border-t border-[#edf2f3] pt-5">
        <button
          type="button"
          aria-expanded={flightsOpen}
          aria-controls={`${ids}-flights`}
          onClick={() => setFlightsOpen((open) => !open)}
          className="flex w-full items-center justify-between gap-3 rounded-2xl px-1 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a9d7dc]"
        >
          <span>
            <span className="block font-semibold text-[#1c3544]">Compare flights (optional)</span>
            <span className="block text-xs text-[#6b8791]">
              Choose your departure and arrival airports. Prices are for comparison and are not part of your trip budget.
            </span>
          </span>
          <ChevronDown size={20} aria-hidden="true" className={`shrink-0 text-[#3c8992] transition ${flightsOpen ? 'rotate-180' : ''}`} />
        </button>
        {/* Mounted only when opened: no airport or flight request for a traveller who does not need flights. */}
        <div id={`${ids}-flights`} hidden={!flightsOpen} className="mt-4">
          {flightsOpen && (
            <FlightSearch key={plan.flightsKey} {...plan.flights} title="Flights for this trip" fetchImpl={fetchImpl}
              airportFetchImpl={fetchImpl} today={today} />
          )}
        </div>
      </div>
    </section>
  )
}
