import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)


from src.web.blueprints.conversion_job_store import ConversionJobStore


class TestConversionJobStore(unittest.TestCase):
    def test_create_append_and_snapshot(self):
        store = ConversionJobStore(log_level_key="level")

        store.create("job-1")
        store.append_log("job-1", "started", "info")

        payload = store.snapshot("job-1", 0)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["progress_pct"], 0)
        self.assertEqual(payload["next_cursor"], 1)
        self.assertEqual(payload["logs"][0]["message"], "started")
        self.assertEqual(payload["logs"][0]["level"], "info")

    def test_cancel_marks_running_job(self):
        store = ConversionJobStore(log_level_key="type")

        store.create("job-2")

        self.assertTrue(store.cancel("job-2"))
        self.assertTrue(store.is_cancelled("job-2"))

    def test_success_snapshot_cleans_finished_job(self):
        store = ConversionJobStore(log_level_key="level")

        store.create("job-3")
        store.success("job-3", {"row_count": 2})

        payload = store.snapshot("job-3", 0)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertTrue(payload["done"])
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["progress_pct"], 100)
        self.assertEqual(payload["result"]["row_count"], 2)
        self.assertIsNone(store.snapshot("job-3", 0))

    def test_failure_sets_error_and_status(self):
        store = ConversionJobStore(log_level_key="level")

        store.create("job-4")
        store.failure("job-4", "Cancelled by user", status="cancelled")

        payload = store.snapshot("job-4", 0)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertFalse(payload["success"])
        self.assertEqual(payload["status"], "cancelled")
        self.assertEqual(payload["error"], "Cancelled by user")

    def test_create_duplicate_id_raises(self):
        store = ConversionJobStore(log_level_key="level")

        store.create("job-dup")
        with self.assertRaises(ValueError):
            store.create("job-dup")

    def test_done_jobs_are_pruned_by_ttl(self):
        current_time = {"value": 100.0}

        def fake_time() -> float:
            return current_time["value"]

        store = ConversionJobStore(
            log_level_key="level",
            done_job_ttl_seconds=5.0,
            prune_interval_seconds=0.0,
            time_fn=fake_time,
        )

        store.create("job-old")
        store.success("job-old", {"ok": True})

        current_time["value"] = 106.0
        store.create("job-new")

        self.assertIsNone(store.snapshot("job-old", 0))
        self.assertIsNotNone(store.snapshot("job-new", 0))


if __name__ == "__main__":
    unittest.main()
