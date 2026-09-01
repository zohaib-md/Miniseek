import os
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from miniseek.core.security import PathSecurity
from miniseek.applications.synthesizer.ingestion import (
    DocumentIngestionEngine,
    IngestedDocument,
    DocumentType
)

class TestDocumentIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ingest_csv_with_header(self):
        csv_file = self.root_dir / "expenses_august.csv"
        csv_content = (
            "Date,Vendor,Amount,Category\n"
            "2026-08-01,AWS Cloud,$142.50,Hosting\n"
            "2026-08-05,Uber Eats,$24.80,Meals\n"
            "2026-08-10,GitHub,$21.00,Software\n"
        )
        csv_file.write_text(csv_content)

        doc = DocumentIngestionEngine.ingest_file(csv_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.CSV)
        self.assertEqual(doc.file_name, "expenses_august.csv")
        self.assertIn("CSV Header: Date, Vendor, Amount, Category", doc.content_text)
        self.assertIn("Row 1: Date: 2026-08-01, Vendor: AWS Cloud, Amount: $142.50, Category: Hosting", doc.content_text)
        self.assertEqual(doc.metadata.get("row_count"), 3)
        self.assertGreater(len(doc.bounded_chunks), 0)

    def test_ingest_json_array(self):
        json_file = self.root_dir / "bank_export.json"
        data = [
            {"date": "2026-08-01", "merchant": "Apple Store", "total": 129.00},
            {"date": "2026-08-03", "merchant": "Starbucks", "total": 5.50}
        ]
        json_file.write_text(json.dumps(data))

        doc = DocumentIngestionEngine.ingest_file(json_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.JSON)
        self.assertIn("Apple Store", doc.content_text)
        self.assertEqual(doc.metadata.get("item_count"), 2)

    def test_ingest_plain_text_receipt(self):
        txt_file = self.root_dir / "hardware_receipt.txt"
        content = (
            "==============================\n"
            "       ACME ELECTRONICS       \n"
            "==============================\n"
            "Date: Aug 14, 2026\n"
            "Item: USB-C Hub Multiport\n"
            "Subtotal: $45.00\n"
            "Tax (8%): $3.60\n"
            "Total Paid: $48.60\n"
            "Payment: Visa ending in 4019\n"
        )
        txt_file.write_text(content)

        doc = DocumentIngestionEngine.ingest_file(txt_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.TEXT)
        self.assertEqual(doc.content_text, content.strip())
        self.assertEqual(len(doc.bounded_chunks), 1)

    def test_ingest_markdown_table(self):
        md_file = self.root_dir / "trip_expenses.md"
        content = (
            "# Travel Expenses - DevConf 2026\n\n"
            "| Date | Description | Amount | Currency |\n"
            "|---|---|---|---|\n"
            "| 2026-08-10 | Flight Ticket | 450.00 | USD |\n"
            "| 2026-08-11 | Hotel Stay | 320.00 | USD |\n"
        )
        md_file.write_text(content)

        doc = DocumentIngestionEngine.ingest_file(md_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.MARKDOWN)
        self.assertIn("Flight Ticket", doc.content_text)

    def test_ingest_native_text_pdf_stream(self):
        """Tests pure-Python PDF extraction of uncompressed and compressed streams."""
        pdf_file = self.root_dir / "invoice.pdf"

        # Build a minimal valid PDF byte structure containing a text stream
        raw_stream_text = b"BT /F1 12 Tf (Invoice Number: INV-2026-001) Tj (Total: $1250.00) Tj ET"
        compressed_stream = zlib.compress(raw_stream_text)

        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length " + str(len(compressed_stream)).encode() + b" /Filter /FlateDecode >>\n"
            b"stream\n" + compressed_stream + b"\nendstream\n"
            b"endobj\n"
            b"xref\n0 5\n0000000000 65535 f \n"
            b"trailer << /Size 5 /Root 1 0 R >>\n"
            b"startxref\n300\n%%EOF\n"
        )
        pdf_file.write_bytes(pdf_bytes)

        doc = DocumentIngestionEngine.ingest_file(pdf_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.PDF)
        self.assertFalse(doc.is_scanned_pdf)
        self.assertIn("Invoice Number: INV-2026-001", doc.content_text)
        self.assertIn("Total: $1250.00", doc.content_text)

    def test_ingest_scanned_image_only_pdf_flags_scanned(self):
        """Tests that an image-only PDF without text streams is safely flagged."""
        pdf_file = self.root_dir / "scanned_receipt.pdf"
        # PDF containing only image XObject and no text streams
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /XObject << /Im1 4 0 R >> >> >> endobj\n"
            b"4 0 obj << /Type /XObject /Subtype /Image /Width 100 /Height 100 /BitsPerComponent 8 >>\n"
            b"stream\n" + b"\x00" * 100 + b"\nendstream\nendobj\n"
            b"%%EOF\n"
        )
        pdf_file.write_bytes(pdf_bytes)

        doc = DocumentIngestionEngine.ingest_file(pdf_file, root_dir=self.root_dir)

        self.assertEqual(doc.doc_type, DocumentType.PDF)
        self.assertTrue(doc.is_scanned_pdf)
        self.assertIn("SCANNED / IMAGE-ONLY PDF", doc.content_text)

    def test_large_document_bounded_chunking(self):
        """Verifies that large files are chunked into bounded blocks respecting token budget."""
        large_txt = self.root_dir / "large_ledger.txt"
        lines = [f"Transaction #{i}: Merchant-{i} on 2026-08-01 Amount: ${i*10}.00 Category: General" for i in range(100)]
        large_txt.write_text("\n".join(lines))

        doc = DocumentIngestionEngine.ingest_file(large_txt, root_dir=self.root_dir, max_chunk_chars=500)

        self.assertGreater(len(doc.bounded_chunks), 5)
        for chunk in doc.bounded_chunks:
            # Each chunk is bounded
            self.assertLessEqual(len(chunk), 600)

    def test_path_traversal_escape_rejected(self):
        """Ingesting files that attempt path escape outside root is blocked."""
        outside_dir = tempfile.TemporaryDirectory()
        outside_file = Path(outside_dir.name) / "secret.csv"
        outside_file.write_text("Date,Vendor,Amount\n2026-01-01,Secret,$999")

        doc = DocumentIngestionEngine.ingest_file(outside_file, root_dir=self.root_dir)

        self.assertIsNotNone(doc.error_message)
        self.assertIn("Security violation", doc.error_message)
        self.assertEqual(doc.content_text, "")

        outside_dir.cleanup()

    def test_missing_file_handled_gracefully(self):
        missing = self.root_dir / "does_not_exist.txt"
        doc = DocumentIngestionEngine.ingest_file(missing, root_dir=self.root_dir)

        self.assertIsNotNone(doc.error_message)
        self.assertIn("File not found", doc.error_message)

if __name__ == "__main__":
    unittest.main()
