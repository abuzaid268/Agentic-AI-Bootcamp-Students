import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { FILTERS, filterTrips, lostApprovals, mergeTrips, STATUS_LABELS } from './myTrips.js'
import { getVerificationState } from './tripResult.js'
import { pdfStatus } from './pdfExport.js'

const card = (over) => ({ id: 'x', destination: 'Rome', savedAt: '2026-11-01', ...over })

describe('My Trips states', () => {
  it('warns about approved trips the Trip Store lost, never about drafts or samples', () => {
    const local = [
      card({ id: 'a', approval: { trip_id: 'TRIP-1' } }), // approved here, not listed by the store any more
      card({ id: 'b' }), // a draft
      card({ id: 'c', sample: true }),
    ]
    const cards = mergeTrips([], local, { storeAvailable: true })
    assert.deepEqual(lostApprovals(cards, { storeAvailable: true }).map((c) => c.tripId), ['TRIP-1'])
    // an unreachable store is a different message (an error with "Try again"), not a loss
    assert.deepEqual(lostApprovals(mergeTrips([], local, { storeAvailable: false }), { storeAvailable: false }), [])
    // listed by the store: nothing lost
    const listed = mergeTrips([{ trip_id: 'TRIP-1', destination: 'Rome' }], local, { storeAvailable: true })
    assert.deepEqual(lostApprovals(listed, { storeAvailable: true }), [])
  })

  it('a sample is labelled as such, never verified or a draft, and has its own filter', () => {
    const cards = mergeTrips([], [card({ id: 's', sample: true, verified: false }), card({ id: 'd' })], { storeAvailable: true })
    const sample = cards.find((c) => c.localId === 's')
    assert.equal(sample.status, 'sample')
    assert.equal(STATUS_LABELS.sample, 'Sample · Demo data')
    assert.deepEqual(FILTERS, ['All Trips', 'Verified', 'Not verified', 'Samples'])
    assert.deepEqual(filterTrips(cards, '', 'Samples').map((c) => c.localId), ['s'])
    assert.deepEqual(filterTrips(cards, '', 'Not verified').map((c) => c.localId), ['d'])
    assert.deepEqual(filterTrips(cards, '', 'Verified'), [])
  })
})

describe('a plan approvable on recorded data', () => {
  const result = {
    status: 'pending_approval', session_id: 's1',
    pending_action: { type: 'save_trip', action_id: 'a1', verification_status: 'verified_on_records',
      disclosure: 'Every check passed, but against recorded data, not live sources.' },
    verification: { state: 'supported_by_records' },
  }

  it('is labelled "recorded data", never "Verified"', () => {
    const v = getVerificationState(result)
    assert.equal(v.level, 'recorded')
    assert.match(v.label, /recorded data/)
    assert.doesNotMatch(v.label, /^Verified/)
  })

  it('its PDF says so and is not marked approved', () => {
    const status = pdfStatus(result, null)
    assert.equal(status.kind, 'recorded')
    assert.match(status.label, /recorded data · Not yet approved/)
  })
})
