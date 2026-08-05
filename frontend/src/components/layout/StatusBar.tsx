import { useCallback } from 'react'
import { api } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import { ThemeToggle } from './ThemeToggle'
import styles from './StatusBar.module.css'

type ServiceState = 'checking' | 'connected' | 'offline'

const STATE_LABEL: Record<ServiceState, string> = {
  checking: 'Checking',
  connected: 'Connected',
  offline: 'Offline',
}

const STATE_DOT_CLASS: Record<ServiceState, keyof typeof styles> = {
  checking: 'dotChecking',
  connected: 'dotConnected',
  offline: 'dotOffline',
}

export function StatusBar() {
  const fetchProject = useCallback((signal: AbortSignal) => api.project(signal), [])
  const { data, error, loading } = useAsync(fetchProject, [])

  const connected = !loading && !error && data !== null
  const state: ServiceState = loading ? 'checking' : connected ? 'connected' : 'offline'

  return (
    <header className={styles.bar}>
      <div className={styles.status}>
        <span className={styles[STATE_DOT_CLASS[state]]} aria-hidden="true" />
        <span className={styles.statusLabel}>{STATE_LABEL[state]}</span>
        {connected && data && (
          <>
            <span className={styles.separator}>·</span>
            <span className={styles.projectName}>{projectName(data.project_root)}</span>
            {data.provider && (
              <>
                <span className={styles.separator}>·</span>
                <span>
                  {data.provider} ({data.provider_ready ? 'ready' : 'not ready'})
                </span>
              </>
            )}
          </>
        )}
      </div>
      <ThemeToggle />
    </header>
  )
}

function projectName(projectRoot: string): string {
  const parts = projectRoot.split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] ?? projectRoot
}
