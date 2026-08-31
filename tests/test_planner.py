import os
import tempfile
import unittest
from pathlib import Path

from miniseek.core.types import FileInfo, ScanResult, PlanStatus
from miniseek.core.security import PathSecurity
from miniseek.applications.janitor.planner import PlanBuilder

class TestPlanBuilder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)

        # Create sample files on disk
        self.file1 = self.root_dir / "invoice.pdf"
        self.file1.write_text("Invoice data 12345")

        self.file2 = self.root_dir / "script.py"
        self.file2.write_text("print('hello world')")

        self.file3 = self.root_dir / "unknown.bin"
        self.file3.write_text("binary content")

        self.info1 = FileInfo(
            path=str(self.file1),
            relative_path="invoice.pdf",
            name="invoice.pdf",
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
        self.info3 = FileInfo(
            path=str(self.file3),
            relative_path="unknown.bin",
            name="unknown.bin",
            extension=".bin",
            size_bytes=self.file3.stat().st_size,
            mtime=self.file3.stat().st_mtime
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_plan_operations_and_needs_review_separation(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice.pdf")
            },
            {
                "file_info": self.info2,
                "category": "Code",
                "destination_path": str(self.root_dir / "Code" / "script.py")
            },
            {
                "file_info": self.info3,
                "category": "NEEDS_REVIEW",
                "destination_path": None
            }
        ]

        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        # Invariant: Operations contain only valid move candidates (2 items)
        self.assertEqual(len(plan.operations), 2)
        op_names = {Path(op.source_path).name for op in plan.operations}
        self.assertEqual(op_names, {"invoice.pdf", "script.py"})

        # Invariant: NEEDS_REVIEW files are strictly in needs_review list (1 item)
        self.assertEqual(len(plan.needs_review), 1)
        self.assertEqual(plan.needs_review[0].relative_path, "unknown.bin")

        # Invariant: Plan has a non-empty cryptographic hash and VALIDATED status
        self.assertTrue(len(plan.plan_hash) == 64)
        self.assertEqual(plan.status, PlanStatus.VALIDATED)

    def test_plan_hash_determinism(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice.pdf")
            }
        ]

        plan1 = PlanBuilder.build_plan(self.root_dir, categorization)
        plan2 = PlanBuilder.build_plan(self.root_dir, categorization)

        # Same operations and structure should yield identical plan hash
        # (ignoring unique plan_id by checking compute_hash on canonical dict)
        plan2.plan_id = plan1.plan_id
        plan2.plan_hash = plan2.compute_hash()
        self.assertEqual(plan1.plan_hash, plan2.plan_hash)

    def test_render_dry_run_preview(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice.pdf")
            },
            {
                "file_info": self.info3,
                "category": "NEEDS_REVIEW",
                "destination_path": None
            }
        ]

        plan = PlanBuilder.build_plan(self.root_dir, categorization)
        preview = PlanBuilder.render_dry_run(plan)

        self.assertIn("MINISEEK DRY-RUN PROPOSAL PREVIEW", preview)
        self.assertIn("invoice.pdf", preview)
        self.assertIn("Receipts_Invoices", preview)
        self.assertIn("NEEDS REVIEW / ABSTAINED", preview)
        self.assertIn("unknown.bin", preview)
        self.assertIn("DRY-RUN ONLY", preview)

    def test_save_and_load_plan_artifact(self):
        categorization = [
            {
                "file_info": self.info1,
                "category": "Receipts_Invoices",
                "destination_path": str(self.root_dir / "Receipts_Invoices" / "invoice.pdf")
            }
        ]
        plan = PlanBuilder.build_plan(self.root_dir, categorization)

        saved_path = PlanBuilder.save_plan(plan, self.root_dir)
        self.assertTrue(saved_path.exists())

        loaded_plan = PlanBuilder.load_plan(saved_path)
        self.assertEqual(loaded_plan.plan_id, plan.plan_id)
        self.assertEqual(loaded_plan.plan_hash, plan.plan_hash)
        self.assertEqual(len(loaded_plan.operations), len(plan.operations))
        self.assertEqual(loaded_plan.operations[0].source_sha256, plan.operations[0].source_sha256)

if __name__ == "__main__":
    unittest.main()
