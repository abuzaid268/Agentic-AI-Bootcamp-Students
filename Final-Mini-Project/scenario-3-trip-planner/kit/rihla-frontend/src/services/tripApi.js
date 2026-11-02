function buildTripMessage(trip) {
  const details = [
    `Plan a trip to ${trip.destination}.`,
    `Departure date: ${trip.departureDate}.`,
    `Return date: ${trip.returnDate}.`,
    `Number of travellers: ${trip.travellers}.`,
    `Total budget: ${trip.budget} USD.`,
  ]

  if (trip.interests?.length) {
    details.push(`Travel interests: ${trip.interests.join(', ')}.`)
  }

  if (trip.customPreferences?.trim()) {
    details.push(`Additional preferences and requests: ${trip.customPreferences.trim()}`)
  }

  return details.join('\n')
}

// The form's own fields, sent as they are: the backend uses them exactly (the
// selected interests are never re-read from the message by an LLM).
export function buildTripForm(trip) {
  return {
    destination: trip.destination.trim(),
    start_date: trip.departureDate,
    end_date: trip.returnDate,
    travellers: Number(trip.travellers),
    budget: Number(trip.budget),
    currency: 'USD',
    interests: [...(trip.interests || [])],
    preferences: trip.customPreferences?.trim() || null,
  }
}

// FastAPI's 422 detail is a list of {loc, msg}: show the messages, not "Request failed".
function validationMessage(detail) {
  if (!Array.isArray(detail)) return null
  const messages = detail
    .map((item) => String(item?.msg || '').replace(/^Value error, /, ''))
    .filter(Boolean)
  return messages.length ? `Please check the trip details: ${messages.join(' ')}` : null
}

const STATUS_MESSAGES = {
  402: 'The AI provider declined the request (payment required). No trip was generated.',
  503: 'The trip planning service is temporarily unavailable. No trip was generated, please try again later.',
}

export async function createTrip(trip, sessionId) {
  let response

  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        message: buildTripMessage(trip),
        trip: buildTripForm(trip),
      }),
    })
  } catch {
    throw new Error('Could not reach the Rihla backend. Check that it is running, then try again.')
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}). No trip was generated.`

    try {
      const error = await response.json()
      if (typeof error.detail === 'string') detail = error.detail
      const invalid = response.status === 422 ? validationMessage(error.detail) : null
      if (invalid) throw new Error(invalid)
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('Please check the trip details')) throw err
      // Keep the HTTP error message.
    }

    throw new Error(STATUS_MESSAGES[response.status] || detail)
  }

  try {
    return await response.json()
  } catch {
    throw new Error('The planner returned an unreadable response. No trip was generated.')
  }
}

// POST /api/chat with a change to the itinerary on screen. `baseVersion` is the plan_version it shows: the
// backend refuses a change made on an older version. Resolves with the backend's answer whatever it is (a
// revised itinerary, a question, a refusal); throws only when there is no answer, and nothing was changed.
const REVISION_STATUS_MESSAGES = {
  402: 'The AI provider declined the request (payment required).',
  503: 'The trip planning service is temporarily unavailable, please try again later.',
}

export async function reviseTrip(sessionId, message, baseVersion) {
  let response
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, revision: true, base_version: baseVersion || null }),
    })
  } catch {
    throw new Error('Could not reach the Rihla backend. Your itinerary was not changed.')
  }
  if (!response.ok) {
    const detail = await readError(response, `The change failed (${response.status}).`)
    throw new Error(`${REVISION_STATUS_MESSAGES[response.status] || detail} Your itinerary was not changed.`)
  }
  const body = await response.json().catch(() => null)
  if (!body || typeof body !== 'object') {
    throw new Error('The planner returned an unreadable response. Your itinerary was not changed.')
  }
  return body
}

async function readError(response, fallback) {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string' && body.detail) return body.detail
  } catch {
    // keep the fallback
  }
  return fallback
}

const APPROVE_ERRORS = {
  400: 'This approval does not belong to the current itinerary. Plan the trip again to approve it.',
  403: 'This itinerary did not pass verification (or changed after it), so it cannot be approved.',
  404: 'There is no approval waiting for this itinerary any more (the server may have restarted). Plan the trip again.',
}

// POST /api/approve: saves a VERIFIED itinerary in the Rihla Trip Store. Resolves only after the backend
// confirmed the save; a repeat of the same approval returns the trip already saved, never a second one.
export async function approveTrip(sessionId, actionId) {
  let response
  try {
    response = await fetch('/api/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, action_id: actionId, approved: true }),
    })
  } catch {
    throw new Error('Could not reach the Rihla backend. Your trip was not saved; try again.')
  }
  if (!response.ok) {
    const detail = await readError(response, `Approval failed (${response.status}). The trip was not saved.`)
    throw new Error(APPROVE_ERRORS[response.status] || detail)
  }
  const body = await response.json().catch(() => null)
  if (body?.status !== 'approved' || !body?.trip?.trip_id) {
    throw new Error('The backend did not confirm the save. The trip was not marked as approved.')
  }
  return { trip: body.trip, alreadyApproved: body.already_approved === true, message: body.message || '' }
}

async function getJson(url, what) {
  let response
  try {
    response = await fetch(url)
  } catch {
    throw new Error(`Could not reach the Rihla backend to load ${what}.`)
  }
  if (!response.ok) {
    throw new Error(await readError(response, `Loading ${what} failed (${response.status}).`))
  }
  try {
    return await response.json()
  } catch {
    throw new Error(`The backend returned unreadable ${what}.`)
  }
}

// GET /api/trips: the approved trips saved in the Rihla Trip Store (summaries).
export async function listApprovedTrips() {
  const body = await getJson('/api/trips', 'your saved trips')
  return Array.isArray(body?.trips) ? body.trips : []
}

// GET /api/trips/{id}: one approved trip with its full itinerary.
export async function getApprovedTrip(tripId) {
  return getJson(`/api/trips/${encodeURIComponent(tripId)}`, 'the saved trip')
}
