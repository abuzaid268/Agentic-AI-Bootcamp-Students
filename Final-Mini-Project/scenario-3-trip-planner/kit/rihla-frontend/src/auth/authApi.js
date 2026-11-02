// The Rihla backend's sign-in endpoints (app/auth). The session is an HttpOnly cookie the backend sets: this
// code never sees or stores it, the browser sends it with every same-origin request.

// A request the backend refused because nobody is signed in (or the session expired).
export class AuthRequiredError extends Error {
  constructor(message = 'Please log in to continue.') {
    super(message)
    this.name = 'AuthRequiredError'
    this.status = 401
  }
}

async function readDetail(response, fallback) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail) return body.detail
  } catch {
    // keep the fallback
  }
  return fallback
}

async function send(path, options = {}) {
  try {
    return await fetch(path, { credentials: 'same-origin', ...options })
  } catch {
    throw new Error('Could not reach the Rihla backend. Check that it is running, then try again.')
  }
}

function validUser(user) {
  return user && typeof user === 'object' && typeof user.uid === 'string' && user.uid ? user : null
}

// GET /api/auth/me: the signed-in user, or null when there is no valid session.
export async function fetchCurrentUser() {
  const response = await send('/api/auth/me', { headers: { Accept: 'application/json' } })
  if (response.status === 401) return null
  if (!response.ok) throw new Error(await readDetail(response, `Could not check your sign-in (${response.status}).`))
  const body = await response.json().catch(() => null)
  return validUser(body?.user)
}

// POST /api/auth/session: the backend verifies the Google sign-in (a Firebase ID token) and opens the session.
export async function openSession(idToken) {
  const response = await send('/api/auth/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  })
  if (!response.ok) {
    throw new Error(await readDetail(response, `Sign-in failed (${response.status}). Please try again.`))
  }
  const user = validUser((await response.json().catch(() => null))?.user)
  if (!user) throw new Error('The backend did not confirm the sign-in. Please try again.')
  return user
}

// POST /api/auth/logout: ends the session on the server too, so the old cookie cannot be reused.
export async function endSession() {
  const response = await send('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  if (!response.ok) throw new Error(await readDetail(response, `Log out failed (${response.status}).`))
}
