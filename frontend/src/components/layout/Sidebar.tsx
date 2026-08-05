import { NavLink } from 'react-router-dom'
import styles from './Sidebar.module.css'

const SECTIONS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/runs', label: 'Runs' },
  { to: '/skills', label: 'Skills' },
  { to: '/pipelines', label: 'Pipelines' },
  { to: '/artifacts', label: 'Artifacts' },
  { to: '/project-intelligence', label: 'Project Intelligence' },
  { to: '/settings', label: 'Settings' },
]

export function Sidebar() {
  return (
    <nav className={styles.sidebar} aria-label="Main">
      <div className={styles.brand}>Buildrail</div>
      <ul className={styles.list}>
        {SECTIONS.map((section) => (
          <li key={section.to}>
            <NavLink
              to={section.to}
              end={section.end}
              className={({ isActive }) => (isActive ? styles.activeLink : styles.link)}
            >
              {section.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
