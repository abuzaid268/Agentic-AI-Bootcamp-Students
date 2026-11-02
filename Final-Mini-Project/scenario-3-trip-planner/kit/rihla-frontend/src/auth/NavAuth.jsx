import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, LogIn, LogOut, Map as MapIcon, UserRound } from 'lucide-react'
import { useAuth } from './authContext.js'

export function Avatar({ user, size = 'h-9 w-9' }) {
  const [broken, setBroken] = useState(false)
  if (user.picture && !broken) {
    return (
      <img
        src={user.picture}
        alt=""
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className={`${size} shrink-0 rounded-full border border-white/50 object-cover`}
      />
    )
  }
  return (
    <span className={`${size} flex shrink-0 items-center justify-center rounded-full border border-white/50 bg-[#89b7ba] text-sm font-bold text-[#0d2a37]`}>
      {(user.name || '?').trim().charAt(0).toUpperCase()}
    </span>
  )
}

function UserMenu({ user, logout, loggingOut }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const menu = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      if (!menu.current?.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // On success the provider goes to the home page and this menu unmounts; on failure the session is untouched.
  const signOut = async () => {
    setError('')
    try {
      await logout()
    } catch (err) {
      setError(`${err instanceof Error ? err.message : 'Log out failed.'} You are still signed in; please try again.`)
    }
  }

  return (
    <div ref={menu} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-full border border-white/40 bg-white/15 py-1.5 pl-1.5 pr-4 text-sm font-medium backdrop-blur-xl transition hover:bg-white/25"
      >
        <Avatar user={user} />
        <span className="max-w-[140px] truncate">{user.name}</span>
        <ChevronDown size={16} className={`transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+10px)] z-30 w-64 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-white/25 bg-[#0d2a37]/95 p-2 text-sm shadow-2xl backdrop-blur-xl"
        >
          <div className="flex items-center gap-3 border-b border-white/10 px-3 pb-3 pt-2">
            <Avatar user={user} size="h-10 w-10" />
            <div className="min-w-0">
              <p className="truncate font-semibold">{user.name}</p>
              {user.email && <p className="truncate text-xs text-white/60">{user.email}</p>}
            </div>
          </div>
          <Link role="menuitem" to="/my-trips" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-white/10">
            <MapIcon size={17} className="text-[#b7e6e4]" /> My Trips
          </Link>
          <button
            role="menuitem"
            type="button"
            disabled
            title="Your profile page arrives in the next phase."
            className="flex w-full cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-left text-white/45"
          >
            <UserRound size={17} /> My Profile
            <span className="ml-auto rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold">SOON</span>
          </button>
          <button
            role="menuitem"
            type="button"
            onClick={signOut}
            disabled={loggingOut}
            aria-busy={loggingOut}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-white/10 disabled:cursor-wait disabled:opacity-60"
          >
            <LogOut size={17} className={`text-[#b7e6e4] ${loggingOut ? 'animate-pulse' : ''}`} />
            {loggingOut ? 'Logging out…' : 'Log Out'}
          </button>
          {error && <p role="alert" className="px-3 pb-2 pt-1 text-xs text-red-200">{error}</p>}
        </div>
      )}
    </div>
  )
}

// The navbar's account control: Log In for a guest, the user's avatar and menu once signed in.
export default function NavAuth() {
  const { user, status, openLogin, logout, loggingOut } = useAuth()

  if (status === 'loading') {
    return <span aria-hidden="true" className="h-11 w-28 animate-pulse rounded-full bg-white/15" />
  }
  if (user) return <UserMenu user={user} logout={logout} loggingOut={loggingOut} />
  return (
    <button
      type="button"
      onClick={openLogin}
      className="flex items-center gap-2 rounded-full bg-[#c7eeec] px-5 py-3 text-sm font-bold text-[#143b46] shadow-lg transition hover:-translate-y-0.5 hover:bg-white"
    >
      <LogIn size={16} /> Log In
    </button>
  )
}
