import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client'
import { mockApi } from '../test/mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('api client', () => {
  it('returns typed data on success', async () => {
    mockApi({ 'GET /health': { body: { status: 'ok', version: '0.1.0' } } })

    const result = await api.health()

    expect(result).toEqual({ status: 'ok', version: '0.1.0' })
  })

  it('throws an ApiError with the server message on a non-2xx response', async () => {
    mockApi({
      'GET /runs/does-not-exist': { status: 404, body: { error: "No run named 'x' found." } },
    })

    await expect(api.run('does-not-exist')).rejects.toMatchObject({
      name: 'ApiError',
      message: "No run named 'x' found.",
      status: 404,
    })
  })

  it('throws an ApiError when the service is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('fetch failed'))),
    )

    await expect(api.health()).rejects.toBeInstanceOf(ApiError)
    await expect(api.health()).rejects.toMatchObject({
      message: expect.stringContaining('buildrail serve'),
    })
  })

  it('sends POST command bodies as JSON', async () => {
    const { calls, fetchMock } = mockApi({
      'POST /commands/explain': { body: { success: true, message: 'ok' } },
    })

    await api.runCommand('explain', { path: '/tmp/project' })

    expect(calls).toEqual([{ method: 'POST', path: '/commands/explain' }])
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({ path: '/tmp/project' })
  })

  it('marks a request cancelled via an external AbortSignal as cancelled', async () => {
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            const err = new DOMException('Aborted', 'AbortError')
            reject(err)
          })
        })
      }),
    )

    const promise = api.health(controller.signal)
    controller.abort()

    await expect(promise).rejects.toMatchObject({ cancelled: true })
  })

  it('does not URL-encode the slash in an artifact id', async () => {
    const { calls } = mockApi({
      'GET /artifacts/20260101-000000-abc/001-review-x': {
        body: { id: '20260101-000000-abc/001-review-x' },
      },
    })

    await api.artifact('20260101-000000-abc/001-review-x')

    expect(calls[0]?.path).toBe('/artifacts/20260101-000000-abc/001-review-x')
  })
})
