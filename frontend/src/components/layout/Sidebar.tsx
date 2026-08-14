import { NavLink } from 'react-router-dom'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import type { ResizableWidth } from '../../hooks/useResizableWidth'
import { ResizeHandle } from './ResizeHandle'
import styles from './Sidebar.module.css'

const SECTIONS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/runs', label: 'Runs' },
  { to: '/skills', label: 'Skills' },
  { to: '/pipelines', label: 'Pipelines' },
  { to: '/artifacts', label: 'Artifacts' },
  { to: '/testing', label: 'Testing' },
  { to: '/project-intelligence', label: 'Project Intelligence' },
  { to: '/settings', label: 'Settings' },
]

const NARROW_QUERY = '(max-width: 720px)'

export function Sidebar({ resizable }: { resizable: ResizableWidth }) {
  const isNarrow = useMediaQuery(NARROW_QUERY)

  return (
    <div
      className={styles.sidebarWrapper}
      style={isNarrow ? undefined : { width: resizable.width }}
    >
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
      {!isNarrow && <ResizeHandle resizable={resizable} label="Resize sidebar" />}
    </div>
  )
}
