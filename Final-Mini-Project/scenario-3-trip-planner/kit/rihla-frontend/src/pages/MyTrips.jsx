import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  Compass,
  Download,
  MapPin,
  Plane,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  BriefcaseBusiness,
  Trash2,
  Users,
  Wallet,
} from 'lucide-react'
import { deleteSavedTrip, getSavedTrip, listSavedTrips, summarizeSavedTrip } from '../services/savedTrips'
import { FALLBACK_IMAGE, formatDate, formatMoney } from '../services/itineraryAdapter'
import { getApprovedTrip, listApprovedTrips } from '../services/tripApi'
import { filterTrips, mergeTrips, STATUS_LABELS, storeTripResult } from '../services/myTrips'
import { useAuth } from '../auth/authContext'

const FILTERS = ['All Trips', 'Verified', 'Not verified']

function loadLocal() {
  return listSavedTrips().map(summarizeSavedTrip)
}

function formatRange(start, end) {
  if (!start) return 'Dates unknown'
  return start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`
}

export default function MyTrips() {
  const navigate = useNavigate()
  const { user } = useAuth() // RequireAuth (main.jsx) only renders this page for a signed-in user
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('All Trips')
  const [local, setLocal] = useState(loadLocal)
  const [store, setStore] = useState({ trips: [], loading: true, error: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  // Approved trips come from the Rihla Trip Store through the backend: loaded on every visit and refresh.
  const loadStore = useCallback(async () => {
    setStore((s) => ({ ...s, loading: true }))
    try {
      setStore({ trips: await listApprovedTrips(), loading: false, error: '' })
    } catch (err) {
      setStore({ trips: [], loading: false, error: err instanceof Error ? err.message : 'Saved trips could not be loaded.' })
    }
  }, [])
  useEffect(() => {
    let cancelled = false
    listApprovedTrips()
      .then((trips) => !cancelled && setStore({ trips, loading: false, error: '' }))
      .catch((err) => !cancelled && setStore({
        trips: [], loading: false, error: err instanceof Error ? err.message : 'Saved trips could not be loaded.',
      }))
    return () => { cancelled = true }
  }, [])

  const trips = mergeTrips(store.trips, local, { storeAvailable: !store.error })
  const filteredTrips = filterTrips(trips, search, activeFilter)

  // The full trip for the dashboard or the PDF: from the Trip Store for an approved trip (with this browser's
  // copy for the request details), else this browser's draft.
  const resolveTrip = async (card) => {
    const entry = card.localId ? getSavedTrip(card.localId) : null
    if (card.source === 'store') {
      const record = await getApprovedTrip(card.tripId)
      return { request: entry?.request || {}, aiResult: storeTripResult(record, entry), sessionId: card.tripId }
    }
    if (!entry) throw new Error('That trip is no longer saved in this browser.')
    const aiResult = entry.approval ? { ...entry.aiResult, approval: entry.approval } : entry.aiResult
    return { request: entry.request, aiResult, sessionId: entry.id }
  }

  const openTrip = async (card) => {
    setError('')
    setBusy(card.id)
    try {
      const { request, aiResult, sessionId } = await resolveTrip(card)
      navigate('/trip', { state: { ...request, sessionId, aiResult, fromSaved: true, ownerUid: user?.uid } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The trip could not be opened.')
      setLocal(loadLocal())
    } finally {
      setBusy('')
    }
  }

  const downloadPdf = async (card) => {
    setError('')
    setBusy(card.id)
    try {
      const { request, aiResult } = await resolveTrip(card)
      const { downloadItineraryPdf } = await import('../services/pdfExport')  // loaded on first use
      downloadItineraryPdf({ aiResult, request, approval: aiResult.approval || null })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The PDF could not be created.')
    } finally {
      setBusy('')
    }
  }

  const removeTrip = (trip) => {
    if (!trip.localId) return
    if (!window.confirm(`Delete your ${trip.destination} trip from this browser? This cannot be undone.`)) return
    setError('')
    try {
      deleteSavedTrip(trip.localId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The trip could not be deleted.')
    }
    setLocal(loadLocal())
  }

  return (
    <main className="min-h-screen bg-[#edf5f7] text-[#1c3544]">
      {/* NAVBAR */}
      <header className="sticky top-0 z-20 border-b border-[#dce9ec] bg-white/85 backdrop-blur-xl">
        <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5">
          <Link to="/" className="flex items-center gap-2 text-2xl font-bold">
            <span className="rounded-xl bg-[#d6eeee] p-2 text-[#2e7b87]">
              <Plane size={21} />
            </span>
            Rihla<span className="text-[#69b7bf]">.</span>
          </Link>

          <div className="hidden items-center gap-8 text-sm font-medium text-[#69808b] md:flex">
            <Link to="/" className="hover:text-[#256a77]">
              Home
            </Link>
            <a href="/#planner" className="hover:text-[#256a77]">
              Trip Planner
            </a>
            <span className="font-bold text-[#256a77]">My Trips</span>
          </div>

          <Link
            to="/login"
            className="rounded-full bg-[#245c6a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#347989]"
          >
            Log In
          </Link>
        </nav>
      </header>

      <div className="mx-auto max-w-7xl px-6 pb-16 pt-10">
        {/* HERO */}
        <section className="relative mb-10 overflow-hidden rounded-[32px] bg-[#173c4a]">
          <div
            className="absolute inset-0 bg-cover bg-center opacity-50"
            style={{
              backgroundImage:
                "linear-gradient(90deg, #123443 5%, transparent 100%), url('https://images.unsplash.com/photo-1470770841072-f978cf4d019e?w=1800&q=90')",
            }}
          />

          <div className="relative flex min-h-[290px] flex-col justify-center p-8 text-white md:p-12">
            <span className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#b8e9e8]">
              <Sparkles size={16} />
              YOUR PERSONAL TRAVEL COLLECTION
            </span>

            <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
              Your journeys,
              <br />
              <span className="font-light italic text-[#b8e9e8]">
                beautifully remembered.
              </span>
            </h1>

            <p className="mt-5 max-w-xl text-sm leading-7 text-white/80 md:text-base">
              Every destination has a story. Keep your adventures together
              and revisit the moments that inspire your next journey.
            </p>
          </div>
        </section>

        {/* HEADER + SEARCH */}
        <section className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-[#79afb6]">
              THE ADVENTURE CONTINUES
            </p>
            <h2 className="text-3xl font-bold tracking-tight">My Trips</h2>
            <p className="mt-2 text-sm text-[#8297a0]">
              Approved trips are saved in the Rihla Trip Store · Drafts stay in this browser only.
            </p>
          </div>

          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#245c6a] px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-[#245c6a]/10 transition hover:-translate-y-0.5 hover:bg-[#347989]"
          >
            <Plus size={18} />
            Plan a new trip
            <ArrowRight size={17} />
          </Link>
        </section>

        {/* SEARCH */}
        <div className="mb-8 flex items-center gap-3 rounded-2xl border border-[#dce9ec] bg-white px-5 py-4 shadow-sm md:max-w-md">
          <Search size={20} className="text-[#83a7af]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search destinations..."
            aria-label="Search trips"
            className="w-full bg-transparent text-sm text-[#245c6a] outline-none placeholder:text-[#a0b4bc]"
          />
        </div>

        {/* TRIP FILTERS */}
        <div className="mb-8 flex flex-wrap gap-3">
          {FILTERS.map((filter) => (
            <button
              key={filter}
              type="button"
              aria-pressed={activeFilter === filter}
              onClick={() => setActiveFilter(filter)}
              className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${
                activeFilter === filter
                  ? 'bg-[#245c6a] text-white shadow-md'
                  : 'border border-[#dce9ec] bg-white text-[#69808b] hover:bg-[#e1eff1]'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        {error && (
          <p role="alert" className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </p>
        )}
        {store.loading && (
          <p role="status" className="mb-6 text-sm text-[#8297a0]">Loading your approved trips…</p>
        )}
        {store.error && (
          <p role="alert" className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            Approved trips could not be loaded from the Trip Store: {store.error}{' '}
            <button type="button" onClick={loadStore} className="font-semibold underline">Try again</button>
          </p>
        )}

        {/* TRIP CARDS */}
        {filteredTrips.length > 0 ? (
          <div className="grid gap-7 md:grid-cols-2 xl:grid-cols-3">
            {filteredTrips.map((trip) => (
              <article
                key={trip.id}
                className="group overflow-hidden rounded-[28px] border border-[#dfeaec] bg-white shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-[0_18px_45px_rgba(31,75,88,0.12)]"
              >
                <div className="relative h-56 overflow-hidden">
                  <img
                    src={FALLBACK_IMAGE.replace('w=500', 'w=1100')}
                    alt=""
                    className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                  />

                  <div className="absolute inset-0 bg-gradient-to-t from-[#102f3b]/60 via-transparent to-transparent" />

                  <span
                    className={`absolute left-5 top-5 flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-bold backdrop-blur-xl ${
                      trip.status !== 'draft'
                        ? 'border-emerald-200 bg-emerald-50/90 text-emerald-700'
                        : 'border-amber-200 bg-amber-50/90 text-amber-700'
                    }`}
                  >
                    {trip.status !== 'draft' ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                    {STATUS_LABELS[trip.status]}
                  </span>

                  <div className="absolute bottom-5 left-6 text-white">
                    <p className="mb-1 flex items-center gap-1.5 text-xs text-white/85">
                      <MapPin size={14} />
                      {trip.tripId ? `${trip.tripId} · ` : ''}Saved{' '}
                      {trip.savedAt ? new Date(trip.savedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                    </p>
                    <h3 className="text-3xl font-bold">{trip.destination}</h3>
                  </div>
                </div>

                <div className="p-6">
                  <div className="grid grid-cols-2 gap-4 text-sm text-[#6f8993]">
                    <div className="flex items-center gap-2">
                      <CalendarDays size={17} className="text-[#65aab3]" />
                      <span>{formatRange(trip.startDate, trip.endDate)}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Compass size={17} className="text-[#65aab3]" />
                      <span>
                        {trip.dayCount} {trip.dayCount === 1 ? 'day' : 'days'} · {trip.activityCount}{' '}
                        {trip.activityCount === 1 ? 'stop' : 'stops'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Users size={17} className="text-[#65aab3]" />
                      <span>
                        {trip.travellers ?? 'Unknown'}{' '}
                        {trip.travellers === 1 ? 'traveller' : 'travellers'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Wallet size={17} className="text-[#65aab3]" />
                      <span>
                        {trip.budgetTotal === null ? 'No budget' : formatMoney(trip.budgetTotal, trip.currency)}
                      </span>
                    </div>
                  </div>

                  {trip.note && <p className="mt-4 text-xs leading-5 text-amber-700">{trip.note}</p>}

                  <div className="mt-6 flex items-center gap-3 border-t border-[#edf2f3] pt-5">
                    <button
                      type="button"
                      onClick={() => openTrip(trip)}
                      disabled={busy === trip.id}
                      className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#245c6a] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#347989] disabled:opacity-60"
                    >
                      {busy === trip.id ? 'Loading…' : 'View itinerary'}
                      <ArrowRight size={16} />
                    </button>

                    <button
                      type="button"
                      onClick={() => downloadPdf(trip)}
                      disabled={busy === trip.id}
                      aria-label={`Download ${trip.destination} itinerary as PDF`}
                      title={trip.status === 'draft' ? 'Download a draft PDF (not verified)' : 'Download PDF'}
                      className="rounded-xl bg-[#edf5f6] p-3 text-[#245c6a] transition hover:bg-[#dcecee] disabled:opacity-60"
                    >
                      <Download size={18} />
                    </button>

                    {trip.localId && trip.source === 'local' && (
                      <button
                        type="button"
                        onClick={() => removeTrip(trip)}
                        aria-label={`Delete ${trip.destination} trip`}
                        title="Delete from this browser"
                        className="rounded-xl bg-[#edf5f6] p-3 text-[#a35c5c] transition hover:bg-red-50"
                      >
                        <Trash2 size={18} />
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-[28px] border border-[#dfeaec] bg-white px-6 py-20 text-center">
            <BriefcaseBusiness size={38} className="mx-auto mb-4 text-[#79afb6]" />
            <h3 className="text-xl font-bold">
              {trips.length ? 'No matching trips' : 'No saved trips yet'}
            </h3>
            <p className="mt-2 text-sm text-[#8297a0]">
              {trips.length
                ? 'Try another destination or filter.'
                : 'Approve a verified trip, or save a draft, from the itinerary page.'}
            </p>
          </div>
        )}

        <div className="mt-10 rounded-2xl border border-[#d7e8ea] bg-[#e6f2f3] p-5 text-sm leading-6 text-[#64848d]">
          <strong>Where trips are kept:</strong> approved trips are saved in the Rihla Trip Store through the
          backend. Drafts (and a copy of each approved trip) are kept in this browser only: clearing site data, or
          another browser or device, will not show them. No account sign-in is involved yet.
        </div>

        <footer className="pt-12 text-center text-sm text-[#8aa0aa]">
          Made for the curious. Powered by Rihla ✨
        </footer>
      </div>
    </main>
  )
}
