import { ThemeToggle } from './ThemeToggle'
import styles from './StatusBar.module.css'

export function StatusBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <header className={styles.bar}>
      <button type="button" className={styles.paletteButton} onClick={onOpenPalette}>
        Search pages and actions…
        <span className={styles.shortcut}>Ctrl K</span>
      </button>
      <ThemeToggle />
    </header>
  )
}
