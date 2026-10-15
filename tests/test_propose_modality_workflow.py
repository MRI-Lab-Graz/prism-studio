from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "propose-modality.yml"


def _load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_runs_only_on_new_modality_issues():
    wf = _load()
    assert wf[True]["issues"]["types"] == ["opened"]  # PyYAML reads `on` as True
    job = wf["jobs"]["propose"]
    assert "type: new-modality" in job["if"]


def test_issue_text_never_reaches_a_run_block():
    text = WORKFLOW.read_text(encoding="utf-8")
    for step in _load()["jobs"]["propose"]["steps"]:
        assert "github.event" not in step.get("run", ""), step
    assert "ISSUE_BODY: ${{ github.event.issue.body }}" in text


def test_actions_are_pinned_by_sha():
    for step in _load()["jobs"]["propose"]["steps"]:
        if "uses" in step:
            assert "@" in step["uses"] and len(step["uses"].split("@")[1]) == 40, step["uses"]


def test_permissions_are_explicit_and_minimal():
    wf = _load()
    assert wf["permissions"] == {}
    assert wf["jobs"]["propose"]["permissions"] == {
        "contents": "write", "pull-requests": "write", "issues": "write",
    }
