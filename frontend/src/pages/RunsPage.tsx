import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { RunSummary } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

type SortKey = 'newest' | 'oldest' | 'status' | 'artifacts'

const SORT_LABELS: Record<SortKey, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  status: 'Status',
  artifacts: 'Artifact count',
}

function timeValue(createdAt: string | null): number {
  if (!createdAt) return 0
  const parsed = Date.parse(createdAt)
  return Number.isNaN(parsed) ? 0 : parsed
}

function sortRuns(runs: RunSummary[], sort: SortKey): RunSummary[] {
  const copy = [...runs]
  switch (sort) {
    case 'oldest':
      return copy.sort((a, b) => timeValue(a.created_at) - timeValue(b.created_at))
    case 'status':
      return copy.sort((a, b) => a.status.localeCompare(b.status))
    case 'artifacts':
      return copy.sort((a, b) => b.artifact_count - a.artifact_count)
    default:
      return copy.sort((a, b) => timeValue(b.created_at) - timeValue(a.created_at))
  }
}

export function RunsPage() {
  const fetchRuns = useCallback((signal: AbortSignal) => api.runs(50, signal), [])
  const { data, error, loading, reload } = useAsync(fetchRuns, [])
  useRegisterRefresh(reload)

  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const status = searchParams.get('status') ?? ''
  const type = searchParams.get('type') ?? ''
  const sort = (searchParams.get('sort') as SortKey | null) ?? 'newest'

  const updateParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams)
      if (value) next.set(key, value)
      else next.delete(key)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const resetFilters = useCallback(() => setSearchParams({}, { replace: true }), [setSearchParams])

  const statuses = useMemo(
    () => Array.from(new Set((data?.runs ?? []).map((run) => run.status))).sort(),
    [data],
  )
  const types = useMemo(
    () => Array.from(new Set((data?.runs ?? []).flatMap((run) => run.artifact_types))).sort(),
    [data],
  )

  const filteredRuns = useMemo(() => {
    if (!data) return []
    const needle = q.trim().toLowerCase()
    const matching = data.runs.filter((run) => {
      if (needle) {
        const haystack = `${run.run_id} ${run.pipeline ?? ''}`.toLowerCase()
        if (!haystack.includes(needle)) return false
      }
      if (status && run.status !== status) return false
      if (type && !run.artifact_types.includes(type)) return false
      return true
    })
    return sortRuns(matching, sort)
  }, [data, q, status, type, sort])

  const hasFilters = q !== '' || status !== '' || type !== ''

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Runs</h1>
      </div>

      {loading && <p className={shared.loadingState}>Loading runs…</p>}
      {error && <p className={shared.errorState}>{error}</p>}

      {data && data.runs.length > 0 && (
        <div className={shared.buttonRow} style={{ alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search run id or pipeline…"
            value={q}
            onChange={(event) => updateParam('q', event.target.value)}
            aria-label="Search runs"
          />
          <select
            value={status}
            onChange={(event) => updateParam('status', event.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={type}
            onChange={(event) => updateParam('type', event.target.value)}
            aria-label="Filter by artifact type"
          >
            <option value="">All artifact types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(event) => updateParam('sort', event.target.value)}
            aria-label="Sort runs"
          >
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <option key={key} value={key}>
                {SORT_LABELS[key]}
              </option>
            ))}
          </select>
          {hasFilters && (
            <button type="button" className={shared.button} onClick={resetFilters}>
              Reset filters
            </button>
          )}
        </div>
      )}

      {data && data.runs.length === 0 && (
        <p className={shared.emptyState}>
          No runs yet. Execute a command from the Overview page to create one.
        </p>
      )}

      {data && data.runs.length > 0 && filteredRuns.length === 0 && (
        <div className={shared.emptyState}>
          <p>No runs match the current filters.</p>
          <button type="button" className={shared.button} onClick={resetFilters}>
            Reset filters
          </button>
        </div>
      )}

      {filteredRuns.length > 0 && (
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Run</th>
              <th>Pipeline / Command</th>
              <th>Status</th>
              <th>Created</th>
              <th>Artifacts</th>
              <th>Types</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => (
              <tr key={run.run_id}>
                <td className={shared.mono}>
                  <Link to={`/runs/${encodeURIComponent(run.run_id)}`}>{run.run_id}</Link>
                </td>
                <td>{run.pipeline ?? '—'}</td>
                <td>
                  <StatusBadge status={run.status} />
                </td>
                <td>{run.created_at ?? 'unknown'}</td>
                <td>{run.artifact_count}</td>
                <td>{Array.from(new Set(run.artifact_types)).join(', ') || 'none'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
