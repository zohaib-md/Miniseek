import json
import tempfile
import unittest
from pathlib import Path

from miniseek.core.types import (
    FileInfo, PlanStatus, OperationStatus,
    UndoStatus, RunUndoStatus
)
from miniseek.core.security import PathSecurity
from miniseek.applications.janitor.planner import PlanBuilder
from miniseek.harness.transaction import TransactionExecutor
from miniseek.harness.history import HistoryManager
from miniseek.harness.undo import UndoEngine


class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_and_execute_run(self, filename, content, category):
        """Helper: create a file, build a plan, execute it, return result."""
        filepath = self.root_dir / filename
        filepath.write_text(content)
        info = FileInfo(
            path=str(filepath), relative_path=filename, name=filename,
            extension=Path(filename).suffix,
            size_bytes=filepath.stat().st_size, mtime=filepath.stat().st_mtime
        )
        categorization = [{
            "file_info": info,
            "category": category,
            "destination_path": str(self.root_dir / category / filename)
        }]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        executor = TransactionExecutor()
        return executor.execute_plan(plan, base_history_dir=self.root_dir)

    def test_list_runs_empty_history(self):
        runs = HistoryManager.list_runs(self.root_dir)
        self.assertEqual(len(runs), 0)

    def test_list_runs_multiple_runs(self):
        r1 = self._create_and_execute_run("invoice.pdf", "Invoice $100", "Receipts_Invoices")
        r2 = self._create_and_execute_run("code.py", "print('hello')", "Code")

        self.assertEqual(r1.status, PlanStatus.COMMITTED)
        self.assertEqual(r2.status, PlanStatus.COMMITTED)

        runs = HistoryManager.list_runs(self.root_dir)
        self.assertEqual(len(runs), 2)

        # Each run has a distinct run_id
        run_ids = {r.run_id for r in runs}
        self.assertEqual(len(run_ids), 2)

    def test_get_run_by_id(self):
        result = self._create_and_execute_run("doc.txt", "Document content", "Documents")
        self.assertIsNotNone(result.manifest_path)

        # Load manifest to get run_id
        manifest = HistoryManager.load_manifest(Path(result.manifest_path))
        run_id = manifest.run_id

        # Retrieve by run_id
        fetched = HistoryManager.get_run(run_id, self.root_dir)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.run_id, run_id)
        self.assertEqual(fetched.status, PlanStatus.COMMITTED)
        self.assertEqual(len(fetched.operations), 1)

    def test_get_run_nonexistent_returns_none(self):
        result = HistoryManager.get_run("run-nonexistent", self.root_dir)
        self.assertIsNone(result)

    def test_render_history_output(self):
        self._create_and_execute_run("file1.txt", "Content A", "Documents")
        self._create_and_execute_run("file2.py", "x = 1", "Code")

        runs = HistoryManager.list_runs(self.root_dir)
        rendered = HistoryManager.render_history(runs)

        self.assertIn("MINISEEK RUN HISTORY", rendered)
        self.assertIn("COMMITTED", rendered)
        self.assertIn("Total runs: 2", rendered)

    def test_render_history_empty(self):
        rendered = HistoryManager.render_history([])
        self.assertIn("No runs recorded", rendered)

    def test_manifest_preserves_plan_run_relationship(self):
        """Verify plan_id → run_id → operations traceability."""
        filepath = self.root_dir / "trace.txt"
        filepath.write_text("Traceable content")
        info = FileInfo(
            path=str(filepath), relative_path="trace.txt", name="trace.txt",
            extension=".txt",
            size_bytes=filepath.stat().st_size, mtime=filepath.stat().st_mtime
        )
        categorization = [{
            "file_info": info, "category": "Documents",
            "destination_path": str(self.root_dir / "Documents" / "trace.txt")
        }]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        original_plan_id = plan.plan_id
        original_plan_hash = plan.plan_hash

        executor = TransactionExecutor()
        result = executor.execute_plan(plan, base_history_dir=self.root_dir)

        manifest = HistoryManager.load_manifest(Path(result.manifest_path))

        # Plan → Run → Operations audit trail
        self.assertEqual(manifest.plan_id, original_plan_id)
        self.assertEqual(manifest.plan_hash, original_plan_hash)
        self.assertTrue(manifest.run_id.startswith("run-"))
        self.assertEqual(len(manifest.operations), 1)
        self.assertEqual(manifest.operations[0].source_original, str(filepath))

    def test_run_status_distinct_from_operation_status(self):
        """Verify run-level status is separate from per-operation status."""
        result = self._create_and_execute_run("sep.txt", "Separation test", "Documents")
        manifest = HistoryManager.load_manifest(Path(result.manifest_path))

        # Run status
        self.assertEqual(manifest.status, PlanStatus.COMMITTED)
        # Operation status
        self.assertEqual(manifest.operations[0].status, "COMPLETED")


class TestUndoEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)
        self.executor = TransactionExecutor()
        self.undo_engine = UndoEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _execute_move(self, filename, content, category):
        """Helper: create file, plan, execute, return (manifest, original_path)."""
        filepath = self.root_dir / filename
        filepath.write_text(content)
        info = FileInfo(
            path=str(filepath), relative_path=filename, name=filename,
            extension=Path(filename).suffix,
            size_bytes=filepath.stat().st_size, mtime=filepath.stat().st_mtime
        )
        categorization = [{
            "file_info": info, "category": category,
            "destination_path": str(self.root_dir / category / filename)
        }]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)
        manifest = HistoryManager.load_manifest(Path(result.manifest_path))
        return manifest, filepath

    # ── Normal Undo ───────────────────────────────────────────────────

    def test_normal_undo_restores_original(self):
        """move → verify → undo → original restored."""
        manifest, original_path = self._execute_move(
            "invoice.pdf", "Invoice data: $500", "Receipts_Invoices"
        )
        dest_path = self.root_dir / "Receipts_Invoices" / "invoice.pdf"

        # File moved successfully
        self.assertFalse(original_path.exists())
        self.assertTrue(dest_path.exists())

        # Undo
        result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(result.status, RunUndoStatus.UNDONE)
        self.assertEqual(result.operations_undone, 1)
        self.assertEqual(result.operations_conflict, 0)

        # File restored to original location
        self.assertTrue(original_path.exists())
        self.assertFalse(dest_path.exists())
        self.assertEqual(original_path.read_text(), "Invoice data: $500")

    def test_undo_reverse_order(self):
        """Verify 3-file undo processes in reverse order (C, B, A)."""
        files = []
        for name, content, cat in [
            ("a.txt", "Content A", "Documents"),
            ("b.txt", "Content B", "Documents"),
            ("c.txt", "Content C", "Documents"),
        ]:
            fp = self.root_dir / name
            fp.write_text(content)
            files.append((fp, name, content))

        infos = [
            FileInfo(
                path=str(fp), relative_path=name, name=name,
                extension=".txt",
                size_bytes=fp.stat().st_size, mtime=fp.stat().st_mtime
            )
            for fp, name, _ in files
        ]
        categorization = [
            {"file_info": info, "category": "Documents",
             "destination_path": str(self.root_dir / "Documents" / info.name)}
            for info in infos
        ]

        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)
        manifest = HistoryManager.load_manifest(Path(result.manifest_path))

        # All 3 moved
        for fp, _, _ in files:
            self.assertFalse(fp.exists())

        # Undo all
        undo_result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(undo_result.status, RunUndoStatus.UNDONE)
        self.assertEqual(undo_result.operations_undone, 3)

        # All restored
        for fp, _, content in files:
            self.assertTrue(fp.exists())
            self.assertEqual(fp.read_text(), content)

    # ── User Modification Conflict ────────────────────────────────────

    def test_undo_refuses_when_destination_modified_by_user(self):
        """move → user modifies destination → undo → MiniSeek refuses overwrite."""
        manifest, original_path = self._execute_move(
            "report.txt", "Original report content", "Documents"
        )
        dest_path = self.root_dir / "Documents" / "report.txt"

        # User modifies the destination file after the move
        dest_path.write_text("USER EDITED: This is my updated report")

        result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(result.status, RunUndoStatus.UNDO_FAILED)
        self.assertEqual(result.operations_undone, 0)
        self.assertEqual(result.operations_conflict, 1)

        # Destination file preserved with user's changes
        self.assertEqual(dest_path.read_text(), "USER EDITED: This is my updated report")
        # Original path still empty
        self.assertFalse(original_path.exists())

        # Conflict details recorded
        self.assertEqual(len(result.conflict_details), 1)
        self.assertIn("modified by user", result.conflict_details[0]["reason"])

    # ── Destination Missing ───────────────────────────────────────────

    def test_undo_conflict_when_destination_manually_deleted(self):
        """move → destination manually deleted → undo → safe conflict."""
        manifest, original_path = self._execute_move(
            "notes.txt", "My important notes", "Documents"
        )
        dest_path = self.root_dir / "Documents" / "notes.txt"

        # User deletes the destination file
        dest_path.unlink()

        result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(result.status, RunUndoStatus.UNDO_FAILED)
        self.assertEqual(result.operations_conflict, 1)
        self.assertIn("no longer exists", result.conflict_details[0]["reason"])

    # ── Original Path Occupied ────────────────────────────────────────

    def test_undo_refuses_when_original_path_occupied(self):
        """move → unrelated file at original location → undo → refuses overwrite."""
        manifest, original_path = self._execute_move(
            "data.csv", "col1,col2\n1,2", "Documents"
        )

        # Create a DIFFERENT file at the original location
        original_path.write_text("COMPLETELY DIFFERENT FILE - not the original")

        result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(result.status, RunUndoStatus.UNDO_FAILED)
        self.assertEqual(result.operations_conflict, 1)
        self.assertIn("occupied", result.conflict_details[0]["reason"])

        # The occupying file is NOT overwritten
        self.assertEqual(original_path.read_text(), "COMPLETELY DIFFERENT FILE - not the original")

    # ── Multiple Independent Runs ─────────────────────────────────────

    def test_undo_one_run_does_not_affect_another(self):
        """run A, run B → undo A → run B's files are untouched."""
        # Run A
        manifest_a, orig_a = self._execute_move(
            "run_a_file.txt", "Run A content", "Documents"
        )
        dest_a = self.root_dir / "Documents" / "run_a_file.txt"

        # Run B
        manifest_b, orig_b = self._execute_move(
            "run_b_file.py", "print('Run B')", "Code"
        )
        dest_b = self.root_dir / "Code" / "run_b_file.py"

        # Both moved
        self.assertTrue(dest_a.exists())
        self.assertTrue(dest_b.exists())

        # Undo ONLY run A
        undo_result = self.undo_engine.execute_undo(manifest_a, self.root_dir)

        self.assertEqual(undo_result.status, RunUndoStatus.UNDONE)
        self.assertEqual(undo_result.operations_undone, 1)

        # Run A: restored
        self.assertTrue(orig_a.exists())
        self.assertFalse(dest_a.exists())

        # Run B: completely untouched
        self.assertTrue(dest_b.exists())
        self.assertFalse(orig_b.exists())

    # ── Interrupted / Partial Undo ────────────────────────────────────

    def test_partial_undo_with_mixed_conflicts(self):
        """
        3 operations: C undone, B conflict (destination modified), A undone.
        Verify UNDO_PARTIAL status with correct per-operation states.
        """
        files_data = [
            ("alpha.txt", "Alpha content", "Documents"),
            ("beta.txt", "Beta content", "Documents"),
            ("gamma.txt", "Gamma content", "Documents"),
        ]
        for name, content, _ in files_data:
            (self.root_dir / name).write_text(content)

        infos = [
            FileInfo(
                path=str(self.root_dir / name), relative_path=name, name=name,
                extension=".txt",
                size_bytes=(self.root_dir / name).stat().st_size,
                mtime=(self.root_dir / name).stat().st_mtime
            )
            for name, _, _ in files_data
        ]
        categorization = [
            {"file_info": info, "category": "Documents",
             "destination_path": str(self.root_dir / "Documents" / info.name)}
            for info in infos
        ]

        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)
        manifest = HistoryManager.load_manifest(Path(result.manifest_path))

        # User modifies beta (op index 1) ONLY
        beta_dest = self.root_dir / "Documents" / "beta.txt"
        beta_dest.write_text("USER MODIFIED BETA")

        undo_result = self.undo_engine.execute_undo(manifest, self.root_dir)

        # Should be UNDO_PARTIAL: gamma and alpha undone, beta conflict
        self.assertEqual(undo_result.status, RunUndoStatus.UNDO_PARTIAL)
        self.assertEqual(undo_result.operations_undone, 2)
        self.assertEqual(undo_result.operations_conflict, 1)

        # Alpha and gamma restored
        self.assertTrue((self.root_dir / "alpha.txt").exists())
        self.assertTrue((self.root_dir / "gamma.txt").exists())

        # Beta: user's modification preserved, NOT overwritten
        self.assertEqual(beta_dest.read_text(), "USER MODIFIED BETA")

    def test_undo_durable_state_after_partial(self):
        """After a partial undo, the manifest on disk reflects exact state."""
        manifest, _ = self._execute_move(
            "durable.txt", "Durable content", "Documents"
        )
        dest = self.root_dir / "Documents" / "durable.txt"

        # Modify destination to cause conflict
        dest.write_text("MODIFIED BY USER")

        self.undo_engine.execute_undo(manifest, self.root_dir)

        # Re-load manifest from disk
        reloaded = HistoryManager.get_run(manifest.run_id, self.root_dir)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.status, RunUndoStatus.UNDO_FAILED)

        # Operation-level undo status persisted
        self.assertEqual(reloaded.operations[0].undo_status, UndoStatus.CONFLICT)
        self.assertIsNotNone(reloaded.operations[0].undo_error)

    def test_undo_durable_state_after_success(self):
        """After successful undo, the manifest on disk reflects UNDONE status."""
        manifest, original_path = self._execute_move(
            "success.txt", "Success content", "Documents"
        )

        self.undo_engine.execute_undo(manifest, self.root_dir)

        reloaded = HistoryManager.get_run(manifest.run_id, self.root_dir)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.status, RunUndoStatus.UNDONE)
        self.assertEqual(reloaded.operations[0].undo_status, UndoStatus.UNDONE)

    # ── Edge Cases ────────────────────────────────────────────────────

    def test_undo_not_applicable_for_failed_operations(self):
        """FAILED operations (from partial execution) are NOT_APPLICABLE for undo."""
        from unittest.mock import patch

        file_a = self.root_dir / "ok.txt"
        file_a.write_text("OK content")
        file_b = self.root_dir / "fail.txt"
        file_b.write_text("Fail content")

        info_a = FileInfo(
            path=str(file_a), relative_path="ok.txt", name="ok.txt",
            extension=".txt", size_bytes=file_a.stat().st_size, mtime=file_a.stat().st_mtime
        )
        info_b = FileInfo(
            path=str(file_b), relative_path="fail.txt", name="fail.txt",
            extension=".txt", size_bytes=file_b.stat().st_size, mtime=file_b.stat().st_mtime
        )

        categorization = [
            {"file_info": info_a, "category": "Documents",
             "destination_path": str(self.root_dir / "Documents" / "ok.txt")},
            {"file_info": info_b, "category": "Documents",
             "destination_path": str(self.root_dir / "Documents" / "fail.txt")},
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Make the second move fail
        original_move = __import__('shutil').move
        call_count = [0]
        def fail_second(src, dst, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("Simulated failure")
            return original_move(src, dst, *a, **kw)

        with patch('miniseek.harness.transaction.shutil.move', side_effect=fail_second):
            exec_result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(exec_result.status, PlanStatus.PARTIALLY_EXECUTED)
        manifest = HistoryManager.load_manifest(Path(exec_result.manifest_path))

        # Undo the partial run
        undo_result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(undo_result.status, RunUndoStatus.UNDONE)
        self.assertEqual(undo_result.operations_undone, 1)
        self.assertEqual(undo_result.operations_not_applicable, 0)  # FAILED ops not in manifest

        # ok.txt restored
        self.assertTrue(file_a.exists())

    def test_undo_ineligible_run_status(self):
        """Undo on a FAILED (pre-flight) run should return UNDO_FAILED immediately."""
        filepath = self.root_dir / "blocked.txt"
        filepath.write_text("Blocked content")
        info = FileInfo(
            path=str(filepath), relative_path="blocked.txt", name="blocked.txt",
            extension=".txt", size_bytes=filepath.stat().st_size, mtime=filepath.stat().st_mtime
        )
        categorization = [{
            "file_info": info, "category": "Documents",
            "destination_path": str(self.root_dir / "Documents" / "blocked.txt")
        }]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Tamper hash to cause pre-flight failure
        plan.plan_hash = "0" * 64
        exec_result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)
        self.assertEqual(exec_result.status, PlanStatus.FAILED)

        # Create a fake manifest with FAILED status
        from miniseek.core.types import RunManifest
        failed_manifest = RunManifest(
            run_id="run-fake-failed",
            plan_id="fake",
            plan_hash="fake",
            timestamp="2026-01-01T00:00:00Z",
            root_path=str(self.root_dir),
            status=PlanStatus.FAILED,
            operations=[]
        )
        HistoryManager.save_manifest(failed_manifest, self.root_dir)

        undo_result = self.undo_engine.execute_undo(failed_manifest, self.root_dir)

        self.assertEqual(undo_result.status, RunUndoStatus.UNDO_FAILED)
        self.assertIn("not eligible for undo", undo_result.error_message)

    def test_undo_sha256_verification_catches_size_preserved_modification(self):
        """Even if size is unchanged, SHA-256 mismatch detects modification."""
        manifest, original_path = self._execute_move(
            "hash_check.txt", "AAAA", "Documents"
        )
        dest = self.root_dir / "Documents" / "hash_check.txt"

        # Overwrite with same-length but different content
        dest.write_text("BBBB")
        self.assertEqual(dest.stat().st_size, 4)  # Same size

        result = self.undo_engine.execute_undo(manifest, self.root_dir)

        self.assertEqual(result.status, RunUndoStatus.UNDO_FAILED)
        self.assertEqual(result.operations_conflict, 1)
        self.assertIn("content hash changed", result.conflict_details[0]["reason"])


if __name__ == "__main__":
    unittest.main()
