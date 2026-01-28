"""
Progress tracking for conversion jobs using Server-Sent Events (SSE).
"""

import json
import queue
import time
from typing import Dict, Generator
from threading import Lock

# Progress store: job_id -> {progress, message, status, step, queue}
_conversion_progress: Dict[str, dict] = {}
_progress_lock = Lock()


def create_job(job_id: str) -> None:
    """Create a new conversion job with a progress queue."""
    with _progress_lock:
        _conversion_progress[job_id] = {
            "progress": 0,
            "message": "Starting...",
            "status": "pending",
            "step": 1,
            "queue": queue.Queue(),
        }


def update_conversion_progress(
    job_id: str, progress: int, message: str, step: int = 1, status: str = "running"
) -> None:
    """Update progress for a conversion job and push to queue for SSE."""
    with _progress_lock:
        if job_id not in _conversion_progress:
            create_job(job_id)

        job = _conversion_progress[job_id]
        job["progress"] = progress
        job["message"] = message
        job["step"] = step
        job["status"] = status if progress < 100 else "complete"

        # Push update to queue for SSE subscribers
        try:
            job["queue"].put_nowait(
                {
                    "progress": progress,
                    "message": message,
                    "step": step,
                    "status": job["status"],
                }
            )
        except queue.Full:
            pass  # Queue full, skip this update


def get_conversion_progress(job_id: str) -> dict:
    """Get current progress for a conversion job."""
    with _progress_lock:
        job = _conversion_progress.get(job_id, {})
        return {
            "progress": job.get("progress", 0),
            "message": job.get("message", "Starting..."),
            "step": job.get("step", 1),
            "status": job.get("status", "pending"),
        }


def stream_progress(job_id: str, timeout: float = 30.0) -> Generator[str, None, None]:
    """
    Generator that yields SSE events for a conversion job.

    Args:
        job_id: The job ID to stream progress for
        timeout: Maximum time to wait for updates (seconds)

    Yields:
        SSE-formatted strings with progress data
    """
    with _progress_lock:
        if job_id not in _conversion_progress:
            create_job(job_id)
        job_queue = _conversion_progress[job_id]["queue"]

    start_time = time.time()

    while True:
        # Check timeout
        if time.time() - start_time > timeout:
            yield f"data: {json.dumps({'status': 'timeout', 'message': 'Stream timeout'})}\n\n"
            break

        try:
            # Wait for update with short timeout
            update = job_queue.get(timeout=0.5)
            yield f"data: {json.dumps(update)}\n\n"

            # Stop streaming if complete or error
            if update.get("status") in ("complete", "error"):
                break

        except queue.Empty:
            # Send heartbeat to keep connection alive
            yield ": heartbeat\n\n"


def clear_conversion_progress(job_id: str) -> None:
    """Clear progress for a completed job."""
    with _progress_lock:
        _conversion_progress.pop(job_id, None)


def complete_job(job_id: str, success: bool = True, message: str = "Complete") -> None:
    """Mark a job as complete."""
    status = "complete" if success else "error"
    update_conversion_progress(job_id, 100, message, step=4, status=status)
