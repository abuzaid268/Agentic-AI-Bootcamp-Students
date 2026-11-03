import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { acceptanceOptions, approvalOptions, sendAcceptance } from './approval.js'
import { filterTrips, lostApprovals, mergeTrips, STATUS_LABELS, storeTripResult } from './myTrips.js'
import { markApproved, summarizeSavedTrip } from './savedTrips.js'
import { pdfModel, pdfStatus } from './pdfExport.js'
import { revisionBlockedReason } from './tripRevision.js'
import { getVerificationState, isValidTripResult } from './tripResult.js'

// The shape app/main.py returns for a plan the verifier left UNKNOWN (app/approval_policy.acceptance).
const ITINERARY = { destination: 'Amman', currency: 'USD', travellers: 2, budget_total: 500, estimated_total: 30,
  days: [{ date: '2026-11-05', activities: [
    { name: 'Amman Citadel', start_time: '09:00', end_time: '11:00', estimated_cost: 30 },
    { name: 'Rainbow Street', start_time: '12:00', end_time: '13:30', estimated_cost: null }] }] }
const OFFER = { acceptance_id: 'acc-1', type: 'save_trip_unverified', mode: 'accepted_with_limitations',
  label: 'Saved · Not Fully Verified', verified: false, verification_status: 'UNKNOWN',
  limitations: ['Opening hours could not be confirmed: Rainbow Street, 2026-11-05',
    'Price unavailable for 1 planned item(s): Rainbow Street. They are not counted in the known subtotal, so the final budget cannot be guaranteed.'],
  confirmed_problems: [],
  costs: { currency: 'USD', known_subtotal: '30.00', unpriced_items: ['Rainbow Street'], budget_guaranteed: false } }
const RESULT = { status: 'verification_required', session_id: 's-1', itinerary: ITINERARY, pending_action: null,
  pending_acceptance: OFFER, verification: { status: 'UNKNOWN', verified: false, state: 'unverifiable', findings: [] } }

function fakeFetch(status, body) {
  const calls = []
  const impl = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) })
    return { ok: status >= 200 && status < 300, status, json: async () => body }
  }
  return { calls, impl }
}

function memoryStorage() {
  const data = new Map()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)) }
}

describe('accepting a plan that is not eligible for approval', () => {
  it('offers "Accept & Save with Limitations" for UNKNOWN, "Save Unverified Draft" for FAIL, nothing when approvable', () => {
    const a = acceptanceOptions(RESULT)
    assert.equal(approvalOptions(RESULT).canApprove, false)
    assert.equal(a.canAccept, true)
    assert.equal(a.button, 'Accept & Save with Limitations')
    assert.equal(a.label, 'Saved · Not Fully Verified')
    assert.deepEqual(a.costs.unpriced_items, ['Rainbow Street'])
    const draft = acceptanceOptions({ ...RESULT, pending_acceptance: { ...OFFER, mode: 'unverified_draft',
      confirmed_problems: ['Day 1 runs past closing time.'] } })
    assert.equal(draft.button, 'Save Unverified Draft')
    assert.deepEqual(draft.problems, ['Day 1 runs past closing time.'])
    const eligible = { ...RESULT, status: 'pending_approval', pending_acceptance: OFFER,
      pending_action: { action_id: 'a', type: 'save_trip', verification_status: 'verified' } }
    assert.equal(acceptanceOptions(eligible).canAccept, false) // the verified path always wins
    assert.equal(acceptanceOptions({ ...RESULT, pending_acceptance: { ...OFFER, mode: 'verified' } }).canAccept, false)
  })

  it('reports a save only with the trip ID the backend returned, and sends the explicit acknowledgment', async () => {
    const ok = fakeFetch(200, { status: 'saved_unverified', reply: 'Saved as TRIP-3001.',
      result: { trip_id: 'TRIP-3001', mode: 'accepted_with_limitations' } })
    const out = await sendAcceptance({ sessionId: 's-1', acceptanceId: 'acc-1', mode: OFFER.mode, acknowledged: true },
      ok.impl)
    assert.deepEqual(ok.calls[0], { url: '/api/accept', body: { session_id: 's-1', acceptance_id: 'acc-1',
      mode: 'accepted_with_limitations', acknowledged: true } })
    assert.equal(out.status, 'saved')
    assert.equal(out.tripId, 'TRIP-3001')

    const noId = fakeFetch(200, { status: 'saved_unverified', reply: 'Saved.', result: null })
    await assert.rejects(sendAcceptance({ sessionId: 's', acceptanceId: 'a', mode: OFFER.mode, acknowledged: true },
      noId.impl))
    const failed = fakeFetch(200, { status: 'save_failed', reply: 'The Trip Store did not save this plan.' })
    await assert.rejects(sendAcceptance({ sessionId: 's', acceptanceId: 'a', mode: OFFER.mode, acknowledged: true },
      failed.impl), /did not save/)
    const conflict = fakeFetch(409, { detail: 'The confirmation does not match this plan\'s status. Nothing was saved.' })
    await assert.rejects(sendAcceptance({ sessionId: 's', acceptanceId: 'a', mode: 'x', acknowledged: true },
      conflict.impl), /Nothing was saved/)
    const offline = async () => { throw new TypeError('network') }
    await assert.rejects(sendAcceptance({ sessionId: 's', acceptanceId: 'a', mode: OFFER.mode, acknowledged: true },
      offline), /Nothing was saved/)
  })

  it('keeps the save status in this browser: saved, never verified', () => {
    const storage = memoryStorage()
    const entry = markApproved(RESULT, { destination: 'Amman' },
      { trip_id: 'TRIP-3001', mode: 'accepted_with_limitations' }, storage)
    assert.equal(entry.approval.mode, 'accepted_with_limitations')
    const summary = summarizeSavedTrip(entry)
    assert.equal(summary.verified, false)
    assert.equal(summary.backendApproved, true)
  })
})

describe('My Trips and the PDF for a trip saved with limitations', () => {
  it('labels store trips by how they were saved, and files them under "Not verified"', () => {
    const cards = mergeTrips([
      { trip_id: 'TRIP-1', destination: 'Amman', save_mode: 'accepted_with_limitations', created_at: '2026-11-02T10' },
      { trip_id: 'TRIP-2', destination: 'Rome', save_mode: 'unverified_draft', created_at: '2026-11-02T09' },
      { trip_id: 'TRIP-3', destination: 'Istanbul', save_mode: 'approved', created_at: '2026-11-02T08' },
    ], [], { storeAvailable: true })
    assert.deepEqual(cards.map((c) => c.status), ['saved_limited', 'saved_draft', 'approved'])
    assert.equal(STATUS_LABELS.saved_limited, 'Saved · Not Fully Verified')
    assert.equal(STATUS_LABELS.saved_draft, 'Saved · Unverified Draft')
    assert.deepEqual(filterTrips(cards, '', 'Verified').map((c) => c.tripId), ['TRIP-3'])
    assert.deepEqual(filterTrips(cards, '', 'Not verified').map((c) => c.tripId), ['TRIP-1', 'TRIP-2'])
  })

  it('an old local copy with a reused trip id is never paired with a different store trip', () => {
    // a store that lost its trips gave TRIP-3001 to a new trip: yesterday's copy of the old TRIP-3001 must not lend
    // its request details or status to it (seen in the browser: the old dates shown above the new itinerary)
    const store = [{ trip_id: 'TRIP-3001', destination: 'Amman', start_date: '2026-12-14', end_date: '2026-12-16',
      save_mode: 'accepted_with_limitations', created_at: '2026-11-03T10' }]
    const old = { id: 'old', destination: 'Amman', startDate: '2026-11-10', endDate: '2026-11-14', savedAt: '2026-11-02',
      approval: { trip_id: 'TRIP-3001', mode: 'accepted_with_limitations' } }
    const same = { id: 'new', destination: 'Amman', startDate: '2026-12-14', endDate: '2026-12-16', savedAt: '2026-11-03',
      approval: { trip_id: 'TRIP-3001', mode: 'accepted_with_limitations' } }
    const cards = mergeTrips(store, [old, same], { storeAvailable: true })
    const storeCard = cards.find((c) => c.source === 'store')
    assert.equal(storeCard.localId, 'new') // only the copy of this very trip
    const oldCard = cards.find((c) => c.localId === 'old')
    assert.equal(oldCard.source, 'local')
    assert.match(oldCard.note, /no longer lists it/)
    assert.equal(mergeTrips(store, [old], { storeAvailable: true }).find((c) => c.source === 'store').localId, null)
  })

  it('a local copy of a lost store trip keeps its saved status', () => {
    const local = [{ id: 'l', destination: 'Amman', savedAt: '2026-11-02',
      approval: { trip_id: 'TRIP-9', mode: 'accepted_with_limitations' } }]
    const cards = mergeTrips([], local, { storeAvailable: true })
    assert.equal(cards[0].status, 'saved_limited')
    assert.match(cards[0].note, /^Saved, but the Trip Store no longer lists it/)
    assert.equal(lostApprovals(cards, { storeAvailable: true }).length, 1)
    // while the store list is still loading, nothing is said to be lost
    assert.equal(mergeTrips([], local, { storeAvailable: true, storeLoading: true })[0].note, null)
  })

  it('opens a saved trip with its status and limitations from the Trip Store record, not this browser', () => {
    const saveInfo = { mode: 'accepted_with_limitations', label: 'Saved · Not Fully Verified', verified: false,
      verification_status: 'UNKNOWN', limitations: OFFER.limitations, confirmed_problems: [], costs: OFFER.costs }
    const record = { trip_id: 'TRIP-1', created_at: '2026-11-02', itinerary: { ...ITINERARY, rihla_save: saveInfo } }
    const opened = storeTripResult(record, { aiResult: RESULT, approval: { trip_id: 'TRIP-1', basis: 'live' } })
    assert.equal(opened.status, 'saved_limited')
    assert.equal(isValidTripResult(opened), true) // the dashboard shows it (it once showed "No trip to show yet")
    assert.equal(getVerificationState(opened).level === 'verified', false)
    assert.equal(opened.approval.mode, 'accepted_with_limitations')
    assert.equal(opened.approval.basis, undefined) // never a verified basis
    assert.equal(opened.verification.status, 'UNKNOWN') // this browser's copy of the same plan adds its report
    assert.match(opened.message, /not fully verified/)
    assert.match(revisionBlockedReason(opened), /saved in My Trips as it is/)

    const status = pdfStatus(opened, opened.approval)
    assert.equal(status.kind, 'limited')
    assert.equal(status.label, 'Saved · Not Fully Verified · Trip TRIP-1')
    assert.doesNotMatch(status.label, /Approved|^Verified/)

    // On another device (no local copy): the PDF lists the saved limitations and the unpriced item, never as free.
    const bare = storeTripResult(record, null)
    const model = pdfModel({ aiResult: bare, approval: bare.approval })
    assert.equal(model.verification.label, 'UNKNOWN · not fully verified')
    assert.ok(model.verification.findings.some((f) => f.includes('Rainbow Street')))
    assert.deepEqual(model.budget.unknownNames, ['Rainbow Street'])
    assert.ok(model.budget.lines.some(([k, v]) => k === 'Known planned costs (entry fees and planned meals)'
      && v.includes('30')))
    assert.ok(model.budget.lines.some(([k, v]) => k === 'Final budget' && /cannot be guaranteed/i.test(v)))
  })

  it('an unverified draft is a draft in the PDF, with its saved trip ID', () => {
    const status = pdfStatus({ itinerary: ITINERARY }, { trip_id: 'TRIP-2', mode: 'unverified_draft' })
    assert.equal(status.kind, 'draft')
    assert.equal(status.label, 'Saved · Unverified Draft · Trip TRIP-2')
  })
})
