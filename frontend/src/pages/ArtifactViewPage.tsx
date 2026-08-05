import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { ArtifactViewer } from '../components/ArtifactViewer'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

export function ArtifactViewPage() {
  // Artifact ids contain a literal "/" ("<run-id>/<slug>"); react-router's
  // splat capture preserves it, matching what GET /artifacts/{id} expects.
  const params = useParams<{ '*': string }>()
  const artifactId = params['*'] ?? ''
  const fetchArtifact = useCallback(
    (signal: AbortSignal) => api.artifact(artifactId, signal),
    [artifactId],
  )
  const { data: artifact, error, loading } = useAsync(fetchArtifact, [artifactId])

  if (loading) return <p className={shared.loadingState}>Loading artifact…</p>
  if (error || !artifact) return <p className={shared.errorState}>{error ?? 'Not found.'}</p>

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>{artifact.display_name ?? artifact.id}</h1>
          <p className={shared.pageSubtitle}>
            <Link to={`/runs/${encodeURIComponent(artifact.run_id)}`}>{artifact.run_id}</Link>
          </p>
        </div>
        <StatusBadge status={artifact.status} />
      </div>

      <div className={shared.card}>
        <div className={shared.metaGrid}>
          <span className={shared.metaLabel}>ID</span>
          <span className={shared.mono}>{artifact.id}</span>
          <span className={shared.metaLabel}>Type</span>
          <span>{artifact.type}</span>
          <span className={shared.metaLabel}>Content type</span>
          <span className={shared.mono}>{artifact.content_type ?? 'unknown'}</span>
          <span className={shared.metaLabel}>Pipeline</span>
          <span>{artifact.pipeline ?? 'none'}</span>
          <span className={shared.metaLabel}>Produced by</span>
          <span>
            {artifact.produced_by_skill ?? 'unknown'}
            {artifact.produced_by_version ? ` (${artifact.produced_by_version})` : ''}
          </span>
          <span className={shared.metaLabel}>Checksum</span>
          <span className={shared.mono}>{artifact.checksum ?? 'unknown'}</span>
          <span className={shared.metaLabel}>Created</span>
          <span>{artifact.created_at ?? 'unknown'}</span>
          {artifact.provider_usage && (
            <>
              <span className={shared.metaLabel}>Provider / model</span>
              <span className={shared.mono}>
                {artifact.provider_usage.provider ?? 'unknown'}/
                {artifact.provider_usage.model ?? 'unknown'}
              </span>
              <span className={shared.metaLabel}>Token usage</span>
              <span>
                {artifact.provider_usage.input_tokens ?? 0} in /{' '}
                {artifact.provider_usage.output_tokens ?? 0} out
              </span>
              {artifact.provider_usage.cost_estimate && (
                <>
                  <span className={shared.metaLabel}>Advisory cost</span>
                  <span>
                    {artifact.provider_usage.cost_estimate.amount}{' '}
                    {artifact.provider_usage.cost_estimate.currency}
                  </span>
                </>
              )}
            </>
          )}
        </div>
      </div>

      <div className={shared.section}>
        <ArtifactViewer artifact={artifact} />
      </div>
    </div>
  )
}
