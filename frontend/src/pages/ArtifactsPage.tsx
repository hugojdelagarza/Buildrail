import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ArtifactDetail } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

const RECENT_RUNS_TO_SCAN = 20

async function fetchRecentArtifacts(signal: AbortSignal): Promise<ArtifactDetail[]> {
  const { runs } = await api.runs(RECENT_RUNS_TO_SCAN, signal)
  const details = await Promise.all(runs.map((run) => api.run(run.run_id, signal)))
  return details.flatMap((detail) => detail.artifacts)
}

export function ArtifactsPage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchRecentArtifacts(signal), [])
  const { data: artifacts, error, loading } = useAsync(fetcher, [])

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>Artifacts</h1>
          <p className={shared.pageSubtitle}>
            Produced by the {RECENT_RUNS_TO_SCAN} most recent runs.
          </p>
        </div>
      </div>

      {loading && <p className={shared.loadingState}>Loading artifacts…</p>}
      {error && <p className={shared.errorState}>{error}</p>}

      {artifacts && artifacts.length === 0 && (
        <p className={shared.emptyState}>No artifacts yet.</p>
      )}

      {artifacts && artifacts.length > 0 && (
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Artifact</th>
              <th>Type</th>
              <th>Status</th>
              <th>Run</th>
              <th>Produced By</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.map((artifact) => (
              <tr key={artifact.id}>
                <td className={shared.mono}>
                  <Link to={`/artifacts/${artifact.id}`}>
                    {artifact.display_name ?? artifact.id}
                  </Link>
                </td>
                <td>{artifact.type}</td>
                <td>
                  <StatusBadge status={artifact.status} />
                </td>
                <td className={shared.mono}>
                  <Link to={`/runs/${encodeURIComponent(artifact.run_id)}`}>{artifact.run_id}</Link>
                </td>
                <td>{artifact.produced_by_skill ?? 'unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
