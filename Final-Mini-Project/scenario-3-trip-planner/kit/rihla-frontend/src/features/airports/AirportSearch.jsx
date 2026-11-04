import { useEffect, useId, useState } from 'react'
import { PlaneLanding, PlaneTakeoff, X } from 'lucide-react'
import { searchAirports } from './airportsApi.js'
import { airportCode, airportDetails, moveHighlight, shouldSearch, statusMessage } from './airportState.js'

// Two looks, the same as DestinationSearch: "dark" for the home page's glass form, "light" for white panels.
const TONES = {
  dark: {
    label: 'mb-2 block text-xs font-medium text-white/85',
    box: 'flex items-center gap-3 rounded-2xl border border-white/30 bg-white/15 px-4 py-4',
    icon: 'shrink-0 text-[#b7e6e4]',
    input: 'w-full bg-transparent text-sm text-white outline-none placeholder:text-white/55',
    clear: 'text-white/70 hover:text-white',
    status: 'mt-2 text-xs text-white/75',
    error: 'mt-2 text-xs text-red-200',
  },
  light: {
    label: 'mb-2 block text-xs font-semibold text-[#456774]',
    box: 'flex items-center gap-3 rounded-2xl border border-[#d5e6e9] bg-white px-4 py-3 focus-within:ring-2 focus-within:ring-[#a9d7dc]',
    icon: 'shrink-0 text-[#3c8992]',
    input: 'w-full bg-transparent text-sm text-[#1c3544] outline-none placeholder:text-[#8297a0]',
    clear: 'text-[#8297a0] hover:text-[#245c6a]',
    status: 'mt-2 text-xs text-[#6b8791]',
    error: 'mt-2 text-xs text-red-700',
  },
}

const KINDS = {
  departure: { label: 'From', icon: PlaneTakeoff, noun: 'departure airport' },
  arrival: { label: 'To', icon: PlaneLanding, noun: 'arrival airport' },
}

/**
 * Airport search as you type (GET /api/airports), for a departure or an arrival airport.
 *
 * Props:
 *  - kind: "departure" | "arrival" (icon, default label and the clear button's name)
 *  - label, placeholder, name, required, disabled, id
 *  - defaultValue: the starting text (the component keeps its own text after that)
 *  - initialAirport: an airport that starts selected (its label is the text); remount with a new `key` to change it
 *  - onTextChange(text): every change of the typed text (also when an airport is chosen: its label)
 *  - onSelect(airport | null): the chosen airport { id, name, city, region, country, countryCode, iata, icao,
 *    latitude, longitude, type, scheduledService, label }, or null as soon as the text no longer matches it.
 *    iata, icao and coordinates can be null: not every airport has them.
 *  - scheduledOnly (false): only airports OurAirports lists with scheduled service
 *  - country (''): only airports in this country (ISO 3166-1 alpha-2, e.g. "JO"); '' means every country
 *  - debounceMs (300), limit (8), tone ("dark" | "light"), fetchImpl (tests)
 */
export default function AirportSearch({
  kind = 'departure',
  label,
  placeholder = 'City, airport or code, e.g. London or LHR',
  defaultValue = '',
  initialAirport = null,
  onTextChange,
  onSelect,
  scheduledOnly = false,
  country = '',
  debounceMs = 300,
  limit = 8,
  tone = 'light',
  required = false,
  disabled = false,
  name,
  id,
  fetchImpl,
}) {
  const autoId = useId()
  const inputId = id || `airport-search-${autoId}`
  const listId = `${inputId}-options`
  const statusId = `${inputId}-status`
  const styles = TONES[tone] || TONES.light
  const meta = KINDS[kind] || KINDS.departure
  const KindIcon = meta.icon
  const fieldLabel = label || meta.label

  // An airport chosen for the traveller (a suggestion they picked, or the only one that qualified) starts selected
  // and is shown as an ordinary choice: typing replaces it, and the parent already holds it (it does not get an
  // onSelect for the starting value).
  const [text, setText] = useState(initialAirport ? initialAirport.label : defaultValue)
  const [selected, setSelected] = useState(initialAirport)
  const [results, setResults] = useState([])
  const [ambiguous, setAmbiguous] = useState(false)
  const [status, setStatus] = useState('idle') // idle | loading | ready | error
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const [attempt, setAttempt] = useState(0) // bumped by "Try again"

  const searchable = shouldSearch(text) && !(selected && selected.label === text)

  useEffect(() => {
    if (!searchable) return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setStatus('loading')
      setError('')
      try {
        const answer = await searchAirports(text, { signal: controller.signal, limit, scheduledOnly, country, fetchImpl })
        setResults(answer.results)
        setAmbiguous(answer.ambiguous)
        setHighlight(answer.results.length ? 0 : -1)
        setStatus('ready')
      } catch (err) {
        if (controller.signal.aborted) return // a newer search replaced this one
        setResults([])
        setHighlight(-1)
        setStatus('error')
        setError(err instanceof Error ? err.message : 'Airport search failed.')
      }
    }, debounceMs)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [text, searchable, debounceMs, limit, scheduledOnly, country, fetchImpl, attempt])

  const reset = () => {
    setResults([])
    setAmbiguous(false)
    setStatus('idle')
    setError('')
    setHighlight(-1)
  }

  const handleChange = (event) => {
    const next = event.target.value
    setText(next)
    setOpen(true)
    if (selected) {
      setSelected(null)
      onSelect?.(null)
    }
    onTextChange?.(next)
    if (!shouldSearch(next)) reset()
  }

  const choose = (airport) => {
    setText(airport.label)
    setSelected(airport)
    setOpen(false)
    setHighlight(-1)
    onTextChange?.(airport.label)
    onSelect?.(airport)
  }

  const clear = () => {
    setText('')
    setOpen(false)
    reset()
    if (selected) {
      setSelected(null)
      onSelect?.(null)
    }
    onTextChange?.('')
  }

  const showList = open && results.length > 0 && !disabled

  const handleKeyDown = (event) => {
    const { key } = event
    if (['ArrowDown', 'ArrowUp'].includes(key) || (showList && ['Home', 'End'].includes(key))) {
      if (!results.length) return
      event.preventDefault()
      setOpen(true)
      setHighlight((current) => moveHighlight(current, key, results.length))
    } else if (key === 'Enter' && showList && results[highlight]) {
      event.preventDefault() // choose the airport instead of submitting the form
      choose(results[highlight])
    } else if (key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    } else if (key === 'Tab') {
      setOpen(false)
    }
  }

  const message = statusMessage({ status, count: results.length, error, ambiguous, searchable })
  const optionId = (index) => `${listId}-${index}`

  return (
    <div className="relative">
      <label htmlFor={inputId} className={styles.label}>
        {fieldLabel}
      </label>
      <div className={styles.box}>
        <KindIcon size={18} className={styles.icon} aria-hidden="true" />
        <input
          id={inputId}
          name={name}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={showList && highlight >= 0 ? optionId(highlight) : undefined}
          aria-describedby={statusId}
          autoComplete="off"
          spellCheck={false}
          required={required}
          disabled={disabled}
          maxLength={100}
          value={text}
          placeholder={placeholder}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length && setOpen(true)}
          onBlur={() => setOpen(false)}
          className={styles.input}
        />
        {status === 'loading' && (
          <span
            aria-hidden="true"
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent opacity-70"
          />
        )}
        {text && !disabled && (
          <button type="button" onClick={clear} aria-label={`Clear ${meta.noun}`} className={styles.clear}>
            <X size={16} />
          </button>
        )}
      </div>

      <ul
        id={listId}
        role="listbox"
        aria-label={`${fieldLabel} airport suggestions`}
        hidden={!showList}
        className="absolute left-0 right-0 z-30 mt-2 max-h-72 overflow-y-auto rounded-2xl border border-[#d5e6e9] bg-white py-1 text-left text-[#1c3544] shadow-xl"
      >
        {results.map((airport, index) => {
          const code = airportCode(airport)
          return (
            <li
              key={airport.id}
              id={optionId(index)}
              role="option"
              aria-selected={index === highlight}
              onMouseDown={(event) => event.preventDefault()} // keep focus in the input
              onMouseEnter={() => setHighlight(index)}
              onClick={() => choose(airport)}
              className={`flex cursor-pointer items-start gap-3 px-4 py-2.5 text-sm ${
                index === highlight ? 'bg-[#e5f4f4]' : 'hover:bg-[#f1f7f8]'
              }`}
            >
              <span
                className="mt-0.5 w-12 shrink-0 rounded-md bg-[#e5f4f4] px-1.5 py-0.5 text-center font-mono text-xs font-bold text-[#245c6a]"
                aria-hidden={!code}
              >
                {code || '—'}
              </span>
              <span className="min-w-0">
                <span className="block font-semibold">{airport.name}</span>
                <span className="block truncate text-xs text-[#6b8791]">
                  {airportDetails(airport) || 'Location unknown'}
                  {!airport.scheduledService && ' · No scheduled service listed'}
                </span>
              </span>
            </li>
          )
        })}
        <li role="presentation" className="border-t border-[#edf2f3] px-4 pb-1 pt-2 text-[10px] text-[#91a3ab]">
          Airport data: OurAirports (public domain)
        </li>
      </ul>

      <p id={statusId} role="status" aria-live="polite" className={status === 'error' ? styles.error : styles.status}>
        {message}
        {status === 'error' && (
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="ml-2 font-semibold underline">
            Try again
          </button>
        )}
      </p>
    </div>
  )
}
