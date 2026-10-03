"""CI / distribution hygiene that is cheap to keep true:

- every workflow starts from least privilege (top-level `permissions:`), so a
  compromised dependency during a build cannot use a write-scoped GITHUB_TOKEN;
- the composite action never interpolates `${{ inputs.* }}` into shell (script
  injection from a consumer's workflow); inputs go through `env:`;
- the validator image does not run as root.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_declares_top_level_permissions(wf):
    assert "permissions" in yaml.safe_load(wf.read_text(encoding="utf-8")), wf.name


def test_composite_action_does_not_interpolate_inputs_into_shell():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")


def test_validator_image_runs_as_non_root():
    users = [l for l in (ROOT / "Dockerfile").read_text().splitlines() if l.startswith("USER ")]
    assert users and users[-1].split()[1] not in ("root", "0")
