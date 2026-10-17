"""The JavaScript unit tests (vitest) run in CI on every push and pull request."""

from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _job_runs_vitest_on_push(job: dict) -> bool:
    return any("vitest run" in str(step.get("run", "")) for step in job.get("steps", []))


def test_a_job_that_runs_on_push_and_pull_request_runs_the_vitest_suite():
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    runs_on_push = [
        name for name, job in jobs.items()
        if "push" in str(job.get("if", "push")) and _job_runs_vitest_on_push(job)
    ]
    assert runs_on_push, "no job that runs on push/pull_request runs `vitest run`"


def test_node_is_set_up_with_a_version_vitest_supports():
    # (pinning to a commit SHA is enforced for every action by test_actions_pinned_to_sha.py)
    text = CI.read_text(encoding="utf-8")
    assert "actions/setup-node@" in text
    assert 'node-version: "22"' in text  # vitest needs 22.12 or newer
