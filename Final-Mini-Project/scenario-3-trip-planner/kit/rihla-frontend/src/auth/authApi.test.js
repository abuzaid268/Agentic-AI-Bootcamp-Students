import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'

import { AuthRequiredError, endSession, fetchCurrentUser, openSession } from './authApi.js'
import { signInErrorMessage } from './signInErrors.js'
import { createTrip } from '../services/tripApi.js'

const realFetch = globalThis.fetch
const USER = { uid: 'u1', name: 'Dima', email: 'dima@example.com', picture: null }

function respondWith(status, body, requests = []) {
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, ...options })
    return { ok: status >= 200 && status < 300, status, json: async () => body }
  }
  return requests
}

afterEach(() => {
  globalThis.fetch = realFetch
})

describe('the session API', () => {
  it('reads the signed-in user, and null when there is no session', async () => {
    respondWith(200, { user: USER })
    assert.deepEqual(await fetchCurrentUser(), USER)
    respondWith(401, { detail: 'Not signed in.' })
    assert.equal(await fetchCurrentUser(), null)
  })

  it('sends the Google ID token to the backend once, as JSON, and returns the verified user', async () => {
    const requests = respondWith(200, { user: USER })
    assert.deepEqual(await openSession('id-token-123'), USER)
    assert.equal(requests.length, 1)
    assert.equal(requests[0].url, '/api/auth/session')
    assert.equal(requests[0].method, 'POST')
    assert.equal(requests[0].credentials, 'same-origin')
    assert.deepEqual(JSON.parse(requests[0].body), { id_token: 'id-token-123' })
  })

  it("shows the backend's reason when it refuses the sign-in", async () => {
    respondWith(401, { detail: 'Only Google sign-in is accepted.' })
    await assert.rejects(openSession('t'), /Only Google sign-in/)
    respondWith(503, { detail: 'Sign-in is not set up on this server yet.' })
    await assert.rejects(openSession('t'), /not set up/)
  })

  it('never treats an unconfirmed answer as signed in', async () => {
    respondWith(200, { user: { name: 'no uid' } })
    await assert.rejects(openSession('t'), /did not confirm/)
  })

  it('logs out on the server, and reports a failed log out', async () => {
    const requests = respondWith(200, { status: 'logged_out' })
    await endSession()
    assert.equal(requests[0].url, '/api/auth/logout')
    assert.equal(requests[0].method, 'POST')
    respondWith(500, {})
    await assert.rejects(endSession(), /Log out failed/)
  })

  it('explains an unreachable backend', async () => {
    globalThis.fetch = async () => {
      throw new TypeError('fetch failed')
    }
    await assert.rejects(fetchCurrentUser(), /Could not reach the Rihla backend/)
  })
})

describe('a trip request without a valid session', () => {
  it('is reported as AuthRequiredError so the page can ask to log in and retry', async () => {
    respondWith(401, { detail: 'Your session has expired. Please log in again.' })
    const trip = { destination: 'Amman', departureDate: '2026-11-02', returnDate: '2026-11-04', travellers: '1', budget: '900' }
    await assert.rejects(createTrip(trip, 's1'), (err) => err instanceof AuthRequiredError && /expired/.test(err.message))
  })
})

describe('sign-in error messages', () => {
  it('says nothing when the traveller closed the Google popup', () => {
    assert.equal(signInErrorMessage({ code: 'auth/popup-closed-by-user' }), null)
    assert.equal(signInErrorMessage({ code: 'auth/cancelled-popup-request' }), null)
  })

  it('explains the setup problems a developer can fix', () => {
    assert.match(signInErrorMessage({ code: 'auth/popup-blocked' }), /blocked/)
    assert.match(signInErrorMessage({ code: 'auth/unauthorized-domain' }), /Authorized domains/)
    assert.match(signInErrorMessage({ code: 'auth/not-configured' }), /VITE_FIREBASE_/)
  })

  it("passes on the backend's explanation and has a fallback for the rest", () => {
    assert.equal(signInErrorMessage(new Error('Only Google sign-in is accepted.')), 'Only Google sign-in is accepted.')
    assert.match(signInErrorMessage({ code: 'auth/internal-error' }), /did not finish/)
  })
})
