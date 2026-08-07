import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { CommandDescriptor } from '../api/types'
import { useTriggerRefresh } from '../hooks/useRefreshRegistry'
import styles from './CommandPalette.module.css'

interface NavEntry {
  label: string
  path: string
  shortcut: string
}

const NAV_ENTRIES: NavEntry[] = [
  { label: 'Overview', path: '/', shortcut: 'G O' },
  { label: 'Runs', path: '/runs', shortcut: 'G R' },
  { label: 'Artifacts', path: '/artifacts', shortcut: 'G A' },
  { label: 'Skills', path: '/skills', shortcut: 'G S' },
  { label: 'Pipelines', path: '/pipelines', shortcut: 'G P' },
  { label: 'Project Intelligence', path: '/project-intelligence', shortcut: 'G I' },
  { label: 'Settings', path: '/settings', shortcut: 'G ,' },
]

interface NavItem {
  kind: 'nav'
  id: string
  label: string
  shortcut?: string
  path: string
}

interface ActionItem {
  kind: 'action'
  id: string
  label: string
  description?: string
  shortcut?: string
  run: () => void | Promise<void>
}

type PaletteItem = NavItem | ActionItem

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const triggerRefresh = useTriggerRefresh()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [commands, setCommands] = useState<CommandDescriptor[] | null>(null)
  const [runningId, setRunningId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    setQuery('')
    setSelectedIndex(0)
    setRunningId(null)
    inputRef.current?.focus()
    return () => {
      previouslyFocused?.focus?.()
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    api
      .commands()
      .then((response) => {
        if (!cancelled) setCommands(response.commands)
      })
      .catch(() => {
        if (!cancelled) setCommands([])
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const items = useMemo<PaletteItem[]>(() => {
    const navItems: PaletteItem[] = NAV_ENTRIES.map((entry) => ({
      kind: 'nav',
      id: `nav-${entry.path}`,
      label: entry.label,
      shortcut: entry.shortcut,
      path: entry.path,
    }))

    const commandItems: PaletteItem[] = (commands ?? []).map((command) => ({
      kind: 'action',
      id: `action-${command.id}`,
      label: command.display_name,
      description: command.description,
      run: async () => {
        await api.runCommand(command.id)
        triggerRefresh()
        navigate('/runs')
      },
    }))

    const refreshItem: PaletteItem = {
      kind: 'action',
      id: 'action-refresh',
      label: 'Refresh Current Page',
      shortcut: 'R',
      run: () => triggerRefresh(),
    }

    return [...navItems, ...commandItems, refreshItem]
  }, [commands, navigate, triggerRefresh])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return items
    return items.filter((item) => item.label.toLowerCase().includes(needle))
  }, [items, query])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const runItem = useCallback(
    async (item: PaletteItem) => {
      if (item.kind === 'nav') {
        onClose()
        navigate(item.path)
        return
      }
      setRunningId(item.id)
      try {
        await item.run()
      } finally {
        setRunningId(null)
        onClose()
      }
    },
    [navigate, onClose],
  )

  if (!open) return null

  const busy = runningId !== null
  const busyLabel = items.find((item) => item.id === runningId)?.label

  function handleKeyDown(event: React.KeyboardEvent) {
    if (busy) {
      if (event.key === 'Escape') onClose()
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setSelectedIndex((index) => (filtered.length === 0 ? 0 : (index + 1) % filtered.length))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedIndex((index) =>
        filtered.length === 0 ? 0 : (index - 1 + filtered.length) % filtered.length,
      )
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const item = filtered[selectedIndex]
      if (item) void runItem(item)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
    }
  }

  let renderedNavHeader = false
  let renderedActionHeader = false

  return (
    <div
      className={styles.backdrop}
      onClick={onClose}
      onKeyDown={(event) => {
        if (event.key === 'Escape') onClose()
      }}
    >
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.inputRow}>
          <input
            ref={inputRef}
            className={styles.input}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-list"
            aria-activedescendant={
              filtered[selectedIndex]
                ? `command-palette-item-${filtered[selectedIndex].id}`
                : undefined
            }
            placeholder="Search pages and actions…"
            value={query}
            disabled={busy}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>

        {filtered.length === 0 ? (
          <p className={styles.empty}>No matches.</p>
        ) : (
          <ul id="command-palette-list" className={styles.list} role="listbox">
            {filtered.map((item, index) => {
              let header: React.ReactNode = null
              if (item.kind === 'nav' && !renderedNavHeader) {
                header = (
                  <li key="header-nav" className={styles.groupLabel} aria-hidden="true">
                    Navigate
                  </li>
                )
                renderedNavHeader = true
              } else if (item.kind === 'action' && !renderedActionHeader) {
                header = (
                  <li key="header-action" className={styles.groupLabel} aria-hidden="true">
                    Actions
                  </li>
                )
                renderedActionHeader = true
              }
              return (
                <li key={item.id} role="presentation">
                  {header}
                  <div
                    id={`command-palette-item-${item.id}`}
                    role="option"
                    aria-selected={index === selectedIndex}
                    className={index === selectedIndex ? styles.itemActive : styles.item}
                    onMouseEnter={() => setSelectedIndex(index)}
                    onClick={() => void runItem(item)}
                  >
                    <span className={styles.itemText}>
                      <span className={styles.itemLabel}>{item.label}</span>
                      {item.kind === 'action' && item.description && (
                        <span className={styles.itemDescription}>{item.description}</span>
                      )}
                    </span>
                    {item.shortcut && <span className={styles.shortcut}>{item.shortcut}</span>}
                  </div>
                </li>
              )
            })}
          </ul>
        )}

        {busy && <div className={styles.status}>Running {busyLabel}…</div>}
      </div>
    </div>
  )
}
