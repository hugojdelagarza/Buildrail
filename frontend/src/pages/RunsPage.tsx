import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

export function RunsPage() {
  const fetchRuns = useCallback((signal: AbortSignal) => api.runs(50, signal), [])
  const { data, error, loading } = useAsync(fetchRuns, [])

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Runs</h1>
      </div>

      {loading && <p className={shared.loadingState}>Loading runs…</p>}
      {error && <p className={shared.errorState}>{error}</p>}

      {data && data.runs.length === 0 && (
        <p className={shared.emptyState}>
          No runs yet. Execute a command from the Overview page to create one.
        </p>
      )}

      {data && data.runs.length > 0 && (
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
            {data.runs.map((run) => (
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
