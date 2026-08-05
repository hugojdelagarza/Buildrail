import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { ArtifactDetail, ProjectAnalysis, RunSummary } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { MarkdownView } from '../components/MarkdownView'
import { MermaidView } from '../components/MermaidView'
import shared from '../styles/shared.module.css'

interface ProjectIntelligenceData {
  run: RunSummary
  analysis: ProjectAnalysis
  summaryMarkdown: string | null
  diagramContent: string | null
  documentationArtifacts: ArtifactDetail[]
}

async function findLatestProjectIntelligence(
  signal: AbortSignal,
): Promise<ProjectIntelligenceData | null> {
  const { runs } = await api.runs(20, signal)
  const candidate = runs.find((run) => run.artifact_types.includes('architecture-summary'))
  if (!candidate) return null

  const detail = await api.run(candidate.run_id, signal)
  const jsonArtifact = detail.artifacts.find(
    (artifact) =>
      artifact.type === 'architecture-summary' && artifact.content_type === 'application/json',
  )
  const markdownArtifact = detail.artifacts.find(
    (artifact) =>
      artifact.type === 'architecture-summary' && artifact.content_type === 'text/markdown',
  )
  const diagramArtifact = detail.artifacts.find((artifact) => artifact.type === 'diagram')
  if (!jsonArtifact) return null

  const jsonPayload = await api.artifact(jsonArtifact.id, signal)
  const summaryPayload = markdownArtifact ? await api.artifact(markdownArtifact.id, signal) : null
  const diagramPayload = diagramArtifact ? await api.artifact(diagramArtifact.id, signal) : null

  return {
    run: candidate,
    analysis: (jsonPayload.content_json ?? {}) as unknown as ProjectAnalysis,
    summaryMarkdown: summaryPayload?.content ?? null,
    diagramContent: diagramPayload?.content ?? null,
    documentationArtifacts: detail.artifacts.filter(
      (artifact) => artifact.type === 'documentation',
    ),
  }
}

export function ProjectIntelligencePage() {
  const fetcher = useCallback((signal: AbortSignal) => findLatestProjectIntelligence(signal), [])
  const { data, error, loading, reload } = useAsync(fetcher, [])
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const runNow = useCallback(async () => {
    setRunning(true)
    setRunError(null)
    try {
      const response = await api.runCommand('project-intelligence')
      if (!response.success) setRunError(response.message)
      reload()
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'Unexpected error.')
    } finally {
      setRunning(false)
    }
  }, [reload])

  if (loading) return <p className={shared.loadingState}>Loading project intelligence…</p>
  if (error) return <p className={shared.errorState}>{error}</p>

  if (!data) {
    return (
      <div className={shared.page}>
        <div className={shared.pageHeader}>
          <h1 className={shared.pageTitle}>Project Intelligence</h1>
        </div>
        <p className={shared.emptyState}>
          No project intelligence run exists yet. Generate one to see architecture, statistics,
          modules, and diagrams for this project.
        </p>
        <div className={shared.buttonRow}>
          <button
            type="button"
            className={shared.buttonPrimary}
            disabled={running}
            onClick={() => void runNow()}
          >
            {running ? 'Running…' : 'Run Project Intelligence'}
          </button>
        </div>
        {runError && <p className={shared.errorState}>{runError}</p>}
      </div>
    )
  }

  const { analysis } = data

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>{analysis.repository_name}</h1>
          <p className={shared.pageSubtitle}>
            From run{' '}
            <Link to={`/runs/${encodeURIComponent(data.run.run_id)}`}>{data.run.run_id}</Link>
          </p>
        </div>
        <button
          type="button"
          className={shared.button}
          disabled={running}
          onClick={() => void runNow()}
        >
          {running ? 'Running…' : 'Re-run'}
        </button>
      </div>

      <div className={shared.statGrid}>
        <Stat label="Python Files" value={analysis.statistics.python_files} />
        <Stat label="Modules" value={analysis.statistics.modules} />
        <Stat label="Classes" value={analysis.statistics.classes} />
        <Stat label="Functions" value={analysis.statistics.functions} />
        <Stat label="Test Files" value={analysis.statistics.test_files} />
        <Stat label="Lines of Python" value={analysis.statistics.lines_of_python} />
      </div>

      <Section title="Entry Points">
        {analysis.entry_points.length === 0 ? (
          <Empty />
        ) : (
          <ul>
            {analysis.entry_points.map((entry) => (
              <li key={entry.name} className={shared.mono}>
                {entry.name} → {entry.target}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="CLI Commands">
        {analysis.cli_commands.length === 0 ? (
          <Empty />
        ) : (
          <ul>
            {analysis.cli_commands.map((command) => (
              <li key={command.command} className={shared.mono}>
                {command.command}
                {command.description ? ` — ${command.description}` : ''}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Modules">
        <p className={shared.pageSubtitle}>{analysis.modules.length} discovered</p>
        <ul>
          {analysis.modules.slice(0, 25).map((module) => (
            <li key={module.dotted_name} className={shared.mono}>
              {module.dotted_name}
            </li>
          ))}
          {analysis.modules.length > 25 && <li>… and {analysis.modules.length - 25} more</li>}
        </ul>
      </Section>

      <Section title="Skills">
        {analysis.skills.length === 0 ? (
          <Empty />
        ) : (
          <ul>
            {analysis.skills.map((skill) => (
              <li key={skill.name}>
                {skill.name} ({skill.version}) —{' '}
                {skill.requires_provider ? 'requires provider' : 'provider-free'}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Pipelines">
        {analysis.pipelines.length === 0 ? (
          <Empty />
        ) : (
          <ul>
            {analysis.pipelines.map((pipeline) => (
              <li key={pipeline.name}>
                {pipeline.name}: {pipeline.steps.join(' → ')}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Artifact Types">
        <p>{analysis.artifact_types.join(', ') || 'none'}</p>
      </Section>

      <Section title="Tests">
        <p>
          {analysis.test_layout.test_files.length} test file(s) in{' '}
          {analysis.test_layout.test_directories.join(', ') || 'no dedicated directory'}
        </p>
      </Section>

      {analysis.warnings.length > 0 && (
        <Section title="Warnings">
          <ul>
            {analysis.warnings.map((warning, index) => (
              <li key={index}>
                [{warning.kind}] {warning.path}: {warning.message}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {data.documentationArtifacts.length > 0 && (
        <Section title="Generated Documentation">
          <ul>
            {data.documentationArtifacts.map((artifact) => (
              <li key={artifact.id}>
                <Link to={`/artifacts/${artifact.id}`}>{artifact.display_name ?? artifact.id}</Link>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {data.diagramContent && (
        <Section title="Diagrams">
          <MermaidView content={data.diagramContent} />
        </Section>
      )}

      {data.summaryMarkdown && (
        <Section title="Suggested Reading Order & Full Summary">
          <MarkdownView content={data.summaryMarkdown} />
        </Section>
      )}
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>{title}</h2>
      {children}
    </div>
  )
}

function Empty() {
  return <p className={shared.pageSubtitle}>None</p>
}
