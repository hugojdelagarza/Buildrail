import { ThemeToggle } from './ThemeToggle'
import styles from './StatusBar.module.css'

export function StatusBar() {
  return (
    <header className={styles.bar}>
      <ThemeToggle />
    </header>
  )
}
