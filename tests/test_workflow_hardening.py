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


def _release_job():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["release"]


def test_release_publishes_checksums_and_provenance():
    job = _release_job()
    steps = job["steps"]
    assert any("sha256sum" in s.get("run", "") and "SHA256SUMS" in s.get("run", "") for s in steps)
    release = next(s for s in steps if "action-gh-release" in s.get("uses", ""))
    assert "SHA256SUMS" in release["with"]["files"]
    attest = [s for s in steps if "attest-build-provenance" in s.get("uses", "")]
    assert attest, "no build provenance attestation step"
    assert job["permissions"]["attestations"] == "write" and job["permissions"]["id-token"] == "write"


def test_readme_explains_how_to_verify_a_download():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "SHA256SUMS" in readme and "gh attestation verify" in readme


def test_release_build_installs_only_hash_locked_requirements():
    wf = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "--require-hashes" in wf and "requirements-release.lock" in wf
    assert "-r requirements-runtime.txt" not in wf and "-r requirements-build.txt" not in wf
    lock = (ROOT / "requirements-release.lock").read_text(encoding="utf-8")
    assert "--hash=sha256:" in lock


def test_lock_covers_every_direct_runtime_and_build_dependency():
    import re

    lock = (ROOT / "requirements-release.lock").read_text(encoding="utf-8").lower().replace("_", "-")
    pinned = set(re.findall(r"^([a-z0-9][a-z0-9.-]*)==", lock, flags=re.M))
    for name in ("requirements-runtime.txt", "requirements-build.txt"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", line.strip())
            if m and not line.strip().startswith("#"):
                assert m.group(1).lower().replace("_", "-") in pinned, (name, m.group(1))
