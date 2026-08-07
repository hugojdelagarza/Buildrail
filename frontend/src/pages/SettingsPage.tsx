import { useCallback, useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { resetLayout } from '../hooks/useResizableWidth'
import shared from '../styles/shared.module.css'

const FRONTEND_VERSION = '0.1.0'

const SHORTCUTS: { keys: string; description: string }[] = [
  { keys: 'Ctrl K', description: 'Open the command palette' },
  { keys: 'Ctrl Shift P', description: 'Open the command palette' },
  { keys: 'G then O', description: 'Go to Overview' },
  { keys: 'G then R', description: 'Go to Runs' },
  { keys: 'G then A', description: 'Go to Artifacts' },
  { keys: 'G then S', description: 'Go to Skills' },
  { keys: 'G then P', description: 'Go to Pipelines' },
  { keys: 'G then I', description: 'Go to Project Intelligence' },
  { keys: 'G then ,', description: 'Go to Settings' },
  { keys: 'R', description: 'Refresh the current page (not while typing)' },
  { keys: 'Escape', description: 'Close the command palette or an open overlay' },
]

export function SettingsPage() {
  const fetchAll = useCallback(async (signal: AbortSignal) => {
    const [config, project, version] = await Promise.all([
      api.config(signal),
      api.project(signal),
      api.version(signal),
    ])
    return { config, project, version }
  }, [])
  const { data, error, loading, reload } = useAsync(fetchAll, [])
  useRegisterRefresh(reload)
  const [layoutReset, setLayoutReset] = useState(false)

  if (loading) return <p className={shared.loadingState}>Loading settings…</p>
  if (error || !data) return <p className={shared.errorState}>{error}</p>

  const { config, project, version } = data

  function handleResetLayout() {
    resetLayout()
    setLayoutReset(true)
    setTimeout(() => setLayoutReset(false), 1500)
  }

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

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Layout</h2>
        <p className={shared.pageSubtitle}>
          The sidebar and artifact details panel widths are remembered on this device.
        </p>
        <div className={shared.buttonRow}>
          <button type="button" className={shared.button} onClick={handleResetLayout}>
            {layoutReset ? 'Layout reset' : 'Reset layout'}
          </button>
        </div>
      </div>

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Keyboard Shortcuts</h2>
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Shortcut</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {SHORTCUTS.map((shortcut) => (
              <tr key={shortcut.keys}>
                <td className={shared.mono}>{shortcut.keys}</td>
                <td>{shortcut.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
