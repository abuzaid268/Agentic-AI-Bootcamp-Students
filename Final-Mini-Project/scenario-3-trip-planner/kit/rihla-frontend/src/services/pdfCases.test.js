import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { describe, it } from 'node:test'

import { storeTripResult } from './myTrips.js'
import { pdfModel, renderItineraryPdf } from './pdfExport.js'
import { applyRevision } from './tripRevision.js'

// The PDF is built from what the dashboard shows (TripDashboard: { aiResult, request, approval }) by the one PDF
// implementation (pdfExport.js). Three cases: a new itinerary, an approved trip from My Trips, an applied WHAT IF.

const act = (name, start, end, cost, notes) => ({ name, start_time: start, end_time: end, estimated_cost: cost,
  source_url: 'https://en.wikivoyage.org/wiki/Istanbul', ...(notes ? { notes } : {}) })
const ITINERARY = { destination: 'Istanbul', currency: 'USD', travellers: 1, budget_total: 900, estimated_total: 41,
  days: [{ date: '2026-11-20', activities: [act('Pera Museum', '09:00', '10:30', 15), act('Galata Convent', '11:00', '12:00', 26)] },
    { date: '2026-11-21', activities: [act('Osman Gourmet Restaurant', '12:00', '13:00', null, 'Opening hours unknown: check before you go')] }] }
const NEW_PLAN = {
  session_id: 's1', status: 'verification_required', plan_version: 'v1', itinerary: ITINERARY, pending_action: null,
  verification: { status: 'UNKNOWN', state: 'unverifiable', counts: { confirmed_problems: 0, unverifiable: 2, advice: 0 },
    findings: [{ state: 'unverifiable', explanation: 'Osman Gourmet Restaurant: cost unknown (no price in the sources).' }] },
  summary: { limitations: ['No usable price in the sources for: Osman Gourmet Restaurant. Its cost is unknown, not zero.'] },
  budget: { planned_known_total: 41 },
}
const REQUEST = { destination: 'Istanbul', travellers: 1, interests: ['History & Culture'] }

function render(input) {
  const model = pdfModel(input)
  const text = Buffer.from(renderItineraryPdf(model).output('arraybuffer')).toString('latin1')
  return { model, text }
}

describe('PDF of the itinerary on screen', () => {
  it('a newly generated itinerary: its activities, costs, verification and warnings; a draft, never approved', () => {
    const { model, text } = render({ aiResult: NEW_PLAN, request: REQUEST, approval: null })
    assert.equal(text.slice(0, 5), '%PDF-')
    assert.equal(model.status.label, 'Draft - Not Verified')
    for (const s of ['Istanbul itinerary', 'Pera Museum', '09:00', 'Galata Convent', 'Osman Gourmet Restaurant',
      'Price unknown', '$900.00', 'UNKNOWN', 'cost unknown', 'DRAFT - NOT VERIFIED']) assert.ok(text.includes(s), s)
    assert.ok(!text.includes('Approved'))
  })

  it('an approved trip from My Trips: the Trip Store itinerary, labelled with its trip ID', () => {
    const record = { trip_id: 'TRIP-3007', created_at: '2026-11-02T12:00:00Z', itinerary: ITINERARY }
    const local = { aiResult: NEW_PLAN, approval: { trip_id: 'TRIP-3007', basis: 'recorded' } }
    const result = storeTripResult(record, local)
    const { model, text } = render({ aiResult: result, request: REQUEST, approval: result.approval })
    assert.equal(model.status.label, 'Approved · Saved trip TRIP-3007')
    assert.match(model.status.detail, /recorded data, not live sources/) // never "verified" on recorded data
    assert.ok(text.includes('TRIP-3007') && text.includes('Pera Museum') && !text.includes('DRAFT - NOT VERIFIED'))
    assert.deepEqual(model.warnings, NEW_PLAN.summary.limitations) // the copy matches the store: its warnings apply
  })

  it('a stale browser copy never adds another version\'s warnings, costs or verification to a saved trip', () => {
    const saved = { ...ITINERARY, budget_total: 630, days: [ITINERARY.days[0]] } // what was approved
    const result = storeTripResult({ trip_id: 'TRIP-9', itinerary: saved }, { aiResult: NEW_PLAN, approval: { trip_id: 'TRIP-9' } })
    const { model, text } = render({ aiResult: result, request: {}, approval: result.approval })
    assert.deepEqual(model.warnings, [])
    assert.equal(model.verification.findings.length, 0)
    assert.equal(model.days.length, 1)
    assert.ok(text.includes('$630.00') && !text.includes('Osman Gourmet Restaurant'))
    assert.match(model.status.detail, /^Approved by you and saved/) // the basis is not known: not claimed
  })

  it('an applied WHAT IF: the revised activities, times and budget, and the earlier approval is not carried over', () => {
    const approvedBefore = { trip_id: 'TRIP-1' }
    const response = { // POST /api/whatif/apply: a revised plan, through the approval gate (not eligible here)
      session_id: 's1', status: 'verification_required', plan_version: 'v2', pending_action: null,
      revision: { outcome: 'revised', changes: ['Day 1 (Fri 20 Nov) now starts at 12:00.'] },
      whatif: { type: 'delay', applied: true, title: 'What if you arrived 3 hours late?' },
      itinerary: { ...ITINERARY, budget_total: 630, days: [
        { date: '2026-11-20', activities: [act('Pera Museum', '12:00', '13:30', 15), act('Müze Gazhane', '14:00', '15:00', 0)] },
        ITINERARY.days[1]] },
      verification: { status: 'UNKNOWN', state: 'unverifiable', findings: [] }, summary: { limitations: [] },
    }
    const next = applyRevision({ ...NEW_PLAN, approval: approvedBefore }, response)
    assert.equal(next.result.approval, undefined) // a new version is never the approved one
    // the dashboard resets its approval state with the new version (showRevised): approval = null
    const { model, text } = render({ aiResult: next.result, request: REQUEST, approval: null })
    assert.notEqual(model.status.kind, 'approved')
    assert.ok(!text.includes('TRIP-1'))
    for (const s of ['12:00', 'Müze Gazhane', '$630.00']) assert.ok(text.includes(s), s)
    assert.ok(!text.includes('Galata Convent')) // the replaced activity is not in the PDF
  })
})
