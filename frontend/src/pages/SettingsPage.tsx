import { useCallback, useState } from 'react'
import { isTauri } from '@tauri-apps/api/core'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { resetLayout } from '../hooks/useResizableWidth'
import { ConfigForm } from '../components/ConfigForm'
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
  const [editingConfig, setEditingConfig] = useState(false)

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
      </div>

      <div className={`${shared.card} ${shared.metaGrid}`}>
        <span className={shared.metaLabel}>Project root</span>
        <span className={shared.mono}>{project.project_root}</span>

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

      {isTauri() && (
        <p className={shared.pageSubtitle}>
          Running as a desktop app. This shell connects to an independently started local{' '}
          <code>buildrail serve</code> — it does not launch or manage that process for you.
        </p>
      )}

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Project Extensions</h2>
        <div className={`${shared.card} ${shared.metaGrid}`}>
          <span className={shared.metaLabel}>Skills</span>
          <span>
            <Link to="/skills">
              {project.skill_count_project_local} project / {project.skill_count_built_in} built-in
            </Link>
          </span>
          <span className={shared.metaLabel}>Pipelines</span>
          <span>
            <Link to="/pipelines">
              {project.pipeline_count_project_local} project / {project.pipeline_count_built_in}{' '}
              built-in
            </Link>
          </span>
        </div>
        <p className={shared.pageSubtitle}>
          Project-local skills and pipelines live under <code>.buildrail/</code> and execute code
          from this repository — only use them in repositories you trust.
        </p>
      </div>

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Project Configuration</h2>
        {!editingConfig ? (
          <>
            <div className={`${shared.card} ${shared.metaGrid}`}>
              <span className={shared.metaLabel}>Provider</span>
              <span>{config.provider ?? 'Not configured'}</span>

              <span className={shared.metaLabel}>Artifact root</span>
              <span className={shared.mono}>{config.artifact_root ?? 'Not configured'}</span>

              {config.provider === 'anthropic' && (
                <>
                  <span className={shared.metaLabel}>Anthropic model</span>
                  <span>{config.anthropic_model ?? 'Provider default'}</span>
                </>
              )}

              <span className={shared.metaLabel}>Credential</span>
              <span>{config.credential_available ? 'Available' : 'Missing'}</span>
            </div>
            <p className={shared.pageSubtitle}>
              API credentials are read from the environment and are never stored in{' '}
              <code>buildrail.toml</code>.
            </p>
            <div className={shared.buttonRow}>
              <button
                type="button"
                className={shared.button}
                onClick={() => setEditingConfig(true)}
              >
                Edit configuration
              </button>
            </div>
          </>
        ) : (
          <div className={shared.card}>
            <ConfigForm
              initialProvider={config.provider as 'fake' | 'anthropic' | null}
              initialArtifactRoot={config.artifact_root}
              initialAnthropicModel={config.anthropic_model}
              submitLabel="Save configuration"
              onCancel={() => setEditingConfig(false)}
              onSaved={() => {
                setEditingConfig(false)
                reload()
              }}
            />
          </div>
        )}
      </div>

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
