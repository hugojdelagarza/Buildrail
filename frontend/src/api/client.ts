// Centralized, typed HTTP client for Buildrail's local service. Every
// request goes through `request()` below — no component fetches directly.
// The backend never wraps responses in a `{ data: ... }` envelope (see
// routes.py's module docstring for why), so this client is also where that
// gets normalized into one consistent shape for the rest of the app: a
// resolved promise of the typed payload, or a thrown `ApiError`.

import type {
  ArtifactPayload,
  CommandResult,
  CommandsResponse,
  ConfigResponse,
  HealthResponse,
  PipelinesResponse,
  ProjectResponse,
  RunDetail,
  RunsResponse,
  SkillsResponse,
  VersionResponse,
} from './types'

const BASE_URL =
  (import.meta.env.VITE_BUILDRAIL_API_URL as string | undefined) ?? 'http://127.0.0.1:8787'

const DEFAULT_TIMEOUT_MS = 10_000
// Commands run synchronously server-side and can be genuinely slow (e.g.
// `verify` runs the full local test suite) — give them a generous ceiling.
const COMMAND_TIMEOUT_MS = 5 * 60 * 1000

export class ApiError extends Error {
  readonly status: number | null
  readonly cancelled: boolean

  constructor(message: string, status: number | null, cancelled = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.cancelled = cancelled
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
}

function isErrorPayload(payload: unknown): payload is { error: string } {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'error' in payload &&
    typeof (payload as { error: unknown }).error === 'string'
  )
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const timeout = setTimeout(() => controller.abort(), timeoutMs)

  const externalSignal = options.signal
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort()
    else externalSignal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    })
  } catch (cause) {
    clearTimeout(timeout)
    if (externalSignal?.aborted) {
      throw new ApiError('Request cancelled.', null, true)
    }
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw new ApiError('Request timed out. Is `buildrail serve` running?', null)
    }
    throw new ApiError('Could not reach the Buildrail service. Is `buildrail serve` running?', null)
  }
  clearTimeout(timeout)

  let payload: unknown = null
  const text = await response.text()
  if (text.length > 0) {
    try {
      payload = JSON.parse(text)
    } catch {
      throw new ApiError('The Buildrail service returned an invalid response.', response.status)
    }
  }

  if (!response.ok) {
    const message = isErrorPayload(payload)
      ? payload.error
      : `Request failed with status ${response.status}.`
    throw new ApiError(message, response.status)
  }

  return payload as T
}

export const api = {
  baseUrl: BASE_URL,
  health: (signal?: AbortSignal) => request<HealthResponse>('/health', { signal }),
  version: (signal?: AbortSignal) => request<VersionResponse>('/version', { signal }),
  commands: (signal?: AbortSignal) => request<CommandsResponse>('/commands', { signal }),
  skills: (signal?: AbortSignal) => request<SkillsResponse>('/skills', { signal }),
  pipelines: (signal?: AbortSignal) => request<PipelinesResponse>('/pipelines', { signal }),
  project: (signal?: AbortSignal) => request<ProjectResponse>('/project', { signal }),
  config: (signal?: AbortSignal) => request<ConfigResponse>('/config', { signal }),
  runs: (limit?: number, signal?: AbortSignal) =>
    request<RunsResponse>(limit ? `/runs?limit=${limit}` : '/runs', { signal }),
  run: (runId: string, signal?: AbortSignal) =>
    request<RunDetail>(`/runs/${encodeURIComponent(runId)}`, { signal }),
  // `artifactId` already contains a literal "/" (e.g. "<run-id>/<slug>") that
  // the backend expects as-is, so it is intentionally not URL-encoded here.
  artifact: (artifactId: string, signal?: AbortSignal) =>
    request<ArtifactPayload>(`/artifacts/${artifactId}`, { signal }),
  runCommand: (id: string, args: Record<string, unknown> = {}, signal?: AbortSignal) =>
    request<CommandResult>(`/commands/${id}`, {
      method: 'POST',
      body: args,
      signal,
      timeoutMs: COMMAND_TIMEOUT_MS,
    }),
}
