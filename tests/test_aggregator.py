import unittest
from decimal import Decimal

from miniseek.applications.synthesizer.types import (
    NormalizedTransaction,
    ExtractionStatus
)
from miniseek.applications.synthesizer.aggregator import (
    ExpenseAggregator,
    AggregationSummary
)

class TestAggregator(unittest.TestCase):

    def test_multi_factor_duplicate_detection_across_files(self):
        """Duplicate detected when vendor, date, amount, and currency match across files."""
        tx1 = NormalizedTransaction(
            transaction_id="tx-1", source_file="invoice_march.pdf", vendor="Amazon Web Services",
            date="2026-08-01", amount=Decimal("142.50"), currency="USD",
            category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        tx2 = NormalizedTransaction(
            transaction_id="tx-2", source_file="bank_statement.csv", vendor="Amazon Web Services",
            date="2026-08-01", amount=Decimal("142.50"), currency="USD",
            category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        tx3 = NormalizedTransaction(
            transaction_id="tx-3", source_file="receipt_lunch.txt", vendor="Green Bowl Cafe",
            date="2026-08-01", amount=Decimal("142.50"), currency="USD",  # Same amount, DIFFERENT vendor
            category="Meals_Dining", status=ExtractionStatus.EXTRACTED
        )

        summary = ExpenseAggregator.aggregate([tx1, tx2, tx3], total_documents=3)

        self.assertEqual(summary.total_transactions, 3)
        self.assertEqual(summary.duplicate_candidates_count, 2)
        self.assertEqual(len(summary.duplicate_groups), 1)

        # tx1 and tx2 flagged as duplicate candidates
        self.assertTrue(tx1.is_duplicate_candidate)
        self.assertTrue(tx2.is_duplicate_candidate)
        # tx3 (different vendor) is NOT flagged
        self.assertFalse(tx3.is_duplicate_candidate)

        # Transactions are NOT deleted
        self.assertEqual(len(summary.all_transactions), 3)

    def test_same_vendor_different_dates_not_duplicate(self):
        """Transactions with same vendor and amount on different dates are NOT duplicates."""
        tx1 = NormalizedTransaction(
            transaction_id="1", source_file="doc1", vendor="Uber",
            date="2026-08-01", amount=Decimal("25.00"), currency="USD",
            category="Travel_Transport", status=ExtractionStatus.EXTRACTED
        )
        tx2 = NormalizedTransaction(
            transaction_id="2", source_file="doc2", vendor="Uber",
            date="2026-08-05", amount=Decimal("25.00"), currency="USD",
            category="Travel_Transport", status=ExtractionStatus.EXTRACTED
        )

        summary = ExpenseAggregator.aggregate([tx1, tx2])

        self.assertEqual(summary.duplicate_candidates_count, 0)
        self.assertEqual(len(summary.duplicate_groups), 0)

    def test_multi_currency_summary_and_top_category(self):
        txs = [
            NormalizedTransaction(
                transaction_id="1", source_file="doc", vendor="AWS", date="2026-08-01",
                amount=Decimal("200.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="2", source_file="doc", vendor="Uber", date="2026-08-02",
                amount=Decimal("50.00"), currency="USD", category="Travel_Transport", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="3", source_file="doc", vendor="Hotel", date="2026-08-03",
                amount=Decimal("8000.00"), currency="INR", category="Travel_Transport", status=ExtractionStatus.EXTRACTED
            )
        ]

        summary = ExpenseAggregator.aggregate(txs)

        self.assertIn("USD", summary.currency_summaries)
        self.assertIn("INR", summary.currency_summaries)

        usd_sum = summary.currency_summaries["USD"]
        self.assertEqual(usd_sum.total_amount, Decimal("250.00"))
        self.assertEqual(usd_sum.top_category, "Software_Cloud")

        inr_sum = summary.currency_summaries["INR"]
        self.assertEqual(inr_sum.total_amount, Decimal("8000.00"))
        self.assertEqual(inr_sum.top_category, "Travel_Transport")

    def test_needs_review_transactions_isolated_from_clean_totals(self):
        tx_clean = NormalizedTransaction(
            transaction_id="1", source_file="doc", vendor="AWS", date="2026-08-01",
            amount=Decimal("100.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        tx_review = NormalizedTransaction(
            transaction_id="2", source_file="doc", vendor="Unknown", date=None,
            amount=Decimal("500.00"), currency="USD", category="NEEDS_REVIEW", status=ExtractionStatus.NEEDS_REVIEW
        )

        summary = ExpenseAggregator.aggregate([tx_clean, tx_review])

        self.assertEqual(summary.clean_transactions_count, 1)
        self.assertEqual(summary.needs_review_count, 1)
        # Clean USD total excludes the needs_review transaction
        self.assertEqual(summary.currency_summaries["USD"].total_amount, Decimal("100.00"))

if __name__ == "__main__":
    unittest.main()
