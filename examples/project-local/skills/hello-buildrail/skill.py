"""hello-buildrail: the smallest possible project-local Buildrail skill.

This is an example only — it is not discovered automatically. Copy this
directory to `.buildrail/skills/hello-buildrail/` in a real project (or run
`buildrail skill create <name>` to scaffold a fresh one) to make it real.

Project-local skills execute code from the repository they're found in —
only use project-local skills from repositories you trust. This follows
the exact same SkillRequest/SkillResponse contract every built-in skill
uses (docs/skills.md); there is no separate "example" format.
"""

from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse


def run(request: SkillRequest, provider: object | None) -> SkillResponse:
    """Produce a one-line greeting artifact. Replace this with real logic."""
    content = "# hello-buildrail\n\nHello from a project-local Buildrail skill.\n"
    output = SkillOutput(
        content=content, artifact_type="hello-buildrail", display_name="hello-buildrail-summary"
    )
    return SkillResponse(status="success", outputs={"summary": output})
