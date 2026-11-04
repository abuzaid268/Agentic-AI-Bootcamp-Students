import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { RECORDED_AMMAN_RESULT } from '../data/recordedAmmanResult.js'
import { sourceLinks } from './citations.js'

describe('Sources on the trip page', () => {
  it('lists the citations the backend sent, in order', () => {
    const links = sourceLinks([
      { id: 'SRC-1', title: 'Wikivoyage', url: 'https://en.wikivoyage.org/wiki/Amman' },
      { id: 'SRC-2', title: 'Google Maps', url: 'https://www.google.com/maps/place/?q=place_id:abc' },
    ])
    assert.deepEqual(links.map((l) => [l.id, l.title, l.host]),
      [['SRC-1', 'Wikivoyage', 'en.wikivoyage.org'], ['SRC-2', 'Google Maps', 'google.com']])
  })

  it('never invents a source: no citations, no list', () => {
    assert.deepEqual(sourceLinks(undefined), [])
    assert.deepEqual(sourceLinks([]), [])
    assert.deepEqual(sourceLinks('https://example.com'), [])
  })

  it('drops entries without a web address, and repeats', () => {
    const links = sourceLinks([
      { id: 'a', title: 'Script', url: 'javascript:alert(1)' },
      { id: 'b', title: 'File', url: 'file:///etc/passwd' },
      { id: 'c', title: 'No URL' },
      null,
      { id: 'd', title: 'Site', url: 'https://example.com/x' },
      { id: 'e', title: 'Same site again', url: 'https://example.com/x' },
    ])
    assert.deepEqual(links.map((l) => l.id), ['d'])
  })

  it('shows the address when the title is missing', () => {
    assert.equal(sourceLinks([{ url: 'https://www.visitjordan.com/' }])[0].title, 'visitjordan.com')
  })

  it('an answer recorded before citations existed shows no Sources list, without failing', () => {
    assert.equal('citations' in RECORDED_AMMAN_RESULT, false)
    assert.deepEqual(sourceLinks(RECORDED_AMMAN_RESULT.citations), [])
  })
})
