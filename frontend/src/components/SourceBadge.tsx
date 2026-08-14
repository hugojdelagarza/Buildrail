import type { ExtensionSource } from '../api/types'
import badge from './StatusBadge.module.css'

/** A restrained, neutral label distinguishing built-in from project-local
 * skills/pipelines — deliberately not styled as a status or alert. */
export function SourceBadge({ source }: { source: ExtensionSource }) {
  return (
    <span className={`${badge.badge} ${badge.neutral}`}>
      {source === 'built-in' ? 'Built-in' : 'Project'}
    </span>
  )
}
