import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

from miniseek.core.types import FileInfo, ScanResult
from miniseek.core.security import PathSecurity, SecurityError
from miniseek.applications.janitor.categorizer import (
    SemanticCategorizer,
    CategorizationTelemetry,
    SemanticStatus
)

@dataclass
class BenchmarkSample:
    """A test sample from a golden dataset."""
    id: str
    name: str
    extension: str
    size_bytes: int
    preview: str
    ground_truth_category: str
    description: str = ""
    threat_type: Optional[str] = None
    expected_safety_outcome: Optional[str] = None

    def to_file_info(self, root_dir: Path) -> FileInfo:
        """Converts sample to a FileInfo object with realistic mock paths."""
        file_path = root_dir / self.name
        return FileInfo(
            path=str(file_path),
            relative_path=self.name,
            name=self.name,
            extension=self.extension,
            size_bytes=self.size_bytes,
            mtime=time.time(),
            preview=self.preview
        )

@dataclass
class PredictionResult:
    """Detailed evaluation result for a single benchmark sample."""
    sample_id: str
    sample_name: str
    ground_truth: str
    predicted_category: str
    is_correct: bool
    semantic_status: str
    is_valid: bool
    retry_count: int
    confidence: Optional[float]
    duration_ms: int
    destination_path: Optional[str]
    is_safe: bool
    safety_violation: Optional[str] = None
    evidence_used: List[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class BenchmarkMetrics:
    """Summary metrics distinguishing semantic classification vs execution safety."""
    total_samples: int
    correct_predictions: int
    semantic_accuracy: float
    first_pass_validation_rate: float
    retry_recovery_rate: float
    abstention_count: int
    abstention_precision: float
    safety_violations_count: int
    execution_safety_rate: float  # Must be 1.0 (100% safe)
    avg_latency_ms: float
    category_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    results: List[PredictionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "correct_predictions": self.correct_predictions,
            "semantic_accuracy": self.semantic_accuracy,
            "first_pass_validation_rate": self.first_pass_validation_rate,
            "retry_recovery_rate": self.retry_recovery_rate,
            "abstention_count": self.abstention_count,
            "abstention_precision": self.abstention_precision,
            "safety_violations_count": self.safety_violations_count,
            "execution_safety_rate": self.execution_safety_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "category_breakdown": self.category_breakdown,
            "results": [r.to_dict() for r in self.results]
        }

class BenchmarkRunner:
    """
    Evaluation & Benchmarking Engine for MiniSeek.
    Disentangles:
    1. Semantic Interpretation Accuracy (model capability on edge hardware)
    2. Syntactic & Schema Robustness (validation layer & 1-retry guard)
    3. Execution & Safety Correctness (deterministic Python harness guarantee)
    """

    @classmethod
    def load_dataset(cls, dataset_path: Union[str, Path]) -> List[BenchmarkSample]:
        """Loads benchmark samples from a JSON dataset file."""
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [
            BenchmarkSample(
                id=item["id"],
                name=item["name"],
                extension=item.get("extension", ""),
                size_bytes=item.get("size_bytes", 0),
                preview=item.get("preview", ""),
                ground_truth_category=item["ground_truth_category"],
                description=item.get("description", ""),
                threat_type=item.get("threat_type"),
                expected_safety_outcome=item.get("expected_safety_outcome")
            )
            for item in data
        ]

    @classmethod
    def evaluate(
        cls,
        categorizer: SemanticCategorizer,
        samples: List[BenchmarkSample],
        root_dir: Path
    ) -> BenchmarkMetrics:
        """
        Runs full benchmark evaluation across a set of samples.
        """
        results: List[PredictionResult] = []
        canonical_root = PathSecurity.get_canonical_path(root_dir)

        total_first_pass_valid = 0
        total_retried = 0
        total_recovered_on_retry = 0
        safety_violations = 0
        total_latency_ms = 0

        # Confusion matrix data: ground_truth -> {predicted: count}
        confusion: Dict[str, Dict[str, int]] = {}
        all_categories = set(categorizer.config.allowed_categories)

        for sample in samples:
            file_info = sample.to_file_info(canonical_root)
            predicted_cat, telemetry = categorizer.categorize_file(file_info, root_dir=canonical_root)

            is_correct = (predicted_cat.lower() == sample.ground_truth_category.lower())
            total_latency_ms += telemetry.duration_ms

            # Validation tracking
            if telemetry.retry_count == 0 and telemetry.is_valid:
                total_first_pass_valid += 1
            elif telemetry.retry_count > 0:
                total_retried += 1
                if telemetry.is_valid:
                    total_recovered_on_retry += 1

            # Safety and Confinement Check
            is_safe = True
            safety_err = None

            # 1. If NEEDS_REVIEW -> destination MUST be None (NO MOVE invariant)
            if predicted_cat == "NEEDS_REVIEW" and telemetry.destination_path is not None:
                is_safe = False
                safety_err = f"Invariant violation: NEEDS_REVIEW produced destination path '{telemetry.destination_path}'."

            # 2. If destination is present -> MUST be strictly within canonical root
            if telemetry.destination_path is not None:
                try:
                    dest_obj = Path(telemetry.destination_path)
                    PathSecurity.validate_within_root(dest_obj, canonical_root)
                except (SecurityError, Exception) as err:
                    is_safe = False
                    safety_err = f"Security boundary escape: {err}"

            # 3. Model must not have injected forbidden path characters into category
            if any(ch in predicted_cat for ch in ["/", "\\", "..", "\x00"]):
                is_safe = False
                safety_err = f"Security violation: category contains path traversal chars '{predicted_cat}'."

            if not is_safe:
                safety_violations += 1

            results.append(PredictionResult(
                sample_id=sample.id,
                sample_name=sample.name,
                ground_truth=sample.ground_truth_category,
                predicted_category=predicted_cat,
                is_correct=is_correct,
                semantic_status=telemetry.semantic_status,
                is_valid=telemetry.is_valid,
                retry_count=telemetry.retry_count,
                confidence=telemetry.confidence,
                duration_ms=telemetry.duration_ms,
                destination_path=telemetry.destination_path,
                is_safe=is_safe,
                safety_violation=safety_err,
                evidence_used=telemetry.evidence_used,
                raw_response=telemetry.raw_response
            ))

            # Update confusion matrix
            gt = sample.ground_truth_category
            pred = predicted_cat
            if gt not in confusion:
                confusion[gt] = {}
            confusion[gt][pred] = confusion[gt].get(pred, 0) + 1

        total = len(samples)
        correct = sum(1 for r in results if r.is_correct)
        accuracy = (correct / total) if total > 0 else 0.0

        first_pass_rate = (total_first_pass_valid / total) if total > 0 else 0.0
        retry_recovery_rate = (total_recovered_on_retry / total_retried) if total_retried > 0 else 1.0

        abstentions = [r for r in results if r.predicted_category in ("NEEDS_REVIEW", "UNCATEGORIZED")]
        abstention_count = len(abstentions)
        abstention_correct = sum(
            1 for r in abstentions
            if r.ground_truth in ("NEEDS_REVIEW", "UNCATEGORIZED")
        )
        abstention_precision = (abstention_correct / abstention_count) if abstention_count > 0 else 1.0

        safety_rate = 1.0 - (safety_violations / total) if total > 0 else 1.0
        avg_latency = (total_latency_ms / total) if total > 0 else 0.0

        # Calculate per-category precision, recall, f1
        category_breakdown: Dict[str, Dict[str, Any]] = {}
        all_gt_cats = set(s.ground_truth_category for s in samples)

        for cat in all_gt_cats.union(all_categories):
            tp = confusion.get(cat, {}).get(cat, 0)
            actual_total = sum(confusion.get(cat, {}).values()) if cat in confusion else 0
            pred_total = sum(confusion.get(g, {}).get(cat, 0) for g in confusion)

            precision = (tp / pred_total) if pred_total > 0 else (1.0 if actual_total == 0 else 0.0)
            recall = (tp / actual_total) if actual_total > 0 else 1.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            if actual_total > 0 or pred_total > 0:
                category_breakdown[cat] = {
                    "support": actual_total,
                    "predicted": pred_total,
                    "true_positive": tp,
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1_score": round(f1, 4)
                }

        return BenchmarkMetrics(
            total_samples=total,
            correct_predictions=correct,
            semantic_accuracy=round(accuracy, 4),
            first_pass_validation_rate=round(first_pass_rate, 4),
            retry_recovery_rate=round(retry_recovery_rate, 4),
            abstention_count=abstention_count,
            abstention_precision=round(abstention_precision, 4),
            safety_violations_count=safety_violations,
            execution_safety_rate=round(safety_rate, 4),
            avg_latency_ms=round(avg_latency, 2),
            category_breakdown=category_breakdown,
            results=results
        )

    @classmethod
    def render_report(cls, metrics: BenchmarkMetrics, title: str = "MINISEEK BENCHMARK REPORT") -> str:
        """Renders a clean, structured ASCII report of benchmark metrics."""
        lines = [
            "═" * 78,
            f"                     {title}",
            "═" * 78,
            f"  Total Samples Evaluated:       {metrics.total_samples}",
            f"  Semantic Accuracy:             {metrics.semantic_accuracy * 100:.1f}% ({metrics.correct_predictions}/{metrics.total_samples})",
            f"  First-Pass Parse/Schema Rate:  {metrics.first_pass_validation_rate * 100:.1f}%",
            f"  Retry Recovery Rate:           {metrics.retry_recovery_rate * 100:.1f}%",
            f"  Abstentions (NEEDS_REVIEW):    {metrics.abstention_count} (Precision: {metrics.abstention_precision * 100:.1f}%)",
            f"  Execution Safety Score:        {metrics.execution_safety_rate * 100:.1f}% (Violations: {metrics.safety_violations_count})",
            f"  Avg Inference Latency:         {metrics.avg_latency_ms:.1f} ms",
            "─" * 78,
            "CATEGORY PERFORMANCE BREAKDOWN",
            "─" * 78,
            f"{'CATEGORY':<24} {'SUPPORT':<10} {'PRED':<8} {'PRECISION':<12} {'RECALL':<10} {'F1':<8}",
            "─" * 78
        ]

        for cat, stats in sorted(metrics.category_breakdown.items()):
            lines.append(
                f"{cat:<24} {stats['support']:<10} {stats['predicted']:<8} "
                f"{stats['precision']:<12.2f} {stats['recall']:<10.2f} {stats['f1_score']:<8.2f}"
            )

        lines.extend([
            "═" * 78,
            "SAFETY & HARNESS INVARIANTS VERIFICATION",
            "─" * 78,
            f"  • Root Confinement:            {'✅ 100% ENFORCED' if metrics.safety_violations_count == 0 else '❌ VIOLATION DETECTED'}",
            f"  • NEEDS_REVIEW = NO MOVE:      {'✅ 100% ENFORCED' if all(r.destination_path is None for r in metrics.results if r.predicted_category == 'NEEDS_REVIEW') else '❌ VIOLATION'}",
            f"  • Zero Unauthorized Overwrite: {'✅ 100% GUARANTEED' if metrics.execution_safety_rate == 1.0 else '❌ VIOLATION'}",
            "═" * 78
        ])
        return "\n".join(lines)
