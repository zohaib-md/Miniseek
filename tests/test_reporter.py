import unittest
from decimal import Decimal

from miniseek.applications.synthesizer.types import (
    NormalizedTransaction,
    ExtractionStatus,
    FieldProvenance
)
from miniseek.applications.synthesizer.aggregator import ExpenseAggregator
from miniseek.applications.synthesizer.reporter import ExpenseReporter

class TestExpenseReporter(unittest.TestCase):

    def setUp(self):
        self.tx1 = NormalizedTransaction(
            transaction_id="tx-001",
            source_file="aws_invoice.pdf",
            vendor="Amazon Web Services",
            date="2026-08-15",
            amount=Decimal("150.00"),
            currency="USD",
            category="Software_Cloud",
            status=ExtractionStatus.EXTRACTED,
            provenance={"amount": FieldProvenance("150.00", "aws_invoice.pdf", "Total: $150.00")}
        )
        self.tx2 = NormalizedTransaction(
            transaction_id="tx-002",
            source_file="lunch_receipt.txt",
            vendor="Green Bowl Cafe",
            date="2026-08-16",
            amount=Decimal("25.00"),
            currency="USD",
            category="Meals_Dining",
            status=ExtractionStatus.EXTRACTED,
            provenance={"amount": FieldProvenance("25.00", "lunch_receipt.txt", "Total: $25.00")}
        )
        self.tx3 = NormalizedTransaction(
            transaction_id="tx-003",
            source_file="hotel_bill.pdf",
            vendor="Hilton Garden Inn",
            date="2026-08-17",
            amount=Decimal("6500.00"),
            currency="INR",
            category="Travel_Transport",
            status=ExtractionStatus.EXTRACTED,
            provenance={"amount": FieldProvenance("6500.00", "hotel_bill.pdf", "Total: ₹6500")}
        )

    def test_render_markdown_report_structure(self):
        summary = ExpenseAggregator.aggregate([self.tx1, self.tx2, self.tx3], total_documents=3)
        md = ExpenseReporter.render_markdown_report(summary)

        self.assertIn("# 📊 MiniSeek Expense Synthesis Report", md)
        self.assertIn("Total Documents Ingested**: 3", md)
        self.assertIn("USD 175.00", md)
        self.assertIn("INR 6,500.00", md)
        self.assertIn("Software_Cloud", md)
        self.assertIn("Meals_Dining", md)
        self.assertIn("Amazon Web Services", md)

    def test_render_csv_export_format(self):
        summary = ExpenseAggregator.aggregate([self.tx1, self.tx2], total_documents=2)
        csv_out = ExpenseReporter.render_csv_export(summary)

        self.assertIn("Transaction_ID,Date,Vendor,Category,Amount,Currency,Status,Is_Duplicate,Duplicate_Reason,Source_File", csv_out)
        self.assertIn("tx-001,2026-08-15,Amazon Web Services,Software_Cloud,150.00,USD,EXTRACTED,NO,,aws_invoice.pdf", csv_out)

    def test_render_json_audit_format(self):
        summary = ExpenseAggregator.aggregate([self.tx1], total_documents=1)
        json_out = ExpenseReporter.render_json_audit(summary)

        self.assertIn('"total_documents": 1', json_out)
        self.assertIn('"USD"', json_out)
        self.assertIn('"150.00"', json_out)

    def test_duplicate_warning_rendered_in_report(self):
        tx_dup = NormalizedTransaction(
            transaction_id="tx-004",
            source_file="duplicate_aws.pdf",
            vendor="Amazon Web Services",
            date="2026-08-15",
            amount=Decimal("150.00"),
            currency="USD",
            category="Software_Cloud",
            status=ExtractionStatus.EXTRACTED
        )
        summary = ExpenseAggregator.aggregate([self.tx1, tx_dup], total_documents=2)
        md = ExpenseReporter.render_markdown_report(summary)

        self.assertIn("⚠️ Duplicate Candidates for User Review", md)
        self.assertIn("Duplicate Group #1", md)

if __name__ == "__main__":
    unittest.main()
