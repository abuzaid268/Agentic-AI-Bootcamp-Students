import { isValidTripResult } from './tripResult.js'

// Trips saved in THIS browser only (localStorage): no account, no cloud copy,
// no sync between devices. The backend has no "list my trips" endpoint for the
// frontend yet, so this is the honest local substitute.
export const STORAGE_KEY = 'rihla.savedTrips.v1'
export const MAX_SAVED_TRIPS = 30

function defaultStorage() {
  try {
    return globalThis.localStorage ?? null
  } catch {
    return null // blocked storage (private mode, disabled site data)
  }
}

function readAll(storage) {
  if (!storage) return []
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || '[]')
    // Drop anything that is no longer a displayable trip (old format, hand-edited).
    return Array.isArray(parsed) ? parsed.filter(isSavedTrip) : []
  } catch {
    return []
  }
}

function writeAll(storage, trips) {
  if (!storage) throw new Error('This browser does not allow saving trips (storage is blocked).')
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(trips))
  } catch {
    throw new Error('The trip could not be saved: browser storage is full or blocked.')
  }
}

function isSavedTrip(entry) {
  return Boolean(
    entry
    && typeof entry === 'object'
    && typeof entry.id === 'string'
    && typeof entry.savedAt === 'string'
    && isValidTripResult(entry.aiResult)
  )
}

// Only what the dashboard needs to show the trip again; never tokens or keys.
function requestFields(request = {}) {
  return {
    destination: String(request.destination || ''),
    departureDate: String(request.departureDate || ''),
    returnDate: String(request.returnDate || ''),
    travellers: request.travellers ?? null,
    budget: request.budget ?? null,
    interests: Array.isArray(request.interests) ? request.interests.map(String) : [],
    customPreferences: String(request.customPreferences || ''),
  }
}

export function summarizeSavedTrip(entry) {
  const itinerary = entry.aiResult.itinerary
  const days = itinerary.days
  return {
    id: entry.id,
    savedAt: entry.savedAt,
    destination: itinerary.destination,
    startDate: days[0]?.date || null,
    endDate: days[days.length - 1]?.date || null,
    dayCount: days.length,
    activityCount: days.reduce((n, d) => n + (d.activities?.length || 0), 0),
    travellers: itinerary.travellers ?? null,
    budgetTotal: itinerary.budget_total ?? null,
    currency: itinerary.currency || 'USD',
    verified: Boolean(entry.approval?.trip_id) || (entry.aiResult.status === 'pending_approval'
      && entry.aiResult.pending_action?.verification_status === 'verified'),
    approval: entry.approval || null,
  }
}

export function listSavedTrips(storage = defaultStorage()) {
  return readAll(storage)
    .sort((a, b) => b.savedAt.localeCompare(a.savedAt))
}

export function getSavedTrip(id, storage = defaultStorage()) {
  return readAll(storage).find((entry) => entry.id === id) || null
}

// The session id identifies one generated result, so saving it twice updates
// the same entry instead of creating a duplicate.
export function saveTrip(aiResult, request, storage = defaultStorage(), now = new Date()) {
  if (!isValidTripResult(aiResult)) {
    throw new Error('Only a generated itinerary can be saved.')
  }

  const id = String(aiResult.session_id || request?.sessionId || `trip-${now.getTime()}`)
  const previous = readAll(storage).find((t) => t.id === id)
  const entry = {
    id,
    savedAt: now.toISOString(),
    request: requestFields(request),
    aiResult,
    // an approval, once confirmed by the backend, is kept when the same trip is saved again
    ...(previous?.approval ? { approval: previous.approval } : {}),
  }

  const others = readAll(storage).filter((t) => t.id !== id)
  if (others.length >= MAX_SAVED_TRIPS) {
    throw new Error(`You can keep up to ${MAX_SAVED_TRIPS} trips in this browser. Delete one to save another.`)
  }
  writeAll(storage, [entry, ...others])
  return entry
}

export function deleteSavedTrip(id, storage = defaultStorage()) {
  const trips = readAll(storage)
  const remaining = trips.filter((t) => t.id !== id)
  if (remaining.length !== trips.length) writeAll(storage, remaining)
  return remaining.length !== trips.length
}

// Logout: these copies belong to whoever was signed in, not to the next person using this browser. The
// approved trips themselves stay in the Rihla Trip Store (the record) and come back with the next sign-in.
export function clearSavedTrips(storage = defaultStorage()) {
  if (!storage) return
  try {
    storage.removeItem(STORAGE_KEY)
  } catch {
    // blocked storage holds nothing to clear
  }
}

export function isTripSaved(id, storage = defaultStorage()) {
  return Boolean(id) && readAll(storage).some((t) => t.id === id)
}

// Record in this browser that the backend approved and saved the trip (only after the backend confirmed it).
// The Trip Store is the record; this local copy keeps what the dashboard shows (interests, warnings) and lets
// My Trips show the trip when the store cannot be reached.
export function markApproved(aiResult, request, savedTrip, storage = defaultStorage(), now = new Date()) {
  if (!savedTrip?.trip_id) throw new Error('The trip was not saved by the backend.')
  const entry = saveTrip(aiResult, request, storage, now)
  const approved = { ...entry, approval: { trip_id: savedTrip.trip_id, approvedAt: now.toISOString() } }
  writeAll(storage, [approved, ...readAll(storage).filter((t) => t.id !== entry.id)])
  return approved
}
