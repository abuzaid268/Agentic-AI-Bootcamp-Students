import { useState } from 'react'
import { ArrowRight, CloudRain, Clock3, Landmark, Loader2, Sparkles, Wallet, X } from 'lucide-react'
import { AuthRequiredError } from '../auth/authApi'
import { useAuth } from '../auth/authContext'
import { formatDate, formatMoney } from '../services/itineraryAdapter'
import {
  applyWhatIf, compareItineraries, getWhatIfOptions, previewWhatIf, SCENARIOS, scenarioPayload, validateScenario,
} from '../services/whatIf'

const ICONS = { budget_cut: Wallet, rain: CloudRain, closure: Landmark, delay: Clock3 }

// WHAT IF on the itinerary page: choose a hypothetical condition, preview the revised plan next to the current one,
// and apply it only after reviewing it. Nothing on the page changes until "Apply this version".
export default function WhatIfPanel({ aiResult, sessionId, blockedReason, onApplied }) {
  const { sessionExpired } = useAuth()
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState({ loading: false, data: null, error: '' })
  const [type, setType] = useState('budget_cut')
  const [inputs, setInputs] = useState({ percent: 30, hours: 3, date: '', placeId: '' })
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [proposal, setProposal] = useState(null)
  // The parent keys this panel by plan_version: a new plan (a revision, an applied WHAT IF) starts it afresh, so an
  // older preview never stays on screen.
  const planVersion = aiResult?.plan_version || null

  const loadOptions = async () => {
    setOptions({ loading: true, data: null, error: '' })
    try {
      setOptions({ loading: false, data: await getWhatIfOptions(sessionId), error: '' })
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        setOptions({ loading: false, data: null, error: '' })
        sessionExpired(() => loadOptions())
        return
      }
      setOptions({ loading: false, data: null, error: err instanceof Error ? err.message : 'The WHAT IF options could not be loaded.' })
    }
  }

  const openPanel = () => {
    setOpen(true)
    if (!blockedReason && !options.data && !options.loading) loadOptions()
  }

  const generate = async () => {
    const problem = validateScenario(type, inputs)
    if (problem) {
      setError(problem)
      return
    }
    setBusy('preview')
    setError('')
    setProposal(null)
    try {
      setProposal(await previewWhatIf(sessionId, planVersion, scenarioPayload(type, inputs)))
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        sessionExpired(() => generate())
        return
      }
      setError(err instanceof Error ? err.message : 'The WHAT IF could not be generated. Your itinerary was not changed.')
    } finally {
      setBusy('')
    }
  }

  const apply = async () => {
    const proposalId = proposal?.whatif?.proposal_id
    if (!proposalId) return
    setBusy('apply')
    setError('')
    try {
      const result = await applyWhatIf(sessionId, proposalId)
      if (result?.revision?.outcome !== 'revised' || !result?.itinerary) {
        setError(result?.message || 'This WHAT IF could not be applied. Your itinerary was not changed.')
        return
      }
      setProposal(null)
      setOpen(false)
      onApplied(result, proposal.whatif)
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        sessionExpired(() => apply())
        return
      }
      setError(err instanceof Error ? err.message : 'This WHAT IF could not be applied. Your itinerary was not changed.')
    } finally {
      setBusy('')
    }
  }

  if (!open) {
    return (
      <section className="rounded-[28px] border border-[#e0ebed] bg-white p-6 shadow-sm">
        <h2 className="mb-2 flex items-center gap-2 text-lg font-bold"><Sparkles size={18} className="text-[#65aab3]" /> WHAT IF</h2>
        <p className="mb-4 text-sm leading-6 text-[#8297a0]">
          Try a smaller budget, rain, a closed attraction or a late arrival on this plan. You see the revised plan
          first; nothing changes unless you apply it.
        </p>
        <button type="button" onClick={openPanel}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#245c6a] px-5 py-3 text-sm font-bold text-white hover:bg-[#347989]">
          Open WHAT IF <ArrowRight size={16} />
        </button>
      </section>
    )
  }

  const data = options.data
  const unavailable = blockedReason || (data && data.available === false ? data.reason : '')
  const preview = proposal?.status === 'whatif_preview' ? proposal : null
  const notFeasible = proposal && !preview ? (proposal.whatif?.reason || proposal.message || proposal.reply) : ''
  const cmp = preview ? compareItineraries(aiResult, preview) : null
  const money = (v) => (v == null ? 'not set' : formatMoney(v, cmp?.budget.currency || 'USD'))

  return (
    <section className="rounded-[28px] border border-[#cfe3e6] bg-white p-6 shadow-sm" aria-label="WHAT IF">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-bold"><Sparkles size={18} className="text-[#65aab3]" /> WHAT IF</h2>
        <button type="button" onClick={() => { setOpen(false); setProposal(null); setError('') }} aria-label="Close WHAT IF"
          className="rounded-full p-1.5 text-[#8297a0] hover:bg-[#edf5f6]"><X size={18} /></button>
      </div>

      {unavailable ? (
        <p role="status" className="rounded-xl bg-[#f3f7f8] p-3 text-sm leading-6 text-[#64848d]">{unavailable}</p>
      ) : options.loading ? (
        <p role="status" className="flex items-center gap-2 text-sm text-[#8297a0]"><Loader2 size={16} className="animate-spin" /> Loading this plan’s options…</p>
      ) : options.error ? (
        <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">
          {options.error} <button type="button" onClick={loadOptions} className="font-semibold underline">Try again</button>
        </p>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Scenario">
            {SCENARIOS.map((s) => {
              const Icon = ICONS[s.type]
              return (
                <button key={s.type} type="button" role="radio" aria-checked={type === s.type}
                  onClick={() => { setType(s.type); setProposal(null); setError('') }}
                  className={`rounded-2xl border p-3 text-left text-xs transition ${type === s.type
                    ? 'border-[#245c6a] bg-[#e6f2f3] text-[#1c3544]' : 'border-[#e0ebed] text-[#64848d] hover:bg-[#f3f7f8]'}`}>
                  <span className="mb-1 flex items-center gap-1.5 text-sm font-semibold"><Icon size={15} /> {s.label}</span>
                  {s.hint}
                </button>
              )
            })}
          </div>

          <div className="mt-4 space-y-3 text-sm">
            {type === 'budget_cut' && (
              <label className="block">Reduce the budget by
                <select value={inputs.percent} onChange={(e) => setInputs({ ...inputs, percent: Number(e.target.value) })}
                  className="ml-2 rounded-lg border border-[#dce9ec] px-2 py-1">
                  {[10, 20, 30, 40, 50].map((p) => <option key={p} value={p}>{p}%</option>)}
                </select>
                {data.budget_total && <span className="ml-2 text-xs text-[#8297a0]">of {formatMoney(Number(data.budget_total), data.currency)}</span>}
              </label>
            )}
            {type === 'rain' && (
              <label className="block">Rain on
                <select value={inputs.date} onChange={(e) => setInputs({ ...inputs, date: e.target.value })}
                  className="ml-2 rounded-lg border border-[#dce9ec] px-2 py-1">
                  <option value="">every day</option>
                  {data.dates.map((d) => <option key={d} value={d}>{formatDate(d)}</option>)}
                </select>
                <span className="mt-1 block text-xs text-[#8297a0]">
                  Outdoor in this plan: {data.attractions.filter((a) => a.setting === 'outdoor').map((a) => a.name).join(', ') || 'none'}.
                </span>
              </label>
            )}
            {type === 'closure' && (
              <label className="block">Closed attraction
                <select value={inputs.placeId} onChange={(e) => setInputs({ ...inputs, placeId: e.target.value })}
                  className="mt-1 block w-full rounded-lg border border-[#dce9ec] px-2 py-1.5">
                  <option value="">Choose one…</option>
                  {data.attractions.map((a) => <option key={a.place_id} value={a.place_id}>{a.name} · {formatDate(a.date)}</option>)}
                </select>
              </label>
            )}
            {type === 'delay' && (
              <label className="block">Arrive later by
                <select value={inputs.hours} onChange={(e) => setInputs({ ...inputs, hours: Number(e.target.value) })}
                  className="ml-2 rounded-lg border border-[#dce9ec] px-2 py-1">
                  {[1, 2, 3, 4, 5, 6].map((h) => <option key={h} value={h}>{h} hour{h === 1 ? '' : 's'}</option>)}
                </select>
              </label>
            )}
          </div>

          <button type="button" onClick={generate} disabled={busy !== ''} aria-busy={busy === 'preview'}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#245c6a] px-5 py-3 text-sm font-bold text-white hover:bg-[#347989] disabled:opacity-60">
            {busy === 'preview' ? <><Loader2 size={16} className="animate-spin" /> Revising and verifying…</> : 'Generate revised itinerary'}
          </button>
          <p className="mt-2 text-center text-xs text-[#91a3ab]">Hypothetical: nothing here claims it really happens.</p>
        </>
      ) : null}

      {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {notFeasible && (
        <p role="status" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
          <strong>Not possible for this plan.</strong> {notFeasible}
        </p>
      )}

      {preview && cmp && (
        <div className="mt-5 space-y-4 border-t border-[#edf2f3] pt-4 text-sm" aria-label="WHAT IF comparison">
          <div>
            <p className="font-semibold">{preview.whatif.title}</p>
            <p className="mt-1 text-xs leading-5 text-[#64848d]">{preview.whatif.assumption}</p>
            {preview.whatif.weather?.note && <p className="mt-1 text-xs leading-5 text-[#64848d]">{preview.whatif.weather.note}</p>}
          </div>

          <dl className="grid grid-cols-2 gap-2 rounded-xl bg-[#f3f7f8] p-3 text-xs">
            <dt className="text-[#8297a0]">Budget</dt><dd>{money(cmp.budget.before)} → <strong>{money(cmp.budget.after)}</strong></dd>
            <dt className="text-[#8297a0]">Known costs</dt><dd>{money(cmp.budget.knownBefore)} → <strong>{money(cmp.budget.knownAfter)}</strong></dd>
            <dt className="text-[#8297a0]">Unknown prices</dt><dd>{cmp.budget.unknownBefore} → <strong>{cmp.budget.unknownAfter}</strong></dd>
            <dt className="text-[#8297a0]">Verification</dt><dd>{cmp.verification.before || '—'} → <strong>{cmp.verification.after || '—'}</strong></dd>
          </dl>

          <ul className="space-y-2">
            {cmp.days.map((d) => (
              <li key={d.date} className={`rounded-xl border p-3 text-xs leading-5 ${d.changed ? 'border-[#cfe3e6]' : 'border-[#edf2f3] text-[#91a3ab]'}`}>
                <p className="font-semibold">{formatDate(d.date)}{d.changed ? '' : ' · unchanged'}</p>
                {d.removed.map((n) => <p key={`r-${n}`} className="text-red-700">− {n}</p>)}
                {d.added.map((n) => <p key={`a-${n}`} className="text-emerald-700">+ {n}</p>)}
                {d.moved.map((m) => <p key={`m-${m.name}`}>{m.name}: {m.from || '—'} → {m.to || '—'}</p>)}
              </li>
            ))}
          </ul>

          {(preview.revision?.notes || []).length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-amber-800">
              {preview.revision.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
          <p className="text-xs leading-5 text-[#64848d]">
            {cmp.verification.eligibleAfter
              ? 'If you apply it, this version can be approved (with what its checks rely on shown before you approve).'
              : `If you apply it, this version cannot be approved yet: ${cmp.verification.reasonAfter || 'it has not passed verification.'}`}
          </p>

          <div className="flex gap-2">
            <button type="button" onClick={apply} disabled={busy !== ''} aria-busy={busy === 'apply'}
              className="flex-1 rounded-2xl bg-[#245c6a] px-4 py-3 text-sm font-bold text-white hover:bg-[#347989] disabled:opacity-60">
              {busy === 'apply' ? 'Applying…' : 'Apply this version'}
            </button>
            <button type="button" onClick={() => setProposal(null)} disabled={busy !== ''}
              className="rounded-2xl border border-[#dce9ec] px-4 py-3 text-sm font-semibold text-[#64848d] hover:bg-[#f3f7f8]">
              Keep my plan
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
