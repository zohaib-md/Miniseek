import json
import unittest

from miniseek.applications.synthesizer.types import (
    ALLOWED_EXPENSE_CATEGORIES,
    ExtractionStatus,
    FieldProvenance,
    RawExtractedTransaction
)
from miniseek.applications.synthesizer.validation import (
    TransactionValidator,
    TransactionValidationResult
)

class TestSynthesizerSchema(unittest.TestCase):

    def test_validate_single_valid_transaction(self):
        raw_output = """
        ```json
        {
            "vendor": "Amazon Web Services",
            "date": "2026-08-15",
            "amount": "$142.50",
            "currency": "USD",
            "category": "Software_Cloud",
            "confidence": 0.95
        }
        ```
        """
        res = TransactionValidator.validate(raw_output, source_file="aws_invoice.pdf")

        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.transactions), 1)
        tx = res.transactions[0]
        self.assertEqual(tx.vendor, "Amazon Web Services")
        self.assertEqual(tx.date_str, "2026-08-15")
        self.assertEqual(tx.amount_str, "$142.50")
        self.assertEqual(tx.currency_str, "USD")
        self.assertEqual(tx.category, "Software_Cloud")
        self.assertEqual(tx.confidence, 0.95)
        self.assertEqual(tx.status, ExtractionStatus.EXTRACTED)
        self.assertIn("amount", tx.provenance)
        self.assertEqual(tx.provenance["amount"].source_file, "aws_invoice.pdf")

    def test_validate_multi_transaction_list(self):
        raw_output = json.dumps([
            {"vendor": "Uber", "date": "2026-08-01", "amount": "$24.50", "currency": "USD", "category": "Travel_Transport"},
            {"vendor": "Starbucks", "date": "2026-08-02", "amount": "₹450", "currency": "INR", "category": "Meals_Dining"}
        ])
        res = TransactionValidator.validate(raw_output)

        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.transactions), 2)
        self.assertEqual(res.transactions[0].vendor, "Uber")
        self.assertEqual(res.transactions[1].category, "Meals_Dining")

    def test_syntax_repair_trailing_commas(self):
        raw_output = '{"vendor": "GitHub", "amount": "$21.00", "category": "Software_Cloud",}'
        res = TransactionValidator.validate(raw_output)

        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.transactions), 1)
        self.assertEqual(res.transactions[0].vendor, "GitHub")

    def test_malformed_json_syntax_error_reported(self):
        raw_output = '{"vendor": "GitHub", "amount": '
        res = TransactionValidator.validate(raw_output)

        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "syntax")
        self.assertIn("JSON syntax error", res.error_message)

    def test_missing_vendor_marks_status_partial(self):
        raw_output = '{"date": "2026-08-01", "amount": "100.00", "category": "UNCATEGORIZED"}'
        res = TransactionValidator.validate(raw_output)

        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.transactions), 1)
        self.assertEqual(res.transactions[0].status, ExtractionStatus.PARTIAL)

    def test_invalid_category_maps_to_uncategorized(self):
        raw_output = '{"vendor": "Custom Service", "amount": "50.00", "category": "CryptoSpeculation"}'
        res = TransactionValidator.validate(raw_output)

        self.assertTrue(res.is_valid)
        self.assertEqual(res.transactions[0].category, "UNCATEGORIZED")

    def test_safety_validation_catches_null_bytes(self):
        raw_output = '{"vendor": "Malicious\\u0000Vendor", "amount": "100.00"}'
        res = TransactionValidator.validate(raw_output)

        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "safety")
        self.assertIn("forbidden control characters", res.error_message)

    def test_empty_json_yields_zero_transactions_safely(self):
        raw_output = '[]'
        res = TransactionValidator.validate(raw_output)

        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.transactions), 0)

if __name__ == "__main__":
    unittest.main()
