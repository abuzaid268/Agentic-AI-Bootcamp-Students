import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createAuthFlow } from './authFlow.js'

const USER = { uid: 'u1', name: 'Dima' }

function flowWith({ signIn = async () => 'id-token', session = async () => USER } = {}) {
  const calls = { signIn: 0, session: [] }
  const flow = createAuthFlow({
    signInForIdToken: async () => {
      calls.signIn += 1
      return signIn()
    },
    openSession: async (token) => {
      calls.session.push(token)
      return session(token)
    },
  })
  return { flow, calls }
}

// The trip request the home page would send; counts how often it really runs.
function generateTrip() {
  const run = () => {
    run.count += 1
  }
  run.count = 0
  return run
}

describe('a guest clicking Generate My Trip', () => {
  it('opens the login modal and sends nothing to the planner', () => {
    const { flow } = flowWith()
    const generate = generateTrip()
    assert.equal(flow.request(generate, { user: null }), 'generate')
    assert.equal(generate.count, 0)
    assert.equal(flow.pending, true)
  })

  it('generates the trip exactly once after the backend confirms the sign-in', async () => {
    const { flow, calls } = flowWith()
    const generate = generateTrip()
    flow.request(generate, { user: null })
    const { user, resume } = await flow.signIn()
    assert.deepEqual(user, USER)
    assert.deepEqual(calls.session, ['id-token']) // the ID token went to the backend for verification
    resume()
    assert.equal(generate.count, 1)
    const again = await flow.signIn()
    assert.equal(again.resume, null) // never a second time
  })

  it('generates nothing when the modal is closed, even if they sign in later', async () => {
    const { flow } = flowWith()
    const generate = generateTrip()
    flow.request(generate, { user: null })
    flow.close()
    assert.equal((await flow.signIn()).resume, null)
    assert.equal(generate.count, 0)
  })

  it('keeps the request when sign-in fails, and runs it once after a successful retry', async () => {
    let attempt = 0
    const { flow } = flowWith({
      session: async () => {
        attempt += 1
        if (attempt === 1) throw new Error('The sign-in token is not valid for Rihla.')
        return USER
      },
    })
    const generate = generateTrip()
    flow.request(generate, { user: null })
    await assert.rejects(flow.signIn(), /not valid/)
    assert.equal(generate.count, 0)
    const { resume } = await flow.signIn()
    resume()
    assert.equal(generate.count, 1)
  })

  it('a closed Google popup opens no session and runs nothing', async () => {
    const { flow, calls } = flowWith({
      signIn: async () => {
        throw Object.assign(new Error('closed'), { code: 'auth/popup-closed-by-user' })
      },
    })
    const generate = generateTrip()
    flow.request(generate, { user: null })
    await assert.rejects(flow.signIn(), (err) => err.code === 'auth/popup-closed-by-user')
    assert.equal(calls.session.length, 0)
    assert.equal(generate.count, 0)
  })
})

describe('other entry points', () => {
  it('a signed-in user generates immediately, without the modal', () => {
    const { flow } = flowWith()
    const generate = generateTrip()
    assert.equal(flow.request(generate, { user: USER }), null)
    assert.equal(generate.count, 1)
  })

  it('Log In from the navbar never starts a trip, even if one was waiting', async () => {
    const { flow } = flowWith()
    const generate = generateTrip()
    flow.request(generate, { user: null })
    assert.equal(flow.navbarLogin(), 'navbar')
    assert.equal((await flow.signIn()).resume, null)
    assert.equal(generate.count, 0)
  })

  it('an expired session retries the refused request once after signing in again', async () => {
    const { flow } = flowWith()
    const retry = generateTrip()
    assert.equal(flow.expired(retry), 'expired')
    ;(await flow.signIn()).resume()
    assert.equal(retry.count, 1)
    assert.equal((await flow.signIn()).resume, null)
  })

  it('logging out drops anything waiting', async () => {
    const { flow } = flowWith()
    const generate = generateTrip()
    flow.request(generate, { user: null })
    flow.clear()
    assert.equal((await flow.signIn()).resume, null)
  })
})
