import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Any

from miniseek.core.security import PathSecurity
from miniseek.core.config import Config
from miniseek.llm import LLMProvider
from miniseek.applications.janitor.categorizer import SemanticCategorizer
from miniseek.evaluation.benchmark import (
    BenchmarkSample,
    BenchmarkRunner,
    BenchmarkMetrics
)

class MockPredictableLLM(LLMProvider):
    """Mock LLM returning deterministic responses mapped by filename or prompt substring."""
    def __init__(self, mapping: Dict[str, str], default_category: str = "Documents"):
        self.mapping = mapping
        self.default_category = default_category
        self.call_count = 0

    def chat(self, messages: List[Dict[str, str]], system: str = "") -> Dict[str, Any]:
        self.call_count += 1
        prompt = messages[-1]["content"]

        category = self.default_category
        for key, cat in self.mapping.items():
            if key in prompt:
                category = cat
                break

        return {
            "content": json.dumps({
                "category": category,
                "confidence": 0.95,
                "evidence_used": ["filename", "extension", "preview"]
            })
        }

class MockFlakyLLM(LLMProvider):
    """Mock LLM that fails on attempt 1 with bad JSON, but succeeds on retry."""
    def __init__(self, target_category: str = "Code"):
        self.target_category = target_category
        self.calls = 0

    def chat(self, messages: List[Dict[str, str]], system: str = "") -> Dict[str, Any]:
        self.calls += 1
        # First call: malformed JSON
        if self.calls % 2 == 1:
            return {"content": "I think this file is Code because it has .py extension."}
        # Second call (retry): valid JSON
        return {
            "content": json.dumps({
                "category": self.target_category,
                "confidence": 0.9,
                "evidence_used": ["extension"]
            })
        }

class TestBenchmarkSuite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = PathSecurity.get_canonical_path(self.temp_dir.name)
        self.dataset_path = Path("/Users/mohammadzohaib/Desktop/Miniseek/evaluation/datasets/organizer/golden_standard.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_dataset_success(self):
        samples = BenchmarkRunner.load_dataset(self.dataset_path)
        self.assertGreater(len(samples), 10)
        self.assertTrue(all(isinstance(s, BenchmarkSample) for s in samples))

        # Verify representation across key categories
        categories = {s.ground_truth_category for s in samples}
        self.assertIn("Documents", categories)
        self.assertIn("Receipts_Invoices", categories)
        self.assertIn("Media_Images", categories)
        self.assertIn("Code", categories)
        self.assertIn("Archives_Data", categories)
        self.assertIn("NEEDS_REVIEW", categories)

    def test_load_dataset_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            BenchmarkRunner.load_dataset(self.root_dir / "nonexistent.json")

    def test_perfect_accuracy_benchmark_evaluation(self):
        """Tests that a model returning ground truth achieves 100% accuracy and safety."""
        samples = BenchmarkRunner.load_dataset(self.dataset_path)

        # Mapping that returns the ground truth category for each filename
        mapping = {s.name: s.ground_truth_category for s in samples}
        llm = MockPredictableLLM(mapping=mapping)
        categorizer = SemanticCategorizer(llm=llm)

        metrics = BenchmarkRunner.evaluate(categorizer, samples, self.root_dir)

        self.assertEqual(metrics.total_samples, len(samples))
        self.assertEqual(metrics.correct_predictions, len(samples))
        self.assertEqual(metrics.semantic_accuracy, 1.0)
        self.assertEqual(metrics.first_pass_validation_rate, 1.0)
        self.assertEqual(metrics.execution_safety_rate, 1.0)
        self.assertEqual(metrics.safety_violations_count, 0)

        # Ensure NEEDS_REVIEW samples produced NO destination path
        for r in metrics.results:
            if r.predicted_category == "NEEDS_REVIEW":
                self.assertIsNone(r.destination_path)
            else:
                self.assertIsNotNone(r.destination_path)
                self.assertTrue(str(r.destination_path).startswith(str(self.root_dir)))

    def test_retry_recovery_metric_tracking(self):
        """Tests that flaky model requiring retry records correct retry recovery metrics."""
        flaky_llm = MockFlakyLLM(target_category="Code")
        categorizer = SemanticCategorizer(llm=flaky_llm)

        sample = BenchmarkSample(
            id="test_01",
            name="script.py",
            extension=".py",
            size_bytes=100,
            preview="print('hello')",
            ground_truth_category="Code"
        )

        metrics = BenchmarkRunner.evaluate(categorizer, [sample], self.root_dir)

        # 0% first pass (failed initially), 100% retry recovery
        self.assertEqual(metrics.first_pass_validation_rate, 0.0)
        self.assertEqual(metrics.retry_recovery_rate, 1.0)
        self.assertEqual(metrics.semantic_accuracy, 1.0)
        self.assertEqual(metrics.results[0].retry_count, 1)

    def test_abstention_precision_calculation(self):
        """Tests abstention precision metrics when model abstains."""
        samples = [
            BenchmarkSample(
                id="s1", name="clear_doc.pdf", extension=".pdf", size_bytes=100,
                preview="doc", ground_truth_category="Documents"
            ),
            BenchmarkSample(
                id="s2", name="ambiguous.dat", extension=".dat", size_bytes=10,
                preview="???", ground_truth_category="NEEDS_REVIEW"
            )
        ]

        # Model correctly abstains on s2, classifies s1
        mapping = {"clear_doc.pdf": "Documents", "ambiguous.dat": "NEEDS_REVIEW"}
        llm = MockPredictableLLM(mapping=mapping)
        categorizer = SemanticCategorizer(llm=llm)

        metrics = BenchmarkRunner.evaluate(categorizer, samples, self.root_dir)

        self.assertEqual(metrics.abstention_count, 1)
        self.assertEqual(metrics.abstention_precision, 1.0)

    def test_render_report_formatting(self):
        samples = BenchmarkRunner.load_dataset(self.dataset_path)[:3]
        mapping = {s.name: s.ground_truth_category for s in samples}
        llm = MockPredictableLLM(mapping=mapping)
        categorizer = SemanticCategorizer(llm=llm)

        metrics = BenchmarkRunner.evaluate(categorizer, samples, self.root_dir)
        report = BenchmarkRunner.render_report(metrics)

        self.assertIn("MINISEEK BENCHMARK REPORT", report)
        self.assertIn("Semantic Accuracy:", report)
        self.assertIn("CATEGORY PERFORMANCE BREAKDOWN", report)
        self.assertIn("SAFETY & HARNESS INVARIANTS VERIFICATION", report)
        self.assertIn("100% ENFORCED", report)

    def test_metrics_serialization(self):
        samples = BenchmarkRunner.load_dataset(self.dataset_path)[:2]
        llm = MockPredictableLLM(mapping={})
        categorizer = SemanticCategorizer(llm=llm)

        metrics = BenchmarkRunner.evaluate(categorizer, samples, self.root_dir)
        m_dict = metrics.to_dict()

        self.assertIn("total_samples", m_dict)
        self.assertIn("semantic_accuracy", m_dict)
        self.assertIn("execution_safety_rate", m_dict)
        self.assertIn("results", m_dict)
        self.assertEqual(len(m_dict["results"]), 2)

if __name__ == "__main__":
    unittest.main()
