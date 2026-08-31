import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from miniseek.core.types import FileInfo, PlanStatus, OperationStatus
from miniseek.core.security import PathSecurity
from miniseek.applications.janitor.planner import PlanBuilder
from miniseek.harness.transaction import TransactionExecutor

class TestTransactionExecutor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)
        self.executor = TransactionExecutor()

        # Create sample files
        self.file1 = self.root_dir / "invoice_march.pdf"
        self.file1.write_text("Invoice data: $500 to Acme Corp")

        self.file2 = self.root_dir / "script.py"
        self.file2.write_text("def hello(): return 'world'")

        self.info1 = FileInfo(
            path=str(self.file1),
            relative_path="invoice_march.pdf",
            name="invoice_march.pdf",
            extension=".pdf",
            size_bytes=self.file1.stat().st_size,
            mtime=self.file1.stat().st_mtime
        )
        self.info2 = FileInfo(
            path=str(self.file2),
            relative_path="script.py",
            name="script.py",
            extension=".py",
            size_bytes=self.file2.stat().st_size,
            mtime=self.file2.stat().st_mtime
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # ── Success Path Tests ────────────────────────────────────────────

    def test_single_file_move_and_verification(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.COMMITTED)
        self.assertEqual(result.operations_completed, 1)
        self.assertEqual(result.operations_failed, 0)
        self.assertEqual(plan.operations[0].status, OperationStatus.COMPLETED)

        # Filesystem verification
        self.assertFalse(self.file1.exists())
        dest_file = self.root_dir / "Receipts_Invoices" / "invoice_march.pdf"
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "Invoice data: $500 to Acme Corp")

        # Run manifest exists
        self.assertIsNotNone(result.manifest_path)
        self.assertTrue(Path(result.manifest_path).exists())

    def test_multi_file_batch_execution(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            },
            {
                "file_info": self.info2,
                "category": "Code",
                "destination_path": str(self.root_dir / "Code" / "script.py")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.COMMITTED)
        self.assertEqual(result.operations_completed, 2)
        self.assertEqual(result.operations_failed, 0)

        self.assertTrue((self.root_dir / "Receipts_Invoices" / "invoice_march.pdf").exists())
        self.assertTrue((self.root_dir / "Code" / "script.py").exists())
        self.assertFalse(self.file1.exists())
        self.assertFalse(self.file2.exists())

    # ── Pre-Flight Failure Tests ──────────────────────────────────────

    def test_preflight_plan_hash_mismatch_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        plan.plan_hash = "0" * 64

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("Plan hash mismatch", result.error_message)
        self.assertTrue(self.file1.exists())

    def test_preflight_missing_source_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        self.file1.unlink()

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("Source file", result.error_message)
        self.assertIn("no longer exists", result.error_message)

    def test_preflight_source_content_modified_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        self.file1.write_text("Invoice data: $999 to Acme Corp")

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("content hash changed", result.error_message)
        self.assertTrue(self.file1.exists())

    def test_preflight_destination_collision_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        dest_folder = self.root_dir / "Receipts_Invoices"
        dest_folder.mkdir(parents=True)
        dest_collision = dest_folder / "invoice_march.pdf"
        dest_collision.write_text("Pre-existing conflicting file")

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertEqual(plan.operations[0].status, OperationStatus.BLOCKED)
        self.assertIn("collision failure", result.error_message)
        self.assertEqual(dest_collision.read_text(), "Pre-existing conflicting file")
        self.assertTrue(self.file1.exists())

    def test_preflight_symlink_appearing_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        self.file1.unlink()
        os.symlink(self.file2, self.file1)

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("is a symlink", result.error_message)

    # ── Mid-Execution Failure Test ────────────────────────────────────

    def test_mid_execution_failure_partial_batch(self):
        """
        Verifies behavior when operations A and B succeed but operation C fails.
        The system must:
        - Preserve an accurate run manifest recording A and B as COMPLETED.
        - Mark the run as PARTIALLY_EXECUTED (never COMMITTED).
        - Expose which operations completed and which failed.
        - Provide enough information for safe rollback in Milestone 4.
        """
        # Create 3 source files
        file_a = self.root_dir / "report_a.txt"
        file_a.write_text("Report A content")

        file_b = self.root_dir / "report_b.txt"
        file_b.write_text("Report B content")

        file_c = self.root_dir / "report_c.txt"
        file_c.write_text("Report C content")

        info_a = FileInfo(
            path=str(file_a), relative_path="report_a.txt", name="report_a.txt",
            extension=".txt", size_bytes=file_a.stat().st_size, mtime=file_a.stat().st_mtime
        )
        info_b = FileInfo(
            path=str(file_b), relative_path="report_b.txt", name="report_b.txt",
            extension=".txt", size_bytes=file_b.stat().st_size, mtime=file_b.stat().st_mtime
        )
        info_c = FileInfo(
            path=str(file_c), relative_path="report_c.txt", name="report_c.txt",
            extension=".txt", size_bytes=file_c.stat().st_size, mtime=file_c.stat().st_mtime
        )

        categorization = [
            {"file_info": info_a, "category": "Documents", "destination_path": str(self.root_dir / "Documents" / "report_a.txt")},
            {"file_info": info_b, "category": "Documents", "destination_path": str(self.root_dir / "Documents" / "report_b.txt")},
            {"file_info": info_c, "category": "Documents", "destination_path": str(self.root_dir / "Documents" / "report_c.txt")},
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Inject a failure on the 3rd shutil.move call using side_effect
        original_move = __import__('shutil').move
        call_count = [0]

        def failing_move(src, dst, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                raise OSError("Simulated disk I/O error on operation C")
            return original_move(src, dst, *args, **kwargs)

        with patch('miniseek.harness.transaction.shutil.move', side_effect=failing_move):
            result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        # 1. Run status must be PARTIALLY_EXECUTED (never COMMITTED)
        self.assertEqual(result.status, PlanStatus.PARTIALLY_EXECUTED)
        self.assertNotEqual(result.status, PlanStatus.COMMITTED)

        # 2. Operations A and B completed, C failed
        self.assertEqual(result.operations_completed, 2)
        self.assertEqual(result.operations_failed, 1)
        self.assertEqual(plan.operations[0].status, OperationStatus.COMPLETED)
        self.assertEqual(plan.operations[1].status, OperationStatus.COMPLETED)
        self.assertEqual(plan.operations[2].status, OperationStatus.FAILED)
        self.assertIn("Simulated disk I/O error", plan.operations[2].error_message)

        # 3. Filesystem: A and B moved, C remains at source
        self.assertTrue((self.root_dir / "Documents" / "report_a.txt").exists())
        self.assertTrue((self.root_dir / "Documents" / "report_b.txt").exists())
        self.assertFalse(file_a.exists())
        self.assertFalse(file_b.exists())
        self.assertTrue(file_c.exists())  # C was NOT moved

        # 4. Manifest exists and contains exactly the 2 completed operations
        self.assertIsNotNone(result.manifest_path)
        with open(result.manifest_path, "r") as f:
            manifest_data = json.load(f)

        self.assertEqual(manifest_data["status"], PlanStatus.PARTIALLY_EXECUTED)
        self.assertEqual(len(manifest_data["operations"]), 2)

        # 5. Manifest contains full undo identity for each completed operation
        for i, op_rec in enumerate(manifest_data["operations"]):
            self.assertEqual(op_rec["status"], "COMPLETED")
            self.assertIn("source_original", op_rec)
            self.assertIn("destination_created", op_rec)
            self.assertIn("sha256", op_rec)
            self.assertIn("size_bytes", op_rec)
            self.assertIn("mtime", op_rec)
            self.assertGreater(op_rec["mtime"], 0)

    # ── Manifest & Undo Identity Tests ────────────────────────────────

    def test_manifest_contains_full_undo_identity(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertIsNotNone(result.manifest_path)
        with open(result.manifest_path, "r") as f:
            manifest_data = json.load(f)

        self.assertEqual(manifest_data["plan_id"], plan.plan_id)
        self.assertEqual(manifest_data["plan_hash"], plan.plan_hash)
        self.assertEqual(len(manifest_data["operations"]), 1)

        op_rec = manifest_data["operations"][0]
        self.assertEqual(op_rec["source_original"], str(self.file1))
        self.assertEqual(op_rec["destination_created"], str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf"))
        self.assertEqual(op_rec["sha256"], plan.operations[0].source_sha256)
        self.assertEqual(op_rec["size_bytes"], self.info1.size_bytes)
        self.assertGreater(op_rec["mtime"], 0)

    def test_incremental_manifest_persistence_survives_partial_run(self):
        """
        Verifies that the manifest file is written incrementally during execution,
        so that if a crash occurs after operation 1, the manifest still records it.
        """
        file_a = self.root_dir / "alpha.txt"
        file_a.write_text("Alpha content here")
        file_b = self.root_dir / "beta.txt"
        file_b.write_text("Beta content here")

        info_a = FileInfo(
            path=str(file_a), relative_path="alpha.txt", name="alpha.txt",
            extension=".txt", size_bytes=file_a.stat().st_size, mtime=file_a.stat().st_mtime
        )
        info_b = FileInfo(
            path=str(file_b), relative_path="beta.txt", name="beta.txt",
            extension=".txt", size_bytes=file_b.stat().st_size, mtime=file_b.stat().st_mtime
        )

        categorization = [
            {"file_info": info_a, "category": "Documents", "destination_path": str(self.root_dir / "Documents" / "alpha.txt")},
            {"file_info": info_b, "category": "Documents", "destination_path": str(self.root_dir / "Documents" / "beta.txt")},
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Simulate crash after first operation by failing the second move
        original_move = __import__('shutil').move
        call_count = [0]

        def crash_on_second(src, dst, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("Simulated crash on second operation")
            return original_move(src, dst, *args, **kwargs)

        with patch('miniseek.harness.transaction.shutil.move', side_effect=crash_on_second):
            result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        # Manifest file must exist and record the first completed operation
        self.assertIsNotNone(result.manifest_path)
        manifest_path = Path(result.manifest_path)
        self.assertTrue(manifest_path.exists())

        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)

        # The manifest should record exactly 1 completed operation
        self.assertEqual(len(manifest_data["operations"]), 1)
        self.assertEqual(manifest_data["operations"][0]["status"], "COMPLETED")
        self.assertEqual(manifest_data["status"], PlanStatus.PARTIALLY_EXECUTED)

    # ── Stale Plan Tests ──────────────────────────────────────────────

    def test_stale_saved_plan_rejected_after_source_deletion(self):
        """
        Verifies: plan saved to disk → source deleted → plan loaded → execution rejected.
        """
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        saved_path = PlanBuilder.save_plan(plan, self.root_dir)

        # Delete source file after plan was saved
        self.file1.unlink()

        # Load the saved plan and attempt execution
        loaded_plan = PlanBuilder.load_plan(saved_path)
        result = self.executor.execute_plan(loaded_plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("no longer exists", result.error_message)

    def test_stale_saved_plan_rejected_after_source_modification(self):
        """
        Verifies: plan saved → source content modified → plan loaded → execution rejected.
        """
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        saved_path = PlanBuilder.save_plan(plan, self.root_dir)

        # Modify the source file after plan was saved
        self.file1.write_text("TAMPERED CONTENT - not the original invoice")

        loaded_plan = PlanBuilder.load_plan(saved_path)
        result = self.executor.execute_plan(loaded_plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        # Should fail on either size or hash mismatch
        self.assertTrue(
            "content hash changed" in result.error_message or
            "size changed" in result.error_message
        )
        # Source file remains untouched
        self.assertTrue(self.file1.exists())

    def test_stale_saved_plan_rejected_after_collision_appears(self):
        """
        Verifies: plan saved → destination collision appears → plan loaded → execution rejected.
        """
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        saved_path = PlanBuilder.save_plan(plan, self.root_dir)

        # Create destination collision after plan was saved
        dest_folder = self.root_dir / "Receipts_Invoices"
        dest_folder.mkdir(parents=True)
        (dest_folder / "invoice_march.pdf").write_text("Collision file")

        loaded_plan = PlanBuilder.load_plan(saved_path)
        result = self.executor.execute_plan(loaded_plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("collision failure", result.error_message)
        self.assertTrue(self.file1.exists())

if __name__ == "__main__":
    unittest.main()
