# Project-Local Extension Examples

These are examples only — Buildrail never discovers anything under
`examples/`. Project-local skills and pipelines are only ever discovered
under `.buildrail/skills/` and `.buildrail/pipelines/` at a project's root
(created by `buildrail init`, or `buildrail init --extensions` for an
already-configured project).

```
examples/project-local/
├── skills/
│   └── hello-buildrail/   # a minimal provider-free skill
│       ├── skill.yaml
│       └── skill.py
└── pipelines/
    └── quality.yaml       # a two-step pipeline referencing built-in skills
```

## Try it

Copy a skill into a real project's `.buildrail/skills/`:

```
mkdir .buildrail\skills\hello-buildrail
copy examples\project-local\skills\hello-buildrail\* .buildrail\skills\hello-buildrail\
buildrail skill list
buildrail skill inspect hello-buildrail
```

Copy the pipeline into `.buildrail/pipelines/`:

```
copy examples\project-local\pipelines\quality.yaml .buildrail\pipelines\quality.yaml
buildrail pipeline list
buildrail pipeline inspect quality
buildrail run quality
```

Or scaffold fresh ones instead of copying these examples:

```
buildrail skill create my-skill
buildrail pipeline create my-pipeline
```

## What a project-local skill is

The exact same format as a built-in skill (`skills/<name>/skill.yaml` +
its entrypoint) — there is no separate "example" or "community" format.
`skill.py` follows the same `SkillRequest`/`SkillResponse` contract every
built-in skill uses (see `docs/skills.md`).

**Project-local skills execute code from the repository they're found
in.** Buildrail does not sandbox them — only use project-local skills
from repositories you trust.

## What a project-local pipeline is

A small declarative YAML manifest: an ordered list of existing skill
names, each with an optional `condition` and `inputs`. Supported
conditions: `always` (the default) and `changes_exist` (skip the step
when there's no Git diff against the resolved base ref). There is no
expression language, no loops, no variables, and no parallel execution —
see `docs/skills.md` and `README.md` for the full, deliberately small
feature set.

## Precedence

A project-local skill or pipeline sharing a built-in's name is a
discovery error, not a silent override — `buildrail skill list` /
`buildrail pipeline list` will report it clearly rather than picking one
silently. Rename the project-local one instead.
