from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "propose-modality.yml"


def _load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps(job):
    return _load()["jobs"][job]["steps"]


def test_runs_only_on_new_modality_issues():
    wf = _load()
    assert wf[True]["issues"]["types"] == ["opened"]  # PyYAML reads `on` as True
    for name in ("check", "report"):
        assert "type: new-modality" in wf["jobs"][name]["if"]


def test_issue_text_never_reaches_a_run_block():
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in _load()["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), step
    assert "ISSUE_BODY: ${{ github.event.issue.body }}" in text


def test_actions_are_pinned_by_sha():
    for job in _load()["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert "@" in step["uses"] and len(step["uses"].split("@")[1]) == 40, step["uses"]


def test_top_level_permissions_are_empty():
    assert _load()["permissions"] == {}


def test_untrusted_job_has_no_write_access_or_credentials():
    job = _load()["jobs"]["check"]
    assert job["permissions"] == {"contents": "read"}
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    text = WORKFLOW.read_text(encoding="utf-8")
    check_text = text.split("\n  report:")[0]
    assert "GH_TOKEN" not in check_text and "github.token" not in check_text
    upload = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["retention-days"] == 1
    assert upload["with"]["if-no-files-found"] == "error"
    assert "RUNNER_TEMP" in check_text


def test_privileged_job_is_separate_and_verifies_the_artifact():
    wf = _load()
    job = wf["jobs"]["report"]
    assert job["needs"] == "check"
    assert job["permissions"] == {
        "contents": "write", "pull-requests": "write", "issues": "write",
    }
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "find bundle -type l" in runs
    assert "find bundle ! -type f ! -type d" in runs
    assert "core.hooksPath=/dev/null" in runs
    assert "GITHUB_RUN_ID" in runs
    assert "gh label create needs-changes --force" in runs
    # fence breakout: backticks are stripped from the log before it is quoted
    assert "tr '`'" in runs
    assert job["steps"][-1]["if"] == "failure()"
    # the issue number comes from the event, never from the artifact
    assert "github.event.issue.number" in WORKFLOW.read_text(encoding="utf-8")


def test_both_jobs_have_timeouts():
    for job in _load()["jobs"].values():
        assert job["timeout-minutes"] == 10


TRUSTED = "contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), github.event.issue.author_association)"


def test_pr_is_opened_only_for_trusted_authors():
    steps = {s["name"]: s for s in _steps("report")}
    pr_if = steps["Open draft pull request"]["if"]
    assert "steps.bundle.outputs.failed != 'true'" in pr_if
    assert TRUSTED in pr_if


def test_other_authors_get_a_static_handover_comment():
    step = next(s for s in _steps("report") if s["name"] == "Tell other authors a maintainer will take over")
    assert "steps.bundle.outputs.failed != 'true'" in step["if"]
    assert f"!{TRUSTED}" in step["if"] or f"! {TRUSTED}" in step["if"]
    assert "${{" not in step["run"] and "maintainer" in step["run"]
    assert step["env"]["ISSUE_NUMBER"] == "${{ github.event.issue.number }}"
    assert "GH_TOKEN" in step["env"]
