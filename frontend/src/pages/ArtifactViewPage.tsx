import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { useResizableWidth } from '../hooks/useResizableWidth'
import { ArtifactViewer } from '../components/ArtifactViewer'
import { ResizeHandle } from '../components/layout/ResizeHandle'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'
import styles from './ArtifactViewPage.module.css'

const NARROW_QUERY = '(max-width: 720px)'

export function ArtifactViewPage() {
  // Artifact ids contain a literal "/" ("<run-id>/<slug>"); react-router's
  // splat capture preserves it, matching what GET /artifacts/{id} expects.
  const params = useParams<{ '*': string }>()
  const artifactId = params['*'] ?? ''
  const fetchArtifact = useCallback(
    (signal: AbortSignal) => api.artifact(artifactId, signal),
    [artifactId],
  )
  const { data: artifact, error, loading, reload } = useAsync(fetchArtifact, [artifactId])
  useRegisterRefresh(reload)

  const isNarrow = useMediaQuery(NARROW_QUERY)
  const panelWidth = useResizableWidth({
    storageKey: 'buildrail:artifact-panel-width',
    defaultWidth: 320,
    min: 220,
    max: 520,
    direction: -1,
  })

  const [copied, setCopied] = useState<'id' | 'payload' | null>(null)

  async function copyText(kind: 'id' | 'payload', text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(kind)
      setTimeout(() => setCopied((current) => (current === kind ? null : current)), 1500)
    } catch {
      // Clipboard access can be denied by the browser; the button simply no-ops.
    }
  }

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

      <div className={styles.layout}>
        <div className={styles.viewerColumn}>
          <ArtifactViewer artifact={artifact} />
        </div>

        {!isNarrow && <ResizeHandle resizable={panelWidth} label="Resize artifact details panel" />}

        <div
          className={styles.metaPanel}
          style={isNarrow ? undefined : { width: panelWidth.width }}
        >
          <div className={shared.buttonRow}>
            <button
              type="button"
              className={shared.button}
              onClick={() => void copyText('id', artifact.id)}
            >
              {copied === 'id' ? 'Copied!' : 'Copy artifact ID'}
            </button>
            <button
              type="button"
              className={shared.button}
              onClick={() => void copyText('payload', artifact.content)}
            >
              {copied === 'payload' ? 'Copied!' : 'Copy payload'}
            </button>
          </div>

          <div className={`${shared.card} ${shared.metaGrid}`}>
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
      </div>
    </div>
  )
}
