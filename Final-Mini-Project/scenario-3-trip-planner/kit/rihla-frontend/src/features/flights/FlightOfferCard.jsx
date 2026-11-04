import { Briefcase, Clock, Plane } from 'lucide-react'
import {
  DATA_MODES, MODE_STYLES, baggageLabel, dayShift, formatClock, formatDuration, formatPrice, journeyMinutes, stopsLabel,
  tripTypeLabel,
} from './flightState.js'

export function DataModeBadge({ mode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-bold tracking-wide ${MODE_STYLES[mode]}`}
      title={DATA_MODES[mode].detail}
    >
      {DATA_MODES[mode].label}
      <span className="sr-only">: {DATA_MODES[mode].detail}</span>
    </span>
  )
}

function SliceRow({ slice, label, timeBasis }) {
  const shift = dayShift(slice.departingAt, slice.arrivingAt)
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 sm:gap-4">
      <div className="text-left">
        <p className="text-lg font-semibold text-[#1c3544]">{formatClock(slice.departingAt)}</p>
        <p className="text-xs font-medium text-[#6b8791]">{slice.origin}</p>
      </div>
      <div className="min-w-0 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8297a0]">{label}</p>
        <div className="my-1 flex items-center gap-2" aria-hidden="true">
          <span className="h-px flex-1 bg-[#d5e6e9]" />
          <Plane size={14} className="text-[#3c8992]" />
          <span className="h-px flex-1 bg-[#d5e6e9]" />
        </div>
        <p className="truncate text-xs text-[#456774]">
          {formatDuration(slice.durationMinutes)} · {stopsLabel(slice)}
        </p>
      </div>
      <div className="text-right">
        <p className="text-lg font-semibold text-[#1c3544]">
          {formatClock(slice.arrivingAt)}
          {shift && <sup className="ml-0.5 text-[10px] font-bold text-[#c2410c]" title="Arrives on a later day">{shift}</sup>}
        </p>
        <p className="text-xs font-medium text-[#6b8791]">{slice.destination}</p>
      </div>
      <p className="col-span-3 -mt-1 text-[11px] text-[#8297a0]">
        {slice.departingAt.slice(0, 10)} · {timeBasis === 'utc' ? 'times in UTC' : 'local times'}
        {slice.flightNumbers.length > 0 && ` · ${slice.flightNumbers.join(', ')}`}
      </p>
    </div>
  )
}

/** One flight offer, read-only: there is deliberately no "book" or "pay" action. */
export default function FlightOfferCard({ offer, cheapest = false, fastest = false }) {
  const price = formatPrice(offer.totalAmount, offer.currency)
  const people = `${offer.passengers} ${offer.passengers === 1 ? 'passenger' : 'passengers'}`
  const total = journeyMinutes(offer)
  const mode = DATA_MODES[offer.dataMode]
  return (
    <article
      aria-label={`${offer.airline}, ${price} total for ${people}, ${tripTypeLabel(offer).toLowerCase()}, ${mode.price}`}
      className="rounded-3xl border border-[#d5e6e9] bg-white p-4 shadow-sm sm:p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-[#1c3544]">
            {offer.airline}
            {offer.airlineCode && <span className="ml-1 text-xs font-medium text-[#6b8791]">({offer.airlineCode})</span>}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <DataModeBadge mode={offer.dataMode} />
            <span className="rounded-full border border-[#d5e6e9] px-2 py-0.5 text-[11px] font-semibold text-[#456774]">
              {tripTypeLabel(offer)}
            </span>
            {cheapest && (
              <span className="rounded-full bg-[#e5f4f4] px-2 py-0.5 text-[11px] font-semibold text-[#245c6a]">
                Cheapest in {offer.currency}
              </span>
            )}
            {fastest && (
              <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-semibold text-sky-900">
                Fastest in {offer.currency}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-[#1c3544]">{price}</p>
          <p className="text-xs text-[#6b8791]">
            total for {people}{offer.slices.length > 1 ? ' · both directions' : ' · outbound only'}
          </p>
          <p className={`mt-1 inline-block rounded-lg border px-2 py-0.5 text-[11px] font-bold ${MODE_STYLES[offer.dataMode]}`}>
            {mode.price}
          </p>
        </div>
      </header>

      <div className="mt-4 space-y-4 border-t border-[#edf2f3] pt-4">
        {offer.slices.map((slice, index) => (
          <SliceRow
            key={`${slice.origin}-${slice.departingAt}`}
            slice={slice}
            label={offer.slices.length > 1 ? (index === 0 ? 'Outbound' : 'Return') : 'One way'}
            timeBasis={offer.timeBasis}
          />
        ))}
      </div>

      <footer className="mt-4 flex flex-col gap-1.5 border-t border-[#edf2f3] pt-3 text-xs text-[#456774] sm:flex-row sm:flex-wrap sm:gap-x-5">
        <span className="inline-flex items-center gap-1.5">
          <Briefcase size={13} aria-hidden="true" /> {baggageLabel(offer.baggage)}
        </span>
        {total !== null && offer.slices.length > 1 && <span>Total travel time {formatDuration(total)}</span>}
        {offer.cabinClass && <span className="capitalize">{offer.cabinClass.replace('_', ' ')}</span>}
        {offer.expiresAt && (
          <span className="inline-flex items-center gap-1.5">
            <Clock size={13} aria-hidden="true" /> Offer valid until {offer.expiresAt.slice(11, 16)} UTC
          </span>
        )}
      </footer>
    </article>
  )
}
