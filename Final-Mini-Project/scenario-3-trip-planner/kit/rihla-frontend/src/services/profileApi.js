import { AuthRequiredError } from '../auth/authApi.js'

// GET /api/profile and PUT /api/profile/preferences (app/auth/profile.py): the signed-in user's own profile,
// identified by the session cookie only. 401 -> AuthRequiredError, so the page can ask to log in again.

async function readDetail(response, fallback) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail) return body.detail
  } catch {
    // keep the fallback
  }
  return fallback
}

async function send(path, options, what) {
  let response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...options })
  } catch {
    throw new Error(`Could not reach the Rihla backend ${what}.`)
  }
  if (response.status === 401) throw new AuthRequiredError(await readDetail(response, 'Please log in again.'))
  if (!response.ok) throw new Error(await readDetail(response, `The request failed (${response.status}).`))
  const body = await response.json().catch(() => null)
  if (!body || typeof body !== 'object') throw new Error('The backend returned an unreadable profile.')
  return body
}

export async function getProfile() {
  const body = await send('/api/profile', { headers: { Accept: 'application/json' } }, 'to load your profile')
  return {
    user: body.user || null,
    preferences: body.preferences && typeof body.preferences === 'object' ? body.preferences : {},
    updatedAt: body.updated_at || null,
    saved: body.saved === true,
    // Only what the backend says the Trip Store accepts can be edited; anything else is shown as not saved yet.
    supportsPace: body.supports?.activity_pace === true,
  }
}

// Resolves only after the backend confirmed the save; the caller shows what the backend stored, not what it sent.
export async function saveProfilePreferences(payload) {
  const body = await send('/api/profile/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 'to save your preferences')
  if (body.saved !== true) throw new Error('The backend did not confirm the save. Your preferences were not changed.')
  return { preferences: body.preferences || {}, updatedAt: body.updated_at || null }
}
