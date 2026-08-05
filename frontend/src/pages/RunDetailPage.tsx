import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

export function RunDetailPage() {
  const { runId = '' } = useParams<{ runId: string }>()
  const fetchRun = useCallback((signal: AbortSignal) => api.run(runId, signal), [runId])
  const { data: run, error, loading } = useAsync(fetchRun, [runId])

  if (loading) return <p className={shared.loadingState}>Loading run…</p>
  if (error || !run) return <p className={shared.errorState}>{error ?? 'Run not found.'}</p>

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>Run {run.run_id}</h1>
          <p className={shared.pageSubtitle}>
            {run.pipeline ?? 'Single skill'} · {run.created_at ?? 'unknown time'}
          </p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className={shared.metaGrid}>
        <span className={shared.metaLabel}>Duration</span>
        <span>{run.duration_seconds != null ? `${run.duration_seconds.toFixed(2)}s` : '—'}</span>
        {run.provider_usage_totals && (
          <>
            <span className={shared.metaLabel}>Provider usage</span>
            <span className={shared.mono}>
              {run.provider_usage_totals.provider}/{run.provider_usage_totals.model} —{' '}
              {run.provider_usage_totals.input_tokens ?? 0} in /{' '}
              {run.provider_usage_totals.output_tokens ?? 0} out
            </span>
          </>
        )}
      </div>

      {run.pipeline_steps.length > 0 && (
        <div className={shared.section}>
          <h2 className={shared.sectionTitle}>Steps</h2>
          <table className={shared.table}>
            <thead>
              <tr>
                <th>Step</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Artifacts</th>
              </tr>
            </thead>
            <tbody>
              {run.pipeline_steps.map((step) => (
                <tr key={step.name}>
                  <td>{step.name}</td>
                  <td>
                    <StatusBadge status={step.status} />
                  </td>
                  <td>{step.reason ?? '—'}</td>
                  <td className={shared.mono}>{step.artifact_ids.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Artifacts</h2>
        {run.artifacts.length === 0 ? (
          <p className={shared.emptyState}>No artifacts were produced.</p>
        ) : (
          <table className={shared.table}>
            <thead>
              <tr>
                <th>Artifact</th>
                <th>Type</th>
                <th>Status</th>
                <th>Produced By</th>
              </tr>
            </thead>
            <tbody>
              {run.artifacts.map((artifact) => (
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
                  <td>
                    {artifact.produced_by_skill ?? 'unknown'}
                    {artifact.produced_by_version ? ` (${artifact.produced_by_version})` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
