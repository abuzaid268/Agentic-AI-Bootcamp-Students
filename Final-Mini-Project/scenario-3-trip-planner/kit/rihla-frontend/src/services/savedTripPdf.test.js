import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { describe, it } from 'node:test'

import { storeTripResult } from './myTrips.js'
import { pdfModel, renderItineraryPdf } from './pdfExport.js'

// My Trips -> Download PDF for a trip saved in the Trip Store, opened where this browser keeps no copy of it
// (after a logout, which clears the copies, or on another device): only the store's record is there.
const RECORD = {
  trip_id: 'TRIP-3007', created_at: '2026-11-02T12:00:00Z',
  itinerary: {
    destination: 'Istanbul', currency: 'USD', travellers: 2, budget_total: 900, estimated_total: 61,
    days: [
      { date: '2026-11-20', activities: [
        { name: 'Topkapı Palace', start_time: '09:00', end_time: '11:30', estimated_cost: 56,
          source_url: 'https://en.wikivoyage.org/wiki/Istanbul/Sultanahmet' },
        { name: 'Bereket Döner', start_time: '12:30', end_time: '13:15', estimated_cost: null },
      ] },
      { date: '2026-11-21', activities: [{ name: 'Galata Tower', start_time: '10:00', end_time: '11:00', estimated_cost: 5 }] },
    ],
  },
}

describe('PDF of a saved trip from the Trip Store', () => {
  it('is the approved trip, built from the store record alone', () => {
    const result = storeTripResult(RECORD, null)
    const model = pdfModel({ aiResult: result, approval: result.approval })
    assert.equal(model.status.label, 'Approved · Saved trip TRIP-3007')
    assert.equal(model.filename, 'Rihla_Istanbul_Itinerary.pdf')
    assert.deepEqual(model.days.map((d) => d.items.map((i) => i.name)),
      [['Topkapı Palace', 'Bereket Döner'], ['Galata Tower']])
    assert.equal(model.days[0].items[1].cost, 'Price unknown')  // an unknown price stays unknown
    assert.deepEqual(model.budget.unknownNames, ['Bereket Döner'])
  })

  it('renders without the draft mark and names the saved trip', () => {
    const result = storeTripResult(RECORD, null)
    const text = Buffer.from(renderItineraryPdf(pdfModel({ aiResult: result, approval: result.approval }))
      .output('arraybuffer')).toString('latin1')
    assert.equal(text.slice(0, 5), '%PDF-')
    assert.ok(!text.includes('DRAFT - NOT VERIFIED'))
    for (const s of ['Istanbul itinerary', 'TRIP-3007', 'Topkapi Palace', 'Galata Tower']) assert.ok(text.includes(s), s)
  })
})
