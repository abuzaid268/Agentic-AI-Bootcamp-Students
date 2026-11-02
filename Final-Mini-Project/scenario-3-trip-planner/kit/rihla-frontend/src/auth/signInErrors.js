// What to tell the traveller when Google sign-in does not finish. null means "say nothing": they closed the
// popup themselves, and the modal simply stays open.
const MESSAGES = {
  'auth/popup-blocked': 'Your browser blocked the Google sign-in window. Allow pop-ups for this site, then try again.',
  'auth/unauthorized-domain': () =>
    `Google sign-in is not allowed from ${globalThis.location?.host || 'this address'}. Open Rihla at ` +
    'http://localhost:5173, or add this domain under Firebase Authentication > Settings > Authorized domains.',
  'auth/operation-not-allowed': 'Google sign-in is not enabled for this Firebase project yet.',
  'auth/network-request-failed': 'Could not reach Google. Check your connection, then try again.',
  'auth/too-many-requests': 'Too many sign-in attempts. Please wait a moment, then try again.',
  'auth/user-disabled': 'This Google account has been disabled for Rihla.',
  'auth/account-exists-with-different-credential': 'This email is already linked to another sign-in method.',
  'auth/not-configured':
    'Google sign-in is not set up in this copy of Rihla yet (the VITE_FIREBASE_* settings are missing).',
}

const SILENT = new Set(['auth/popup-closed-by-user', 'auth/cancelled-popup-request', 'auth/user-cancelled'])

export function signInErrorMessage(error) {
  const code = typeof error?.code === 'string' ? error.code : ''
  if (SILENT.has(code)) return null
  const message = MESSAGES[code]
  if (typeof message === 'function') return message()
  if (message) return message
  if (!code && error instanceof Error && error.message) return error.message // the backend's own explanation
  return 'Google sign-in did not finish. Please try again.'
}
