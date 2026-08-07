export interface HeadingEntry {
  level: number
  text: string
  slug: string
}

function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '') || 'section'
  )
}

/**
 * Extracts ATX ("#") headings from Markdown source, ignoring fenced code
 * blocks, and assigns each a stable, de-duplicated slug id. `MarkdownView`'s
 * heading renderer consumes these slugs in the same top-to-bottom order it
 * renders headings, so the ids always line up with this list.
 */
export function extractHeadings(markdown: string): HeadingEntry[] {
  const headings: HeadingEntry[] = []
  const seen = new Map<string, number>()
  let inFence = false

  for (const line of markdown.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('```') || trimmed.startsWith('~~~')) {
      inFence = !inFence
      continue
    }
    if (inFence) continue

    const match = /^(#{1,6})\s+(.+?)\s*#*$/.exec(trimmed)
    if (!match) continue

    const level = match[1].length
    const text = match[2].trim()
    const base = slugify(text)
    const occurrence = seen.get(base) ?? 0
    seen.set(base, occurrence + 1)
    const slug = occurrence === 0 ? base : `${base}-${occurrence}`
    headings.push({ level, text, slug })
  }

  return headings
}
