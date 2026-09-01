import json
import unittest
from pathlib import Path
from decimal import Decimal, InvalidOperation

from miniseek.applications.synthesizer.types import ALLOWED_EXPENSE_CATEGORIES

class TestDatasetIntegrity(unittest.TestCase):

    def setUp(self):
        self.dataset_path = Path("/Users/mohammadzohaib/Desktop/Miniseek/evaluation/datasets/synthesizer/golden_expenses.json")

    def test_golden_dataset_structure_and_types(self):
        self.assertTrue(self.dataset_path.exists(), "Dataset file missing")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 8)

        required_keys = {
            "id", "source_file", "document_type", "content_chunk",
            "expected_vendor", "expected_date", "expected_amount",
            "expected_currency", "expected_category", "expected_status"
        }

        for item in data:
            self.assertTrue(required_keys.issubset(item.keys()), f"Missing keys in {item.get('id')}")

            # Check category validity if present
            cat = item["expected_category"]
            if cat is not None:
                self.assertIn(cat, ALLOWED_EXPENSE_CATEGORIES, f"Invalid category '{cat}' in {item['id']}")

            # Check Decimal parseability if amount is present
            amt_str = item["expected_amount"]
            if amt_str is not None:
                try:
                    dec = Decimal(amt_str)
                    self.assertIsInstance(dec, Decimal)
                except InvalidOperation:
                    self.fail(f"Invalid decimal string '{amt_str}' in {item['id']}")

if __name__ == "__main__":
    unittest.main()
