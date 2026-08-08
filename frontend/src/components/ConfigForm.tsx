import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ConfigResponse } from '../api/types'
import shared from '../styles/shared.module.css'
import styles from './ConfigForm.module.css'

interface ConfigFormProps {
  initialProvider: 'fake' | 'anthropic' | null
  initialArtifactRoot: string | null
  initialAnthropicModel: string | null
  onSaved: (config: ConfigResponse) => void
  onCancel?: () => void
  submitLabel?: string
}

/**
 * The one form Buildrail uses to write project configuration — shared by the
 * onboarding first-run flow and Settings' later edits, so both always agree
 * on what fields exist and how they're validated. Writes go through the same
 * `PUT /config` endpoint either way; there is no separate "settings" API.
 */
export function ConfigForm({
  initialProvider,
  initialArtifactRoot,
  initialAnthropicModel,
  onSaved,
  onCancel,
  submitLabel = 'Save configuration',
}: ConfigFormProps) {
  const [provider, setProvider] = useState<'fake' | 'anthropic'>(initialProvider ?? 'fake')
  const [artifactRoot, setArtifactRoot] = useState(initialArtifactRoot ?? 'artifacts')
  const [anthropicModel, setAnthropicModel] = useState(initialAnthropicModel ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const response = await api.updateConfig({
        provider,
        artifact_root: artifactRoot.trim() || 'artifacts',
        ...(provider === 'anthropic' && anthropicModel.trim()
          ? { anthropic_model: anthropicModel.trim() }
          : {}),
      })
      onSaved(response)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className={shared.section}>
      <div className={styles.providerOptions} role="radiogroup" aria-label="Provider">
        <label className={styles.providerOption}>
          <input
            type="radio"
            name="provider"
            value="fake"
            checked={provider === 'fake'}
            onChange={() => setProvider('fake')}
          />
          <span>
            <span className={styles.optionTitle}>Fake / Offline</span>
            <p className={styles.optionDescription}>
              Deterministic local provider for testing Buildrail without API usage.
            </p>
          </span>
        </label>
        <label className={styles.providerOption}>
          <input
            type="radio"
            name="provider"
            value="anthropic"
            checked={provider === 'anthropic'}
            onChange={() => setProvider('anthropic')}
          />
          <span>
            <span className={styles.optionTitle}>Anthropic</span>
            <p className={styles.optionDescription}>
              Uses ANTHROPIC_API_KEY from the environment. The key is never stored by Buildrail.
            </p>
          </span>
        </label>
      </div>

      <label className={styles.field}>
        <span>Artifact directory</span>
        <input
          type="text"
          value={artifactRoot}
          onChange={(event) => setArtifactRoot(event.target.value)}
          placeholder="artifacts"
        />
      </label>

      {provider === 'anthropic' && (
        <label className={styles.field}>
          <span>Anthropic model</span>
          <input
            type="text"
            value={anthropicModel}
            onChange={(event) => setAnthropicModel(event.target.value)}
            placeholder="Provider default"
          />
        </label>
      )}

      {error && <p className={shared.errorState}>{error}</p>}

      <div className={shared.buttonRow}>
        <button type="submit" className={shared.buttonPrimary} disabled={saving}>
          {saving ? 'Saving…' : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className={shared.button} onClick={onCancel} disabled={saving}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
