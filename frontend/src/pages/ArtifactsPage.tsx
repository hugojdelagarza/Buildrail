import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ArtifactDetail } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

const RECENT_RUNS_TO_SCAN = 20
const UNKNOWN_SKILL = '(unknown)'
const NO_PIPELINE = '(none)'

type SortKey = 'newest' | 'oldest' | 'type' | 'name'

const SORT_LABELS: Record<SortKey, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  type: 'Type',
  name: 'Name',
}

function timeValue(createdAt: string | null): number {
  if (!createdAt) return 0
  const parsed = Date.parse(createdAt)
  return Number.isNaN(parsed) ? 0 : parsed
}

function displayNameOf(artifact: ArtifactDetail): string {
  return artifact.display_name ?? artifact.id
}

function sortArtifacts(artifacts: ArtifactDetail[], sort: SortKey): ArtifactDetail[] {
  const copy = [...artifacts]
  switch (sort) {
    case 'oldest':
      return copy.sort((a, b) => timeValue(a.created_at) - timeValue(b.created_at))
    case 'type':
      return copy.sort((a, b) => a.type.localeCompare(b.type))
    case 'name':
      return copy.sort((a, b) => displayNameOf(a).localeCompare(displayNameOf(b)))
    default:
      return copy.sort((a, b) => timeValue(b.created_at) - timeValue(a.created_at))
  }
}

async function fetchRecentArtifacts(signal: AbortSignal): Promise<ArtifactDetail[]> {
  const { runs } = await api.runs(RECENT_RUNS_TO_SCAN, signal)
  const details = await Promise.all(runs.map((run) => api.run(run.run_id, signal)))
  return details.flatMap((detail) => detail.artifacts)
}

export function ArtifactsPage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchRecentArtifacts(signal), [])
  const { data: artifacts, error, loading, reload } = useAsync(fetcher, [])
  useRegisterRefresh(reload)

  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const type = searchParams.get('type') ?? ''
  const contentType = searchParams.get('content_type') ?? ''
  const skill = searchParams.get('skill') ?? ''
  const pipeline = searchParams.get('pipeline') ?? ''
  const sort = (searchParams.get('sort') as SortKey | null) ?? 'newest'

  const updateParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams)
      if (value) next.set(key, value)
      else next.delete(key)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const resetFilters = useCallback(() => setSearchParams({}, { replace: true }), [setSearchParams])

  const types = useMemo(
    () => Array.from(new Set((artifacts ?? []).map((a) => a.type))).sort(),
    [artifacts],
  )
  const contentTypes = useMemo(
    () =>
      Array.from(
        new Set((artifacts ?? []).map((a) => a.content_type).filter(Boolean)),
      ).sort() as string[],
    [artifacts],
  )
  const skills = useMemo(
    () =>
      Array.from(
        new Set((artifacts ?? []).map((a) => a.produced_by_skill ?? UNKNOWN_SKILL)),
      ).sort(),
    [artifacts],
  )
  const pipelines = useMemo(
    () => Array.from(new Set((artifacts ?? []).map((a) => a.pipeline ?? NO_PIPELINE))).sort(),
    [artifacts],
  )

  const filteredArtifacts = useMemo(() => {
    if (!artifacts) return []
    const needle = q.trim().toLowerCase()
    const matching = artifacts.filter((artifact) => {
      if (needle) {
        const haystack = `${artifact.id} ${artifact.display_name ?? ''}`.toLowerCase()
        if (!haystack.includes(needle)) return false
      }
      if (type && artifact.type !== type) return false
      if (contentType && artifact.content_type !== contentType) return false
      if (skill && (artifact.produced_by_skill ?? UNKNOWN_SKILL) !== skill) return false
      if (pipeline && (artifact.pipeline ?? NO_PIPELINE) !== pipeline) return false
      return true
    })
    return sortArtifacts(matching, sort)
  }, [artifacts, q, type, contentType, skill, pipeline, sort])

  const hasFilters =
    q !== '' || type !== '' || contentType !== '' || skill !== '' || pipeline !== ''

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>Artifacts</h1>
          <p className={shared.pageSubtitle}>
            Produced by the {RECENT_RUNS_TO_SCAN} most recent runs.
          </p>
        </div>
      </div>

      {loading && <p className={shared.loadingState}>Loading artifacts…</p>}
      {error && <p className={shared.errorState}>{error}</p>}

      {artifacts && artifacts.length > 0 && (
        <div className={shared.buttonRow} style={{ alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search id or name…"
            value={q}
            onChange={(event) => updateParam('q', event.target.value)}
            aria-label="Search artifacts"
          />
          <select
            value={type}
            onChange={(event) => updateParam('type', event.target.value)}
            aria-label="Filter by artifact type"
          >
            <option value="">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={contentType}
            onChange={(event) => updateParam('content_type', event.target.value)}
            aria-label="Filter by content type"
          >
            <option value="">All content types</option>
            {contentTypes.map((ct) => (
              <option key={ct} value={ct}>
                {ct}
              </option>
            ))}
          </select>
          <select
            value={skill}
            onChange={(event) => updateParam('skill', event.target.value)}
            aria-label="Filter by producing skill"
          >
            <option value="">All skills</option>
            {skills.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={pipeline}
            onChange={(event) => updateParam('pipeline', event.target.value)}
            aria-label="Filter by pipeline"
          >
            <option value="">All pipelines</option>
            {pipelines.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(event) => updateParam('sort', event.target.value)}
            aria-label="Sort artifacts"
          >
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <option key={key} value={key}>
                {SORT_LABELS[key]}
              </option>
            ))}
          </select>
          {hasFilters && (
            <button type="button" className={shared.button} onClick={resetFilters}>
              Reset filters
            </button>
          )}
        </div>
      )}

      {artifacts && artifacts.length === 0 && (
        <p className={shared.emptyState}>
          No artifacts yet. Generated documentation, diagrams, reviews, and reports will appear
          here.
        </p>
      )}

      {artifacts && artifacts.length > 0 && filteredArtifacts.length === 0 && (
        <div className={shared.emptyState}>
          <p>No artifacts match the current filters.</p>
          <button type="button" className={shared.button} onClick={resetFilters}>
            Reset filters
          </button>
        </div>
      )}

      {filteredArtifacts.length > 0 && (
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Artifact</th>
              <th>Type</th>
              <th>Status</th>
              <th>Run</th>
              <th>Produced By</th>
            </tr>
          </thead>
          <tbody>
            {filteredArtifacts.map((artifact) => (
              <tr key={artifact.id}>
                <td className={shared.mono}>
                  <Link to={`/artifacts/${artifact.id}`}>{displayNameOf(artifact)}</Link>
                </td>
                <td>{artifact.type}</td>
                <td>
                  <StatusBadge status={artifact.status} />
                </td>
                <td className={shared.mono}>
                  <Link to={`/runs/${encodeURIComponent(artifact.run_id)}`}>{artifact.run_id}</Link>
                </td>
                <td>{artifact.produced_by_skill ?? 'unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
