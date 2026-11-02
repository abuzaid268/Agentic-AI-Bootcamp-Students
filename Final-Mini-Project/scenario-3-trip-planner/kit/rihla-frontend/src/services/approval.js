// Client for POST /api/approve (app/main.py). The backend saves a trip to the Trip Store, through the MCP
// save_trip tool, only for the pending save_trip action of a plan its approval policy made eligible
// (app/approval_policy.py): "verified" (every check passed on live evidence) or "verified_on_records" (every check
// passed, on recorded data, said so). UNKNOWN and FAIL plans never get an action.
import { requireSession } from '../auth/authApi.js'

export const APPROVABLE_STATUSES = ['verified', 'verified_on_records']

// What the dashboard may offer for this result: backend approval only for an eligible pending action; otherwise
// the traveller can keep it as a local draft. `basis` is the evidence the approval relies on (live | recorded).
export function approvalOptions(result) {
  const action = result?.pending_action
  const canApprove = Boolean(
    result?.status === 'pending_approval'
    && action?.type === 'save_trip'
    && APPROVABLE_STATUSES.includes(action?.verification_status)
    && action?.action_id
    && result?.session_id
  )
  const basis = !canApprove ? null : action.verification_status === 'verified' ? 'live' : 'recorded'
  return { canApprove, canAcceptDraft: !canApprove, basis, disclosure: canApprove ? action.disclosure || null : null }
}

const STATUS_MESSAGES = {
  400: 'This approval request no longer matches the planned trip. Plan the trip again to approve it.',
  403: 'Approval refused: the trip has not passed verification, or it changed after verification.',
  404: 'There is no approval waiting for this trip on the server (it may have restarted, or the trip was already decided). Plan the trip again to approve it.',
  422: 'The approval request was incomplete.',
}

// The trip ID the Trip Store returned, from either answer shape; never made up here.
function savedTripId(body) {
  const id = body?.result?.trip_id ?? body?.trip?.trip_id ?? body?.trip?.id
  return typeof id === 'string' && id ? id : null
}

// Returns { status: 'approved' | 'rejected', message, trip?, tripId, alreadyApproved } or throws an Error whose
// message is safe to show (AuthRequiredError when the session ended). Never reports approval without the backend
// confirming it with a trip ID. Two answer shapes are understood:
// - the older app/main.py: { status: 'approved' | 'rejected', message, trip: { trip_id } }
// - the bootcamp contract (common/CONTRACT.md): a ChatResponse { status, reply, result: { trip_id } | null }, where
//   approval counts only with a result.trip_id, and approved:false with no result is a rejection.
export async function sendApproval({ sessionId, actionId, approved }, fetchImpl = globalThis.fetch) {
  let response
  try {
    response = await fetchImpl('/api/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, action_id: actionId, approved }),
    })
  } catch {
    throw new Error('Could not reach the Rihla backend. Nothing was approved, and your trip was not saved.')
  }

  await requireSession(response, 'Your session ended. Please log in again to approve this trip.')

  let body = null
  try {
    body = await response.json()
  } catch {
    // Not JSON: handled below as a failed or unexpected answer.
  }

  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : ''
    if (response.status === 503) {
      throw new Error(`The trip could not be saved on the server${detail ? `: ${detail}` : ''}. Nothing was approved.`)
    }
    throw new Error(
      `${STATUS_MESSAGES[response.status] || `Approval failed (${response.status}).`}${detail ? ` (${detail})` : ''}`
    )
  }

  const reply = typeof body?.reply === 'string' ? body.reply : ''
  const tripId = savedTripId(body)
  const alreadyApproved = body?.already_approved === true || /already saved/i.test(reply)

  if (body?.status === 'approved') {
    if (!tripId) throw new Error('The backend did not confirm the save. Nothing is shown as approved.')
    return { status: 'approved', message: reply || body.message || 'Trip saved successfully.',
      trip: body.trip ?? body.result ?? null, tripId, alreadyApproved }
  }
  if (body?.status === 'rejected') {
    return { status: 'rejected', message: reply || body.message || 'Trip was not saved.', tripId: null,
      alreadyApproved: false }
  }
  if (body && typeof body === 'object' && 'reply' in body) {
    if (approved && tripId) {
      return { status: 'approved', message: reply || 'Trip saved successfully.', trip: body.result, tripId, alreadyApproved }
    }
    if (!approved && !tripId) return { status: 'rejected', message: reply || 'Trip was not saved.', tripId: null, alreadyApproved: false }
    // save_failed, no_pending_action, already_decided: the backend's own words; nothing was approved.
    if (approved) throw new Error(reply || 'The server did not save the trip. Nothing was approved.')
  }
  throw new Error('The server gave an unexpected approval answer. Nothing is shown as approved.')
}

// A plan the approval policy did not make eligible can still be kept by the traveller, as their own decision, after
// reading its limitations (POST /api/accept, app/approval_policy.acceptance). It is never an approval: the saved
// trip says "Saved · Not Fully Verified" (facts missing) or "Saved · Unverified Draft" (confirmed problems).
export const ACCEPTANCE_MODES = ['accepted_with_limitations', 'unverified_draft']
export const ACCEPTANCE_LABELS = {
  accepted_with_limitations: 'Saved · Not Fully Verified',
  unverified_draft: 'Saved · Unverified Draft',
}

export function acceptanceOptions(result) {
  const offer = result?.pending_acceptance
  const canAccept = Boolean(
    ACCEPTANCE_MODES.includes(offer?.mode) && offer?.acceptance_id && result?.session_id
    && !approvalOptions(result).canApprove
  )
  if (!canAccept) return { canAccept: false }
  return {
    canAccept,
    acceptanceId: offer.acceptance_id,
    mode: offer.mode,
    label: ACCEPTANCE_LABELS[offer.mode],
    button: offer.mode === 'unverified_draft' ? 'Save Unverified Draft' : 'Accept & Save with Limitations',
    limitations: Array.isArray(offer.limitations) ? offer.limitations : [],
    problems: Array.isArray(offer.confirmed_problems) ? offer.confirmed_problems : [],
    costs: offer.costs || {},
  }
}

// POST /api/accept. With acknowledged: true resolves { status: 'saved', tripId, mode, message } only when the backend
// returned the Trip Store's trip ID; with acknowledged: false (a cancelled confirmation) resolves
// { status: 'not_saved' }. Anything else throws an Error whose message is safe to show; nothing is shown as saved.
export async function sendAcceptance({ sessionId, acceptanceId, mode, acknowledged }, fetchImpl = globalThis.fetch) {
  let response
  try {
    response = await fetchImpl('/api/accept', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, acceptance_id: acceptanceId, mode, acknowledged }),
    })
  } catch {
    throw new Error('Could not reach the Rihla backend. Nothing was saved.')
  }
  await requireSession(response, 'Your session ended. Please log in again to save this trip.')
  let body = null
  try {
    body = await response.json()
  } catch {
    // handled below
  }
  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : ''
    throw new Error(detail || `Saving failed (${response.status}). Nothing was saved.`)
  }
  const reply = typeof body?.reply === 'string' ? body.reply : ''
  const tripId = savedTripId(body)
  if (acknowledged && body?.status === 'saved_unverified' && tripId) {
    return { status: 'saved', tripId, mode: body.result?.mode || mode, message: reply,
      alreadySaved: /already saved/i.test(reply) }
  }
  if (!acknowledged && body?.status === 'not_saved') return { status: 'not_saved', message: reply }
  throw new Error(reply || 'The server did not save the trip. Nothing was saved.')
}
