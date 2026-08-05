import { useCallback } from 'react'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import shared from '../styles/shared.module.css'

const FRONTEND_VERSION = '0.1.0'

export function SettingsPage() {
  const fetchAll = useCallback(async (signal: AbortSignal) => {
    const [config, project, version] = await Promise.all([
      api.config(signal),
      api.project(signal),
      api.version(signal),
    ])
    return { config, project, version }
  }, [])
  const { data, error, loading } = useAsync(fetchAll, [])

  if (loading) return <p className={shared.loadingState}>Loading settings…</p>
  if (error || !data) return <p className={shared.errorState}>{error}</p>

  const { config, project, version } = data

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Settings</h1>
        <p className={shared.pageSubtitle}>Read-only in this release.</p>
      </div>

      <div className={`${shared.card} ${shared.metaGrid}`}>
        <span className={shared.metaLabel}>Project root</span>
        <span className={shared.mono}>{project.project_root}</span>

        <span className={shared.metaLabel}>Artifact root</span>
        <span className={shared.mono}>{config.artifact_root ?? 'not configured'}</span>

        <span className={shared.metaLabel}>Provider</span>
        <span>{config.provider ?? 'not configured'}</span>

        <span className={shared.metaLabel}>Model</span>
        <span>{config.anthropic_model ?? 'default'}</span>

        <span className={shared.metaLabel}>Credential</span>
        <span>{config.credential_available ? 'Available' : 'Missing'}</span>

        <span className={shared.metaLabel}>Buildrail version</span>
        <span className={shared.mono}>{version.buildrail_version}</span>

        <span className={shared.metaLabel}>API version</span>
        <span className={shared.mono}>{version.api_version}</span>

        <span className={shared.metaLabel}>Python</span>
        <span className={shared.mono}>{version.python_version}</span>

        <span className={shared.metaLabel}>Platform</span>
        <span className={shared.mono}>{version.platform}</span>

        <span className={shared.metaLabel}>Frontend version</span>
        <span className={shared.mono}>{FRONTEND_VERSION}</span>
      </div>

      <p className={shared.pageSubtitle}>
        Configuration is read-only from the frontend in this release — edit{' '}
        <code>buildrail.toml</code> directly to change the provider or artifact root.
      </p>
    </div>
  )
}
