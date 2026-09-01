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

    def test_amount_normalization_explicit_us_dollars(self):
        dec, curr = ExpenseNormalizer.parse_amount("USD $1,249.50")
        self.assertEqual(dec, Decimal("1249.50"))
        self.assertEqual(curr, "USD")

    def test_amount_normalization_standalone_dollar_is_unknown(self):
        """Bare '$' with no country context must yield UNKNOWN, never silently assuming USD."""
        dec, curr = ExpenseNormalizer.parse_amount("$1,249.50")
        self.assertEqual(dec, Decimal("1249.50"))
        self.assertEqual(curr, "UNKNOWN")

    def test_currency_normalization_conservatism(self):
        """Verify strict currency normalization mapping and unknown dollar behavior."""
        self.assertEqual(ExpenseNormalizer.normalize_currency("₹"), "INR")
        self.assertEqual(ExpenseNormalizer.normalize_currency("INR"), "INR")
        self.assertEqual(ExpenseNormalizer.normalize_currency("Rs."), "INR")
        self.assertEqual(ExpenseNormalizer.normalize_currency("€"), "EUR")
        self.assertEqual(ExpenseNormalizer.normalize_currency("EUR"), "EUR")
        self.assertEqual(ExpenseNormalizer.normalize_currency("£"), "GBP")
        self.assertEqual(ExpenseNormalizer.normalize_currency("GBP"), "GBP")
        self.assertEqual(ExpenseNormalizer.normalize_currency("USD"), "USD")
        self.assertEqual(ExpenseNormalizer.normalize_currency("US$"), "USD")
        self.assertEqual(ExpenseNormalizer.normalize_currency("CAD"), "CAD")
        self.assertEqual(ExpenseNormalizer.normalize_currency("C$"), "CAD")
        self.assertEqual(ExpenseNormalizer.normalize_currency("JPY"), "JPY")
        self.assertEqual(ExpenseNormalizer.normalize_currency("¥"), "JPY")
        # Standalone dollar with no context -> UNKNOWN
        self.assertEqual(ExpenseNormalizer.normalize_currency("$"), "UNKNOWN")

    def test_amount_normalization_indian_rupees(self):
        dec, curr = ExpenseNormalizer.parse_amount("₹ 45,200.00")
        self.assertEqual(dec, Decimal("45200.00"))
        self.assertEqual(curr, "INR")

    def test_amount_normalization_european_format(self):
        dec, curr = ExpenseNormalizer.parse_amount("1.249,50 €")
        self.assertEqual(dec, Decimal("1249.50"))
        self.assertEqual(curr, "EUR")

    def test_amount_normalization_negative_and_refund_formats(self):
        """Supports negative sign, accounting parentheses, and credit memo keywords."""
        # 1. Negative sign: -$35.50
        dec1, _ = ExpenseNormalizer.parse_amount("-$35.50")
        self.assertEqual(dec1, Decimal("-35.50"))

        # 2. Accounting parenthetical notation: ($120.00)
        dec2, _ = ExpenseNormalizer.parse_amount("($120.00)")
        self.assertEqual(dec2, Decimal("-120.00"))

        # 3. Credit memo keyword: 45.00 CR
        dec3, _ = ExpenseNormalizer.parse_amount("45.00 CR")
        self.assertEqual(dec3, Decimal("-45.00"))

        # 4. Refund keyword: Refund $15.25
        dec4, _ = ExpenseNormalizer.parse_amount("Refund $15.25")
        self.assertEqual(dec4, Decimal("-15.25"))

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

    def test_unreadable_missing_amount_is_none_and_excluded_from_arithmetic(self):
        """Unreadable/missing amount must become amount=None, NEEDS_REVIEW, and be excluded from math."""
        raw_tx = RawExtractedTransaction(
            vendor="Office Depot",
            date_str="2026-08-22",
            amount_str=None,  # Unreadable / torn amount
            currency_str="USD",
            category="Office_Hardware"
        )
        norm_tx = ExpenseNormalizer.normalize_transaction(raw_tx, source_file="torn.txt")

        self.assertIsNone(norm_tx.amount)
        self.assertEqual(norm_tx.status, ExtractionStatus.NEEDS_REVIEW)

        # In arithmetic, tx with amount=None must be excluded from totals
        clean_tx = NormalizedTransaction(
            transaction_id="1", source_file="doc", vendor="AWS", date="2026-08-01",
            amount=Decimal("100.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        breakdown = DecimalMathEngine.calculate_currency_breakdown([clean_tx, norm_tx])

        # Total is $100.00, transaction count is 1 (excluding None)
        self.assertEqual(breakdown["USD"]["total_amount"], Decimal("100.00"))
        self.assertEqual(breakdown["USD"]["transaction_count"], 1)

    def test_legitimate_zero_dollar_amount_is_decimal_zero_and_included(self):
        """An explicit $0.00 amount (e.g. promotional item, free trial) is Decimal('0.00') and distinct from None."""
        raw_tx = RawExtractedTransaction(
            vendor="Free Trial SaaS",
            date_str="2026-08-01",
            amount_str="$0.00",
            currency_str="USD",
            category="Software_Cloud"
        )
        norm_tx = ExpenseNormalizer.normalize_transaction(raw_tx, source_file="promo.txt")

        self.assertIsNotNone(norm_tx.amount)
        self.assertEqual(norm_tx.amount, Decimal("0.00"))
        self.assertEqual(norm_tx.status, ExtractionStatus.EXTRACTED)

        # In arithmetic, $0.00 is a valid transaction and contributes to count
        clean_tx = NormalizedTransaction(
            transaction_id="1", source_file="doc", vendor="AWS", date="2026-08-01",
            amount=Decimal("100.00"), currency="USD", category="Software_Cloud", status=ExtractionStatus.EXTRACTED
        )
        breakdown = DecimalMathEngine.calculate_currency_breakdown([clean_tx, norm_tx])

        # Total is $100.00, count is 2, average is (100.00 / 2) = $50.00
        self.assertEqual(breakdown["USD"]["total_amount"], Decimal("100.00"))
        self.assertEqual(breakdown["USD"]["transaction_count"], 2)
        self.assertEqual(breakdown["USD"]["average_transaction"], Decimal("50.00"))

if __name__ == "__main__":
    unittest.main()
