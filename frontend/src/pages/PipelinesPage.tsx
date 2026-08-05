import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { PipelineDescriptor } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'
import layout from '../styles/listDetail.module.css'

export function PipelinesPage() {
  const fetchPipelines = useCallback((signal: AbortSignal) => api.pipelines(signal), [])
  const { data, error, loading } = useAsync(fetchPipelines, [])
  const [selected, setSelected] = useState<string | null>(null)

  if (loading) return <p className={shared.loadingState}>Loading pipelines…</p>
  if (error || !data) return <p className={shared.errorState}>{error}</p>

  const active: PipelineDescriptor | undefined =
    data.pipelines.find((pipeline) => pipeline.name === selected) ?? data.pipelines[0]

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Pipelines</h1>
      </div>

      <div className={layout.split}>
        <ul className={layout.list}>
          {data.pipelines.map((pipeline) => (
            <li key={pipeline.name}>
              <button
                type="button"
                className={active?.name === pipeline.name ? layout.itemActive : layout.item}
                onClick={() => setSelected(pipeline.name)}
              >
                {pipeline.display_name}
              </button>
            </li>
          ))}
        </ul>

        {active && <PipelineDetail pipeline={active} />}
      </div>
    </div>
  )
}

function PipelineDetail({ pipeline }: { pipeline: PipelineDescriptor }) {
  const [baseRef, setBaseRef] = useState('')
  const [skipReview, setSkipReview] = useState(false)
  const [path, setPath] = useState('')
  const [enhance, setEnhance] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<{
    success: boolean
    message: string
    runId?: string
  } | null>(null)

  const run = useCallback(async () => {
    setRunning(true)
    setResult(null)
    try {
      const args: Record<string, unknown> = {}
      if (pipeline.name === 'pre-commit') {
        if (baseRef.trim()) args.base = baseRef.trim()
        args.skip_review = skipReview
      } else if (pipeline.name === 'project-intelligence') {
        if (path.trim()) args.path = path.trim()
        args.enhance = enhance
      }
      const response = await api.runCommand(pipeline.name, args)
      let runId: string | undefined
      try {
        const latest = await api.runs(1)
        runId = latest.runs[0]?.run_id
      } catch {
        // Non-fatal — the result message is still shown without a direct link.
      }
      setResult({ success: response.success, message: response.message, runId })
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof ApiError ? err.message : 'Unexpected error.',
      })
    } finally {
      setRunning(false)
    }
  }, [pipeline.name, baseRef, skipReview, path, enhance])

  return (
    <div className={`${shared.card} ${layout.detail}`}>
      <h2 className={shared.pageTitle}>{pipeline.display_name}</h2>
      <p>{pipeline.description}</p>

      <div className={shared.section}>
        <h3 className={shared.sectionTitle}>Steps</h3>
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Step</th>
              <th>Skippable</th>
              <th>Condition</th>
            </tr>
          </thead>
          <tbody>
            {pipeline.steps.map((step) => (
              <tr key={step.name}>
                <td>{step.name}</td>
                <td>{step.skippable ? 'Yes' : 'No'}</td>
                <td>{step.skip_condition ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={shared.section}>
        <h3 className={shared.sectionTitle}>Run</h3>
        {pipeline.name === 'pre-commit' && (
          <div className={shared.buttonRow} style={{ alignItems: 'center' }}>
            <input
              type="text"
              placeholder="base ref (optional)"
              value={baseRef}
              onChange={(event) => setBaseRef(event.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={skipReview}
                onChange={(event) => setSkipReview(event.target.checked)}
              />{' '}
              Skip review
            </label>
          </div>
        )}
        {pipeline.name === 'project-intelligence' && (
          <div className={shared.buttonRow} style={{ alignItems: 'center' }}>
            <input
              type="text"
              placeholder="path (optional, default: cwd)"
              value={path}
              onChange={(event) => setPath(event.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={enhance}
                onChange={(event) => setEnhance(event.target.checked)}
              />{' '}
              Enhance with provider
            </label>
          </div>
        )}
        <div className={shared.buttonRow}>
          <button
            type="button"
            className={shared.buttonPrimary}
            disabled={running}
            onClick={() => void run()}
          >
            {running ? 'Running…' : `Run ${pipeline.display_name}`}
          </button>
        </div>

        {result && (
          <div className={shared.card}>
            <p>
              <StatusBadge status={result.success ? 'success' : 'failure'} />
            </p>
            <pre className={shared.mono} style={{ whiteSpace: 'pre-wrap' }}>
              {result.message}
            </pre>
            {result.runId && (
              <Link to={`/runs/${encodeURIComponent(result.runId)}`}>View run →</Link>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
