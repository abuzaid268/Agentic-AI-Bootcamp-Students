import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { afterEach, describe, it } from 'node:test'

import { approveTrip, getApprovedTrip, listApprovedTrips } from './tripApi.js'
import { filterTrips, mergeTrips, STATUS_LABELS, storeTripResult } from './myTrips.js'
import { getSavedTrip, listSavedTrips, markApproved, saveTrip, summarizeSavedTrip } from './savedTrips.js'
import { approvalBlockedReason, getVerificationState, isValidTripResult } from './tripResult.js'
import { pdfModel, pdfStatus, pdfText, renderItineraryPdf } from './pdfExport.js'

const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch })

function respond(status, body) {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return { ok: status >= 200 && status < 300, status, json: async () => body }
  }
  return calls
}

function memoryStorage() {
  const data = new Map()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)) }
}

const ITINERARY = {
  destination: 'Tokyo', currency: 'USD', travellers: 2, budget_total: 1500, estimated_total: 20,
  days: [
    { date: '2026-11-10', activities: [
      { name: 'Hama-rikyū Gardens', start_time: '09:00', end_time: '10:30', estimated_cost: null,
        source_url: 'https://en.wikivoyage.org/wiki/Tokyo/Chuo#See', notes: 'Opening hours unknown: check before you go' },
      { name: 'Daiei', start_time: '12:00', end_time: '13:00', estimated_cost: 20,
        notes: 'By taxi or car from the previous stop: 5 min (walking: 36 min); OSRM driving time without traffic, fare not included' },
    ] },
    { date: '2026-11-11', activities: [] },
  ],
}
const UNVERIFIED = {
  session_id: 's-1', status: 'verification_required', itinerary: ITINERARY, pending_action: null,
  message: 'The itinerary could not be fully verified. No approval is allowed.',
  summary: { days: [{ date: '2026-11-10', activities: [
    { kind: 'see', meal: false, travel_minutes: null, travel_mode: null },
    { kind: 'eat', meal: true, travel_minutes: 5, travel_mode: 'driving' },
  ] }], limitations: ['No usable price in the sources for: Hama-rikyū Gardens. Their cost is unknown, not zero.'] },
  verification: { status: 'UNKNOWN', state: 'unverifiable', verified: false,
    counts: { confirmed_problems: 0, unverifiable: 2, advice: 1 },
    findings: [
      { code: 'hours_unknown', state: 'unverifiable', explanation: 'Hama-rikyū Gardens: opening hours unknown.' },
      { code: 'cost_unknown', state: 'unverifiable', explanation: 'Hama-rikyū Gardens: cost unknown.' },
      { code: 'ride_planned', state: 'advice', explanation: 'A ride is planned.' },
    ] },
  budget: { planned_known_total: '20.00', confidence: 'low', confidence_basis: '1 of 2 planned places have a price.',
    not_included: ['accommodation', 'flights and intercity transport'] },
}
const VERIFIED = {
  ...UNVERIFIED, status: 'pending_approval', message: 'Verified.',
  pending_action: { action_id: 'act-1', type: 'save_trip', verification_status: 'verified' },
}
const REQUEST = { destination: 'Tokyo', departureDate: '2026-11-10', returnDate: '2026-11-11', travellers: '2',
  budget: '1500', interests: ['Nature & Outdoors'] }

describe('approval', () => {
  it('sends the session and action ids and returns the saved trip', async () => {
    const calls = respond(200, { status: 'approved', trip: { trip_id: 'TRIP-3001' } })
    const out = await approveTrip('s-1', 'act-1')
    assert.equal(out.trip.trip_id, 'TRIP-3001')
    assert.equal(out.alreadyApproved, false)
    assert.equal(calls[0].url, '/api/approve')
    assert.deepEqual(JSON.parse(calls[0].options.body), { session_id: 's-1', action_id: 'act-1', approved: true })
  })

  it('reports a repeated approval as the same saved trip, not a new one', async () => {
    respond(200, { status: 'approved', trip: { trip_id: 'TRIP-3001' }, already_approved: true })
    assert.equal((await approveTrip('s-1', 'act-1')).alreadyApproved, true)
  })

  it('never treats an unconfirmed save as approved', async () => {
    respond(200, { status: 'approved' })
    await assert.rejects(approveTrip('s-1', 'act-1'), /did not confirm the save/)
  })

  it('explains each refusal', async () => {
    respond(403, { detail: 'Trip has not passed real verification.' })
    await assert.rejects(approveTrip('s', 'a'), /did not pass verification/)
    respond(404, { detail: 'No pending action for this session' })
    await assert.rejects(approveTrip('s', 'a'), /no approval waiting/)
    respond(503, { detail: 'Traveller ID is not configured: set TRAVEL_TRAVELLER_ID on the server.' })
    await assert.rejects(approveTrip('s', 'a'), /TRAVEL_TRAVELLER_ID/)
    globalThis.fetch = async () => { throw new TypeError('offline') }
    await assert.rejects(approveTrip('s', 'a'), /was not saved/)
  })

  it('an unverified result is not approvable and says why in the verifier\'s terms', () => {
    assert.equal(getVerificationState(UNVERIFIED).level, 'unverified')
    const why = approvalBlockedReason(UNVERIFIED)
    assert.match(why, /2 fact\(s\) could not be confirmed from the sources \(opening hours, prices\)/)
    assert.match(approvalBlockedReason({ verification: { counts: { confirmed_problems: 1 }, findings: [] } }),
      /1 confirmed problem/)
    assert.equal(getVerificationState(VERIFIED).level, 'verified')
  })
})

describe('saved trips', () => {
  it('lists and loads approved trips from the backend Trip Store', async () => {
    respond(200, { count: 1, trips: [{ trip_id: 'TRIP-3001', destination: 'Tokyo' }] })
    assert.equal((await listApprovedTrips())[0].trip_id, 'TRIP-3001')
    const calls = respond(200, { trip_id: 'TRIP 1', itinerary: ITINERARY })
    await getApprovedTrip('TRIP 1')
    assert.equal(calls[0].url, '/api/trips/TRIP%201')
    respond(503, { detail: 'The Trip Store could not be reached. Please try again.' })
    await assert.rejects(listApprovedTrips(), /Trip Store could not be reached/)
  })

  it('records an approval locally only with the backend trip id, and keeps it on a later save', () => {
    const storage = memoryStorage()
    assert.throws(() => markApproved(VERIFIED, REQUEST, {}, storage), /not saved by the backend/)
    markApproved(VERIFIED, REQUEST, { trip_id: 'TRIP-3001' }, storage)
    saveTrip(VERIFIED, REQUEST, storage)  // saving again must not lose the approval
    assert.equal(getSavedTrip('s-1', storage).approval.trip_id, 'TRIP-3001')
    assert.equal(listSavedTrips(storage).length, 1)  // one entry, no duplicate
    assert.equal(summarizeSavedTrip(getSavedTrip('s-1', storage)).verified, true)
  })

  it('merges the store and this browser without duplicates, with honest labels', () => {
    const storage = memoryStorage()
    markApproved(VERIFIED, REQUEST, { trip_id: 'TRIP-3001' }, storage)
    saveTrip({ ...UNVERIFIED, session_id: 's-2', itinerary: { ...ITINERARY, destination: 'Paris' } },
      { ...REQUEST, destination: 'Paris' }, storage)
    const local = listSavedTrips(storage).map(summarizeSavedTrip)
    const store = [{ trip_id: 'TRIP-3001', destination: 'Tokyo', start_date: '2026-11-10', end_date: '2026-11-11',
      days_count: 2, activities_count: 2, currency: 'USD', budget_total: 1500, travellers: 2, created_at: '2026-10-30' }]
    const cards = mergeTrips(store, local, { storeAvailable: true })
    assert.deepEqual(cards.map((c) => [c.source, c.status, c.tripId]).sort(),
      [['local', 'draft', null], ['store', 'approved', 'TRIP-3001']])
    assert.equal(STATUS_LABELS.draft, 'Draft · Not verified')
    assert.deepEqual(filterTrips(cards, '', 'Verified').map((c) => c.tripId), ['TRIP-3001'])
    assert.equal(filterTrips(cards, 'par', 'Not verified').length, 1)
    assert.equal(filterTrips(cards, 'rome', 'All Trips').length, 0)
    // The store restarted (in-memory): the approval is still shown, said to be the browser's copy
    const lost = mergeTrips([], local, { storeAvailable: true }).find((c) => c.tripId === 'TRIP-3001')
    assert.equal(lost.status, 'approved')
    assert.match(lost.note, /no longer lists it/)
    assert.match(mergeTrips([], local, { storeAvailable: false }).find((c) => c.tripId).note, /cannot be reached/)
  })

  it('a trip from the store opens as an approved, displayable result', () => {
    const result = storeTripResult({ trip_id: 'TRIP-3001', itinerary: ITINERARY, created_at: 'x' }, null)
    assert.equal(isValidTripResult(result), true)
    assert.equal(getVerificationState(result).label, 'Approved · Saved trip TRIP-3001')
  })
})

describe('PDF', () => {
  it('labels an unverified trip as a draft and keeps unknown prices unknown', () => {
    const model = pdfModel({ aiResult: UNVERIFIED, request: REQUEST })
    assert.equal(model.status.label, 'Draft - Not Verified')
    assert.equal(model.filename, 'Rihla_Tokyo_Itinerary_DRAFT.pdf')
    const [garden, lunch] = model.days[0].items
    assert.equal(garden.cost, 'Price unknown')
    assert.equal(garden.time, '09:00–10:30')
    assert.equal(lunch.meal, true)
    assert.equal(lunch.travel, '5 min by taxi or car from the previous stop (fare not included)')
    assert.equal(model.days[1].items.length, 0)
    assert.deepEqual(model.budget.unknownNames, ['Hama-rikyū Gardens'])
    assert.ok(model.budget.notIncluded.includes('accommodation'))
    assert.deepEqual(model.verification.findings, ['Hama-rikyū Gardens: opening hours unknown.',
      'Hama-rikyū Gardens: cost unknown.'])  // advice is not a warning
    assert.ok(!JSON.stringify(model).includes('Approved'))  // nothing implies an approval
  })

  it('says approved only with a saved trip id, and verified only when it was', () => {
    assert.equal(pdfStatus(VERIFIED).label, 'Verified · Not yet approved')
    assert.equal(pdfStatus(VERIFIED, { trip_id: 'TRIP-9' }).label, 'Approved · Saved trip TRIP-9')
    assert.equal(pdfModel({ aiResult: VERIFIED, approval: { trip_id: 'TRIP-9' } }).filename, 'Rihla_Tokyo_Itinerary.pdf')
  })

  it('renders a real PDF with the trip data, a draft mark on every page and page numbers', () => {
    const many = { ...UNVERIFIED, itinerary: { ...ITINERARY, days: Array.from({ length: 9 }, (_, n) => ({
      date: `2026-11-${String(10 + n).padStart(2, '0')}`, activities: ITINERARY.days[0].activities })) } }
    const doc = renderItineraryPdf(pdfModel({ aiResult: many, request: REQUEST }))
    const bytes = Buffer.from(doc.output('arraybuffer'))
    const text = bytes.toString('latin1')
    assert.equal(text.slice(0, 5), '%PDF-')
    const pages = doc.getNumberOfPages()
    assert.ok(pages >= 2)  // the page breaks happened
    assert.equal(text.split('DRAFT - NOT VERIFIED').length - 1, pages)
    for (const s of ['Rihla.', 'Tokyo itinerary', 'Hama-rikyu Gardens', 'Price unknown', `Page ${pages} of ${pages}`,
      'Not included in the estimate', 'fare not included']) {
      assert.ok(text.includes(s), s)
    }
  })

  it('keeps Latin-1 letters and never draws a wrong letter for others', () => {
    assert.equal(pdfText('Musée Ōsaka Topkapı 東京'), 'Musée Osaka Topkapi ??')
  })
})
