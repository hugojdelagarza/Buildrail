import { useState } from 'react'
import { api, ApiError } from '../api/client'
import { Modal } from './Modal'
import modal from './Modal.module.css'
import shared from '../styles/shared.module.css'

interface CreateSkillModalProps {
  onClose: () => void
  onCreated: (projectRelativePath: string) => void
}

/** Calls the same narrowly-scoped scaffold endpoint `buildrail skill create`
 * uses — the server always generates the skill.yaml/skill.py template, this
 * form never sends source code. */
export function CreateSkillModal({ onClose, onCreated }: CreateSkillModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [requiresProvider, setRequiresProvider] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const response = await api.createSkill({
        name: name.trim(),
        description: description.trim() || undefined,
        requires_provider: requiresProvider,
      })
      onCreated(response.project_relative_path)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="New Skill" onClose={onClose}>
      <form onSubmit={(event) => void handleSubmit(event)} className={modal.field}>
        <div className={modal.field}>
          <label htmlFor="skill-name">Name</label>
          <input
            id="skill-name"
            type="text"
            placeholder="api-review"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div className={modal.field}>
          <label htmlFor="skill-description">Description</label>
          <input
            id="skill-description"
            type="text"
            placeholder="A project-local Buildrail skill."
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        <div className={modal.checkboxField}>
          <input
            id="skill-requires-provider"
            type="checkbox"
            checked={requiresProvider}
            onChange={(event) => setRequiresProvider(event.target.checked)}
          />
          <label htmlFor="skill-requires-provider">Requires provider</label>
        </div>
        {error && <p className={shared.errorState}>{error}</p>}
        <div className={shared.buttonRow}>
          <button type="submit" className={shared.buttonPrimary} disabled={submitting}>
            {submitting ? 'Creating…' : 'Create Skill'}
          </button>
          <button type="button" className={shared.button} onClick={onClose} disabled={submitting}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}
