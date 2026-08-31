import os
import tempfile
import unittest
from pathlib import Path

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

        # Verification of execution result
        self.assertEqual(result.status, PlanStatus.COMMITTED)
        self.assertEqual(result.operations_completed, 1)
        self.assertEqual(result.operations_failed, 0)
        self.assertEqual(plan.operations[0].status, OperationStatus.COMPLETED)

        # Verification on filesystem
        self.assertFalse(self.file1.exists())
        dest_file = self.root_dir / "Receipts_Invoices" / "invoice_march.pdf"
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "Invoice data: $500 to Acme Corp")

        # Verification of run manifest
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

        # Both files moved to their respective folders
        self.assertTrue((self.root_dir / "Receipts_Invoices" / "invoice_march.pdf").exists())
        self.assertTrue((self.root_dir / "Code" / "script.py").exists())
        self.assertFalse(self.file1.exists())
        self.assertFalse(self.file2.exists())

    def test_preflight_plan_hash_mismatch_aborts(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Tamper with the plan hash to simulate modified / stale plan
        plan.plan_hash = "0" * 64

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        # Execution aborted with 0 modifications
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

        # Delete source file before execution
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

        # Modify source file content after plan creation (same size, different bytes)
        self.file1.write_text("Invoice data: $999 to Acme Corp")

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        # Pre-flight SHA-256 integrity check catches the modification
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

        # Pre-create the destination file to trigger collision
        dest_folder = self.root_dir / "Receipts_Invoices"
        dest_folder.mkdir(parents=True)
        dest_collision = dest_folder / "invoice_march.pdf"
        dest_collision.write_text("Pre-existing conflicting file")

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        # Conservative collision handling: aborts execution, destination not overwritten
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

        # Replace source with a symlink before execution
        self.file1.unlink()
        os.symlink(self.file2, self.file1)

        result = self.executor.execute_plan(plan, base_history_dir=self.root_dir)

        self.assertEqual(result.status, PlanStatus.FAILED)
        self.assertEqual(result.operations_completed, 0)
        self.assertIn("is a symlink", result.error_message)

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
        import json
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

if __name__ == "__main__":
    unittest.main()
