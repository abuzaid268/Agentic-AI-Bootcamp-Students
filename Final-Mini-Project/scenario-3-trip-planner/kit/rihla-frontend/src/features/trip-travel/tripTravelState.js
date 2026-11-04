// Pure helpers for TripTravelInfo: what the weather and flight boxes get from a trip (FROM -> TO and dates).

// Open-Meteo's forecast reaches 16 days, today included (app/weather FORECAST_DAYS).
export const FORECAST_DAYS = 16

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const isIsoDate = (value) => typeof value === 'string' && ISO_DATE.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`))
const textOrNull = (value) => (typeof value === 'string' && value.trim() ? value.replace(/\s+/g, ' ').trim() : null)
const isCoordinate = (value, bound) => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= bound

export function addDays(iso, days) {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

// A place from DestinationSearch's onSelect ({ name, country, countryCode, latitude, longitude, label, ... }), kept
// only when it is one: coordinates are never guessed from a typed name.
export function placeFrom(raw) {
  if (!raw || typeof raw !== 'object') return null
  const name = textOrNull(raw.name)
  if (!name) return null
  return {
    name,
    country: textOrNull(raw.country),
    countryCode: typeof raw.countryCode === 'string' && /^[A-Za-z]{2}$/.test(raw.countryCode) ? raw.countryCode.toUpperCase() : null,
    latitude: isCoordinate(raw.latitude, 90) ? raw.latitude : null,
    longitude: isCoordinate(raw.longitude, 180) ? raw.longitude : null,
    label: textOrNull(raw.label) || [name, textOrNull(raw.country)].filter(Boolean).join(', '),
  }
}

// The city part of a typed destination ("Amman, Jordan" -> "Amman"), for a trip saved before places were chosen.
export function cityFromText(text) {
  return textOrNull(String(text ?? '').split(',')[0]) || ''
}

// The dates to ask the weather for: the trip's days that have a forecast. The server refuses a range that ends
// past the horizon, so a longer trip is cut to the days that have one (and says so); a trip that starts after the
// horizon is not asked about at all ('later': no forecast exists yet).
export function weatherWindow(startDate, endDate, today) {
  if (!isIsoDate(startDate) || !isIsoDate(today)) return { status: 'no_dates' }
  const end = isIsoDate(endDate) && endDate >= startDate ? endDate : startDate
  if (end < today) return { status: 'past' }
  const start = startDate < today ? today : startDate
  const horizon = addDays(today, FORECAST_DAYS - 1)
  if (start > horizon) return { status: 'later', horizon }
  return { status: end > horizon ? 'partial' : 'full', startDate: start, endDate: end > horizon ? horizon : end, horizon }
}

// Everything TripTravelInfo shows, from what the parent page knows about the trip. Flight values are only starting
// text and dates for FlightSearch: no airport is chosen here, and nothing is priced into the trip.
export function travelInfoPlan({ destination, destinationText, origin, startDate, endDate, travellers, today }) {
  const to = placeFrom(destination)
  const from = placeFrom(origin)
  const toLabel = to?.label || textOrNull(destinationText) || null
  const hasCoordinates = Boolean(to && to.latitude !== null && to.longitude !== null)
  const window = weatherWindow(startDate, endDate, today)
  const flights = {
    departureHint: from?.name || '',
    departureCountry: from?.countryCode || '',
    arrivalHint: to?.name || cityFromText(destinationText),
    departureDate: isIsoDate(startDate) && startDate >= today ? startDate : '',
    returnDate: isIsoDate(endDate) && isIsoDate(startDate) && startDate >= today && endDate >= startDate ? endDate : '',
    adults: Number.isInteger(Number(travellers)) && Number(travellers) >= 1 ? Number(travellers) : 1,
  }
  return {
    fromLabel: from?.label || null,
    toLabel,
    weather: hasCoordinates && window.startDate
      ? { latitude: to.latitude, longitude: to.longitude, startDate: window.startDate, endDate: window.endDate, locationName: to.name }
      : null,
    weatherStatus: !toLabel ? 'no_destination' : !hasCoordinates ? 'no_coordinates' : window.status,
    weatherHorizon: window.horizon || null,
    flights,
    // A new trip (another place, other dates or party) starts the flight form over; the same trip keeps its choices.
    flightsKey: JSON.stringify([flights.departureHint, flights.departureCountry, flights.arrivalHint,
      flights.departureDate, flights.returnDate, flights.adults]),
  }
}
