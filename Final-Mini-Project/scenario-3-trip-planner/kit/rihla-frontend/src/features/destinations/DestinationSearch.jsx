import { useEffect, useId, useState } from 'react'
import { MapPin, X } from 'lucide-react'
import { searchDestinations } from './destinationsApi.js'
import { destinationText, moveHighlight, placeDetails, shouldSearch, statusMessage } from './searchState.js'

// Two looks: "dark" for the home page's glass form, "light" for white panels.
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

/**
 * Worldwide city search as you type (GET /api/destinations).
 *
 * Props:
 *  - label, placeholder, name, required, disabled, id
 *  - defaultValue: the starting text (the component keeps its own text after that)
 *  - onTextChange(text): every change of the typed text (also when a city is chosen: its label, shortened to
 *    100 characters when needed, the trip form's limit)
 *  - onSelect(destination | null): the chosen city { id, name, region, country, countryCode, latitude,
 *    longitude, timezone, label, ... }, or null as soon as the text no longer matches a chosen city
 *  - debounceMs (300), limit (8), tone ("dark" | "light"), fetchImpl (tests)
 */
export default function DestinationSearch({
  label = 'Destination',
  placeholder = 'City, e.g. Paris',
  defaultValue = '',
  onTextChange,
  onSelect,
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
  const inputId = id || `destination-search-${autoId}`
  const listId = `${inputId}-options`
  const statusId = `${inputId}-status`
  const styles = TONES[tone] || TONES.light

  const [text, setText] = useState(defaultValue)
  const [selected, setSelected] = useState(null)
  const [results, setResults] = useState([])
  const [ambiguous, setAmbiguous] = useState(false)
  const [scope, setScope] = useState('worldwide') // 'popular' for one or two letters (the server's popular list)
  const [status, setStatus] = useState('idle') // idle | loading | ready | error
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const [attempt, setAttempt] = useState(0) // bumped by "Try again"

  const searchable = shouldSearch(text) && !(selected && destinationText(selected) === text)

  useEffect(() => {
    if (!searchable) return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setStatus('loading')
      setError('')
      try {
        const answer = await searchDestinations(text, { signal: controller.signal, limit, fetchImpl })
        setResults(answer.results)
        setAmbiguous(answer.ambiguous)
        setScope(answer.scope)
        setHighlight(answer.results.length ? 0 : -1)
        setStatus('ready')
      } catch (err) {
        if (controller.signal.aborted) return // a newer search replaced this one
        setResults([])
        setHighlight(-1)
        setStatus('error')
        setError(err instanceof Error ? err.message : 'City search failed.')
      }
    }, debounceMs)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [text, searchable, debounceMs, limit, fetchImpl, attempt])

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

  const choose = (destination) => {
    const chosen = destinationText(destination)
    setText(chosen)
    setSelected(destination)
    setOpen(false)
    setHighlight(-1)
    onTextChange?.(chosen)
    onSelect?.(destination)
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
      event.preventDefault() // choose the city instead of submitting the form
      choose(results[highlight])
    } else if (key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    } else if (key === 'Tab') {
      setOpen(false)
    }
  }

  const message = statusMessage({ status, count: results.length, error, ambiguous, searchable, scope })
  const optionId = (index) => `${listId}-${index}`

  return (
    <div className="relative">
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <div className={styles.box}>
        <MapPin size={18} className={styles.icon} aria-hidden="true" />
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
          <button type="button" onClick={clear} aria-label="Clear destination" className={styles.clear}>
            <X size={16} />
          </button>
        )}
      </div>

      <ul
        id={listId}
        role="listbox"
        aria-label={`${label} suggestions`}
        hidden={!showList}
        className="absolute left-0 right-0 z-30 mt-2 max-h-72 overflow-y-auto rounded-2xl border border-[#d5e6e9] bg-white py-1 text-left text-[#1c3544] shadow-xl"
      >
        {results.map((destination, index) => (
          <li
            key={destination.id}
            id={optionId(index)}
            role="option"
            aria-selected={index === highlight}
            onMouseDown={(event) => event.preventDefault()} // keep focus in the input
            onMouseEnter={() => setHighlight(index)}
            onClick={() => choose(destination)}
            className={`flex cursor-pointer items-start gap-3 px-4 py-2.5 text-sm ${
              index === highlight ? 'bg-[#e5f4f4]' : 'hover:bg-[#f1f7f8]'
            }`}
          >
            <MapPin size={15} className="mt-0.5 shrink-0 text-[#3c8992]" aria-hidden="true" />
            <span className="min-w-0">
              <span className="block font-semibold">{destination.name}</span>
              <span className="block truncate text-xs text-[#6b8791]">
                {placeDetails(destination) || 'Region unknown'}
                {destination.countryCode ? ` · ${destination.countryCode}` : ''}
              </span>
            </span>
          </li>
        ))}
        <li role="presentation" className="border-t border-[#edf2f3] px-4 pb-1 pt-2 text-[10px] text-[#91a3ab]">
          City data: GeoNames (CC BY 4.0) via Open-Meteo
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
