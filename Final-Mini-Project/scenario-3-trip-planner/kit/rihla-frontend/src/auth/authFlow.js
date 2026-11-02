import { createPendingAction } from './pendingAction.js'

// The login rules, without React (AuthProvider.jsx renders them; the tests check them):
// - a guest's protected action is not run; the login modal opens instead, and the action waits;
// - a successful sign-in, verified by the backend, runs the waiting action exactly once, with the signed-in user;
// - closing the modal, or a Log In started from the navbar, drops it: signing in then starts nothing.
export function createAuthFlow({ signInForIdToken, openSession }) {
  const pending = createPendingAction()

  return {
    // Run `action(user)` now when signed in; otherwise keep it and return the modal to open.
    request(action, { user, reason = 'generate' }) {
      if (user) {
        action(user)
        return null
      }
      pending.set(action)
      return reason
    },

    navbarLogin() {
      pending.clear()
      return 'navbar'
    },

    // A protected request answered 401: retry it once after the next sign-in.
    expired(retry) {
      pending.set(retry)
      return 'expired'
    },

    close() {
      pending.clear()
    },

    clear() {
      pending.clear()
    },

    // Google sign-in, then the backend's verification; a failure leaves the waiting action for a retry.
    // `resume` (or null) is the waiting action, already bound to the signed-in user.
    async signIn() {
      const idToken = await signInForIdToken()
      const user = await openSession(idToken)
      const action = pending.take()
      return { user, resume: action ? () => action(user) : null }
    },

    get pending() {
      return pending.pending
    },
  }
}

// Log out, in the order that keeps the account safe: the backend session is revoked first. If that fails the
// user is still signed in (a refresh would restore the session), so nothing else changes and the error is
// reported. Then Firebase (best effort: Rihla keeps no Firebase user anyway) and this browser's private data.
export async function performLogout({ endSession, signOutFirebase, clearPrivateData }) {
  await endSession()
  try {
    await signOutFirebase()
  } catch {
    // Firebase holds no user between sign-ins (in-memory persistence, signed out after each token).
  }
  clearPrivateData()
}
