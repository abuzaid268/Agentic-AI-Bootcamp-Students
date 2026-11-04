import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { Component, createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { sanitizeNearby } from '../airports/airportState.js'
import { sanitizeFlightAnswer, sanitizeOffer } from '../flights/flightState.js'
import TravelInfoBoundary from './TravelInfoBoundary.js'

// What these tests do and do not show: they check the boundary's contract (the calls React makes when a child throws
// while rendering) and that nothing the weather and flight boxes render can throw on a bad server answer. They do not
// render into a real DOM (the project has no DOM test environment), and react-dom/server does not use error
// boundaries, so "a broken child is replaced by the notice" is verified by the contract, not by a browser.

// The calls React makes: getDerivedStateFromError, then componentDidCatch, then render again.
function mount(children) {
  const boundary = new TravelInfoBoundary({ children })
  boundary.setState = (patch) => Object.assign(boundary.state, typeof patch === 'function' ? patch(boundary.state) : patch)
  return boundary
}
function fail(boundary, error = new Error('render failed')) {
  Object.assign(boundary.state, TravelInfoBoundary.getDerivedStateFromError(error))
  const logged = []
  const original = console.error
  console.error = (...args) => logged.push(args)
  try { boundary.componentDidCatch(error, { componentStack: '' }) } finally { console.error = original }
  return logged
}

describe('the weather and flights error boundary', () => {
  it('is a React class component with getDerivedStateFromError, which is what makes it a boundary', () => {
    assert.ok(TravelInfoBoundary.prototype instanceof Component)
    assert.equal(typeof TravelInfoBoundary.getDerivedStateFromError, 'function')
    assert.deepEqual(TravelInfoBoundary.getDerivedStateFromError(new Error('x')), { failed: true })
  })

  it('shows its children untouched while nothing fails', () => {
    const child = h('p', null, 'weather and flights')
    assert.equal(mount(child).render(), child)
    assert.equal(renderToStaticMarkup(h(TravelInfoBoundary, null, child)), '<p>weather and flights</p>')
  })

  it('replaces a failed child by a short notice that says the itinerary is not affected', () => {
    const boundary = mount(h('p', null, 'weather and flights'))
    fail(boundary)
    const html = renderToStaticMarkup(boundary.render())
    assert.match(html, /Weather and flights could not be shown/)
    assert.match(html, /Your itinerary is not affected/)
    assert.match(html, /role="status"/)
    assert.match(html, /<button type="button"[^>]*>Try again<\/button>/)
    assert.doesNotMatch(html, /weather and flights<\/p>/) // the failed child is gone
  })

  it('logs the error for the developer and keeps the user\'s page going', () => {
    const boundary = mount(null)
    const logged = fail(boundary, new Error('boom'))
    assert.equal(logged.length, 1)
    assert.match(String(logged[0][0]), /could not be shown/)
    assert.equal(logged[0][1].message, 'boom')
  })

  it('can try again: the children are rendered again', () => {
    const child = h('p', null, 'back')
    const boundary = mount(child)
    fail(boundary)
    assert.notEqual(boundary.render(), child)
    boundary.retry()
    assert.equal(boundary.render(), child)
  })
})

describe('the trip page', () => {
  const page = readFileSync(new URL('../../pages/TripDashboard.jsx', import.meta.url), 'utf8')

  it('wraps only the weather and flights section, and imports the boundary from the feature', () => {
    assert.match(page, /import \{ TravelInfoBoundary, TripTravelInfo \} from '\.\.\/features\/trip-travel'/)
    const open = page.indexOf('<TravelInfoBoundary>')
    const close = page.indexOf('</TravelInfoBoundary>')
    assert.ok(open > 0 && close > open)
    const inside = page.slice(open, close)
    assert.equal((inside.match(/<TripTravelInfo\b/g) || []).length, 1)
    // nothing of the itinerary, the budget, WHAT IF or the PDF is inside the boundary
    assert.doesNotMatch(inside, /WhatIfPanel|Budget overview|pdf|activeDay|planDays\.map/i)
    assert.equal((page.match(/<TravelInfoBoundary>/g) || []).length, 1)
  })

  it('still shows the section for a generated trip only, never the sample', () => {
    assert.match(page, /\{isReal && !sampleEntry && \(\s*\n\s*<div className="mt-7">\s*\n\s*<TravelInfoBoundary>/)
  })

  it('exports the boundary from the feature', () => {
    assert.match(readFileSync(new URL('./index.js', import.meta.url), 'utf8'), /default as TravelInfoBoundary/)
  })
})

// What the boxes render comes from the sanitizers, so a broken or hostile server answer must never make them throw:
// each field of a real answer is replaced, one at a time, by every kind of wrong value.
describe('a bad server answer cannot break rendering', () => {
  const GARBAGE = [null, undefined, 0, -1, 1.5, Number.NaN, Infinity, '', 'x', '9'.repeat(500), true, [], [null], {}, { a: 1 }, () => 1]
  const DEMO = JSON.parse(readFileSync(new URL('../flights/fixtures/demo_tlv_lhr_round_trip.json', import.meta.url), 'utf8'))
  const NEAR = JSON.parse(readFileSync(new URL('../airports/fixtures/near_jerusalem.json', import.meta.url), 'utf8'))

  // every path to a value in a JSON document
  function* paths(value, prefix = []) {
    yield prefix
    if (value && typeof value === 'object') for (const key of Object.keys(value)) yield* paths(value[key], [...prefix, key])
  }
  function withValue(root, path, replacement) {
    if (!path.length) return replacement
    const copy = Array.isArray(root) ? [...root] : { ...root }
    copy[path[0]] = withValue(root[path[0]], path.slice(1), replacement)
    return copy
  }

  it('flight offers: the sanitizer returns an offer or null, and never throws', () => {
    let checked = 0
    for (const path of paths(DEMO.offers[0])) {
      for (const bad of GARBAGE) {
        const result = sanitizeOffer(withValue(DEMO.offers[0], path, bad))
        assert.ok(result === null || typeof result === 'object', path.join('.'))
        checked += 1
      }
    }
    assert.ok(checked > 400)
  })

  it('a whole flight answer: cleaned, or a plain Error the caller shows as a message', () => {
    for (const path of paths(DEMO)) {
      for (const bad of GARBAGE) {
        try {
          const answer = sanitizeFlightAnswer(withValue(DEMO, path, bad))
          assert.ok(Array.isArray(answer.offers) && answer.query && Array.isArray(answer.notices))
        } catch (err) {
          assert.ok(err instanceof Error && /unexpected flight search answer/.test(err.message), `${path.join('.')}: ${err.message}`)
        }
      }
    }
  })

  it('nearby airports: cleaned, or a plain Error the caller shows as a message', () => {
    for (const path of paths(NEAR)) {
      for (const bad of GARBAGE) {
        try {
          const answer = sanitizeNearby(withValue(NEAR, path, bad))
          assert.ok(Array.isArray(answer.airports))
          for (const a of answer.airports) assert.ok(a.iata && Number.isFinite(a.distanceKm))
        } catch (err) {
          assert.ok(err instanceof Error && /unexpected nearby airports answer/.test(err.message), `${path.join('.')}: ${err.message}`)
        }
      }
    }
  })
})
