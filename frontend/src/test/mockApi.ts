import { vi } from 'vitest'

export interface MockResponse {
  status?: number
  body: unknown
}

/** Stubs global fetch with a small routing table keyed by "METHOD /path". */
export function mockApi(handlers: Record<string, MockResponse>) {
  const calls: { method: string; path: string }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const path = url.replace(/^https?:\/\/[^/]+/, '')
    const method = (init?.method ?? 'GET').toUpperCase()
    calls.push({ method, path })

    const key = `${method} ${path}`
    const withoutQuery = `${method} ${path.split('?')[0]}`
    const handler = handlers[key] ?? handlers[withoutQuery]
    if (!handler) {
      return new Response(JSON.stringify({ error: `No mock for ${key}` }), { status: 404 })
    }
    return new Response(JSON.stringify(handler.body), { status: handler.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, calls }
}
