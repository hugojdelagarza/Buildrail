import { Link } from 'react-router-dom'
import type { DependencyAudit } from '../api/types'
import { JsonView } from './JsonView'
import shared from '../styles/shared.module.css'

interface DependencyAuditSummaryProps {
  audit: DependencyAudit | null
  runId: string | null
  markdownArtifactId: string | null
  rawJson: string | null
  running: boolean
  error: string | null
  onRun: () => void
}

/** A compact, restrained view of the latest dependency-audit artifact — an
 * engineering audit of declared dependencies vs. observed imports, never
 * styled as a security alert (no vulnerability/CVE scanning happens here). */
export function DependencyAuditSummary({
  audit,
  runId,
  markdownArtifactId,
  rawJson,
  running,
  error,
  onRun,
}: DependencyAuditSummaryProps) {
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Dependency Audit</h2>
      <p className={shared.pageSubtitle}>
        A local, offline audit of declared dependencies against observed imports — not a
        vulnerability or CVE scan.
      </p>

      {!audit ? (
        <>
          <p className={shared.emptyState}>No dependency audit has been generated yet.</p>
          <div className={shared.buttonRow}>
            <button type="button" className={shared.button} disabled={running} onClick={onRun}>
              {running ? 'Running…' : 'Run Dependency Audit'}
            </button>
          </div>
          {error && <p className={shared.errorState}>{error}</p>}
        </>
      ) : (
        <>
          {runId && (
            <p className={shared.pageSubtitle}>
              From run <Link to={`/runs/${encodeURIComponent(runId)}`}>{runId}</Link>
            </p>
          )}
          <div className={shared.buttonRow}>
            <button type="button" className={shared.button} disabled={running} onClick={onRun}>
              {running ? 'Running…' : 'Re-run'}
            </button>
            {markdownArtifactId && (
              <Link to={`/artifacts/${markdownArtifactId}`} className={shared.button}>
                View full report
              </Link>
            )}
          </div>
          {error && <p className={shared.errorState}>{error}</p>}

          <DependencyStats audit={audit} />
          <MismatchLists audit={audit} />
          <SpecialDependencyList audit={audit} />
          <WarningList audit={audit} />

          {rawJson && (
            <details>
              <summary>Raw JSON details</summary>
              <JsonView raw={rawJson} parsed={audit} />
            </details>
          )}
        </>
      )}
    </div>
  )
}

function DependencyStats({ audit }: { audit: DependencyAudit }) {
  const total = audit.dependencies.length
  const runtime = audit.dependencies.filter((d) => d.group === 'runtime').length
  const dev = audit.dependencies.filter((d) => d.group === 'dev').length
  const optionalGroups = new Set(
    audit.dependencies
      .filter((d) => d.group !== 'runtime' && d.group !== 'dev')
      .map((d) => d.group),
  ).size
  const pinned = audit.dependencies.filter((d) => d.is_pinned).length
  const special = audit.dependencies.filter((d) => d.is_vcs || d.is_url || d.is_local_path).length
  const unpinned = total - pinned - special

  return (
    <div className={shared.statGrid}>
      <Stat label="Total Declared" value={total} />
      <Stat label="Runtime" value={runtime} />
      <Stat label="Development" value={dev} />
      <Stat label="Optional Groups" value={optionalGroups} />
      <Stat label="Pinned" value={pinned} />
      <Stat label="Unpinned" value={unpinned} />
      <Stat label="Local / VCS / URL" value={special} />
      <Stat label="Duplicates" value={audit.duplicates.length} />
      <Stat label="Conflicts" value={audit.conflicts.length} />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className={shared.statCard}>
      <div className={shared.statLabel}>{label}</div>
      <div className={shared.statValue}>{value}</div>
    </div>
  )
}

function MismatchLists({ audit }: { audit: DependencyAudit }) {
  const undeclared = audit.mismatches.filter((m) => m.kind === 'imported_not_declared')
  const notObserved = audit.mismatches.filter((m) => m.kind === 'declared_not_observed')
  if (undeclared.length === 0 && notObserved.length === 0) return null
  return (
    <div className={shared.section}>
      {undeclared.length > 0 && (
        <>
          <h3 className={shared.sectionTitle}>Possible Undeclared Dependencies</h3>
          <ul>
            {undeclared.map((mismatch) => (
              <li key={mismatch.name}>
                <span className={shared.mono}>{mismatch.name}</span> —{' '}
                <span className={shared.pageSubtitle}>{mismatch.note}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {notObserved.length > 0 && (
        <>
          <h3 className={shared.sectionTitle}>Declared but Not Observed</h3>
          <ul>
            {notObserved.map((mismatch) => (
              <li key={mismatch.name}>
                <span className={shared.mono}>{mismatch.name}</span> —{' '}
                <span className={shared.pageSubtitle}>{mismatch.note}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function SpecialDependencyList({ audit }: { audit: DependencyAudit }) {
  const special = audit.dependencies.filter((d) => d.is_vcs || d.is_url || d.is_local_path)
  if (special.length === 0) return null
  return (
    <div className={shared.section}>
      <h3 className={shared.sectionTitle}>Local / VCS / URL Dependencies</h3>
      <ul>
        {special.map((dep) => (
          <li key={`${dep.source}:${dep.raw}`}>
            <span className={shared.mono}>{dep.raw}</span>{' '}
            <span className={shared.pageSubtitle}>({dep.source})</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function WarningList({ audit }: { audit: DependencyAudit }) {
  if (audit.warnings.length === 0) return null
  return (
    <div className={shared.section}>
      <h3 className={shared.sectionTitle}>Warnings</h3>
      <ul>
        {audit.warnings.map((warning, index) => (
          <li key={index}>
            [{warning.kind}] {warning.path}: {warning.message}
          </li>
        ))}
      </ul>
    </div>
  )
}
