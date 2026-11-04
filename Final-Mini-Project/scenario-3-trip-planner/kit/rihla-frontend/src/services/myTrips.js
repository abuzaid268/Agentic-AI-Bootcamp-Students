// The trips My Trips shows: approved trips from the Rihla Trip Store (the record), merged with what this browser
// keeps (drafts, and a copy of each trip it approved). Pure functions: the page and the tests share them.

// A store trip's status from how it was saved (GET /api/trips save_mode): approved through the verified path, or
// kept by the traveller with its limitations / as an unverified draft (POST /api/accept).
const SAVE_MODE_STATUS = { accepted_with_limitations: 'saved_limited', unverified_draft: 'saved_draft' }
const storeStatus = (mode) => SAVE_MODE_STATUS[mode] || 'approved'

// One card per trip. A store trip is "approved" (it can only get there through a verified approval). A local
// entry with an approval the store does not list stays approved, said to be a local copy. A local entry
// without one is a draft.
// While the store's list is loading (`storeLoading`), a local copy carries no note: it is not known yet whether
// the store lists it.
// A local copy belongs to a store trip only when it is that trip: the same id AND destination and dates. An id
// alone is not enough: a Trip Store that lost its trips (one without TRAVEL_DB_PATH, restarted) gives the same ids
// to new trips, and an old copy would show another trip's request details and its own status on the new one.
const sameTrip = (local, s) => local.approval?.trip_id === s.trip_id
  && (!s.start_date || local.startDate === s.start_date) && (!s.end_date || local.endDate === s.end_date)
  && (!s.destination || String(local.destination || '').toLowerCase() === String(s.destination).toLowerCase())

export function mergeTrips(storeTrips, localTrips, { storeAvailable, storeLoading = false }) {
  const matched = new Set()
  const cards = (storeTrips || []).map((s) => {
    const local = localTrips.find((t) => !matched.has(t.id) && sameTrip(t, s))
    if (local) matched.add(local.id)
    return {
      id: `store:${s.trip_id}`,
      tripId: s.trip_id,
      source: 'store',
      status: storeStatus(s.save_mode),
      destination: s.destination || local?.destination || 'Trip',
      startDate: s.start_date || local?.startDate || null,
      endDate: s.end_date || local?.endDate || null,
      dayCount: s.days_count ?? local?.dayCount ?? 0,
      activityCount: s.activities_count ?? local?.activityCount ?? 0,
      travellers: s.travellers ?? local?.travellers ?? null,
      budgetTotal: s.budget_total ?? local?.budgetTotal ?? null,
      currency: s.currency || local?.currency || 'USD',
      savedAt: s.created_at || local?.savedAt || '',
      localId: local?.id || null,
    }
  })
  for (const t of localTrips) {
    if (matched.has(t.id)) continue // shown as its store trip
    cards.push({
      ...t,
      id: `local:${t.id}`,
      tripId: t.approval?.trip_id || null,
      source: 'local',
      localId: t.id,
      status: t.sample ? 'sample' : t.approval?.trip_id ? storeStatus(t.approval.mode) : t.verified ? 'verified_draft' : 'draft',
      note: t.approval?.trip_id && !storeLoading
        ? (storeAvailable
          ? `${t.approval.mode ? 'Saved' : 'Approved'}, but the Trip Store no longer lists it (the simulated store was restarted). Showing the copy kept in this browser.`
          : `${t.approval.mode ? 'Saved' : 'Approved'}. The Trip Store cannot be reached right now: showing the copy kept in this browser.`)
        : null,
    })
  }
  return cards.sort((a, b) => String(b.savedAt).localeCompare(String(a.savedAt)))
}

export const STATUS_LABELS = {
  approved: 'Approved · Verified',
  saved_limited: 'Saved · Not Fully Verified',
  saved_draft: 'Saved · Unverified Draft',
  verified_draft: 'Verified · Not approved',
  draft: 'Draft · Not verified',
  sample: 'Sample · Demo data',
}

const SAVED = ['approved', 'saved_limited', 'saved_draft'] // in the Trip Store

export const FILTERS = ['All Trips', 'Verified', 'Not verified', 'Samples']

// Approved trips the Trip Store did not list although this browser recorded their approval: the simulated store
// keeps trips in memory, so a restart loses them. The page says so instead of showing nothing.
export function lostApprovals(cards, { storeAvailable }) {
  return storeAvailable ? cards.filter((c) => c.source === 'local' && SAVED.includes(c.status)) : []
}

// The page's filters: "Verified" means verified by Rihla (approved or not); "Not verified" means drafts and trips
// saved with limitations; sample
// trips (labelled demo data) only appear under "All Trips" and "Samples".
export function filterTrips(cards, search, filter) {
  const q = String(search || '').trim().toLowerCase()
  const keep = {
    'All Trips': () => true,
    Verified: (c) => c.status === 'approved' || c.status === 'verified_draft',
    'Not verified': (c) => ['draft', 'saved_limited', 'saved_draft'].includes(c.status),
    Samples: (c) => c.status === 'sample',
  }[filter] || (() => true)
  return cards.filter((c) => String(c.destination).toLowerCase().includes(q) && keep(c))
}

const sameItinerary = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// What the dashboard (and its PDF) needs to show a trip from the Trip Store: the store's itinerary and the approval.
// This browser's copy adds its verification, summary and budget only when it is exactly that itinerary: a copy of
// another version (an older draft, a revision) would describe activities and costs the saved trip does not have.
// A trip the traveller accepted with its limitations carries them in itinerary.rihla_save (app/approval_policy.py):
// its status comes from there, never from this browser.
export function storeTripResult(record, local) {
  const { rihla_save: saveInfo, ...plan } = record.itinerary || {}
  const extras = local?.aiResult && sameItinerary(local.aiResult.itinerary, plan) ? local.aiResult : {}
  const mode = saveInfo?.mode && SAVE_MODE_STATUS[saveInfo.mode] ? saveInfo.mode : null
  return {
    ...extras,
    status: mode ? storeStatus(mode) : 'approved',
    session_id: record.trip_id,
    itinerary: record.itinerary,
    pending_action: null,
    pending_acceptance: null,
    approval: { trip_id: record.trip_id, approvedAt: record.created_at || null,
      ...(mode ? { mode, limitations: saveInfo.limitations || [], problems: saveInfo.confirmed_problems || [],
        costs: saveInfo.costs || null } : {}),
      ...(!mode && extras === local?.aiResult && local?.approval?.basis ? { basis: local.approval.basis } : {}) },
    message: mode
      ? `Saved in the Rihla Trip Store as ${record.trip_id} (${saveInfo.label || STATUS_LABELS[storeStatus(mode)]}): you `
        + 'accepted it with its limitations; it was not fully verified.'
      : `Approved and saved in the Rihla Trip Store as ${record.trip_id}.`,
  }
}
