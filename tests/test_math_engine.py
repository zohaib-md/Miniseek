import unittest
from decimal import Decimal

from miniseek.applications.synthesizer.types import (
    RawExtractedTransaction,
    NormalizedTransaction,
    ExtractionStatus
)
from miniseek.applications.synthesizer.math_engine import (
    ExpenseNormalizer,
    DecimalMathEngine
)

class TestMathEngine(unittest.TestCase):

    def test_amount_normalization_standard_us(self):
        dec, curr = ExpenseNormalizer.parse_amount("$1,249.50")
        self.assertEqual(dec, Decimal("1249.50"))
        self.assertEqual(curr, "USD")

    def test_amount_normalization_indian_rupees(self):
        dec, curr = ExpenseNormalizer.parse_amount("₹ 45,200.00")
        self.assertEqual(dec, Decimal("45200.00"))
        self.assertEqual(curr, "INR")

    def test_amount_normalization_european_format(self):
        dec, curr = ExpenseNormalizer.parse_amount("1.249,50 €")
        self.assertEqual(dec, Decimal("1249.50"))
        self.assertEqual(curr, "EUR")

    def test_amount_normalization_empty_or_malformed(self):
        dec, curr = ExpenseNormalizer.parse_amount("N/A")
        self.assertIsNone(dec)

    def test_date_normalization_iso(self):
        norm_date, is_ambig = ExpenseNormalizer.normalize_date("2026-08-14")
        self.assertEqual(norm_date, "2026-08-14")
        self.assertFalse(is_ambig)

    def test_date_normalization_month_name(self):
        norm_date, is_ambig = ExpenseNormalizer.normalize_date("August 14, 2026")
        self.assertEqual(norm_date, "2026-08-14")
        self.assertFalse(is_ambig)

    def test_date_normalization_ambiguous_flags(self):
        # 05/06/2026 (May 6 or June 5)
        norm_date, is_ambig = ExpenseNormalizer.normalize_date("05/06/2026")
        self.assertTrue(is_ambig)

    def test_floating_point_drift_prevention(self):
        """0.1 + 0.2 must equal exactly 0.30 with Decimal."""
        tx1 = NormalizedTransaction(
            transaction_id="1", source_file="doc", vendor="A", date="2026-01-01",
            amount=Decimal("0.10"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        tx2 = NormalizedTransaction(
            transaction_id="2", source_file="doc", vendor="B", date="2026-01-01",
            amount=Decimal("0.20"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        breakdown = DecimalMathEngine.calculate_currency_breakdown([tx1, tx2])

        usd_total = breakdown["USD"]["total_amount"]
        self.assertEqual(usd_total, Decimal("0.30"))
        self.assertIsInstance(usd_total, Decimal)

    def test_multi_currency_isolation(self):
        """USD and INR must be kept in separate currency buckets with exact totals."""
        txs = [
            NormalizedTransaction(
                transaction_id="1", source_file="doc", vendor="AWS", date="2026-08-01",
                amount=Decimal("100.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="2", source_file="doc", vendor="GitHub", date="2026-08-02",
                amount=Decimal("20.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="3", source_file="doc", vendor="Chai Point", date="2026-08-03",
                amount=Decimal("150.00"), currency="INR", category="Meals_Dining", status=ExtractionStatus.EXTRACTED
            )
        ]
        breakdown = DecimalMathEngine.calculate_currency_breakdown(txs)

        self.assertIn("USD", breakdown)
        self.assertIn("INR", breakdown)
        self.assertEqual(breakdown["USD"]["total_amount"], Decimal("120.00"))
        self.assertEqual(breakdown["USD"]["transaction_count"], 2)
        self.assertEqual(breakdown["INR"]["total_amount"], Decimal("150.00"))
        self.assertEqual(breakdown["INR"]["transaction_count"], 1)

    def test_category_subtotals_calculation(self):
        txs = [
            NormalizedTransaction(
                transaction_id="1", source_file="doc", vendor="Uber Eats", date="2026-08-01",
                amount=Decimal("25.00"), currency="USD", category="Meals_Dining", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="2", source_file="doc", vendor="Starbucks", date="2026-08-02",
                amount=Decimal("15.00"), currency="USD", category="Meals_Dining", status=ExtractionStatus.EXTRACTED
            ),
            NormalizedTransaction(
                transaction_id="3", source_file="doc", vendor="AWS", date="2026-08-03",
                amount=Decimal("80.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
            )
        ]
        breakdown = DecimalMathEngine.calculate_currency_breakdown(txs)
        cat_sums = breakdown["USD"]["category_totals"]

        self.assertEqual(cat_sums["Meals_Dining"], Decimal("40.00"))
        self.assertEqual(cat_sums["Software_Cloud"], Decimal("80.00"))
        self.assertEqual(breakdown["USD"]["average_transaction"], Decimal("40.00"))

if __name__ == "__main__":
    unittest.main()
