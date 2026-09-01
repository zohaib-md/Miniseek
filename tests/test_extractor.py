import json
import unittest
from typing import List, Dict, Any, Optional

from miniseek.llm import LLMProvider
from miniseek.applications.synthesizer.types import ExtractionStatus
from miniseek.applications.synthesizer.ingestion import IngestedDocument, DocumentType
from miniseek.applications.synthesizer.extractor import SemanticExpenseExtractor

class MockExtractorLLM(LLMProvider):
    def __init__(self, responses: List[str]):
        self.responses = list(responses)
        self.call_count = 0

    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> Dict[str, Any]:
        self.call_count += 1
        if self.responses:
            content = self.responses.pop(0)
        else:
            content = "[]"
        return {"content": content}

class TestSemanticExtractor(unittest.TestCase):

    def test_extract_single_receipt_transaction(self):
        llm_response = json.dumps([{
            "vendor": "Apple Store",
            "date": "2026-08-14",
            "amount": "48.60",
            "currency": "USD",
            "category": "Office_Hardware",
            "amount_evidence": "Total Paid: $48.60",
            "confidence": 0.98
        }])
        mock_llm = MockExtractorLLM([llm_response])
        extractor = SemanticExpenseExtractor(llm=mock_llm)

        chunk_text = "Apple Store Receipt\nTotal Paid: $48.60 on Aug 14, 2026"
        txs, telemetry = extractor.extract_from_chunk(chunk_text, source_file="receipt.txt")

        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].vendor, "Apple Store")
        self.assertEqual(txs[0].amount_str, "48.60")
        self.assertEqual(txs[0].category, "Office_Hardware")
        self.assertEqual(telemetry.retry_count, 0)
        self.assertTrue(telemetry.is_valid)
        self.assertEqual(telemetry.transactions_extracted, 1)

    def test_extract_multi_item_chunk(self):
        llm_response = json.dumps([
            {"vendor": "AWS", "date": "2026-08-01", "amount": "142.50", "currency": "USD", "category": "Software_Cloud"},
            {"vendor": "Uber", "date": "2026-08-02", "amount": "24.80", "currency": "USD", "category": "Travel_Transport"}
        ])
        mock_llm = MockExtractorLLM([llm_response])
        extractor = SemanticExpenseExtractor(llm=mock_llm)

        txs, telemetry = extractor.extract_from_chunk("Multi item chunk...", source_file="ledger.csv")

        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].vendor, "AWS")
        self.assertEqual(txs[1].vendor, "Uber")

    def test_retry_on_initial_validation_failure(self):
        mock_llm = MockExtractorLLM([
            "Found transaction for AWS of $142.50",  # Non-JSON
            json.dumps([{"vendor": "AWS", "amount": "142.50", "category": "Software_Cloud"}])  # Valid retry
        ])
        extractor = SemanticExpenseExtractor(llm=mock_llm)

        txs, telemetry = extractor.extract_from_chunk("AWS invoice text", source_file="aws.pdf")

        self.assertEqual(len(txs), 1)
        self.assertEqual(telemetry.retry_count, 1)
        self.assertTrue(telemetry.is_valid)
        self.assertEqual(mock_llm.call_count, 2)

    def test_scanned_pdf_document_abstains_cleanly(self):
        doc = IngestedDocument(
            source_path="/path/to/scan.pdf",
            file_name="scan.pdf",
            extension=".pdf",
            size_bytes=1000,
            doc_type=DocumentType.PDF,
            content_text="[SCANNED PDF]",
            is_scanned_pdf=True
        )
        mock_llm = MockExtractorLLM([])
        extractor = SemanticExpenseExtractor(llm=mock_llm)

        txs, telemetries = extractor.extract_from_document(doc)

        self.assertEqual(len(txs), 0)
        self.assertEqual(len(telemetries), 1)
        self.assertEqual(telemetries[0].status, ExtractionStatus.NEEDS_REVIEW.value)
        self.assertEqual(mock_llm.call_count, 0)  # Never calls LLM for image-only PDF

if __name__ == "__main__":
    unittest.main()
