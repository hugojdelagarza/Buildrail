"""Milestone-1 hardcoded skill loading: imports a built-in skill's module by path.

Stands in for the manifest-driven Skill Registry (docs/skills.md) until
Phase 2 adds discovery of multiple skills. Only works from a source checkout
(editable install) — built-in skills aren't yet packaged for installed
wheels, which is a real limitation of this phase, not an oversight.
"""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import cast

from buildrail.providers import ProviderGateway
from buildrail.skill_protocol import SkillRequest, SkillResponse

SkillRunner = Callable[[SkillRequest, ProviderGateway], SkillResponse]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILLS_DIR = _REPO_ROOT / "skills"


def load_skill(name: str) -> SkillRunner:
    """Import a built-in skill's skill.py module by name and return its run() function."""
    module_path = _SKILLS_DIR / name / "skill.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"No skill named '{name}' found at {module_path}.")

    spec = importlib.util.spec_from_file_location(f"buildrail_skill_{name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load skill '{name}' from {module_path}.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(SkillRunner, module.run)
