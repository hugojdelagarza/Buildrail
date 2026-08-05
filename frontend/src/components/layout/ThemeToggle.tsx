import { useEffect, useState } from 'react'
import styles from './ThemeToggle.module.css'

type Theme = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'buildrail-theme'

function applyTheme(theme: Theme) {
  if (theme === 'system') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

function readStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

/** Cycles light -> dark -> system, persisted locally. Defaults to the OS
 * preference via `prefers-color-scheme` (see global.css) until overridden. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme())

  useEffect(() => {
    applyTheme(theme)
    if (theme === 'system') localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const next: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
  const labels: Record<Theme, string> = { system: 'System', light: 'Light', dark: 'Dark' }

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={() => setTheme(next[theme])}
      aria-label={`Theme: ${labels[theme]}. Click to change.`}
    >
      {labels[theme]}
    </button>
  )
}
