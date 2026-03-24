from __future__ import annotations

import time
import threading
from typing import Any, Callable


class ConversionJobStore:
    """Thread-safe in-memory job store for async conversion jobs."""

    def __init__(
        self,
        *,
        log_level_key: str,
        done_job_ttl_seconds: float = 900.0,
        prune_interval_seconds: float = 30.0,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.log_level_key = log_level_key
        self.done_job_ttl_seconds = max(0.0, float(done_job_ttl_seconds))
        self.prune_interval_seconds = max(0.0, float(prune_interval_seconds))
        self._time_fn = time_fn or time.monotonic
        self._last_prune_at = 0.0

    def _now(self) -> float:
        return float(self._time_fn())

    def _prune_done_jobs_locked(self, *, force: bool = False) -> None:
        now = self._now()
        if (
            not force
            and self.prune_interval_seconds > 0
            and (now - self._last_prune_at) < self.prune_interval_seconds
        ):
            return

        cutoff = now - self.done_job_ttl_seconds
        to_delete: list[str] = []
        for job_id, job in self.jobs.items():
            if not job.get("done"):
                continue
            done_at = job.get("done_at")
            if done_at is None:
                continue
            if float(done_at) <= cutoff:
                to_delete.append(job_id)

        for job_id in to_delete:
            self.jobs.pop(job_id, None)

        self._last_prune_at = now

    def create(self, job_id: str) -> None:
        with self.lock:
            self._prune_done_jobs_locked(force=True)
            if job_id in self.jobs:
                raise ValueError(f"Job id already exists: {job_id}")
            now = self._now()
            self.jobs[job_id] = {
                "logs": [],
                "done": False,
                "status": "running",
                "progress_pct": 0,
                "success": None,
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
                "done_at": None,
            }

    def append_log(self, job_id: str, message: str, level: str = "info") -> None:
        with self.lock:
            self._prune_done_jobs_locked()
            job = self.jobs.get(job_id)
            if not job:
                return
            job["logs"].append({"message": message, self.log_level_key: level})
            job["updated_at"] = self._now()

    def is_cancelled(self, job_id: str) -> bool:
        with self.lock:
            self._prune_done_jobs_locked()
            job = self.jobs.get(job_id)
            if not job:
                return False
            return job.get("status") == "cancelled"

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            self._prune_done_jobs_locked()
            job = self.jobs.get(job_id)
            if not job or job.get("done"):
                return False
            job["status"] = "cancelled"
            job["updated_at"] = self._now()
            return True

    def update(self, job_id: str, **updates: Any) -> bool:
        with self.lock:
            self._prune_done_jobs_locked()
            job = self.jobs.get(job_id)
            if not job:
                return False
            job.update(updates)
            now = self._now()
            job["updated_at"] = now
            if bool(job.get("done")) and job.get("done_at") is None:
                job["done_at"] = now
            return True

    def success(self, job_id: str, result: dict[str, Any]) -> bool:
        return self.update(
            job_id,
            done=True,
            success=True,
            progress_pct=100,
            result=result,
            error=None,
            status="completed",
        )

    def failure(self, job_id: str, error: str, *, status: str = "failed") -> bool:
        return self.update(
            job_id,
            done=True,
            success=False,
            result=None,
            error=error,
            status=status,
        )

    def snapshot(self, job_id: str, cursor: int) -> dict[str, Any] | None:
        with self.lock:
            self._prune_done_jobs_locked()
            job = self.jobs.get(job_id)
            if not job:
                return None

            logs = job["logs"]
            bounded_cursor = max(0, min(cursor, len(logs)))
            payload = {
                "logs": logs[bounded_cursor:],
                "next_cursor": len(logs),
                "done": bool(job["done"]),
                "status": job.get("status", "running"),
                "progress_pct": job.get("progress_pct", 0),
                "success": job["success"],
                "result": job["result"],
                "error": job["error"],
            }

            if job["done"]:
                self.jobs.pop(job_id, None)

            return payload

    def metrics(self) -> dict[str, Any]:
        with self.lock:
            self._prune_done_jobs_locked()
            jobs = list(self.jobs.values())

            return {
                "total_jobs": len(jobs),
                "running_jobs": sum(1 for j in jobs if j.get("status") == "running"),
                "cancelled_jobs": sum(
                    1 for j in jobs if j.get("status") == "cancelled"
                ),
                "completed_jobs": sum(
                    1 for j in jobs if j.get("status") == "completed"
                ),
                "failed_jobs": sum(1 for j in jobs if j.get("status") == "failed"),
                "done_jobs": sum(1 for j in jobs if bool(j.get("done"))),
                "done_job_ttl_seconds": self.done_job_ttl_seconds,
                "prune_interval_seconds": self.prune_interval_seconds,
                "last_prune_at": self._last_prune_at,
            }