import { jsPDF } from 'jspdf'
import { getVerificationState } from './tripResult.js'

// The PDF of a trip, built only from the trip's own data (the generated result, or the trip saved in the Trip
// Store): no demo activity, no invented time or price. An unknown cost stays "Price unknown"; a trip that is not
// verified is marked "Draft - Not Verified" on every page, and nothing in it says it was approved unless it was.

const NOT_INCLUDED = [
  'accommodation',
  'flights and intercity transport',
  'local transport (taxis, trams, ferries)',
  'meals that are not in the plan',
  'shopping, tips and incidentals',
]
const KIND_LABELS = { see: 'Sight', do: 'Activity', buy: 'Shopping', eat: 'Restaurant', drink: 'Café / bar' }
const WIN_ANSI_EXTRA = new Set(['€', '–', '—', '‘', '’', '“', '”', '•', '…'])

// The standard PDF fonts cover Latin-1 (é, ü, ñ...). Other letters lose their accent (ū -> u, ı -> i); a script
// the fonts cannot draw at all (e.g. Japanese) becomes "?", never a wrong letter.
export function pdfText(value) {
  return Array.from(String(value ?? '').normalize('NFC')).map((ch) => {
    if (ch.charCodeAt(0) <= 0xff || WIN_ANSI_EXTRA.has(ch)) return ch
    const plain = ch.normalize('NFKD').replace(/[̀-ͯ]/g, '')
    if (plain === 'ı') return 'i'
    return Array.from(plain).every((c) => c.charCodeAt(0) <= 0xff) ? plain : '?'
  }).join('')
}

function asciiName(value) {
  const plain = String(value || 'Trip').normalize('NFKD').replace(/[̀-ͯ]/g, '')
  return plain.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'Trip'
}

function money(value, currency) {
  if (!Number.isFinite(Number(value)) || value === null || value === '') return null
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD', maximumFractionDigits: 2 })
    .format(Number(value))
}

function longDate(iso) {
  const d = new Date(`${iso}T12:00:00`)
  return Number.isNaN(d.getTime()) ? String(iso || '')
    : d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

function costText(a, currency) {
  if (a.cost_status === 'range' && Number.isFinite(a.cost_min) && Number.isFinite(a.cost_max)) {
    return `${money(a.cost_min, currency)}–${money(a.cost_max, currency)} (sources disagree)`
  }
  if (a.cost_status === 'free' || a.estimated_cost === 0) return 'Free (listed as free)'
  return Number.isFinite(a.estimated_cost) ? `${money(a.estimated_cost, currency)} (estimate, whole party)` : 'Price unknown'
}

function travelText(extra, activity) {
  const minutes = extra?.travel_minutes ?? activity.travel_minutes_from_previous
  if (!Number.isInteger(minutes)) return null
  if (extra?.travel_mode === 'driving') return `${minutes} min by taxi or car from the previous stop (fare not included)`
  return `${minutes} min walk from the previous stop`
}

// The trip's status for the PDF: approved (saved in the Trip Store), verified (not approved yet), or a draft.
export function pdfStatus(aiResult, approval) {
  const saved = approval?.trip_id || aiResult?.approval?.trip_id
  if (saved) {
    return { kind: 'approved', label: `Approved · Saved trip ${saved}`,
      detail: 'Verified by Rihla and approved by you. Rihla never books or pays for anything.' }
  }
  const v = getVerificationState(aiResult)
  if (v.level === 'verified') {
    return { kind: 'verified', label: 'Verified · Not yet approved',
      detail: 'This itinerary passed verification but you have not approved it yet.' }
  }
  return { kind: 'draft', label: 'Draft - Not Verified',
    detail: 'This itinerary could not be fully verified. Check opening hours, prices and routes before relying on it.' }
}

// Everything the PDF says, as plain data (testable without drawing anything).
export function pdfModel({ aiResult, request = {}, approval = null }) {
  const it = aiResult.itinerary
  const currency = it.currency || 'USD'
  const extraDays = Object.fromEntries((aiResult.summary?.days || []).map((d) => [d.date, d.activities || []]))
  const days = it.days.map((day, n) => ({
    title: `Day ${n + 1} · ${longDate(day.date)}`,
    items: (day.activities || []).map((a, k) => {
      const extra = extraDays[day.date]?.[k]
      const kind = extra?.kind || a.kind
      return {
        time: a.start_time && a.end_time ? `${a.start_time}–${a.end_time}` : 'Time not set',
        name: a.name,
        kind: KIND_LABELS[kind] || null,
        meal: kind === 'eat' || kind === 'drink' || extra?.meal === true,
        cost: costText(a, currency),
        travel: travelText(extra, a),
        notes: a.notes || null,
        source: a.source_url || null,
      }
    }),
  }))
  const acts = it.days.flatMap((d) => d.activities || [])
  const unknown = acts.filter((a) => !Number.isFinite(a.estimated_cost) && a.cost_status !== 'free')
  const b = aiResult.budget || {}
  const known = b.planned_known_total ?? it.estimated_total ?? null
  const budgetTotal = it.budget_total ?? null
  const verification = aiResult.verification
  const findings = (verification?.findings || []).filter((f) => f.state !== 'advice')
  const status = pdfStatus(aiResult, approval)
  const first = it.days[0]?.date
  const last = it.days[it.days.length - 1]?.date
  return {
    filename: `Rihla_${asciiName(it.destination)}_Itinerary${status.kind === 'draft' ? '_DRAFT' : ''}.pdf`,
    title: `${it.destination} itinerary`,
    status,
    facts: [
      ['Destination', it.destination],
      ['Dates', first === last ? longDate(first) : `${longDate(first)} – ${longDate(last)}`],
      ['Travellers', String(it.travellers ?? request.travellers ?? 'Not given')],
      ['Total trip budget', money(budgetTotal, currency) || 'Not given'],
      ['Interests', (request.interests || []).join(', ') || 'Not given'],
    ],
    days,
    budget: {
      lines: [
        ['Known planned costs (entry fees and planned meals)', money(known, currency) || 'Unknown'],
        ['Activities with an unknown price', `${unknown.length}${unknown.length ? ` (not counted as free)` : ''}`],
        ['Budget left after the known costs (before excluded costs)',
          budgetTotal !== null && known !== null ? money(budgetTotal - Number(known), currency) : 'Cannot be confirmed'],
        ...(b.confidence ? [['How complete the priced picture is', `${b.confidence} — ${b.confidence_basis || ''}`]] : []),
      ],
      unknownNames: unknown.map((a) => a.name),
      notIncluded: b.not_included || NOT_INCLUDED,
    },
    verification: {
      label: verification ? `${verification.status} · ${String(verification.state || '').replace(/_/g, ' ')}` : status.label,
      counts: verification?.counts || null,
      findings: findings.slice(0, 12).map((f) => f.explanation),
      more: Math.max(0, findings.length - 12),
    },
    warnings: [...(aiResult.summary?.limitations || [])],
    disclosure: 'Costs cover only the entry fees and meals priced in this plan, for the whole party, in '
      + `${currency}. Not included: ${(b.not_included || NOT_INCLUDED).join(', ')}. Prices, opening hours and `
      + 'routes come from public sources (Wikivoyage, OpenStreetMap) and can be out of date. Rihla does not book anything.',
  }
}

const COLORS = { ink: [28, 53, 68], muted: [105, 128, 139], teal: [36, 92, 106], light: [230, 242, 243],
  draft: [180, 83, 9], ok: [4, 120, 87], rule: [220, 233, 236] }

// Draws the model on A4 pages: wrapped text, page breaks, a footer on every page, and the draft mark.
export function renderItineraryPdf(model) {
  const doc = new jsPDF({ unit: 'pt', format: 'a4', compress: false })
  const W = doc.internal.pageSize.getWidth()
  const H = doc.internal.pageSize.getHeight()
  const M = 48
  let y = M

  const color = (c) => doc.setTextColor(...c)
  const ensure = (h) => {
    if (y + h > H - M - 20) {
      doc.addPage()
      y = M
    }
  }
  const write = (text, { size = 10, style = 'normal', c = COLORS.ink, indent = 0, gap = 4 } = {}) => {
    doc.setFont('helvetica', style)
    doc.setFontSize(size)
    color(c)
    const lines = doc.splitTextToSize(pdfText(text), W - 2 * M - indent)
    for (const line of lines) {
      ensure(size + 3)
      doc.text(line, M + indent, y + size)
      y += size + 3
    }
    y += gap
  }
  const heading = (text) => {
    ensure(40)
    y += 8
    write(text, { size: 14, style: 'bold', c: COLORS.teal, gap: 2 })
    doc.setDrawColor(...COLORS.rule)
    doc.line(M, y, W - M, y)
    y += 8
  }

  // Title band
  doc.setFillColor(...COLORS.teal)
  doc.rect(0, 0, W, 92, 'F')
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(24)
  doc.setTextColor(255, 255, 255)
  doc.text('Rihla.', M, 44)
  doc.setFontSize(15)
  doc.text(pdfText(model.title), M, 72)
  y = 112
  const statusColor = model.status.kind === 'draft' ? COLORS.draft : COLORS.ok
  write(model.status.label, { size: 13, style: 'bold', c: statusColor, gap: 2 })
  write(model.status.detail, { size: 9, c: COLORS.muted, gap: 10 })
  for (const [label, value] of model.facts) {
    write(`${label}: ${value}`, { size: 10.5, gap: 1 })
  }

  heading('Day by day')
  for (const day of model.days) {
    ensure(50)
    write(day.title, { size: 12, style: 'bold', c: COLORS.teal, gap: 3 })
    if (!day.items.length) write('Free day: nothing planned.', { size: 10, c: COLORS.muted, indent: 12 })
    for (const item of day.items) {
      ensure(42)
      const tag = item.meal ? 'Meal' : item.kind
      write(`${item.time}   ${item.name}${tag ? `  (${tag})` : ''}`, { size: 10.5, style: 'bold', indent: 12, gap: 1 })
      write(`Cost: ${item.cost}`, { size: 9, c: COLORS.muted, indent: 24, gap: 1 })
      if (item.travel) write(item.travel, { size: 9, c: COLORS.muted, indent: 24, gap: 1 })
      if (item.notes) write(`Notes: ${item.notes}`, { size: 8.5, c: COLORS.muted, indent: 24, gap: 1 })
      if (item.source) write(`Source: ${item.source}`, { size: 8, c: COLORS.teal, indent: 24, gap: 1 })
      y += 5
    }
  }

  heading('Budget')
  for (const [label, value] of model.budget.lines) write(`${label}: ${value}`, { size: 10, gap: 1 })
  if (model.budget.unknownNames.length) {
    write(`Unknown prices: ${model.budget.unknownNames.join(', ')}.`, { size: 9, c: COLORS.muted, gap: 2 })
  }
  write(`Not included in the estimate: ${model.budget.notIncluded.join(', ')}.`, { size: 9, c: COLORS.draft })

  heading('Verification')
  write(model.verification.label, { size: 10.5, style: 'bold', gap: 2 })
  if (model.verification.counts) {
    const c = model.verification.counts
    write(`${c.confirmed_problems} confirmed problem(s), ${c.unverifiable} fact(s) that could not be confirmed, `
      + `${c.advice} note(s).`, { size: 9.5, gap: 2 })
  }
  for (const f of model.verification.findings) write(`• ${f}`, { size: 8.5, c: COLORS.muted, indent: 8, gap: 1 })
  if (model.verification.more) write(`… and ${model.verification.more} more.`, { size: 8.5, c: COLORS.muted })

  if (model.warnings.length) {
    heading('Important warnings')
    for (const w of model.warnings) write(`• ${w}`, { size: 9, indent: 8, gap: 2 })
  }
  heading('About these figures')
  write(model.disclosure, { size: 8.5, c: COLORS.muted })

  // Footer and draft mark on every page
  const pages = doc.getNumberOfPages()
  for (let n = 1; n <= pages; n += 1) {
    doc.setPage(n)
    if (model.status.kind === 'draft') {
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      color(COLORS.draft)
      doc.text('DRAFT - NOT VERIFIED', W - M, n === 1 ? 108 : 30, { align: 'right' })
    }
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    color(COLORS.muted)
    doc.text(pdfText(`Rihla · ${model.title} · ${model.status.label}`), M, H - 24)
    doc.text(`Page ${n} of ${pages}`, W - M, H - 24, { align: 'right' })
  }
  return doc
}

export function downloadItineraryPdf(input) {
  const model = pdfModel(input)
  renderItineraryPdf(model).save(model.filename)
  return model.filename
}
