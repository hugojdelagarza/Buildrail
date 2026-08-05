import { useCallback, useState } from 'react'
import { api } from '../api/client'
import type { SkillManifest } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import shared from '../styles/shared.module.css'
import layout from '../styles/listDetail.module.css'

export function SkillsPage() {
  const fetchSkills = useCallback((signal: AbortSignal) => api.skills(signal), [])
  const { data, error, loading } = useAsync(fetchSkills, [])
  const [selected, setSelected] = useState<string | null>(null)

  if (loading) return <p className={shared.loadingState}>Loading skills…</p>
  if (error || !data) return <p className={shared.errorState}>{error}</p>

  const activeSkill: SkillManifest | undefined =
    data.skills.find((skill) => skill.name === selected) ?? data.skills[0]

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Skills</h1>
        <p className={shared.pageSubtitle}>{data.skills.length} discovered</p>
      </div>

      <div className={layout.split}>
        <ul className={layout.list}>
          {data.skills.map((skill) => (
            <li key={skill.name}>
              <button
                type="button"
                className={activeSkill?.name === skill.name ? layout.itemActive : layout.item}
                onClick={() => setSelected(skill.name)}
              >
                <span className={shared.mono}>{skill.name}</span>
                <span className={layout.itemMeta}>{skill.version}</span>
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
    </div>
  )
}
