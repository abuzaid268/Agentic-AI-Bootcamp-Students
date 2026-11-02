import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthContext } from './authContext.js'
import { endSession, fetchCurrentUser, openSession } from './authApi.js'
import { createAuthFlow, performLogout } from './authFlow.js'
import { signInWithGoogleForIdToken, signOutOfFirebase } from './firebaseClient.js'
import { clearSavedTrips } from '../services/savedTrips.js'
import LoginModal from './LoginModal.jsx'

// Who is signed in, as the backend says (GET /api/auth/me): the backend's HttpOnly session is the only source
// of truth, so a refresh keeps a valid session and an expired one is noticed. The rules are in authFlow.js.
export default function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')
  const [modalReason, setModalReason] = useState(null) // null (closed) | 'navbar' | 'generate' | 'protected' | 'expired'
  const [loggingOut, setLoggingOut] = useState(false)
  // Changes on every logout: the pages are keyed on it (main.jsx), so their in-memory state (the trip form,
  // an open itinerary, the trip list) is discarded instead of being shown to the next person.
  const [resetKey, setResetKey] = useState(0)
  const [flow] = useState(() => createAuthFlow({ signInForIdToken: signInWithGoogleForIdToken, openSession }))

  useEffect(() => {
    let active = true
    const refresh = () =>
      fetchCurrentUser()
        // The backend unreachable counts as signed out; the next action explains why.
        .catch(() => null)
        .then((current) => {
          if (!active) return
          setUser(current)
          setStatus(current ? 'signed_in' : 'signed_out')
        })
    refresh()
    // A session can end while the tab is in the background (expiry, logout in another tab).
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  // Run `action(user)` now when signed in; otherwise ask to log in first and run it once, right after.
  const requireAuth = useCallback((action, reason = 'generate') => {
    const modal = flow.request(action, { user: status === 'signed_in' ? user : null, reason })
    if (modal) setModalReason(modal)
  }, [flow, status, user])

  // The navbar's Log In: signing in from here never starts anything by itself.
  const openLogin = useCallback(() => setModalReason(flow.navbarLogin()), [flow])

  const closeLogin = useCallback(() => {
    flow.close()
    setModalReason(null)
  }, [flow])

  const signInWithGoogle = useCallback(async () => {
    const { user: signedIn, resume } = await flow.signIn()
    setUser(signedIn)
    setStatus('signed_in')
    setModalReason(null)
    if (resume) resume()
  }, [flow])

  // Throws (and changes nothing) when the backend could not end the session: the user is still signed in.
  const logout = useCallback(async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await performLogout({ endSession, signOutFirebase: signOutOfFirebase, clearPrivateData: clearSavedTrips })
    } finally {
      setLoggingOut(false)
    }
    flow.clear()
    setUser(null)
    setStatus('signed_out')
    setModalReason(null)
    setResetKey((key) => key + 1)
    navigate('/', { replace: true })
  }, [flow, loggingOut, navigate])

  // A protected request answered 401: the session ended. Ask to log in again and retry `retry` once after.
  const sessionExpired = useCallback((retry) => {
    setUser(null)
    setStatus('signed_out')
    setModalReason(flow.expired(retry))
  }, [flow])

  const value = useMemo(
    () => ({
      user, status, loggingOut, resetKey, requireAuth, openLogin, closeLogin, signInWithGoogle, logout, sessionExpired,
    }),
    [user, status, loggingOut, resetKey, requireAuth, openLogin, closeLogin, signInWithGoogle, logout, sessionExpired],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
      {modalReason && <LoginModal reason={modalReason} onClose={closeLogin} onSignIn={signInWithGoogle} />}
    </AuthContext.Provider>
  )
}
