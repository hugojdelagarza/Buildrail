import styles from './StatusBadge.module.css'

const SYMBOLS: Record<string, string> = {
  success: '✓',
  passed: '✓',
  ok: '✓',
  failure: '✕',
  failed: '✕',
  error: '✕',
  skipped: '−',
  empty: '·',
  unknown: '?',
}

const VARIANTS: Record<string, 'success' | 'danger' | 'skipped' | 'neutral'> = {
  success: 'success',
  passed: 'success',
  ok: 'success',
  failure: 'danger',
  failed: 'danger',
  error: 'danger',
  skipped: 'skipped',
  empty: 'neutral',
  unknown: 'neutral',
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  const variant = VARIANTS[normalized] ?? 'neutral'
  const symbol = SYMBOLS[normalized] ?? '?'

  return (
    <span className={`${styles.badge} ${styles[variant]}`}>
      <span aria-hidden="true">{symbol}</span>
      {status}
    </span>
  )
}
