import { useCallback, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { ExtensionSource, SkillManifest } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { CreateSkillModal } from '../components/CreateSkillModal'
import { SourceBadge } from '../components/SourceBadge'
import shared from '../styles/shared.module.css'
import layout from '../styles/listDetail.module.css'

type SourceFilter = 'all' | ExtensionSource

export function SkillsPage() {
  const fetchSkills = useCallback((signal: AbortSignal) => api.skills(signal), [])
  const { data, error, loading, reload } = useAsync(fetchSkills, [])
  useRegisterRefresh(reload)
  const [selected, setSelected] = useState<string | null>(null)
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [creating, setCreating] = useState(false)
  const [createdMessage, setCreatedMessage] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const skills = data?.skills ?? []
    if (sourceFilter === 'all') return skills
    return skills.filter((skill) => skill.source === sourceFilter)
  }, [data, sourceFilter])

  if (loading) return <p className={shared.loadingState}>Loading skills…</p>
  if (error || !data) return <p className={shared.errorState}>{error}</p>

  const activeSkill: SkillManifest | undefined =
    filtered.find((skill) => skill.name === selected) ?? filtered[0]

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>Skills</h1>
          <p className={shared.pageSubtitle}>{filtered.length} shown</p>
        </div>
        <button
          type="button"
          className={shared.buttonPrimary}
          onClick={() => {
            setCreatedMessage(null)
            setCreating(true)
          }}
        >
          New Skill
        </button>
      </div>

      <div className={shared.buttonRow}>
        {(['all', 'built-in', 'project-local'] as const).map((option) => (
          <button
            key={option}
            type="button"
            className={sourceFilter === option ? shared.buttonPrimary : shared.button}
            onClick={() => setSourceFilter(option)}
          >
            {option === 'all' ? 'All' : option === 'built-in' ? 'Built-in' : 'Project'}
          </button>
        ))}
      </div>

      {createdMessage && <p className={shared.pageSubtitle}>Created at {createdMessage}.</p>}

      <div className={layout.split}>
        <ul className={layout.list}>
          {filtered.map((skill) => (
            <li key={skill.name}>
              <button
                type="button"
                className={activeSkill?.name === skill.name ? layout.itemActive : layout.item}
                onClick={() => setSelected(skill.name)}
              >
                <span className={shared.mono}>{skill.name}</span>
                <span className={layout.itemMeta}>
                  {skill.version} · <SourceBadge source={skill.source} />
                </span>
              </button>
            </li>
          ))}
        </ul>

        {activeSkill && (
          <div className={`${shared.card} ${layout.detail}`}>
            <h2 className={shared.pageTitle}>{activeSkill.name}</h2>
            <p>{activeSkill.description}</p>
            <div className={shared.metaGrid}>
              <span className={shared.metaLabel}>Version</span>
              <span>{activeSkill.version}</span>
              <span className={shared.metaLabel}>Protocol</span>
              <span>{activeSkill.protocol_version}</span>
              <span className={shared.metaLabel}>Requires provider</span>
              <span>{activeSkill.requires_provider ? 'Yes' : 'No'}</span>
              <span className={shared.metaLabel}>Source</span>
              <span>
                <SourceBadge source={activeSkill.source} />
                {activeSkill.project_relative_path && (
                  <span className={shared.mono}> {activeSkill.project_relative_path}</span>
                )}
              </span>
            </div>

            <div className={shared.section}>
              <h3 className={shared.sectionTitle}>Inputs</h3>
              {activeSkill.inputs.length === 0 ? (
                <p className={shared.pageSubtitle}>None</p>
              ) : (
                <table className={shared.table}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Required</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeSkill.inputs.map((input) => (
                      <tr key={input.name}>
                        <td className={shared.mono}>{input.name}</td>
                        <td>{input.type}</td>
                        <td>{input.required ? 'Yes' : 'No'}</td>
                        <td>{input.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className={shared.section}>
              <h3 className={shared.sectionTitle}>Outputs</h3>
              <table className={shared.table}>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Artifact Type</th>
                  </tr>
                </thead>
                <tbody>
                  {activeSkill.outputs.map((output) => (
                    <tr key={output.name}>
                      <td className={shared.mono}>{output.name}</td>
                      <td>{output.artifact_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {creating && (
        <CreateSkillModal
          onClose={() => setCreating(false)}
          onCreated={(path) => {
            setCreating(false)
            setCreatedMessage(path)
            reload()
          }}
        />
      )}
    </div>
  )
}
