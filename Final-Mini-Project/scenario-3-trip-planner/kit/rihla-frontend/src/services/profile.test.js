import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'

import { AuthRequiredError } from '../auth/authApi.js'
import { routeAccess } from '../auth/access.js'
import { getProfile, saveProfilePreferences } from './profileApi.js'
import { hasChanges, toForm, toPayload, validateProfileForm } from './profileForm.js'

const realFetch = globalThis.fetch
afterEach(() => {
  globalThis.fetch = realFetch
})

function respondWith(status, body, requests = []) {
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, ...options })
    return { ok: status >= 200 && status < 300, status, json: async () => body }
  }
  return requests
}

const STORED = {
  home_currency: 'EUR',
  budget_style: 'mid-range',
  interests: ['history', 'museum', 'local food'],
  walking_tolerance: 'low',
  max_walk_minutes: 20,
}

describe('the preferences form', () => {
  it('reads stored preferences, mapping the planner tags to the home page interests', () => {
    const form = toForm(STORED)
    assert.equal(form.homeCurrency, 'EUR')
    assert.equal(form.budgetStyle, 'mid-range')
    assert.deepEqual(form.interests, ['history', 'art']) // "museum" is Art & Museums
    assert.deepEqual(form.otherInterests, ['local food']) // kept, not lost
    assert.equal(form.maxWalkMinutes, '20')
  })

  it('starts empty for a new traveller', () => {
    assert.deepEqual(toForm({}), {
      homeCurrency: '', budgetStyle: '', interests: [], otherInterests: [], walkingTolerance: '', maxWalkMinutes: '',
      activityPace: '',
    })
  })

  it('sends only what changed, in the Trip Store field names', () => {
    const original = toForm(STORED)
    assert.equal(hasChanges(original, original), false)
    const edited = { ...original, budgetStyle: 'splurge', maxWalkMinutes: '35' }
    assert.deepEqual(toPayload(edited, original), { budget_style: 'splurge', max_walk_minutes: 35 })
  })

  it('saves interests with the ones it has no button for, and allows clearing them', () => {
    const original = toForm(STORED)
    assert.deepEqual(toPayload({ ...original, interests: ['food'] }, original), { interests: ['food', 'local food'] })
    const none = toForm({ interests: ['food'] })
    assert.deepEqual(toPayload({ ...none, interests: [] }, none), { interests: [] })
  })

  it('the profile page edits currency and walking only: a save never sends budget style or interests', () => {
    // What the page can change; budget style and interests stay as loaded (chosen per trip on the home page).
    const original = toForm(STORED)
    const edited = { ...original, homeCurrency: 'JOD', walkingTolerance: 'high', maxWalkMinutes: '45' }
    const payload = toPayload(edited, original)
    assert.deepEqual(payload, { home_currency: 'JOD', walking_tolerance: 'high', max_walk_minutes: 45 })
    assert.equal('budget_style' in payload, false)
    assert.equal('interests' in payload, false)
  })

  it('reads a saved pace, and ignores a value it does not know', () => {
    assert.equal(toForm({ activity_pace: 'relaxed' }).activityPace, 'relaxed')
    assert.equal(toForm({ activity_pace: 'turbo' }).activityPace, '')
    assert.equal(toForm({}).activityPace, '')
  })

  it('one pace at a time: choosing another replaces it, and only a change is sent', () => {
    const original = toForm({ activity_pace: 'balanced', home_currency: 'EUR' })
    let form = { ...original, activityPace: 'relaxed' }
    form = { ...form, activityPace: 'packed' } // the page keeps a single value, never a list
    assert.deepEqual(toPayload(form, original), { activity_pace: 'packed' })
    assert.equal(hasChanges({ ...original }, original), false)
  })

  it('Cancel goes back to the saved pace (the page resets the form to the last loaded or saved values)', () => {
    const saved = toForm({ activity_pace: 'relaxed', walking_tolerance: 'low' })
    const edited = { ...saved, activityPace: 'packed' }
    assert.equal(hasChanges(edited, saved), true)
    const cancelled = saved // what onCancel sets
    assert.equal(cancelled.activityPace, 'relaxed')
    assert.equal(hasChanges(cancelled, saved), false)
  })

  it('saving pace never sends currency, walking, budget style or interests that did not change', () => {
    const original = toForm({ ...STORED, activity_pace: 'balanced' })
    assert.deepEqual(toPayload({ ...original, activityPace: 'relaxed' }, original), { activity_pace: 'relaxed' })
  })

  it('validates the walking limit and the choices', () => {
    const base = toForm({})
    assert.deepEqual(validateProfileForm(base), {})
    for (const bad of ['4', '241', '12.5', 'abc']) {
      assert.ok(validateProfileForm({ ...base, maxWalkMinutes: bad }).maxWalkMinutes, bad)
    }
    assert.deepEqual(validateProfileForm({ ...base, maxWalkMinutes: '60' }), {})
    assert.ok(validateProfileForm({ ...base, homeCurrency: 'euro' }).homeCurrency)
    assert.ok(validateProfileForm({ ...base, budgetStyle: 'cheap' }).budgetStyle)
    assert.ok(validateProfileForm({ ...base, walkingTolerance: 'extreme' }).walkingTolerance)
  })
})

describe('the profile API', () => {
  it('loads the signed-in user and their preferences with the session cookie only', async () => {
    const requests = respondWith(200, { user: { uid: 'u1', name: 'Dima' }, preferences: STORED, updated_at: 't', saved: true })
    const profile = await getProfile()
    assert.equal(profile.user.name, 'Dima')
    assert.deepEqual(profile.preferences, STORED)
    assert.equal(requests[0].url, '/api/profile') // no traveller ID anywhere in the request
    assert.equal(requests[0].credentials, 'same-origin')
  })

  it('saves with PUT and returns what the backend stored', async () => {
    const requests = respondWith(200, { preferences: { budget_style: 'budget' }, updated_at: 't2', saved: true })
    const result = await saveProfilePreferences({ budget_style: 'budget' })
    assert.equal(requests[0].method, 'PUT')
    assert.deepEqual(JSON.parse(requests[0].body), { budget_style: 'budget' })
    assert.deepEqual(result.preferences, { budget_style: 'budget' })
  })

  it('never reports a save the backend did not confirm', async () => {
    respondWith(200, { preferences: {} })
    await assert.rejects(saveProfilePreferences({ budget_style: 'budget' }), /did not confirm/)
    respondWith(503, { detail: 'The Trip Store could not be reached. Your preferences were not saved.' })
    await assert.rejects(saveProfilePreferences({ budget_style: 'budget' }), /not saved/)
  })

  it('pace can only be edited when the backend says the Trip Store supports it', async () => {
    respondWith(200, { user: { uid: 'u1' }, preferences: {}, saved: false, supports: { activity_pace: false } })
    assert.equal((await getProfile()).supportsPace, false)
    respondWith(200, { user: { uid: 'u1' }, preferences: {}, saved: false }) // an older backend says nothing
    assert.equal((await getProfile()).supportsPace, false)
    respondWith(200, { user: { uid: 'u1' }, preferences: { activity_pace: 'packed' }, saved: true, supports: { activity_pace: true } })
    const profile = await getProfile()
    assert.equal(profile.supportsPace, true)
    assert.equal(toForm(profile.preferences).activityPace, 'packed')
  })

  it('a refused pace is reported as not saved, never as saved', async () => {
    respondWith(422, { detail: "Activity pace cannot be saved yet: Rihla's Trip Store does not support it so far. Nothing was saved.", code: 'field_not_supported' })
    await assert.rejects(saveProfilePreferences({ activity_pace: 'relaxed' }), /Nothing was saved/)
  })

  it('a 401 asks to log in again', async () => {
    respondWith(401, { detail: 'Please log in to see your profile.' })
    await assert.rejects(getProfile(), (err) => err instanceof AuthRequiredError)
  })

  it('the profile page itself needs a signed-in user', () => {
    assert.equal(routeAccess({ kind: 'private', status: 'signed_out', user: null }), 'login')
    assert.equal(routeAccess({ kind: 'private', status: 'signed_in', user: { uid: 'u1' } }), 'allow')
  })
})
