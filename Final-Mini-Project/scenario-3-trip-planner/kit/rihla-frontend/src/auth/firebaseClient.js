// Firebase runs Google's sign-in popup and returns a fresh ID token for the Rihla backend to verify. The Rihla
// session is the backend's HttpOnly cookie, so Firebase keeps nothing in this browser (in-memory persistence)
// and is signed out again as soon as the token is handed over.
//
// The web config is public by design (it identifies the project, it grants nothing); it still comes from
// rihla-frontend/.env.local (see .env.example), never from code, and there is no demo fallback.
const CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export function firebaseConfigured() {
  return Boolean(CONFIG.apiKey && CONFIG.authDomain && CONFIG.projectId && CONFIG.appId)
}

let firebasePromise = null

// Loaded on first use (the home page does not pay for it); call it when the login modal opens so the popup
// still opens inside the click that asked for it.
export function loadFirebaseAuth() {
  if (!firebaseConfigured()) return Promise.reject(Object.assign(new Error('not configured'), { code: 'auth/not-configured' }))
  firebasePromise ??= Promise.all([import('firebase/app'), import('firebase/auth')])
    .then(([{ initializeApp }, firebaseAuth]) => {
      const app = initializeApp(CONFIG, 'rihla')
      const auth = firebaseAuth.initializeAuth(app, {
        persistence: firebaseAuth.inMemoryPersistence,
        popupRedirectResolver: firebaseAuth.browserPopupRedirectResolver,
      })
      return { auth, firebaseAuth }
    })
    .catch((error) => {
      firebasePromise = null
      throw error
    })
  return firebasePromise
}

// Logout: make sure Firebase holds no user in this tab. It normally holds none (in-memory persistence, and
// signed out right after each token), and nothing is loaded when the user never opened the login modal here.
export async function signOutOfFirebase() {
  if (!firebasePromise) return
  const { auth, firebaseAuth } = await firebasePromise
  await firebaseAuth.signOut(auth)
}

// Google sign-in in a popup; resolves with the Firebase ID token (valid for an hour, sent to the backend once).
export async function signInWithGoogleForIdToken() {
  const { auth, firebaseAuth } = await loadFirebaseAuth()
  const provider = new firebaseAuth.GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  const result = await firebaseAuth.signInWithPopup(auth, provider)
  try {
    return await result.user.getIdToken()
  } finally {
    await firebaseAuth.signOut(auth).catch(() => {})
  }
}
