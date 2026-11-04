// The "Sources" list on the trip page: aiResult.citations from /api/chat ([{id, title, url}], one per source URL
// behind the itinerary, app/contract.py build_citations). Only what the backend sent is shown: an entry without an
// http(s) URL is dropped, a missing title shows the site's address, and nothing is added.

export function sourceLinks(citations) {
  if (!Array.isArray(citations)) return []
  const seen = new Set()
  const links = []
  for (const citation of citations) {
    const url = typeof citation?.url === 'string' ? citation.url.trim() : ''
    let parsed
    try {
      parsed = new URL(url)
    } catch {
      continue
    }
    if (!['http:', 'https:'].includes(parsed.protocol) || seen.has(parsed.href)) continue
    seen.add(parsed.href)
    const title = typeof citation.title === 'string' && citation.title.trim() ? citation.title.trim() : null
    links.push({
      id: typeof citation.id === 'string' && citation.id ? citation.id : parsed.href,
      title: title || parsed.hostname.replace(/^www\./, ''),
      url: parsed.href,
      host: parsed.hostname.replace(/^www\./, ''),
    })
  }
  return links
}
