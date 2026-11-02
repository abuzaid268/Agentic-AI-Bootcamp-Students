// Statuses for which POST /api/chat returns a freshly generated itinerary.
// See app/main.py: "pending_approval" is only set after trusted verification.
// "approved": a trip saved in the Rihla Trip Store after approval (opened from My Trips).
const ITINERARY_STATUSES = new Set(['pending_approval', 'verification_required', 'approved'])

function incomplete(what) {
  return new Error(
    `The planner returned an incomplete itinerary (${what}). No trip was generated, please try again.`
  )
}

// Throws an Error with a user-facing message unless `result` holds a
// complete, displayable itinerary from the backend.
export function validateTripResult(result) {
  if (!result || typeof result !== 'object') {
    throw new Error('The planner returned an empty response. No trip was generated.')
  }

  const { itinerary, status } = result

  if (!itinerary) {
    throw new Error(result.message || 'The planner could not generate an itinerary for this request.')
  }

  if (!ITINERARY_STATUSES.has(status)) {
    throw new Error(result.message || `The planner returned an unexpected status (${status || 'none'}).`)
  }

  // The backend never sends a low-coverage itinerary; refuse one anyway.
  if (result.coverage && result.coverage.sufficient === false) {
    throw new Error(result.message || 'The itinerary covers too few days of the trip. No trip was generated.')
  }

  if (typeof itinerary.destination !== 'string' || !itinerary.destination.trim()) {
    throw incomplete('missing destination')
  }

  if (!Array.isArray(itinerary.days) || itinerary.days.length === 0) {
    throw incomplete('no days')
  }

  itinerary.days.forEach((day, index) => {
    if (!day || typeof day.date !== 'string' || !day.date) {
      throw incomplete(`day ${index + 1} has no date`)
    }
    if (!Array.isArray(day.activities)) {
      throw incomplete(`day ${index + 1} has no activity list`)
    }
  })

  return result
}

export function isValidTripResult(result) {
  try {
    validateTripResult(result)
    return true
  } catch {
    return false
  }
}

// Verification state comes only from the backend's verdict: the backend
// issues a save_trip pending_action solely when verification passed.
export function getVerificationState(result) {
  const action = result?.pending_action

  if (result?.status === 'approved' && result?.approval?.trip_id) {
    return {
      level: 'verified',
      label: `Approved · Saved trip ${result.approval.trip_id}`,
      detail: result.message || 'This trip passed verification, you approved it, and it is saved in your trips.',
    }
  }

  if (
    result?.status === 'pending_approval'
    && action?.type === 'save_trip'
    && action?.verification_status === 'verified'
  ) {
    return {
      level: 'verified',
      label: 'Verified · Awaiting your approval',
      detail: result.message || 'This itinerary passed verification.',
    }
  }

  return {
    level: 'unverified',
    label: 'Not verified',
    detail: result?.message || 'This itinerary could not be fully verified. Check details before relying on it.',
  }
}

// plan_quality from the backend (app/coverage.py DensityReport): advice about
// how full the days are. A light plan is still a valid plan.
export function summarizeDensity(planQuality) {
  if (!planQuality || !Array.isArray(planQuality.days)) return null

  return {
    light: planQuality.level === 'light',
    total: planQuality.total_non_meal ?? 0,
    targetMin: planQuality.target_min ?? null,
    targetMax: planQuality.target_max ?? null,
    lightDays: planQuality.days.filter((d) => d.non_meal < d.target),
  }
}

// estimatedTotal is the sum of KNOWN costs. With unknown costs it is only a
// lower bound, so the remaining budget is an upper bound, never a fact.
export function summarizeBudget(budgetTotal, estimatedTotal, unknownCostCount = 0) {
  const hasBudget = Number.isFinite(budgetTotal)
  const hasEstimate = Number.isFinite(estimatedTotal)
  const costComplete = hasEstimate && unknownCostCount === 0
  const left = hasBudget && hasEstimate ? budgetTotal - estimatedTotal : null
  const overBudget = left !== null && left < 0  // known costs alone already exceed it
  const percentUsed = hasBudget && hasEstimate && budgetTotal > 0
    ? Math.min(100, Math.max(0, (estimatedTotal / budgetTotal) * 100))
    : null

  return {
    budgetTotal: hasBudget ? budgetTotal : null,
    estimatedTotal: hasEstimate ? estimatedTotal : null,
    unknownCostCount,
    costComplete,
    remaining: costComplete && !overBudget ? left : null,
    maxRemaining: !costComplete && !overBudget ? left : null,
    overrun: overBudget ? -left : null,
    percentUsed,
    overBudget,
  }
}

// Why approval is not possible, in the verifier's own counts (app/orchestrator.verification_summary): the
// itinerary is not hidden, but approving it would claim more than the evidence shows.
export function approvalBlockedReason(result) {
  const v = result?.verification
  if (!v) {
    return 'Approval needs a verified itinerary, and this one could not be fully verified.'
  }
  const counts = v.counts || {}
  const unknownCodes = new Set((v.findings || []).filter((f) => f.state === 'unverifiable').map((f) => f.code))
  const what = []
  if (unknownCodes.has('hours_unknown') || unknownCodes.has('hours_unconfirmed')) what.push('opening hours')
  if (unknownCodes.has('cost_unknown') || unknownCodes.has('budget_undetermined')) what.push('prices')
  if (unknownCodes.has('route_unknown') || unknownCodes.has('walk_unverified')) what.push('travel times')
  const parts = []
  if (counts.confirmed_problems) parts.push(`${counts.confirmed_problems} confirmed problem(s) must be fixed`)
  if (counts.unverifiable) {
    parts.push(`${counts.unverifiable} fact(s) could not be confirmed from the sources`
      + (what.length ? ` (${what.join(', ')})` : ''))
  }
  return `Approval needs a verified itinerary. ${parts.join('; ') || 'Verification is incomplete'}. `
    + 'You can still save it as a draft or download it as a draft PDF.'
}
