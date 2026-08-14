import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { SkillManifest } from '../api/types'
import { Modal } from './Modal'
import modal from './Modal.module.css'
import shared from '../styles/shared.module.css'

interface StepDraft {
  skill: string
  condition: 'always' | 'changes_exist'
}

interface CreatePipelineModalProps {
  onClose: () => void
  onCreated: (projectRelativePath: string) => void
}

/** Calls the same narrowly-scoped scaffold endpoint `buildrail pipeline
 * create` uses — the server renders validated YAML from these fields, this
 * form never sends raw YAML. Steps are an ordered list of existing skills
 * only: no DAG editor, no arbitrary expressions. */
export function CreatePipelineModal({ onClose, onCreated }: CreatePipelineModalProps) {
  const [skills, setSkills] = useState<SkillManifest[] | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState<StepDraft[]>([{ skill: '', condition: 'always' }])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .skills()
      .then((response) => {
        if (cancelled) return
        setSkills(response.skills)
        setSteps((current) =>
          current[0]?.skill
            ? current
            : [{ skill: response.skills[0]?.name ?? '', condition: 'always' }],
        )
      })
      .catch(() => {
        if (!cancelled) setSkills([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updateStep = useCallback((index: number, patch: Partial<StepDraft>) => {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)))
  }, [])

  const addStep = useCallback(() => {
    setSteps((current) => [...current, { skill: skills?.[0]?.name ?? '', condition: 'always' }])
  }, [skills])

  const removeStep = useCallback((index: number) => {
    setSteps((current) => current.filter((_, i) => i !== index))
  }, [])

  const moveStep = useCallback((index: number, direction: -1 | 1) => {
    setSteps((current) => {
      const target = index + direction
      if (target < 0 || target >= current.length) return current
      const next = [...current]
      const [moved] = next.splice(index, 1)
      next.splice(target, 0, moved)
      return next
    })
  }, [])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    if (steps.some((step) => !step.skill)) {
      setError('Every step needs a skill selected.')
      return
    }
    setSubmitting(true)
    try {
      const response = await api.createPipeline({
        name: name.trim(),
        description: description.trim() || undefined,
        steps: steps.map((step) => ({ skill: step.skill, condition: step.condition })),
      })
      onCreated(response.project_relative_path)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="New Pipeline" onClose={onClose}>
      <form onSubmit={(event) => void handleSubmit(event)} className={modal.field}>
        <div className={modal.field}>
          <label htmlFor="pipeline-name">Name</label>
          <input
            id="pipeline-name"
            type="text"
            placeholder="quality"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div className={modal.field}>
          <label htmlFor="pipeline-description">Description</label>
          <input
            id="pipeline-description"
            type="text"
            placeholder="Project-local Buildrail pipeline"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        <div className={modal.field}>
          <label>Steps</label>
          {steps.map((step, index) => (
            <div key={index} className={shared.buttonRow} style={{ alignItems: 'center' }}>
              <select
                aria-label={`Step ${index + 1} skill`}
                value={step.skill}
                onChange={(event) => updateStep(index, { skill: event.target.value })}
              >
                <option value="" disabled>
                  Select a skill…
                </option>
                {(skills ?? []).map((skill) => (
                  <option key={skill.name} value={skill.name}>
                    {skill.name}
                  </option>
                ))}
              </select>
              <select
                aria-label={`Step ${index + 1} condition`}
                value={step.condition}
                onChange={(event) =>
                  updateStep(index, { condition: event.target.value as StepDraft['condition'] })
                }
              >
                <option value="always">always</option>
                <option value="changes_exist">changes_exist</option>
              </select>
              <button
                type="button"
                className={shared.button}
                onClick={() => moveStep(index, -1)}
                disabled={index === 0}
                aria-label={`Move step ${index + 1} up`}
              >
                ↑
              </button>
              <button
                type="button"
                className={shared.button}
                onClick={() => moveStep(index, 1)}
                disabled={index === steps.length - 1}
                aria-label={`Move step ${index + 1} down`}
              >
                ↓
              </button>
              <button
                type="button"
                className={shared.button}
                onClick={() => removeStep(index)}
                disabled={steps.length === 1}
                aria-label={`Remove step ${index + 1}`}
              >
                Remove
              </button>
            </div>
          ))}
          <div className={shared.buttonRow}>
            <button type="button" className={shared.button} onClick={addStep}>
              Add step
            </button>
          </div>
        </div>

        {error && <p className={shared.errorState}>{error}</p>}
        <div className={shared.buttonRow}>
          <button type="submit" className={shared.buttonPrimary} disabled={submitting}>
            {submitting ? 'Creating…' : 'Create Pipeline'}
          </button>
          <button type="button" className={shared.button} onClick={onClose} disabled={submitting}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}
