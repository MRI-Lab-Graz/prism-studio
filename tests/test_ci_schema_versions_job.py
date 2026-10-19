from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _job():
    jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return next(j for j in jobs.values() if j.get("name") == "Modality schema versions")


def test_job_runs_on_pull_requests_and_pushes_without_shell_interpolation():
    job = _job()
    assert "pull_request" in job["if"] and "push" in job["if"]
    assert any(s.get("with", {}).get("fetch-depth") == 0 for s in job["steps"])
    for step in job["steps"]:
        assert "${{" not in step.get("run", "")
