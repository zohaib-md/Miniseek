import json
import unittest
from pathlib import Path

from miniseek.llm import LLMProvider
from miniseek.applications.synthesizer.extractor import SemanticExpenseExtractor
from miniseek.evaluation.synthesizer_benchmark import (
    SynthesizerBenchmarkRunner,
    SynthesizerBenchmarkMetrics
)

class GoldenDatasetMockLLM(LLMProvider):
    """Mock LLM that maps golden test samples to their exact expected ground truth."""
    def __init__(self, golden_path: Path):
        with open(golden_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)

    def chat(self, messages, system=""):
        prompt = messages[-1]["content"]
        for item in self.dataset:
            # Match item by content chunk snippet
            snippet = item["content_chunk"][:20]
            if snippet in prompt:
                if item["expected_status"] == "UNKNOWN":
                    return {"content": "[]"}
                resp = [{
                    "vendor": item["expected_vendor"],
                    "date": item["expected_date"],
                    "amount": item["expected_amount"],
                    "currency": item["expected_currency"],
                    "category": item["expected_category"],
                    "amount_evidence": f"Total: {item['expected_amount']}",
                    "confidence": 0.95
                }]
                return {"content": json.dumps(resp)}

        return {"content": "[]"}

class TestSynthesizerBenchmark(unittest.TestCase):

    def setUp(self):
        self.dataset_path = Path("/Users/mohammadzohaib/Desktop/Miniseek/evaluation/datasets/synthesizer/golden_expenses.json")

    def test_load_dataset(self):
        samples = SynthesizerBenchmarkRunner.load_dataset(self.dataset_path)
        self.assertGreaterEqual(len(samples), 8)
        self.assertEqual(samples[0].id, "exp_001")

    def test_end_to_end_benchmark_evaluation(self):
        samples = SynthesizerBenchmarkRunner.load_dataset(self.dataset_path)
        mock_llm = GoldenDatasetMockLLM(self.dataset_path)
        extractor = SemanticExpenseExtractor(llm=mock_llm)

        metrics = SynthesizerBenchmarkRunner.evaluate(extractor, samples)

        self.assertEqual(metrics.total_samples, len(samples))
        self.assertEqual(metrics.math_correctness_rate, 1.0)
        self.assertEqual(metrics.security_containment_rate, 1.0)
        self.assertEqual(metrics.first_pass_validation_rate, 1.0)
        self.assertGreater(metrics.field_accuracies["amount_accuracy"], 0.8)

        report = metrics.summary_report
        self.assertIn("MINISEEK EXPENSE SYNTHESIZER BENCHMARK REPORT", report)
        self.assertIn("Exact Decimal Math Accuracy:   100.0%", report)

if __name__ == "__main__":
    unittest.main()
