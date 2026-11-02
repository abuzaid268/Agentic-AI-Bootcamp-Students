// The trips My Trips shows: approved trips from the Rihla Trip Store (the record), merged with what this browser
// keeps (drafts, and a copy of each trip it approved). Pure functions: the page and the tests share them.

// One card per trip. A store trip is "approved" (it can only get there through a verified approval). A local
// entry with an approval the store does not list stays approved, said to be a local copy. A local entry
// without one is a draft.
export function mergeTrips(storeTrips, localTrips, { storeAvailable }) {
  const byTripId = new Map(localTrips.filter((t) => t.approval?.trip_id).map((t) => [t.approval.trip_id, t]))
  const cards = (storeTrips || []).map((s) => {
    const local = byTripId.get(s.trip_id)
    return {
      id: `store:${s.trip_id}`,
      tripId: s.trip_id,
      source: 'store',
      status: 'approved',
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
  const listed = new Set(cards.map((c) => c.tripId))
  for (const t of localTrips) {
    if (t.approval?.trip_id && listed.has(t.approval.trip_id)) continue
    cards.push({
      ...t,
      id: `local:${t.id}`,
      tripId: t.approval?.trip_id || null,
      source: 'local',
      localId: t.id,
      status: t.approval?.trip_id ? 'approved' : t.verified ? 'verified_draft' : 'draft',
      note: t.approval?.trip_id
        ? (storeAvailable
          ? 'Approved, but the Trip Store no longer lists it (the simulated store was restarted). Showing the copy kept in this browser.'
          : 'Approved. The Trip Store cannot be reached right now: showing the copy kept in this browser.')
        : null,
    })
  }
  return cards.sort((a, b) => String(b.savedAt).localeCompare(String(a.savedAt)))
}

export const STATUS_LABELS = {
  approved: 'Approved · Verified',
  verified_draft: 'Verified · Not approved',
  draft: 'Draft · Not verified',
}

// The page's filters: "Verified" means verified by Rihla (approved or not); "Not verified" means drafts.
export function filterTrips(cards, search, filter) {
  const q = String(search || '').trim().toLowerCase()
  return cards.filter((c) => String(c.destination).toLowerCase().includes(q)
    && (filter === 'All Trips' || (filter === 'Verified' ? c.status !== 'draft' : c.status === 'draft')))
}

// What the dashboard needs to show a trip from the Trip Store: its itinerary, and the approval.
export function storeTripResult(record, local) {
  return {
    ...(local?.aiResult || {}),
    status: 'approved',
    session_id: record.trip_id,
    itinerary: record.itinerary,
    pending_action: null,
    approval: { trip_id: record.trip_id, approvedAt: record.created_at || null },
    message: `Approved and saved in the Rihla Trip Store as ${record.trip_id}.`,
  }
}
