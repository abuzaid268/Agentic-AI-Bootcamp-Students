import { useEffect, useId, useRef, useState } from 'react'
import { AlertTriangle, Info, Search } from 'lucide-react'
import { AirportSearch, NearbyAirports, fetchAirportCountries } from '../airports/index.js'
import FlightOfferCard, { DataModeBadge } from './FlightOfferCard.jsx'
import { fetchFlightStatus, isFlightsUnavailable, searchFlights } from './flightsApi.js'
import {
  CABIN_CLASSES, DATA_MODES, MAX_ADULTS, MODE_STYLES, cheapestByCurrency, compareOffers, fastestByCurrency,
  formatDuration, formatPrice, initialFlightForm, isoToday, journeyMinutes, latestOnly, resultState, searchKey,
  searchSummary, sortOffers, validateFlightForm,
} from './flightState.js'

const FIELD_FOR_SERVER = {
  origin: 'origin', destination: 'destination', departure_date: 'departureDate', return_date: 'returnDate',
  adults: 'adults', cabin_class: 'cabinClass',
}

const inputClass = 'w-full rounded-2xl border border-[#d5e6e9] bg-white px-4 py-3 text-sm text-[#1c3544] outline-none focus:ring-2 focus:ring-[#a9d7dc] aria-[invalid=true]:border-red-400'
const labelClass = 'mb-2 block text-xs font-semibold text-[#456774]'

// The optional country filter of one airport box ("Any country" searches worldwide).
function CountryPicker({ id, label, value, countries, onChange }) {
  if (!countries.length) return null
  return (
    <div className="mt-5 max-w-sm">
      <label htmlFor={id} className={labelClass}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>
        <option value="">Any country</option>
        {countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
      </select>
    </div>
  )
}

// One currency's cheapest-versus-fastest sentence (compareOffers). Prices of different currencies are never compared.
function CompareLine({ entry, showCurrency }) {
  const { cheapest, fastest, same, extra, saved } = entry
  const time = (offer) => { const m = journeyMinutes(offer); return m === null ? 'duration not given' : formatDuration(m) }
  const prefix = showCurrency ? `${entry.currency}: ` : ''
  if (same) {
    return (
      <p>{prefix}The cheapest offer ({formatPrice(cheapest.totalAmount, cheapest.currency)}, {time(cheapest)}) is also the fastest.</p>
    )
  }
  const price = Number(extra) === 0 ? 'the same price' : `${formatPrice(extra, fastest.currency)} more`
  const gain = saved ? `, ${formatDuration(saved)} shorter` : ''
  return (
    <p>
      {prefix}Cheapest: {formatPrice(cheapest.totalAmount, cheapest.currency)}, {time(cheapest)}.
      {' '}Fastest: {formatPrice(fastest.totalAmount, fastest.currency)}, {time(fastest)} ({price}{gain}).
    </p>
  )
}

function FieldError({ id, message }) {
  if (!message) return null
  return <p id={id} className="mt-1.5 text-xs text-red-700">{message}</p>
}

/**
 * Flight search and price comparison (GET /api/flights). Informational only: no booking, no payment, and the
 * prices are not added to the trip budget.
 *
 * Optional starting values from the trip (flightState.initialFlightForm cleans them). They only fill the form when
 * it first appears; what the traveller changes afterwards is kept. To start over for another trip, remount the
 * component with a new `key`. A hint is only typed into an airport box, which then lists matching airports. An
 * airport is put into a box for the traveller in one case only: a chosen place (departurePlace/arrivalPlace) near
 * which exactly one airport clearly qualifies (the server decides, see app/airports `suggested`). It is shown as
 * an ordinary, editable choice, and never replaces something the traveller already did in that box.
 *  - departureHint: text for the "From" box, e.g. the city the traveller leaves from ("London")
 *  - departureCountry: ISO 3166-1 alpha-2 code that starts the departure country picker ("GB")
 *  - arrivalHint: text for the "To" box, e.g. the destination city ("Amman")
 *  - arrivalCountry: the same, for the arrival country picker
 *  - departurePlace, arrivalPlace: the cities chosen in the destination box ({ name, region, country, countryCode,
 *    latitude, longitude }). With one, a list of the airports near it is offered under that box (nearest first, other
 *    countries marked). An airport is preselected only when exactly one clearly qualifies; every choice is editable.
 *    Their country codes start the country pickers, so "Paris" in Texas never lists Paris, France airports.
 *  - departureDate, returnDate ("YYYY-MM-DD"), adults (1 to 9; a larger party is capped at 9 and said so)
 *  - title: the heading ("Compare flight prices")
 * Props for tests: fetchImpl (flights), airportFetchImpl (airport boxes), today ("YYYY-MM-DD").
 */
export default function FlightSearch({
  fetchImpl, airportFetchImpl, today = isoToday(), title = 'Compare flight prices', ...initial
}) {
  const ids = useId()
  const [start] = useState(() => initialFlightForm(initial)) // read once: later prop changes never overwrite choices
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  // An airport put into a box for the traveller (a suggestion they clicked, or the only one that qualified): the box
  // starts from it, and a new key remounts the box. `touched` is set once the traveller used the box themselves.
  const [originSeed, setOriginSeed] = useState(null)
  const [destinationSeed, setDestinationSeed] = useState(null)
  const [originBox, setOriginBox] = useState(0)
  const [destinationBox, setDestinationBox] = useState(0)
  const touched = useRef({ origin: false, destination: false })
  const [roundTrip, setRoundTrip] = useState(start.roundTrip)
  const [departureDate, setDepartureDate] = useState(start.departureDate)
  const [returnDate, setReturnDate] = useState(start.returnDate)
  const [adults, setAdults] = useState(start.adults)
  const [cabinClass, setCabinClass] = useState('economy')
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState('idle') // idle | loading | ready | error
  const [answer, setAnswer] = useState(null)
  const [failure, setFailure] = useState(null)
  const [order, setOrder] = useState('price-asc')
  const [serverStatus, setServerStatus] = useState(null) // from GET /api/flights/status, null until known
  const [resultKey, setResultKey] = useState(null) // the search the answer or error on screen belongs to
  const [countries, setCountries] = useState([]) // from GET /api/airports/countries; [] hides the picker
  const [departureCountry, setDepartureCountry] = useState(start.departureCountry) // '' = any country
  const [departureHint, setDepartureHint] = useState(start.departureHint) // typed into "From" until the country changes
  const [arrivalCountry, setArrivalCountry] = useState(start.arrivalCountry) // '' = any country
  const [arrivalHint, setArrivalHint] = useState(start.arrivalHint)
  const pending = useRef(null)
  const searches = useRef(latestOnly())

  useEffect(() => () => pending.current?.abort(), []) // no answer lands after the form is gone

  useEffect(() => {
    const controller = new AbortController()
    fetchAirportCountries({ signal: controller.signal, fetchImpl: airportFetchImpl })
      .then((found) => {
        setCountries(found)
        // a starting country the server does not list is dropped, never kept as a hidden filter
        if (found.length) {
          setDepartureCountry((code) => (found.some((c) => c.code === code) ? code : ''))
          setArrivalCountry((code) => (found.some((c) => c.code === code) ? code : ''))
        }
      })
      .catch(() => {}) // aborted on unmount
    return () => controller.abort()
  }, [airportFetchImpl])

  // A new departure country starts the departure airport over: the box is remounted empty (key) and searches
  // only that country's airports.
  const chooseDepartureCountry = (code) => {
    setDepartureCountry(code)
    setDepartureHint('') // the hint belonged to the starting country
    setOrigin(null)
    setOriginSeed(null)
  }
  const chooseArrivalCountry = (code) => {
    setArrivalCountry(code)
    setArrivalHint('')
    setDestination(null)
    setDestinationSeed(null)
  }

  // A nearby airport the traveller clicked, or the one that clearly qualified: put into its box like any choice.
  const putAirport = (side, airport) => {
    if (side === 'origin') {
      setOrigin(airport)
      setOriginSeed(airport)
      setOriginBox((n) => n + 1)
    } else {
      setDestination(airport)
      setDestinationSeed(airport)
      setDestinationBox((n) => n + 1)
    }
  }
  const pickNearby = (side) => (airport) => {
    touched.current[side] = true
    putAirport(side, airport)
  }
  // The sole qualifying airport is preselected only if the traveller has not started choosing for themselves.
  const preselect = (side) => (airport) => {
    if (touched.current[side]) return
    putAirport(side, airport)
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchFlightStatus({ signal: controller.signal, fetchImpl })
      .then((found) => setServerStatus(found))
      .catch(() => {}) // aborted on unmount
    return () => controller.abort()
  }, [fetchImpl])

  const currentKey = searchKey({ origin, destination, departureDate, returnDate, roundTrip, adults, cabinClass })
  const shown = resultState(status, resultKey, currentKey) // 'stale' once the form no longer matches the results
  const unavailable = serverStatus?.available === false || (status === 'error' && isFlightsUnavailable(failure))

  const run = async () => {
    const form = { origin, destination, departureDate, returnDate, roundTrip, adults }
    const found = validateFlightForm(form, today)
    setErrors(found)
    if (Object.keys(found).length) return
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    const ticket = searches.current.start()
    setResultKey(currentKey)
    setAnswer(null)
    setStatus('loading')
    setFailure(null)
    try {
      const result = await searchFlights({
        origin: origin.iata, destination: destination.iata, departureDate,
        returnDate: roundTrip ? returnDate : '', adults, cabinClass,
      }, { signal: controller.signal, fetchImpl })
      if (!searches.current.isCurrent(ticket)) return // a newer search replaced this one
      setAnswer(result)
      setStatus('ready')
    } catch (err) {
      if (controller.signal.aborted || !searches.current.isCurrent(ticket)) return
      setAnswer(null)
      setFailure(err)
      setStatus('error')
      const field = FIELD_FOR_SERVER[err?.field]
      if (field) setErrors({ [field]: err.message })
    }
  }

  const onSubmit = (event) => {
    event.preventDefault()
    run()
  }

  const describe = (field) => (errors[field] ? `${ids}-${field}-error` : undefined)
  const offers = answer ? sortOffers(answer.offers, order) : []
  const cheapest = cheapestByCurrency(offers)
  const fastest = fastestByCurrency(offers)
  const comparison = compareOffers(offers)

  return (
    <section aria-labelledby={`${ids}-title`} className="space-y-6">
      <form onSubmit={onSubmit} noValidate className="rounded-3xl border border-[#d5e6e9] bg-[#f7fbfb] p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id={`${ids}-title`} className="text-lg font-semibold text-[#1c3544]">{title}</h2>
          <fieldset className="flex rounded-full border border-[#d5e6e9] bg-white p-1 text-xs font-semibold">
            <legend className="sr-only">Trip type</legend>
            {[[true, 'Round trip'], [false, 'One way']].map(([value, text]) => (
              <label
                key={text}
                className={`cursor-pointer rounded-full px-3 py-1.5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#a9d7dc] ${
                  roundTrip === value ? 'bg-[#245c6a] text-white' : 'text-[#456774]'
                }`}
              >
                <input
                  type="radio"
                  name={`${ids}-trip-type`}
                  className="sr-only"
                  checked={roundTrip === value}
                  onChange={() => setRoundTrip(value)}
                />
                {text}
              </label>
            ))}
          </fieldset>
        </div>
        <p className="mt-2 text-xs text-[#6b8791]">
          {roundTrip
            ? 'Round trip: one price for the outbound and the return flight together.'
            : 'One way: the outbound flight only, with no return.'}
          {' '}Adults only, up to {MAX_ADULTS}; no multi-city trips.
        </p>

        <div className="grid gap-x-4 md:grid-cols-2">
          <CountryPicker id={`${ids}-country`} label="Departure country (optional)" value={departureCountry}
            countries={countries} onChange={chooseDepartureCountry} />
          <CountryPicker id={`${ids}-arrival-country`} label="Arrival country (optional)" value={arrivalCountry}
            countries={countries} onChange={chooseArrivalCountry} />
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <AirportSearch
              key={`from-${departureCountry}-${originBox}`}
              kind="departure"
              label="From"
              country={departureCountry}
              defaultValue={departureHint}
              initialAirport={originSeed}
              onSelect={setOrigin}
              onTextChange={() => { touched.current.origin = true }}
              fetchImpl={airportFetchImpl}
              required
            />
            <FieldError id={describe('origin')} message={errors.origin} />
            <NearbyAirports place={start.departurePlace} kind="departure" selectedId={origin?.id ?? null}
              onChoose={pickNearby('origin')} onSuggested={preselect('origin')} fetchImpl={airportFetchImpl} />
          </div>
          <div>
            <AirportSearch
              key={`to-${arrivalCountry}-${destinationBox}`}
              kind="arrival"
              label="To"
              country={arrivalCountry}
              defaultValue={arrivalHint}
              initialAirport={destinationSeed}
              onSelect={setDestination}
              onTextChange={() => { touched.current.destination = true }}
              fetchImpl={airportFetchImpl}
              required
            />
            <FieldError id={describe('destination')} message={errors.destination} />
            <NearbyAirports place={start.arrivalPlace} kind="arrival" selectedId={destination?.id ?? null}
              onChoose={pickNearby('destination')} onSuggested={preselect('destination')} fetchImpl={airportFetchImpl} />
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor={`${ids}-depart`} className={labelClass}>Departure date</label>
            <input
              id={`${ids}-depart`}
              type="date"
              min={today}
              required
              value={departureDate}
              onChange={(e) => setDepartureDate(e.target.value)}
              aria-invalid={Boolean(errors.departureDate)}
              aria-describedby={describe('departureDate')}
              className={inputClass}
            />
            <FieldError id={describe('departureDate')} message={errors.departureDate} />
          </div>
          <div>
            <label htmlFor={`${ids}-return`} className={labelClass}>Return date</label>
            <input
              id={`${ids}-return`}
              type="date"
              min={departureDate || today}
              required={roundTrip}
              disabled={!roundTrip}
              value={roundTrip ? returnDate : ''}
              onChange={(e) => setReturnDate(e.target.value)}
              aria-invalid={Boolean(errors.returnDate)}
              aria-describedby={describe('returnDate')}
              className={`${inputClass} disabled:bg-[#eef3f4] disabled:text-[#8297a0]`}
            />
            <FieldError id={describe('returnDate')} message={errors.returnDate} />
          </div>
          <div>
            <label htmlFor={`${ids}-adults`} className={labelClass}>Adults</label>
            <select
              id={`${ids}-adults`}
              value={adults}
              onChange={(e) => setAdults(Number(e.target.value))}
              aria-invalid={Boolean(errors.adults)}
              aria-describedby={describe('adults')}
              className={inputClass}
            >
              {Array.from({ length: MAX_ADULTS }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n} {n === 1 ? 'adult' : 'adults'}</option>
              ))}
            </select>
            <FieldError id={describe('adults')} message={errors.adults} />
            {start.adultsCapped && (
              <p className="mt-1.5 text-xs text-[#6b8791]">
                Your trip has more than {MAX_ADULTS} travellers: search for up to {MAX_ADULTS} at a time.
              </p>
            )}
          </div>
          <div>
            <label htmlFor={`${ids}-cabin`} className={labelClass}>Cabin</label>
            <select
              id={`${ids}-cabin`}
              value={cabinClass}
              onChange={(e) => setCabinClass(e.target.value)}
              className={inputClass}
            >
              {CABIN_CLASSES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
            </select>
          </div>
        </div>

        <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-[#6b8791]">
            For information only: Rihla does not book flights, and flight prices are not added to the trip budget.
          </p>
          <button
            type="submit"
            disabled={status === 'loading' || unavailable}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#245c6a] px-6 py-3 text-sm font-semibold text-white hover:bg-[#1c4b57] disabled:opacity-60"
          >
            <Search size={16} aria-hidden="true" />
            {status === 'loading' ? 'Searching…' : 'Search flights'}
          </button>
        </div>
      </form>

      <div aria-live="polite" aria-busy={status === 'loading'} className="space-y-4">
        {unavailable && (
          <div role="status" className="flex items-start gap-3 rounded-2xl border border-[#d5e6e9] bg-[#f1f7f8] p-4 text-sm text-[#456774]">
            <Info size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold text-[#1c3544]">Real-time flight prices are not available here</p>
              <p className="mt-1">
                Rihla has no approved live flight data on this service, and it never shows made-up prices instead.
                Please check airline or travel websites directly. The rest of your trip plan is not affected.
              </p>
            </div>
          </div>
        )}

        {serverStatus?.available && serverStatus.dataMode && serverStatus.dataMode !== 'LIVE' && status === 'idle' && (
          <p className={`flex flex-wrap items-center gap-2 rounded-2xl border p-3 text-xs ${MODE_STYLES[serverStatus.dataMode]}`}>
            <DataModeBadge mode={serverStatus.dataMode} /> {DATA_MODES[serverStatus.dataMode].detail}
          </p>
        )}

        {status === 'loading' && (
          <p role="status" className="rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#456774]">
            Searching for flights… this can take up to half a minute.
          </p>
        )}

        {shown === 'stale' && (
          <p role="status" className="rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#456774]">
            Your search changed. Search again to see flights for it.
          </p>
        )}

        {shown === 'error' && failure && !isFlightsUnavailable(failure) && (
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p>{failure.message}</p>
              {failure.retryable && (
                <button type="button" onClick={run} className="mt-1 font-semibold underline">Try again</button>
              )}
            </div>
          </div>
        )}

        {shown === 'ready' && answer && (
          <>
            <div className={`rounded-2xl border p-4 text-sm ${MODE_STYLES[answer.dataMode]}`}>
              <p className="flex flex-wrap items-center gap-2 font-semibold">
                <DataModeBadge mode={answer.dataMode} /> {DATA_MODES[answer.dataMode].title}
                {answer.provider && <span className="font-normal">from {answer.provider}</span>}
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
                {answer.notices.map((notice) => <li key={notice}>{notice}</li>)}
              </ul>
              {answer.retrievedAt && (
                <p className="mt-2 text-xs opacity-80">Retrieved {answer.retrievedAt.replace('T', ' ').replace('Z', ' UTC')}</p>
              )}
            </div>

            {offers.length === 0 ? (
              <p className="rounded-2xl bg-[#f1f7f8] p-4 text-sm text-[#456774]">
                No flights found for this search. Try other dates or a nearby airport.
              </p>
            ) : (
              <>
                {comparison.length > 0 && (
                  <div aria-label="Cheapest versus fastest" className="space-y-1 rounded-2xl border border-[#d5e6e9] bg-white p-4 text-sm text-[#1c3544]">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#6b8791]">
                      Cheapest vs fastest{answer.dataMode !== 'LIVE' && ` · ${DATA_MODES[answer.dataMode].label} data: simulated, not bookable`}
                    </p>
                    {comparison.map((entry) => <CompareLine key={entry.currency} entry={entry} showCurrency={comparison.length > 1} />)}
                  </div>
                )}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-sm text-[#456774]">
                    <p>
                      {offers.length} {offers.length === 1 ? 'offer' : 'offers'}
                      {answer.totalOffers > offers.length && ` (of ${answer.totalOffers})`}
                    </p>
                    {searchSummary(answer.query) && <p className="text-xs">{searchSummary(answer.query)}</p>}
                  </div>
                  <label className="flex items-center gap-2 text-xs font-semibold text-[#456774]">
                    Sort by
                    <select
                      value={order}
                      onChange={(e) => setOrder(e.target.value)}
                      className="rounded-xl border border-[#d5e6e9] bg-white px-3 py-2 text-sm font-normal text-[#1c3544]"
                    >
                      <option value="price-asc">Lowest price</option>
                      <option value="price-desc">Highest price</option>
                      <option value="duration">Shortest travel time</option>
                    </select>
                  </label>
                </div>
                {!answer.comparable && (
                  <p className="flex items-start gap-2 rounded-2xl bg-amber-50 p-3 text-xs text-amber-900">
                    <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                    These offers are in different currencies. They are sorted within each currency and not compared
                    across currencies.
                  </p>
                )}
                <ol className="space-y-4">
                  {offers.map((offer) => (
                    <li key={offer.id}>
                      <FlightOfferCard
                        offer={offer}
                        cheapest={cheapest[offer.currency]?.id === offer.id}
                        fastest={fastest[offer.currency]?.id === offer.id}
                      />
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </div>
    </section>
  )
}
