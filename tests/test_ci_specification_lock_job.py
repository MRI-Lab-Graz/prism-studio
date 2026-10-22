from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _job():
    jobs = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    return next(j for j in jobs.values() if j.get("name") == "Vendored specification")


def test_job_runs_the_lock_check_without_shell_interpolation():
    job = _job()
    runs = [s.get("run", "") for s in job["steps"]]
    assert any("scripts/ci/check_specification_lock.py" in r for r in runs)
    assert not any("${{" in r for r in runs)
