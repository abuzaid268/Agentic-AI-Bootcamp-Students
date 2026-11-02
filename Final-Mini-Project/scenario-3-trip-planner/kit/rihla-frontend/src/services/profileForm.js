// The travel-preferences form on /profile. Pure functions: the page and the tests share them.
// Values are the Trip Store's (GET/PUT /api/profile, app/auth/profile.py): the same record the planner's
// persistent memory reads through MCP get_preferences.

export const CURRENCIES = ['USD', 'EUR', 'GBP', 'JOD', 'ILS', 'AED', 'SAR', 'EGP', 'TRY', 'JPY', 'CHF', 'CAD', 'AUD']

export const BUDGET_STYLES = [
  { value: 'budget', label: 'Budget', hint: 'Free sights, street food, public transport' },
  { value: 'mid-range', label: 'Mid-range', hint: 'A balance of comfort and value' },
  { value: 'splurge', label: 'Splurge', hint: 'Top experiences and fine dining' },
]

// The home page's interest buttons, and the planner's tag for each (app/research_adapter.py INTEREST_WORDS).
export const INTERESTS = [
  { label: 'History & Culture', tag: 'history' },
  { label: 'Nature & Outdoors', tag: 'nature' },
  { label: 'Food & Cuisine', tag: 'food' },
  { label: 'Shopping', tag: 'markets' },
  { label: 'Art & Museums', tag: 'art' },
  { label: 'Adventure', tag: 'adventure' },
  { label: 'Relaxation', tag: 'relaxation' },
  { label: 'Entertainment', tag: 'entertainment' },
]
const KNOWN_TAGS = new Set(INTERESTS.map((i) => i.tag))
const TAG_ALIASES = { museum: 'art' } // the planner also writes "museum" for Art & Museums

export const WALKING = [
  { value: 'low', label: 'Low', hint: 'Short walks, taxis between areas' },
  { value: 'medium', label: 'Medium', hint: 'Comfortable walking most of the day' },
  { value: 'high', label: 'High', hint: 'Happy to explore on foot' },
]

// A preference for how full each day is, never a quota: opening hours, walking limits, travel times and the
// budget still decide what fits. Saved only when the Trip Store supports it (GET /api/profile "supports").
export const PACES = [
  { value: 'relaxed', label: 'Relaxed', hint: 'Fewer activities, more breaks, a flexible schedule' },
  { value: 'balanced', label: 'Balanced', hint: 'A moderate number of activities with reasonable breaks' },
  { value: 'packed', label: 'Packed', hint: 'More activities when opening hours, walking and budget allow' },
]

export const MIN_WALK = 5
export const MAX_WALK = 240

// Stored preferences -> form values. Interest tags Rihla has no button for (written by the chat memory, e.g.
// "local food") are kept in `otherInterests`: shown, and saved back unchanged.
export function toForm(preferences = {}) {
  const tags = Array.isArray(preferences.interests) ? preferences.interests.map((t) => String(t).toLowerCase()) : []
  const normalised = tags.map((t) => TAG_ALIASES[t] || t)
  return {
    homeCurrency: typeof preferences.home_currency === 'string' ? preferences.home_currency : '',
    budgetStyle: typeof preferences.budget_style === 'string' ? preferences.budget_style : '',
    interests: INTERESTS.filter((i) => normalised.includes(i.tag)).map((i) => i.tag),
    otherInterests: [...new Set(normalised.filter((t) => !KNOWN_TAGS.has(t)))],
    walkingTolerance: typeof preferences.walking_tolerance === 'string' ? preferences.walking_tolerance : '',
    maxWalkMinutes: Number.isInteger(preferences.max_walk_minutes) ? String(preferences.max_walk_minutes) : '',
    activityPace: PACES.some((p) => p.value === preferences.activity_pace) ? preferences.activity_pace : '',
  }
}

export function validateProfileForm(form) {
  const errors = {}
  if (form.homeCurrency && !/^[A-Z]{3}$/.test(form.homeCurrency)) errors.homeCurrency = 'Choose a currency code.'
  if (form.budgetStyle && !BUDGET_STYLES.some((b) => b.value === form.budgetStyle)) errors.budgetStyle = 'Choose a budget style.'
  if (form.walkingTolerance && !WALKING.some((w) => w.value === form.walkingTolerance)) {
    errors.walkingTolerance = 'Choose a walking tolerance.'
  }
  if (form.activityPace && !PACES.some((p) => p.value === form.activityPace)) errors.activityPace = 'Choose a pace.'
  if (form.maxWalkMinutes !== '') {
    const minutes = Number(form.maxWalkMinutes)
    if (!Number.isInteger(minutes) || minutes < MIN_WALK || minutes > MAX_WALK) {
      errors.maxWalkMinutes = `Enter whole minutes between ${MIN_WALK} and ${MAX_WALK}.`
    }
  }
  return errors
}

function sameSet(a, b) {
  return a.length === b.length && a.every((x) => b.includes(x))
}

// Only what changed, in the Trip Store's field names. A value left empty is not sent (the store merges, so an
// emptied field keeps its stored value); interests can be cleared.
export function toPayload(form, original) {
  const payload = {}
  if (form.homeCurrency && form.homeCurrency !== original.homeCurrency) payload.home_currency = form.homeCurrency
  if (form.budgetStyle && form.budgetStyle !== original.budgetStyle) payload.budget_style = form.budgetStyle
  if (!sameSet(form.interests, original.interests)) payload.interests = [...form.interests, ...form.otherInterests]
  if (form.walkingTolerance && form.walkingTolerance !== original.walkingTolerance) {
    payload.walking_tolerance = form.walkingTolerance
  }
  if (form.maxWalkMinutes !== '' && form.maxWalkMinutes !== original.maxWalkMinutes) {
    payload.max_walk_minutes = Number(form.maxWalkMinutes)
  }
  if (form.activityPace && form.activityPace !== original.activityPace) payload.activity_pace = form.activityPace
  return payload
}

export function hasChanges(form, original) {
  return Object.keys(toPayload(form, original)).length > 0
}
