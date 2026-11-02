import { Navigate, useLocation } from 'react-router-dom'
import { Plane } from 'lucide-react'
import { useAuth } from './authContext.js'
import { routeAccess } from './access.js'

// Frontend access control (the backend enforces it too: its 401s are the real protection). A guest is sent
// to the public home page with the login modal open; with `resumeAfterLogin`, signing in brings them back here.
export default function RequireAuth({ kind = 'private', resumeAfterLogin = false, children }) {
  const { status, user } = useAuth()
  const location = useLocation()
  const access = routeAccess({ kind, status, user, state: location.state })

  if (access === 'allow') return children
  if (access === 'wait') {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#e8f1f3] text-[#245c6a]" role="status">
        <span className="flex items-center gap-3 text-sm font-semibold">
          <Plane size={20} className="animate-pulse" /> Checking your sign-in…
        </span>
      </main>
    )
  }
  const state = access === 'login'
    ? { openLogin: true, returnTo: resumeAfterLogin ? location.pathname : null }
    : null
  return <Navigate to="/" replace state={state} />
}
