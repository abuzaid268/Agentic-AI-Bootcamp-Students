import { requireSession } from '../auth/authApi.js'

// WHAT IF (app/whatif.py): a hypothetical condition tried on the plan on screen. The backend previews a revised
// plan (the same revision, scheduling and verification as a change request) WITHOUT changing the plan; it becomes
// the plan only with applyWhatIf, and is then approvable only through the normal approval policy.

export const SCENARIOS = [
  { type: 'budget_cut', label: 'Budget reduction', hint: 'Cut the trip budget and keep what still fits.' },
  { type: 'rain', label: 'Rain', hint: 'Swap outdoor places for indoor ones the research found.' },
  { type: 'closure', label: 'Attraction closure', hint: 'Pretend one attraction is unavailable.' },
  { type: 'delay', label: 'Late arrival', hint: 'Shift the first day by a few hours.' },
]

export const WHATIF_TIMEOUT_MS = 5 * 60 * 1000

async function post(path, body, what, timeoutMs = WHATIF_TIMEOUT_MS) {
  let response
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
  } catch {
    if (controller.signal.aborted) {
      throw new Error(`The planner did not answer within ${Math.round(timeoutMs / 60000)} minutes. Your itinerary was not changed.`)
    }
    throw new Error(`Could not reach the Rihla backend ${what}. Your itinerary was not changed.`)
  } finally {
    clearTimeout(timer)
  }
  await requireSession(response, 'Your session ended. Please log in again to try a WHAT IF.')
  let data = null
  try {
    data = await response.json()
  } catch {
    // handled below
  }
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : `The request failed (${response.status}).`
    throw new Error(/not changed/.test(detail) ? detail : `${detail} Your itinerary was not changed.`)
  }
  if (!data || typeof data !== 'object') throw new Error('The backend returned an unreadable answer. Your itinerary was not changed.')
  return data
}

export function getWhatIfOptions(sessionId) {
  return post('/api/whatif/options', { session_id: sessionId }, 'to load the WHAT IF options')
}

// Only the fields a scenario uses are sent.
export function scenarioPayload(type, inputs = {}) {
  if (type === 'budget_cut') return { type, percent: Number(inputs.percent ?? 30) }
  if (type === 'rain') return inputs.date ? { type, date: inputs.date } : { type }
  if (type === 'closure') return { type, place_id: inputs.placeId || null }
  if (type === 'delay') return { type, hours: Number(inputs.hours ?? 3) }
  throw new Error('Choose a WHAT IF scenario.')
}

export function validateScenario(type, inputs = {}) {
  if (type === 'budget_cut') {
    const p = Number(inputs.percent ?? 30)
    return Number.isFinite(p) && p >= 1 && p <= 90 ? null : 'Choose a budget cut between 1 and 90 percent.'
  }
  if (type === 'closure') return inputs.placeId ? null : 'Choose the attraction that would be closed.'
  if (type === 'delay') {
    const h = Number(inputs.hours ?? 3)
    return Number.isInteger(h) && h >= 1 && h <= 12 ? null : 'Choose a delay of 1 to 12 whole hours.'
  }
  return type === 'rain' ? null : 'Choose a WHAT IF scenario.'
}

export function previewWhatIf(sessionId, baseVersion, scenario) {
  return post('/api/whatif', { session_id: sessionId, base_version: baseVersion || null, scenario }, 'to preview this WHAT IF')
}

export function applyWhatIf(sessionId, proposalId) {
  return post('/api/whatif/apply', { session_id: sessionId, proposal_id: proposalId }, 'to apply this WHAT IF')
}

const isMeal = (a) => a.kind === 'eat' || a.kind === 'drink'

// The differences between the plan on screen and the WHAT IF proposal, from the two itineraries alone (nothing is
// estimated): per day, what was added, removed and kept, which kept activities moved in time; the budget and
// known costs; and each plan's verification verdict.
export function compareItineraries(original, proposal) {
  const before = original?.itinerary || {}
  const after = proposal?.itinerary || {}
  const byDate = (it) => Object.fromEntries((it.days || []).map((d) => [d.date, d.activities || []]))
  const a = byDate(before)
  const b = byDate(after)
  const dates = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()
  const days = dates.map((date) => {
    const old = a[date] || []
    const now = b[date] || []
    const oldNames = old.map((x) => x.name)
    const newNames = now.map((x) => x.name)
    const moved = now.filter((x) => oldNames.includes(x.name))
      .map((x) => ({ name: x.name, from: old.find((o) => o.name === x.name)?.start_time || null, to: x.start_time || null }))
      .filter((m) => m.from !== m.to)
    const added = now.filter((x) => !oldNames.includes(x.name)).map((x) => x.name)
    const removed = old.filter((x) => !newNames.includes(x.name)).map((x) => x.name)
    return { date, added, removed, kept: newNames.filter((n) => oldNames.includes(n)), moved,
      changed: added.length > 0 || removed.length > 0 || moved.length > 0,
      activitiesBefore: old.filter((x) => !isMeal(x)).length, activitiesAfter: now.filter((x) => !isMeal(x)).length }
  })
  const unknown = (it) => (it.days || []).reduce((n, d) => n + (d.activities || []).filter((x) => x.estimated_cost == null).length, 0)
  return {
    days,
    changedDays: days.filter((d) => d.changed).map((d) => d.date),
    budget: { before: before.budget_total ?? null, after: after.budget_total ?? null,
      knownBefore: before.estimated_total ?? null, knownAfter: after.estimated_total ?? null,
      unknownBefore: unknown(before), unknownAfter: unknown(after), currency: after.currency || before.currency || 'USD' },
    verification: { before: original?.verification?.status || null, after: proposal?.verification?.status || null,
      eligibleAfter: proposal?.approval_eligibility?.eligible === true,
      reasonAfter: proposal?.approval_eligibility?.reason || null },
  }
}
