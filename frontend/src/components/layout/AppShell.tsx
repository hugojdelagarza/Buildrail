import { useCallback, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { CommandPalette } from '../CommandPalette'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { RefreshProvider, useTriggerRefresh } from '../../hooks/useRefreshRegistry'
import { useResizableWidth } from '../../hooks/useResizableWidth'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'
import styles from './AppShell.module.css'

export function AppShell() {
  return (
    <RefreshProvider>
      <AppShellContent />
    </RefreshProvider>
  )
}

function AppShellContent() {
  const navigate = useNavigate()
  const triggerRefresh = useTriggerRefresh()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const openPalette = useCallback(() => setPaletteOpen(true), [])
  const closePalette = useCallback(() => setPaletteOpen(false), [])

  useKeyboardShortcuts({
    onOpenPalette: openPalette,
    onNavigate: navigate,
    onRefresh: triggerRefresh,
    suspended: paletteOpen,
  })

  const sidebarWidth = useResizableWidth({
    storageKey: 'buildrail:sidebar-width',
    defaultWidth: 200,
    min: 160,
    max: 360,
  })

  return (
    <div className={styles.shell}>
      <Sidebar resizable={sidebarWidth} />
      <div className={styles.main}>
        <StatusBar onOpenPalette={openPalette} />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  )
}
