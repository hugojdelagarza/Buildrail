// TypeScript models matching Buildrail's local HTTP service response shapes
// exactly (see src/buildrail/service/routes.py). Every field here mirrors a
// field the backend actually serializes — no client-side invented fields.

export interface HealthResponse {
  status: string
  version: string
}

export interface VersionResponse {
  buildrail_version: string
  api_version: string
  python_version: string
  platform: string
}

export interface CommandArgument {
  name: string
  type: string
  required: boolean
  description: string
}

export interface CommandDescriptor {
  id: string
  display_name: string
  description: string
  endpoint: string
  method: string
  requires_provider: boolean
  accepts_arguments: boolean
  arguments: CommandArgument[]
  artifact_types: string[]
  category: string
}

export interface CommandsResponse {
  commands: CommandDescriptor[]
}

export interface SkillManifestInput {
  name: string
  type: string
  required: boolean
  description: string
}

export interface SkillManifestOutput {
  name: string
  artifact_type: string
}

export interface SkillManifest {
  name: string
  version: string
  protocol_version: string
  description: string
  requires_provider: boolean
  inputs: SkillManifestInput[]
  outputs: SkillManifestOutput[]
}

export interface SkillsResponse {
  skills: SkillManifest[]
}

export interface PipelineStep {
  name: string
  skippable: boolean
  skip_condition: string | null
}

export interface PipelineDescriptor {
  name: string
  display_name: string
  description: string
  steps: PipelineStep[]
  requires_provider: boolean
  arguments: CommandArgument[]
}

export interface PipelinesResponse {
  pipelines: PipelineDescriptor[]
}

export interface ProviderUsage {
  provider?: string | null
  model?: string | null
  input_tokens?: number
  output_tokens?: number
  cost_estimate?: { amount: number; currency: string } | null
}

export interface RunSummary {
  run_id: string
  status: string
  created_at: string | null
  artifact_count: number
  artifact_types: string[]
  pipeline: string | null
}

export interface RunsResponse {
  runs: RunSummary[]
}

export interface PipelineStepStatus {
  name: string
  status: string
  reason: string | null
  artifact_ids: string[]
}

export interface ArtifactDetail {
  id: string
  run_id: string
  type: string
  content_path: string
  status: string
  produced_by_skill: string | null
  produced_by_version: string | null
  provider_usage: ProviderUsage | null
  pipeline: string | null
  display_name: string | null
  created_at: string | null
  checksum: string | null
  content_type: string | null
}

export interface RunDetail {
  run_id: string
  status: string
  created_at: string | null
  pipeline: string | null
  duration_seconds: number | null
  pipeline_steps: PipelineStepStatus[]
  artifacts: ArtifactDetail[]
  provider_usage_totals: ProviderUsage | null
}

export interface ArtifactPayload extends ArtifactDetail {
  content: string
  content_json: Record<string, unknown> | null
}

export interface ProjectResponse {
  service_version: string
  project_root: string
  config_status: 'ok' | 'missing'
  artifact_root: string | null
  provider: string | null
  provider_ready: boolean
  skill_count: number
  pipeline_count: number
  recent_run_count: number
  latest_run: RunSummary | null
  statistics: ProjectStatistics | null
}

export interface ProjectStatistics {
  python_files: number
  modules: number
  classes: number
  functions: number
  test_files: number
  lines_of_python: number
}

export interface ConfigResponse {
  status: 'ok' | 'missing' | 'invalid'
  configured: boolean
  provider: string | null
  anthropic_model: string | null
  artifact_root: string | null
  credential_available: boolean
  error: string | null
}

// Only these three fields are ever accepted by PUT /config — never an API
// key, never arbitrary TOML. Omitted fields keep their current value (or
// Buildrail's offline-friendly defaults, if no config exists yet).
export interface ConfigUpdateRequest {
  provider?: 'fake' | 'anthropic'
  artifact_root?: string
  anthropic_model?: string
}

export interface CommandResult {
  success: boolean
  message: string
}

// The explain-project skill's JSON sidecar artifact (see
// src/buildrail/analysis/models.py's ProjectAnalysis). Only the fields the
// Project Intelligence page actually renders are typed here.
export interface ProjectAnalysis {
  schema_version: string
  repository_name: string
  repository_root: string
  python_requires: string | null
  build_system: string | null
  entry_points: { name: string; target: string; kind: string }[]
  cli_commands: { command: string; description: string | null; source_module: string | null }[]
  packages: { dotted_name: string; modules: string[]; subpackages: string[] }[]
  modules: {
    dotted_name: string
    file_path: string
    docstring: string | null
    classes: { name: string; docstring: string | null }[]
    functions: { name: string; docstring: string | null }[]
    imports: string[]
    lines: number
  }[]
  skills: {
    name: string
    version: string
    description: string
    requires_provider: boolean
    artifact_types: string[]
  }[]
  pipelines: { name: string; steps: string[] }[]
  artifact_types: string[]
  test_layout: { test_directories: string[]; test_files: string[] }
  tooling: { has_ruff: boolean; has_mypy: boolean; has_pytest: boolean }
  statistics: ProjectStatistics
  warnings: { kind: string; path: string; message: string }[]
}

// The dependency-audit skill's JSON sidecar artifact (see
// src/buildrail/dependencies/models.py's DependencyAudit). A declaration
// audit, not a vulnerability/CVE scanner.
export interface DeclaredDependency {
  name: string
  raw: string
  group: string
  source: string
  version_constraint: string | null
  is_pinned: boolean
  is_vcs: boolean
  is_url: boolean
  is_editable: boolean
  is_local_path: boolean
}

export interface DependencyAuditWarning {
  kind: string
  path: string
  message: string
}

export interface DependencyAudit {
  schema_version: string
  repository_name: string
  repository_root: string
  build_backend: string | null
  sources: string[]
  dependencies: DeclaredDependency[]
  duplicates: { name: string; occurrences: string[] }[]
  conflicts: { name: string; constraints: string[]; note: string }[]
  mismatches: { name: string; kind: string; note: string }[]
  observed_third_party_imports: string[]
  warnings: DependencyAuditWarning[]
}
