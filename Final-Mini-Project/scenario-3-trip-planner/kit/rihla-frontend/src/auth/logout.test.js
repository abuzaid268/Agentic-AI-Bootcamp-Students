import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { routeAccess } from './access.js'
import { createAuthFlow, performLogout } from './authFlow.js'
import { clearSavedTrips, listSavedTrips, saveTrip, STORAGE_KEY } from '../services/savedTrips.js'

const ALICE = { uid: 'alice', name: 'Alice' }
const BOB = { uid: 'bob', name: 'Bob' }

function memoryStorage() {
  const data = new Map()
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
    keys: () => [...data.keys()],
  }
}

const AI_RESULT = {
  session_id: 's1',
  status: 'verification_required',
  itinerary: {
    destination: 'Amman',
    currency: 'USD',
    budget_total: 800,
    days: [{ date: '2026-11-05', activities: [{ name: 'Amman Citadel', start_time: '09:00', end_time: '11:00' }] }],
  },
}

describe('logging out', () => {
  it('revokes the backend session first, then signs out of Firebase and clears private data', async () => {
    const order = []
    await performLogout({
      endSession: async () => order.push('backend session revoked'),
      signOutFirebase: async () => order.push('firebase signed out'),
      clearPrivateData: () => order.push('private data cleared'),
    })
    assert.deepEqual(order, ['backend session revoked', 'firebase signed out', 'private data cleared'])
  })

  it('changes nothing when the backend could not end the session (the user is still signed in)', async () => {
    const order = []
    await assert.rejects(
      performLogout({
        endSession: async () => {
          throw new Error('Could not reach the Rihla backend.')
        },
        signOutFirebase: async () => order.push('firebase'),
        clearPrivateData: () => order.push('cleared'),
      }),
      /Could not reach/,
    )
    assert.deepEqual(order, [])
  })

  it('still completes when Firebase has nothing to sign out', async () => {
    let cleared = false
    await performLogout({
      endSession: async () => {},
      signOutFirebase: async () => {
        throw new Error('Firebase not loaded')
      },
      clearPrivateData: () => {
        cleared = true
      },
    })
    assert.equal(cleared, true)
  })

  it("removes this browser's copies of the user's trips, and nothing else", () => {
    const storage = memoryStorage()
    storage.setItem('unrelated.setting', 'keep')
    saveTrip(AI_RESULT, { destination: 'Amman' }, storage)
    assert.equal(listSavedTrips(storage).length, 1)
    clearSavedTrips(storage)
    assert.equal(listSavedTrips(storage).length, 0)
    assert.equal(storage.getItem(STORAGE_KEY), null)
    assert.equal(storage.getItem('unrelated.setting'), 'keep')
    clearSavedTrips(null) // blocked storage: nothing to clear, no error
  })

  it('drops a trip that was waiting for sign-in', async () => {
    const flow = createAuthFlow({ signInForIdToken: async () => 't', openSession: async () => ALICE })
    let generated = 0
    flow.request(() => (generated += 1), { user: null })
    flow.clear() // what the provider does on logout
    assert.equal((await flow.signIn()).resume, null)
    assert.equal(generated, 0)
  })

  it('a resumed trip is generated for the account that just signed in', async () => {
    const flow = createAuthFlow({ signInForIdToken: async () => 't', openSession: async () => BOB })
    let owner = null
    flow.request((user) => (owner = user), { user: null })
    ;(await flow.signIn()).resume()
    assert.deepEqual(owner, BOB)
  })
})

describe('after logout, private pages need a sign-in again', () => {
  const tripState = { aiResult: AI_RESULT, ownerUid: 'alice' }

  it('My Trips sends a guest to log in', () => {
    assert.equal(routeAccess({ kind: 'private', status: 'signed_out', user: null }), 'login')
    assert.equal(routeAccess({ kind: 'private', status: 'signed_in', user: ALICE }), 'allow')
  })

  it("the browser's Back button cannot show a logged-out user's itinerary to a guest", () => {
    assert.equal(routeAccess({ kind: 'trip', status: 'signed_out', user: null, state: tripState }), 'login')
  })

  it('nor to the next account signing in on the same browser', () => {
    assert.equal(routeAccess({ kind: 'trip', status: 'signed_in', user: BOB, state: tripState }), 'home')
    assert.equal(routeAccess({ kind: 'trip', status: 'signed_in', user: ALICE, state: tripState }), 'allow')
    // an itinerary with no recorded owner is treated as someone else's
    assert.equal(routeAccess({ kind: 'trip', status: 'signed_in', user: ALICE, state: { aiResult: AI_RESULT } }), 'home')
  })

  it('the sample trip stays public', () => {
    assert.equal(routeAccess({ kind: 'trip', status: 'signed_out', user: null, state: { sample: true } }), 'allow')
    assert.equal(routeAccess({ kind: 'trip', status: 'loading', user: null, state: null }), 'allow')
  })

  it('waits for the sign-in check instead of redirecting a signed-in user on refresh', () => {
    assert.equal(routeAccess({ kind: 'private', status: 'loading', user: null }), 'wait')
    assert.equal(routeAccess({ kind: 'trip', status: 'loading', user: null, state: tripState }), 'wait')
  })
})
