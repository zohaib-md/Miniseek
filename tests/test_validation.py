import unittest
from miniseek.harness.validation import CategorizationValidator
from miniseek.core.config import DEFAULT_CONFIG

class TestCategorizationValidator(unittest.TestCase):
    def setUp(self):
        self.allowed = DEFAULT_CONFIG.allowed_categories

    def test_valid_json_output_without_reasoning(self):
        raw = '{"category": "Documents", "confidence": 0.95, "evidence_used": ["extension", "preview"]}'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.parsed_data["category"], "Documents")
        self.assertEqual(res.parsed_data["confidence"], 0.95)
        self.assertEqual(res.parsed_data["evidence_used"], ["extension", "preview"])

    def test_valid_minimal_json_category_only(self):
        raw = '{"category": "Code"}'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.parsed_data["category"], "Code")

    def test_valid_markdown_wrapped_json(self):
        raw = """Here is the classification:
```json
{
    "category": "Code",
    "confidence": 0.88
}
```"""
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.parsed_data["category"], "Code")

    def test_safe_syntax_repair_trailing_comma(self):
        raw = '{"category": "Media_Images", "confidence": 0.90, }'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.parsed_data["category"], "Media_Images")

    def test_empty_or_non_json_extraction_failure(self):
        raw = "This is a document file."
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "extraction")

    def test_malformed_json_syntax_error(self):
        raw = '{"category": "Documents", "confidence": 0.95'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "syntax")

    def test_schema_missing_category(self):
        raw = '{"confidence": 0.95, "evidence_used": ["filename"]}'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "schema")
        self.assertIn("Missing required field", res.error_message)

    def test_schema_invalid_confidence_out_of_bounds(self):
        raw = '{"category": "Documents", "confidence": 1.5}'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "schema")
        self.assertIn("must be a number between 0.0 and 1.0", res.error_message)

    def test_semantic_invalid_category(self):
        raw = '{"category": "ArbitraryUserFolder", "confidence": 0.9}'
        res = CategorizationValidator.validate(raw, self.allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "semantic")
        self.assertIn("Invalid category", res.error_message)

    def test_model_abstention_categories_valid(self):
        for abstention in ["UNCATEGORIZED", "NEEDS_REVIEW"]:
            raw = f'{{"category": "{abstention}", "confidence": 0.5}}'
            res = CategorizationValidator.validate(raw, self.allowed)
            self.assertTrue(res.is_valid)
            self.assertEqual(res.parsed_data["category"], abstention)

    def test_semantic_rejection_of_path_syntax_in_category(self):
        # Arbitrary path-like strings fail semantic validation because they are not allowed categories
        malicious_categories = ["../../Documents", "/etc/passwd", "Code/sub"]
        for bad_cat in malicious_categories:
            raw = f'{{"category": "{bad_cat}", "confidence": 0.9}}'
            res = CategorizationValidator.validate(raw, self.allowed)
            self.assertFalse(res.is_valid)
            self.assertEqual(res.error_stage, "semantic")

    def test_safety_validation_catches_forbidden_characters_in_custom_sets(self):
        # If an allowed set contained a category with forbidden characters, safety layer catches it
        unsafe_allowed = ("Documents/Unsafe", "Code")
        raw = '{"category": "Documents/Unsafe"}'
        res = CategorizationValidator.validate(raw, unsafe_allowed)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error_stage, "safety")
        self.assertIn("forbidden character", res.error_message)

if __name__ == "__main__":
    unittest.main()
