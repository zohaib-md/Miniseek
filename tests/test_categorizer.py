import unittest
from pathlib import Path
from typing import List, Dict, Any, Optional

from miniseek.core.types import FileInfo
from miniseek.core.config import DEFAULT_CONFIG
from miniseek.core.security import PathSecurity
from miniseek.llm import LLMProvider
from miniseek.applications.janitor.categorizer import SemanticCategorizer, SemanticStatus

class MockLLM(LLMProvider):
    """Configurable mock LLM for deterministic testing of categorizer behaviors."""
    def __init__(self, responses: List[str]):
        self.responses = list(responses)
        self.call_count = 0
        self.call_history: List[List[Dict[str, str]]] = []

    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> Dict[str, Any]:
        self.call_count += 1
        self.call_history.append(messages)
        if self.responses:
            content = self.responses.pop(0)
        else:
            content = '{"category": "UNCATEGORIZED", "confidence": 0.5}'
        return {"content": content}

class TestSemanticCategorizer(unittest.TestCase):
    def setUp(self):
        # Resolve canonical root path to handle OS symlinks (e.g. macOS /tmp -> /private/tmp)
        self.root_dir = PathSecurity.get_canonical_path("/tmp/test_workspace")
        self.sample_file = FileInfo(
            path=str(self.root_dir / "invoice_march.pdf"),
            relative_path="invoice_march.pdf",
            name="invoice_march.pdf",
            extension=".pdf",
            size_bytes=1048576,
            mtime=1700000000.0,
            preview="(PDF Binary File)"
        )

    def test_successful_categorization_and_telemetry(self):
        mock_llm = MockLLM(['{"category": "Receipts_Invoices", "confidence": 0.95, "evidence_used": ["filename", "extension"]}'])
        categorizer = SemanticCategorizer(llm=mock_llm)

        category, telemetry = categorizer.categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(category, "Receipts_Invoices")
        self.assertEqual(telemetry.semantic_status, SemanticStatus.CLASSIFIED)
        self.assertTrue(telemetry.is_valid)
        self.assertEqual(telemetry.retry_count, 0)
        self.assertEqual(telemetry.confidence, 0.95)
        self.assertEqual(telemetry.evidence_used, ["filename", "extension"])
        self.assertEqual(telemetry.model_name, DEFAULT_CONFIG.model_name)
        self.assertEqual(telemetry.runtime, "ollama")
        self.assertEqual(telemetry.prompt_version, SemanticCategorizer.PROMPT_VERSION)
        self.assertEqual(telemetry.destination_path, str(self.root_dir / "Receipts_Invoices" / "invoice_march.pdf"))

    def test_needs_review_produces_no_move_proposal(self):
        mock_llm = MockLLM(['{"category": "NEEDS_REVIEW", "confidence": 0.3}'])
        categorizer = SemanticCategorizer(llm=mock_llm)

        category, telemetry = categorizer.categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(category, "NEEDS_REVIEW")
        self.assertEqual(telemetry.semantic_status, SemanticStatus.NEEDS_REVIEW)
        self.assertTrue(telemetry.is_valid)
        # Invariant 1: NEEDS_REVIEW yields NO MOVE (destination_path is None)
        self.assertIsNone(telemetry.destination_path)
        self.assertIsNone(SemanticCategorizer.get_destination_path(self.root_dir, self.sample_file.name, "NEEDS_REVIEW"))

    def test_uncategorized_and_needs_review_handled_differently(self):
        # UNCATEGORIZED is eligible for destination move; NEEDS_REVIEW is NO MOVE
        dest_uncat = SemanticCategorizer.get_destination_path(self.root_dir, "notes.txt", "UNCATEGORIZED")
        self.assertEqual(dest_uncat, self.root_dir / "UNCATEGORIZED" / "notes.txt")

        dest_review = SemanticCategorizer.get_destination_path(self.root_dir, "notes.txt", "NEEDS_REVIEW")
        self.assertIsNone(dest_review)

    def test_model_cannot_supply_arbitrary_destination_path(self):
        # Even if model injects a malicious or arbitrary destination field, Python ignores it completely
        malicious_response = (
            '{"category": "Documents", "destination": "/etc/shadow", "path": "../../root", "folder": "custom"}'
        )
        mock_llm = MockLLM([malicious_response])
        categorizer = SemanticCategorizer(llm=mock_llm)

        category, telemetry = categorizer.categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(category, "Documents")
        # Invariant 4: Destination is strictly derived by Python: root / category / filename
        self.assertEqual(telemetry.destination_path, str(self.root_dir / "Documents" / "invoice_march.pdf"))
        self.assertNotIn("etc", telemetry.destination_path)
        self.assertNotIn("..", telemetry.destination_path)

    def test_validation_failure_then_successful_retry(self):
        mock_llm = MockLLM([
            'This is a receipt',  # Extraction failure
            '{"category": "Receipts_Invoices", "confidence": 0.90}'
        ])
        categorizer = SemanticCategorizer(llm=mock_llm)

        category, telemetry = categorizer.categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(category, "Receipts_Invoices")
        self.assertTrue(telemetry.is_valid)
        self.assertEqual(telemetry.retry_count, 1)
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(telemetry.semantic_status, SemanticStatus.CLASSIFIED)

    def test_validation_failure_exhausts_retries_falls_back_to_needs_review(self):
        mock_llm = MockLLM([
            'Invalid output 1',
            '{"category": "InvalidCategory"}'  # Semantic failure on retry
        ])
        categorizer = SemanticCategorizer(llm=mock_llm)

        category, telemetry = categorizer.categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(category, "NEEDS_REVIEW")
        self.assertFalse(telemetry.is_valid)
        self.assertEqual(telemetry.semantic_status, SemanticStatus.INVALID)
        self.assertIsNone(telemetry.destination_path)
        self.assertEqual(telemetry.retry_count, 1)

    def test_idempotency_and_reproducibility(self):
        # Identical inputs and mock responses produce identical telemetry & output
        response = '{"category": "Code", "confidence": 0.92, "evidence_used": ["extension"]}'
        mock_llm1 = MockLLM([response])
        mock_llm2 = MockLLM([response])

        cat1, tel1 = SemanticCategorizer(llm=mock_llm1).categorize_file(self.sample_file, root_dir=self.root_dir)
        cat2, tel2 = SemanticCategorizer(llm=mock_llm2).categorize_file(self.sample_file, root_dir=self.root_dir)

        self.assertEqual(cat1, cat2)
        self.assertEqual(tel1.semantic_status, tel2.semantic_status)
        self.assertEqual(tel1.destination_path, tel2.destination_path)
        self.assertEqual(tel1.confidence, tel2.confidence)

if __name__ == "__main__":
    unittest.main()
