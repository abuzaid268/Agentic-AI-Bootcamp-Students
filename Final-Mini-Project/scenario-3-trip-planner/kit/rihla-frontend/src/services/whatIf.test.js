import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'

import { AuthRequiredError } from '../auth/authApi.js'
import { applyWhatIf, compareItineraries, getWhatIfOptions, previewWhatIf, scenarioPayload, validateScenario } from './whatIf.js'

const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch })

function respond(status, body) {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) })
    return { ok: status >= 200 && status < 300, status, json: async () => body }
  }
  return calls
}

const day = (date, ...acts) => ({ date, activities: acts.map(([name, start, cost = 10]) => ({ name, start_time: start, estimated_cost: cost })) })
const ORIGINAL = {
  plan_version: 'v1', verification: { status: 'UNKNOWN' },
  itinerary: { currency: 'USD', budget_total: 700, estimated_total: 315,
    days: [day('2026-11-02', ['Mosque', '09:00'], ['Bazaar', '10:43']), day('2026-11-04', ['Pera Museum', '11:00'], ['Lunch', '13:00', null])] },
}

describe('WHAT IF requests', () => {
  it('sends only what each scenario uses', () => {
    assert.deepEqual(scenarioPayload('budget_cut', { percent: 30, hours: 3 }), { type: 'budget_cut', percent: 30 })
    assert.deepEqual(scenarioPayload('rain', { date: '' }), { type: 'rain' })
    assert.deepEqual(scenarioPayload('rain', { date: '2026-11-04' }), { type: 'rain', date: '2026-11-04' })
    assert.deepEqual(scenarioPayload('closure', { placeId: 'wv-x' }), { type: 'closure', place_id: 'wv-x' })
    assert.deepEqual(scenarioPayload('delay', {}), { type: 'delay', hours: 3 })
  })

  it('checks the inputs before asking the server', () => {
    assert.equal(validateScenario('budget_cut', { percent: 30 }), null)
    assert.match(validateScenario('budget_cut', { percent: 95 }), /between 1 and 90/)
    assert.match(validateScenario('closure', {}), /Choose the attraction/)
    assert.match(validateScenario('delay', { hours: 2.5 }), /whole hours/)
    assert.equal(validateScenario('rain', {}), null)
  })

  it('previews and applies through the real endpoints, on the version on screen', async () => {
    const calls = respond(200, { status: 'whatif_preview', whatif: { proposal_id: 'p1' } })
    await previewWhatIf('s1', 'v1', { type: 'delay', hours: 3 })
    assert.deepEqual(calls[0], { url: '/api/whatif', body: { session_id: 's1', base_version: 'v1', scenario: { type: 'delay', hours: 3 } } })
    const applied = respond(200, { status: 'verification_required', revision: { outcome: 'revised' } })
    await applyWhatIf('s1', 'p1')
    assert.deepEqual(applied[0], { url: '/api/whatif/apply', body: { session_id: 's1', proposal_id: 'p1' } })
    const opts = respond(200, { available: true, dates: [] })
    await getWhatIfOptions('s1')
    assert.equal(opts[0].url, '/api/whatif/options')
  })

  it('an ended session asks to log in again; any other failure says nothing changed', async () => {
    respond(401, { detail: 'Please log in again.' })
    await assert.rejects(previewWhatIf('s1', 'v1', { type: 'rain' }), (err) => err instanceof AuthRequiredError)
    respond(403, { detail: 'This planning session belongs to another account.' })
    await assert.rejects(previewWhatIf('s1', 'v1', { type: 'rain' }), /another account[\s\S]*not changed/)
    globalThis.fetch = async () => { throw new TypeError('offline') }
    await assert.rejects(applyWhatIf('s1', 'p1'), /Could not reach the Rihla backend[\s\S]*not changed/)
  })
})

describe('comparing the plan with a WHAT IF proposal', () => {
  it('shows what was removed, added and moved per day, and what stayed the same', () => {
    const proposal = { verification: { status: 'PASS' }, approval_eligibility: { eligible: true, reason: null },
      itinerary: { currency: 'USD', budget_total: 490, estimated_total: 300,
        days: [day('2026-11-02', ['Mosque', '12:00'], ['Bazaar', '13:43']), day('2026-11-04', ['Galata Tower', '11:00'], ['Lunch', '13:00', null])] } }
    const cmp = compareItineraries(ORIGINAL, proposal)
    assert.deepEqual(cmp.changedDays, ['2026-11-02', '2026-11-04'])
    assert.deepEqual(cmp.days[0].moved, [{ name: 'Mosque', from: '09:00', to: '12:00' }, { name: 'Bazaar', from: '10:43', to: '13:43' }])
    assert.deepEqual(cmp.days[1].removed, ['Pera Museum'])
    assert.deepEqual(cmp.days[1].added, ['Galata Tower'])
    assert.deepEqual(cmp.budget, { before: 700, after: 490, knownBefore: 315, knownAfter: 300, unknownBefore: 1,
      unknownAfter: 1, currency: 'USD' })
    assert.deepEqual(cmp.verification, { before: 'UNKNOWN', after: 'PASS', eligibleAfter: true, reasonAfter: null })
  })

  it('an unchanged day is said to be unchanged', () => {
    const cmp = compareItineraries(ORIGINAL, ORIGINAL)
    assert.deepEqual(cmp.changedDays, [])
    assert.equal(cmp.verification.eligibleAfter, false)
  })
})
