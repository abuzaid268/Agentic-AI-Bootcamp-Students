import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  BadgeCheck,
  CheckCircle2,
  ExternalLink,
  Footprints,
  Gauge,
  Loader2,
  LogOut,
  Plane,
  ShieldCheck,
  Sparkles,
  Wallet,
} from 'lucide-react'
import { useAuth } from '../auth/authContext'
import { AuthRequiredError } from '../auth/authApi'
import { Avatar } from '../auth/NavAuth'
import { getProfile, saveProfilePreferences } from '../services/profileApi'
import {
  CURRENCIES,
  hasChanges,
  MAX_WALK,
  MIN_WALK,
  PACES,
  toForm,
  toPayload,
  validateProfileForm,
  WALKING,
} from '../services/profileForm'

function formatDateTime(value) {
  if (!value) return null
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function Section({ icon: Icon, title, hint, children }) {
  return (
    <fieldset className="rounded-3xl border border-[#dce9ec] bg-white p-5 shadow-sm md:p-6">
      <legend className="sr-only">{title}</legend>
      <div className="mb-4 flex items-start gap-3">
        <span className="rounded-2xl bg-[#e3f3f3] p-2.5 text-[#2e7b87]">
          <Icon size={19} />
        </span>
        <div>
          <h3 className="font-semibold text-[#1c3544]">{title}</h3>
          {hint && <p className="mt-0.5 text-sm text-[#69808b]">{hint}</p>}
        </div>
      </div>
      {children}
    </fieldset>
  )
}

function Choice({ selected, disabled, onClick, label, hint }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-2xl border px-4 py-3 text-left text-sm transition disabled:cursor-not-allowed ${
        selected
          ? 'border-[#2e7b87] bg-[#e3f3f3] text-[#143b46] ring-2 ring-[#2e7b87]/20'
          : 'border-[#dce9ec] bg-white text-[#1c3544] hover:border-[#9fcfd2] disabled:hover:border-[#dce9ec]'
      } ${disabled ? 'opacity-50' : ''}`}
    >
      <span className="block font-semibold">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-[#69808b]">{hint}</span>}
    </button>
  )
}

export default function Profile() {
  const navigate = useNavigate()
  const { user, logout, loggingOut, sessionExpired } = useAuth() // RequireAuth renders this for a signed-in user
  const [load, setLoad] = useState({ status: 'loading', error: '' })
  const [saved, setSaved] = useState(null) // the form as last loaded or saved (what Cancel returns to)
  const [form, setForm] = useState(null)
  const [record, setRecord] = useState({ updatedAt: null, exists: false })
  const [supportsPace, setSupportsPace] = useState(false) // what the Trip Store accepts, as the backend reports
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState({ type: '', text: '' })
  const [logoutError, setLogoutError] = useState('')

  const onAuthError = useCallback((err) => {
    if (err instanceof AuthRequiredError) {
      sessionExpired(() => navigate('/profile'))
      return true
    }
    return false
  }, [navigate, sessionExpired])

  // Fetch the profile; `isActive` lets the first load ignore an answer that arrives after the page closed.
  const fetchProfile = useCallback((isActive = () => true) =>
    getProfile()
      .then((profile) => {
        if (!isActive()) return
        const values = toForm(profile.preferences)
        setSaved(values)
        setForm(values)
        setRecord({ updatedAt: profile.updatedAt, exists: profile.saved })
        setSupportsPace(profile.supportsPace)
        setLoad({ status: 'ready', error: '' })
      })
      .catch((err) => {
        if (!isActive() || onAuthError(err)) return
        setLoad({ status: 'error', error: err instanceof Error ? err.message : 'Your profile could not be loaded.' })
      }), [onAuthError])

  useEffect(() => {
    let active = true
    fetchProfile(() => active)
    return () => {
      active = false
    }
  }, [fetchProfile])

  const retryLoad = () => {
    setLoad({ status: 'loading', error: '' })
    fetchProfile()
  }

  const errors = form ? validateProfileForm(form) : {}
  const invalid = Object.keys(errors).length > 0
  const dirty = form && saved ? hasChanges(form, saved) : false

  const update = (field, value) => {
    setNotice({ type: '', text: '' })
    setForm((current) => ({ ...current, [field]: value }))
  }

  const onSave = async (event) => {
    event.preventDefault()
    if (saving || invalid || !dirty) return
    setSaving(true)
    setNotice({ type: '', text: '' })
    try {
      const result = await saveProfilePreferences(toPayload(form, saved))
      const values = toForm(result.preferences) // what the backend stored, not what was sent
      setSaved(values)
      setForm(values)
      setRecord({ updatedAt: result.updatedAt, exists: true })
      setNotice({ type: 'success', text: 'Your travel preferences were saved to your Rihla profile.' })
    } catch (err) {
      if (onAuthError(err)) return
      setNotice({ type: 'error', text: `${err instanceof Error ? err.message : 'Saving failed.'} Nothing was changed.` })
    } finally {
      setSaving(false)
    }
  }

  const onCancel = () => {
    setForm(saved)
    setNotice({ type: '', text: '' })
  }

  const onLogout = () => {
    setLogoutError('')
    logout().catch((err) => setLogoutError(`${err.message} You are still signed in; please try again.`))
  }

  const sessionEnds = formatDateTime(user?.expires_at)

  return (
    <main className="min-h-screen bg-[#edf5f7] text-[#1c3544]">
      <header className="sticky top-0 z-20 border-b border-[#dce9ec] bg-white/85 backdrop-blur-xl">
        <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5">
          <Link to="/" className="flex items-center gap-2 text-2xl font-bold">
            <span className="rounded-xl bg-[#d6eeee] p-2 text-[#2e7b87]">
              <Plane size={21} />
            </span>
            Rihla<span className="text-[#69b7bf]">.</span>
          </Link>
          <div className="hidden items-center gap-8 text-sm font-medium text-[#69808b] md:flex">
            <Link to="/" className="hover:text-[#256a77]">Home</Link>
            <Link to="/my-trips" className="hover:text-[#256a77]">My Trips</Link>
            <span className="font-bold text-[#256a77]">My Profile</span>
          </div>
          <button
            type="button"
            onClick={onLogout}
            disabled={loggingOut}
            className="flex items-center gap-2 rounded-full bg-[#245c6a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#347989] disabled:cursor-wait disabled:opacity-70"
          >
            <LogOut size={16} /> {loggingOut ? 'Logging out…' : 'Log Out'}
          </button>
        </nav>
        {logoutError && <p role="alert" className="mx-auto max-w-7xl px-6 pb-3 text-sm text-red-700">{logoutError}</p>}
      </header>

      <div className="mx-auto max-w-7xl px-6 pb-16 pt-10">
        {/* IDENTITY */}
        <section className="relative mb-8 overflow-hidden rounded-[32px] bg-[#173c4a]">
          <div
            className="absolute inset-0 bg-cover bg-center opacity-45"
            style={{
              backgroundImage:
                "linear-gradient(90deg, #123443 10%, transparent 100%), url('https://images.unsplash.com/photo-1470770841072-f978cf4d019e?w=1800&q=90')",
            }}
          />
          <div className="relative flex flex-col gap-6 p-8 text-white sm:flex-row sm:items-center md:p-12">
            {user && <Avatar user={user} size="h-24 w-24 text-3xl" />}
            <div className="min-w-0">
              <span className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#b8e9e8]">
                <Sparkles size={15} /> YOUR RIHLA PROFILE
              </span>
              <h1 className="truncate text-3xl font-semibold tracking-tight md:text-4xl">{user?.name}</h1>
              {user?.email && (
                <p className="mt-2 flex flex-wrap items-center gap-2 text-white/80">
                  <span className="truncate">{user.email}</span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-xs font-semibold text-[#c7eeec]">
                    <BadgeCheck size={14} /> Verified by Google
                  </span>
                </p>
              )}
            </div>
          </div>
        </section>

        <div className="grid gap-8 lg:grid-cols-[340px_1fr]">
          {/* ACCOUNT (read-only) */}
          <aside className="h-fit rounded-3xl border border-[#dce9ec] bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
              <ShieldCheck size={19} className="text-[#2e7b87]" /> Account
            </h2>
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-[#69808b]">Name</dt>
                <dd className="mt-1 font-medium">{user?.name}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-[#69808b]">Email</dt>
                <dd className="mt-1 break-all font-medium">{user?.email || 'Not shared by Google'}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-[#69808b]">Sign-in method</dt>
                <dd className="mt-1 font-medium">Google</dd>
              </div>
              {sessionEnds && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-[#69808b]">This session ends</dt>
                  <dd className="mt-1 font-medium">{sessionEnds}</dd>
                </div>
              )}
            </dl>
            <p className="mt-5 rounded-2xl bg-[#f3f9fa] p-4 text-xs leading-5 text-[#56707b]">
              Your name, photo, email and password are managed by Google, not by Rihla.{' '}
              <a
                href="https://myaccount.google.com/"
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 font-semibold text-[#256a77] hover:underline"
              >
                Manage your Google Account <ExternalLink size={12} />
              </a>
            </p>
          </aside>

          {/* TRAVEL PREFERENCES */}
          <section aria-labelledby="preferences-title">
            <div className="mb-5">
              <h2 id="preferences-title" className="text-2xl font-semibold tracking-tight">Personal travel preferences</h2>
              <p className="mt-1 text-sm text-[#69808b]">
                How you like to get around. Budget and interests are chosen for each trip on the home page.
                Saved to your own Rihla traveller profile, visible only to you.
              </p>
            </div>

            {load.status === 'loading' && (
              <div role="status" className="space-y-4">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-36 animate-pulse rounded-3xl bg-white/70" />
                ))}
                <span className="sr-only">Loading your profile…</span>
              </div>
            )}

            {load.status === 'error' && (
              <div role="alert" className="rounded-3xl border border-red-200 bg-red-50 p-6 text-sm text-red-800">
                <p className="flex items-center gap-2 font-semibold"><AlertCircle size={18} /> {load.error}</p>
                <button
                  type="button"
                  onClick={retryLoad}
                  className="mt-4 rounded-full bg-[#245c6a] px-5 py-2.5 font-semibold text-white hover:bg-[#347989]"
                >
                  Try again
                </button>
              </div>
            )}

            {load.status === 'ready' && form && (
              <form onSubmit={onSave} className="space-y-5" noValidate>
                <Section icon={Wallet} title="Preferred currency" hint="Prices are shown in this currency when Rihla can convert them.">
                  <select
                    aria-label="Preferred currency"
                    value={form.homeCurrency}
                    onChange={(e) => update('homeCurrency', e.target.value)}
                    className="w-full max-w-xs rounded-2xl border border-[#dce9ec] bg-white px-4 py-3 text-sm outline-none focus:border-[#2e7b87] focus:ring-2 focus:ring-[#2e7b87]/20"
                  >
                    {!form.homeCurrency && <option value="">Not set</option>}
                    {[...new Set([...CURRENCIES, ...(form.homeCurrency ? [form.homeCurrency] : [])])].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  {errors.homeCurrency && <p className="mt-2 text-sm text-red-700">{errors.homeCurrency}</p>}
                </Section>

                <Section icon={Footprints} title="Walking tolerance">
                  <div className="grid gap-3 sm:grid-cols-3">
                    {WALKING.map((w) => (
                      <Choice key={w.value} selected={form.walkingTolerance === w.value} label={w.label} hint={w.hint}
                        onClick={() => update('walkingTolerance', w.value)} />
                    ))}
                  </div>
                  <label className="mt-4 block max-w-xs text-sm">
                    <span className="mb-1.5 block font-medium">Maximum walking minutes between places (optional)</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min={MIN_WALK}
                      max={MAX_WALK}
                      step={1}
                      value={form.maxWalkMinutes}
                      onChange={(e) => update('maxWalkMinutes', e.target.value)}
                      placeholder="e.g. 20"
                      aria-invalid={Boolean(errors.maxWalkMinutes)}
                      className="w-full rounded-2xl border border-[#dce9ec] bg-white px-4 py-3 outline-none focus:border-[#2e7b87] focus:ring-2 focus:ring-[#2e7b87]/20 aria-[invalid=true]:border-red-400"
                    />
                  </label>
                  {errors.maxWalkMinutes && <p className="mt-2 text-sm text-red-700">{errors.maxWalkMinutes}</p>}
                </Section>

                <Section
                  icon={Gauge}
                  title="Preferred activity pace"
                  hint={supportsPace
                    ? 'How full you like your days. A preference, not a quota: opening hours, walking and your budget still decide what fits.'
                    : "Not saved yet: Rihla's Trip Store does not support a pace setting so far."}
                >
                  <div className="grid gap-3 sm:grid-cols-3" aria-disabled={!supportsPace}>
                    {PACES.map((p) => (
                      <Choice key={p.value} selected={supportsPace && form.activityPace === p.value} disabled={!supportsPace}
                        label={p.label} hint={p.hint} onClick={() => update('activityPace', p.value)} />
                    ))}
                  </div>
                  {errors.activityPace && <p className="mt-2 text-sm text-red-700">{errors.activityPace}</p>}
                </Section>

                {notice.text && (
                  <p
                    role={notice.type === 'error' ? 'alert' : 'status'}
                    className={`flex items-start gap-2 rounded-2xl px-4 py-3 text-sm ${
                      notice.type === 'error' ? 'bg-red-50 text-red-800' : 'bg-[#e3f3f3] text-[#1f5f6b]'
                    }`}
                  >
                    {notice.type === 'error' ? <AlertCircle size={18} className="shrink-0" /> : <CheckCircle2 size={18} className="shrink-0" />}
                    {notice.text}
                  </p>
                )}

                <div className="flex flex-col-reverse gap-3 rounded-3xl border border-[#dce9ec] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs leading-5 text-[#69808b]">
                    {record.exists && formatDateTime(record.updatedAt)
                      ? `Last saved ${formatDateTime(record.updatedAt)}. `
                      : 'Nothing saved yet. '}
                    Stored in Rihla's Trip Store (a demo store: it is reset when the travel service restarts).
                    The AI planner does not read these preferences yet.
                  </p>
                  <div className="flex shrink-0 gap-3">
                    <button
                      type="button"
                      onClick={onCancel}
                      disabled={!dirty || saving}
                      className="rounded-full border border-[#cfe2e6] px-5 py-2.5 text-sm font-semibold text-[#245c6a] transition hover:bg-[#f3f9fa] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!dirty || invalid || saving}
                      className="flex items-center gap-2 rounded-full bg-[#245c6a] px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-[#347989] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {saving && <Loader2 size={16} className="animate-spin" />}
                      {saving ? 'Saving…' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              </form>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}
