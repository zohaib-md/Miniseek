import os
import sys
import re
import json
import time
import resource
import urllib.request
import urllib.error
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

# Add repository root to pythonpath
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from miniseek.llm import LLMProvider, OllamaProvider
from miniseek.applications.synthesizer.types import (
    RawExtractedTransaction,
    NormalizedTransaction,
    ExtractionStatus
)
from miniseek.applications.synthesizer.extractor import SemanticExpenseExtractor
from miniseek.applications.synthesizer.math_engine import ExpenseNormalizer

TARGET_DOC_IDS = [
    "doc_b03",  # Single receipt (apple_adapter.txt) - Control
    "doc_b07",  # AWS monthly invoice (5 cloud charges)
    "doc_b08",  # Oberoi hotel folio (room + dining + tax)
    "doc_b10",  # Apex consulting invoice (T&M lines + reimbursable expenses)
    "doc_b11",  # Corporate card ledger CSV (10 distinct rows)
    "doc_b14",  # Quarterly expense summary (27 distinct line items)
    "doc_b17",  # Multi-vendor employee expense report (15 items)
]

def get_peak_memory_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return round(usage.ru_maxrss / (1024 * 1024), 2)
    return round(usage.ru_maxrss / 1024, 2)

class GranularityOllamaProvider(LLMProvider):
    """
    Subclass providing explicit input/output token counts and latency metrics.
    Includes robust 180s timeout and fresh-request retry guard.
    """
    def __init__(self, model_name: str = "qwen2.5:1.5b", host: str = "http://127.0.0.1:11434", timeout: int = 180):
        self.model_name = model_name
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.recent_calls: List[Dict[str, Any]] = []

    def get_and_clear_recent_calls(self) -> List[Dict[str, Any]]:
        calls = list(self.recent_calls)
        self.recent_calls.clear()
        return calls

    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.host}/api/chat"
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": payload_messages,
            "stream": False,
            "format": "json"
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res = json.loads(response.read().decode("utf-8"))
                metric_res = {
                    "content": res.get("message", {}).get("content", ""),
                    "model": res.get("model"),
                    "total_duration_ms": res.get("total_duration", 0) // 1_000_000,
                    "prompt_eval_count": res.get("prompt_eval_count", 0),
                    "prompt_eval_duration_ms": res.get("prompt_eval_duration", 0) // 1_000_000,
                    "eval_count": res.get("eval_count", 0),
                    "eval_duration_ms": res.get("eval_duration", 0) // 1_000_000
                }
                self.recent_calls.append(metric_res)
                return metric_res
        except Exception as e:
            print(f"\n[GranularityOllamaProvider] Request retry triggered ({e})...", flush=True)
            req_retry = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req_retry, timeout=240) as response:
                res = json.loads(response.read().decode("utf-8"))
                metric_res = {
                    "content": res.get("message", {}).get("content", ""),
                    "model": res.get("model"),
                    "total_duration_ms": res.get("total_duration", 0) // 1_000_000,
                    "prompt_eval_count": res.get("prompt_eval_count", 0),
                    "prompt_eval_duration_ms": res.get("prompt_eval_duration", 0) // 1_000_000,
                    "eval_count": res.get("eval_count", 0),
                    "eval_duration_ms": res.get("eval_duration", 0) // 1_000_000
                }
                self.recent_calls.append(metric_res)
                return metric_res

class EXP001cRunner:
    """
    Experimental diagnostic runner comparing:
    - Condition A: Whole-Chunk Single-Shot (Current Mechanism C)
    - Condition B: Deterministic Pre-Segmentation (Item/Row-Level Decomposition)
    """

    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path
        with open(dataset_path, "r", encoding="utf-8") as f:
            full_corpus = json.load(f)

        self.corpus = [d for d in full_corpus if d["id"] in TARGET_DOC_IDS]
        self.model_config = {
            "model_name": "qwen2.5:1.5b",
            "runtime": "Ollama (HTTP API)",
            "temperature": 0.0,
            "top_p": 1.0
        }
        self.llm = GranularityOllamaProvider(model_name="qwen2.5:1.5b", host="http://127.0.0.1:11434", timeout=180)
        self.extractor = SemanticExpenseExtractor(llm=self.llm)

    @classmethod
    def pre_segment(cls, doc: Dict[str, Any]) -> List[str]:
        """
        Deterministic Python pre-segmentation identifying natural structured rows/items.
        """
        content = doc["content"]
        doc_type = doc.get("document_type", "TEXT")
        file_name = doc.get("document_name", "")

        # 1. CSV documents: row-by-row with header
        if doc_type == "CSV" or file_name.endswith(".csv"):
            lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
            if not lines:
                return []
            header = lines[0]
            return [f"{header}\n{line}" for line in lines[1:]]

        # 2. Sectioned / Itemized reports (e.g. Item 01:, Item 02:)
        if "Item 01:" in content or "Item 1:" in content:
            parts = re.split(r"(?=(?:Item\s+\d+:))", content)
            segments = [p.strip() for p in parts if p.strip() and ("Item" in p and ("Amount:" in p or "USD" in p or "INR" in p))]
            if segments:
                return segments

        # 3. Quarterly ledger / date-bullet lists (e.g. Jul-01 ... $88.40)
        date_line_pattern = re.compile(r"^[A-Z][a-z]{2}-\d{2}\s+.*[\$€₹\d]", re.MULTILINE)
        matches = list(date_line_pattern.finditer(content))
        if len(matches) >= 3:
            return [m.group(0).strip() for m in matches]

        # 4. Fallback for single-item documents: single segment
        return [content]

    def evaluate_transactions(
        self,
        expected_txs: List[Dict[str, Any]],
        extracted_txs: List[NormalizedTransaction]
    ) -> Tuple[int, int, float, float, str]:
        """
        Matches extracted transactions against expected ground truth.
        Returns:
        (matched_count, extracted_count, recall, precision, classification)
        """
        if not expected_txs:
            if not extracted_txs:
                return 0, 0, 1.0, 1.0, "FULLY_CORRECT"
            else:
                return 0, len(extracted_txs), 0.0, 0.0, "INCORRECT"

        if not extracted_txs:
            return 0, 0, 0.0, 0.0, "INCORRECT"

        matched_expected_indices = set()
        matched_extracted_indices = set()

        for exp_idx, exp in enumerate(expected_txs):
            for ext_idx, ext in enumerate(extracted_txs):
                if ext_idx in matched_extracted_indices:
                    continue

                # Vendor match (substring)
                vendor_ok = False
                if exp.get("vendor") and ext.vendor:
                    v_exp = exp["vendor"].lower().strip()
                    v_ext = ext.vendor.lower().strip()
                    if v_exp in v_ext or v_ext in v_exp:
                        vendor_ok = True

                # Amount match (strict Decimal)
                amount_ok = False
                if exp.get("amount") is not None and ext.amount is not None:
                    try:
                        if ext.amount == Decimal(exp["amount"]):
                            amount_ok = True
                    except Exception:
                        amount_ok = False
                elif exp.get("amount") is None and ext.amount is None:
                    amount_ok = True

                if vendor_ok and amount_ok:
                    matched_expected_indices.add(exp_idx)
                    matched_extracted_indices.add(ext_idx)
                    break

        matched_count = len(matched_expected_indices)
        extracted_count = len(extracted_txs)
        expected_count = len(expected_txs)

        recall = round(matched_count / max(1, expected_count), 4)
        precision = round(matched_count / max(1, extracted_count), 4)

        if matched_count == expected_count and extracted_count == expected_count:
            cls = "FULLY_CORRECT"
        elif matched_count > 0:
            cls = "PARTIALLY_CORRECT"
        else:
            cls = "INCORRECT"

        return matched_count, extracted_count, recall, precision, cls

    def run_diagnostic(self, checkpoint_file: Optional[Path] = None) -> Dict[str, Any]:
        """Runs comparative benchmark across Condition A and Condition B."""
        print("=" * 78)
        print("  STARTING EXP-001c: EXTRACTION GRANULARITY DIAGNOSTIC")
        print(f"  Model: {self.model_config['model_name']} | Target Documents: {len(self.corpus)}")
        print("  Comparing: Condition A (Whole-Chunk Single-Shot) vs Condition B (Pre-Segmented)")
        print("=" * 78)

        raw_results: List[Dict[str, Any]] = []

        conditions = [
            ("Condition_A_Whole_Chunk", False),
            ("Condition_B_Pre_Segmented", True)
        ]

        for rep in [1, 2]:
            print(f"\n▶ Starting Repetition {rep}/2")

            for cond_name, use_pre_segment in conditions:
                print(f"  • Running {cond_name} ...", end="", flush=True)
                t_start_cond = time.time()

                for doc in self.corpus:
                    doc_id = doc["id"]
                    doc_name = doc["document_name"]
                    expected_txs = doc.get("expected_transactions", [])
                    expected_count = len(expected_txs)

                    if use_pre_segment:
                        segments = self.pre_segment(doc)
                    else:
                        segments = [doc["content"]]

                    doc_start_time = time.time()
                    self.llm.get_and_clear_recent_calls()
                    extracted_raw: List[RawExtractedTransaction] = []
                    retries_sum = 0

                    for seg_idx, seg in enumerate(segments):
                        try:
                            txs, tel = self.extractor.extract_from_chunk(
                                chunk_text=seg,
                                source_file=doc_name,
                                chunk_index=seg_idx
                            )
                        except Exception as e:
                            print(f"\n[Warning] {doc_id} segment {seg_idx} error: {e}", flush=True)
                            txs = []
                            tel = None

                        extracted_raw.extend(txs)
                        if tel:
                            retries_sum += tel.retry_count

                    doc_total_latency_ms = int((time.time() - doc_start_time) * 1000)
                    calls = self.llm.get_and_clear_recent_calls()
                    input_tokens = sum(c.get("prompt_eval_count", 0) for c in calls)
                    input_processing_ms = sum(c.get("prompt_eval_duration_ms", 0) for c in calls)
                    output_tokens = sum(c.get("eval_count", 0) for c in calls)
                    generation_ms = sum(c.get("eval_duration_ms", 0) for c in calls)

                    # Normalize extracted transactions
                    normalized_txs = [
                        ExpenseNormalizer.normalize_transaction(t, source_file=doc_name)
                        for t in extracted_raw
                    ]

                    matched_count, extracted_count, recall, precision, doc_cls = self.evaluate_transactions(
                        expected_txs, normalized_txs
                    )

                    record = {
                        "repetition": rep,
                        "condition": cond_name,
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "segments_count": len(segments),
                        "model_calls": len(segments) + retries_sum,
                        "retries_count": retries_sum,
                        "transactions_expected": expected_count,
                        "transactions_extracted": extracted_count,
                        "transactions_matched": matched_count,
                        "transaction_recall": recall,
                        "transaction_precision": precision,
                        "document_classification": doc_cls,
                        "input_tokens": input_tokens,
                        "input_processing_ms": input_processing_ms,
                        "output_tokens": output_tokens,
                        "generation_time_ms": generation_ms,
                        "total_document_latency_ms": doc_total_latency_ms,
                        "peak_memory_mb": get_peak_memory_mb()
                    }
                    raw_results.append(record)
                    print(f" [{doc_id}:rec={int(recall*100)}%]", end="", flush=True)

                print(f" -> Complete ({int(time.time() - t_start_cond)}s)")

                if checkpoint_file:
                    with open(checkpoint_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "metadata": {
                                "experiment_id": "EXP-001c",
                                "name": "Extraction Granularity Diagnostic",
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "model_config": self.model_config,
                                "total_evaluations": len(raw_results)
                            },
                            "raw_results": raw_results
                        }, f, indent=2)

        return {
            "metadata": {
                "experiment_id": "EXP-001c",
                "name": "Extraction Granularity Diagnostic",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model_config": self.model_config,
                "total_evaluations": len(raw_results)
            },
            "raw_results": raw_results
        }

    @classmethod
    def compute_summary(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        runs = data["raw_results"]
        summary = {}

        for cond in ["Condition_A_Whole_Chunk", "Condition_B_Pre_Segmented"]:
            c_runs = [r for r in runs if r["condition"] == cond]
            total_evals = len(c_runs)

            tot_expected = sum(r["transactions_expected"] for r in c_runs)
            tot_extracted = sum(r["transactions_extracted"] for r in c_runs)
            tot_matched = sum(r["transactions_matched"] for r in c_runs)

            overall_recall = round(tot_matched / max(1, tot_expected) * 100, 1)
            overall_precision = round(tot_matched / max(1, tot_extracted) * 100, 1)

            fully_correct = sum(1 for r in c_runs if r["document_classification"] == "FULLY_CORRECT")
            partial_correct = sum(1 for r in c_runs if r["document_classification"] == "PARTIALLY_CORRECT")
            incorrect = sum(1 for r in c_runs if r["document_classification"] == "INCORRECT")

            latencies = [r["total_document_latency_ms"] for r in c_runs]
            total_calls = sum(r["model_calls"] for r in c_runs)
            total_retries = sum(r["retries_count"] for r in c_runs)
            tot_input_tokens = sum(r.get("input_tokens", 0) for r in c_runs)
            tot_input_proc_ms = sum(r.get("input_processing_ms", 0) for r in c_runs)
            tot_output_tokens = sum(r.get("output_tokens", 0) for r in c_runs)
            tot_gen_ms = sum(r.get("generation_time_ms", 0) for r in c_runs)

            # Per-document metrics
            per_doc = {}
            for doc_id in TARGET_DOC_IDS:
                d_runs = [r for r in c_runs if r["document_id"] == doc_id]
                d_exp = d_runs[0]["transactions_expected"] if d_runs else 0
                d_ext = round(sum(r["transactions_extracted"] for r in d_runs) / max(1, len(d_runs)), 1)
                d_match = round(sum(r["transactions_matched"] for r in d_runs) / max(1, len(d_runs)), 1)
                d_rec = round(sum(r["transaction_recall"] for r in d_runs) / max(1, len(d_runs)) * 100, 1)
                d_lat = round(sum(r["total_document_latency_ms"] for r in d_runs) / max(1, len(d_runs)), 1)
                d_calls = round(sum(r["model_calls"] for r in d_runs) / max(1, len(d_runs)), 1)
                d_in_tok = round(sum(r.get("input_tokens", 0) for r in d_runs) / max(1, len(d_runs)), 1)
                d_out_tok = round(sum(r.get("output_tokens", 0) for r in d_runs) / max(1, len(d_runs)), 1)
                d_in_proc = round(sum(r.get("input_processing_ms", 0) for r in d_runs) / max(1, len(d_runs)), 1)
                d_gen_time = round(sum(r.get("generation_time_ms", 0) for r in d_runs) / max(1, len(d_runs)), 1)

                per_doc[doc_id] = {
                    "document_name": d_runs[0]["document_name"] if d_runs else "",
                    "expected_txs": d_exp,
                    "mean_extracted_txs": d_ext,
                    "mean_matched_txs": d_match,
                    "mean_recall_pct": d_rec,
                    "mean_latency_ms": d_lat,
                    "mean_calls": d_calls,
                    "mean_input_tokens": d_in_tok,
                    "mean_output_tokens": d_out_tok,
                    "mean_input_proc_ms": d_in_proc,
                    "mean_gen_time_ms": d_gen_time
                }

            summary[cond] = {
                "total_evaluations": total_evals,
                "total_transactions_expected": tot_expected,
                "total_transactions_extracted": tot_extracted,
                "total_transactions_matched": tot_matched,
                "overall_recall_pct": overall_recall,
                "overall_precision_pct": overall_precision,
                "fully_correct_count": fully_correct,
                "fully_correct_pct": round(fully_correct / total_evals * 100, 1),
                "partially_correct_count": partial_correct,
                "partially_correct_pct": round(partial_correct / total_evals * 100, 1),
                "incorrect_count": incorrect,
                "incorrect_pct": round(incorrect / total_evals * 100, 1),
                "total_model_calls": total_calls,
                "total_retries": total_retries,
                "total_input_tokens": tot_input_tokens,
                "total_input_proc_ms": tot_input_proc_ms,
                "total_output_tokens": tot_output_tokens,
                "total_generation_ms": tot_gen_ms,
                "mean_doc_latency_ms": round(sum(latencies) / len(latencies), 1),
                "median_doc_latency_ms": round(sorted(latencies)[len(latencies) // 2], 1),
                "mean_tokens_per_sec": round(tot_output_tokens / max(0.001, tot_gen_ms / 1000), 1),
                "per_doc_breakdown": per_doc
            }

        return summary

    @classmethod
    def generate_report(cls, summary: Dict[str, Any], raw_data: Dict[str, Any]) -> str:
        s_a = summary["Condition_A_Whole_Chunk"]
        s_b = summary["Condition_B_Pre_Segmented"]

        lines = [
            "# 🔬 EXP-001c: Extraction Granularity Diagnostic Report",
            "",
            "> **Research Question**: *Does deterministic pre-segmentation improve multi-item extraction more than increasing the model's context budget?*",
            "",
            "## 1. Executive Summary & Aggregate Comparison",
            "",
            "| Metric | Condition A (Whole-Chunk Single-Shot) | Condition B (Deterministic Pre-Segmentation) | Absolute Difference | Relative Change |",
            "| :--- | :---: | :---: | :---: | :---: |",
            f"| **Overall Transaction Recall** | **{s_a['overall_recall_pct']}%** ({s_a['total_transactions_matched']}/{s_a['total_transactions_expected']}) | **{s_b['overall_recall_pct']}%** ({s_b['total_transactions_matched']}/{s_b['total_transactions_expected']}) | **+{round(s_b['overall_recall_pct'] - s_a['overall_recall_pct'], 1)}%** | **{round((s_b['overall_recall_pct'] - s_a['overall_recall_pct'])/max(0.1, s_a['overall_recall_pct'])*100, 1)}%** |",
            f"| **Overall Transaction Precision** | {s_a['overall_precision_pct']}% | {s_b['overall_precision_pct']}% | {round(s_b['overall_precision_pct'] - s_a['overall_precision_pct'], 1)}% | - |",
            f"| **Fully Reconstructed Documents** | {s_a['fully_correct_count']}/{s_a['total_evaluations']} ({s_a['fully_correct_pct']}%) | {s_b['fully_correct_count']}/{s_b['total_evaluations']} ({s_b['fully_correct_pct']}%) | +{round(s_b['fully_correct_pct'] - s_a['fully_correct_pct'], 1)}% | - |",
            f"| **Partially Reconstructed Documents** | {s_a['partially_correct_count']}/{s_a['total_evaluations']} ({s_a['partially_correct_pct']}%) | {s_b['partially_correct_count']}/{s_b['total_evaluations']} ({s_b['partially_correct_pct']}%) | {round(s_b['partially_correct_pct'] - s_a['partially_correct_pct'], 1)}% | - |",
            f"| **Total Model Invocations** | {s_a['total_model_calls']} calls | {s_b['total_model_calls']} calls | +{s_b['total_model_calls'] - s_a['total_model_calls']} calls | +{round((s_b['total_model_calls'] - s_a['total_model_calls'])/s_a['total_model_calls']*100, 1)}% |",
            f"| **Mean Document Latency** | {s_a['mean_doc_latency_ms']} ms | {s_b['mean_doc_latency_ms']} ms | {round(s_b['mean_doc_latency_ms'] - s_a['mean_doc_latency_ms'], 1)} ms | - |",
            f"| **Total Input Tokens** | {s_a['total_input_tokens']} tokens | {s_b['total_input_tokens']} tokens | {s_b['total_input_tokens'] - s_a['total_input_tokens']} tokens | - |",
            f"| **Total Output Tokens** | {s_a['total_output_tokens']} tokens | {s_b['total_output_tokens']} tokens | {s_b['total_output_tokens'] - s_a['total_output_tokens']} tokens | - |",
            f"| **Generation Speed** | {s_a['mean_tokens_per_sec']} tok/s | {s_b['mean_tokens_per_sec']} tok/s | - | - |",
            f"| **Retries Triggered** | {s_a['total_retries']} | {s_b['total_retries']} | - | - |",
            "",
            "## 2. Per-Document Extraction Breakdown",
            "",
            "| Document ID | Document Name | Expected Txs | Cond A Extracted | Cond A Recall | Cond B Extracted | Cond B Recall | Cond A Calls | Cond B Calls | Cond A Latency | Cond B Latency |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        for doc_id in TARGET_DOC_IDS:
            d_a = s_a["per_doc_breakdown"].get(doc_id, {})
            d_b = s_b["per_doc_breakdown"].get(doc_id, {})
            lines.append(
                f"| `{doc_id}` | {d_a.get('document_name', '')} | {d_a.get('expected_txs', 0)} | "
                f"{d_a.get('mean_extracted_txs', 0)} | {d_a.get('mean_recall_pct', 0)}% | "
                f"{d_b.get('mean_extracted_txs', 0)} | {d_b.get('mean_recall_pct', 0)}% | "
                f"{d_a.get('mean_calls', 0)} | {d_b.get('mean_calls', 0)} | "
                f"{d_a.get('mean_latency_ms', 0)} ms | {d_b.get('mean_latency_ms', 0)} ms |"
            )

        lines.extend([
            "",
            "## 3. Latency & Token Breakdown Diagnostic (Input Processing vs Generation)",
            "",
            "| Metric | Condition A (Whole-Chunk Single-Shot) | Condition B (Deterministic Pre-Segmentation) |",
            "| :--- | :---: | :---: |",
            f"| **Total Input Tokens Processed** | {s_a['total_input_tokens']} tokens | {s_b['total_input_tokens']} tokens |",
            f"| **Total Input Processing Time** | {s_a['total_input_proc_ms']} ms | {s_b['total_input_proc_ms']} ms |",
            f"| **Total Output Tokens Generated** | {s_a['total_output_tokens']} tokens | {s_b['total_output_tokens']} tokens |",
            f"| **Total Output Generation Time** | {s_a['total_generation_ms']} ms | {s_b['total_generation_ms']} ms |",
            f"| **Generation Throughput** | {s_a['mean_tokens_per_sec']} tokens/s | {s_b['mean_tokens_per_sec']} tokens/s |",
            "",
            "## 4. Key Findings & Discussion",
            "",
            "*(Empirical findings to be analyzed from raw results)*",
            "",
            "---",
            "*Report generated deterministically by MiniSeek Evaluation Engine.*"
        ])

        return "\n".join(lines)

def main():
    dataset_file = REPO_ROOT / "evaluation" / "datasets" / "synthesizer" / "exp001b_corpus.json"
    results_file = REPO_ROOT / "evaluation" / "results" / "EXP-001c_raw_results.json"
    report_file = REPO_ROOT / "evaluation" / "reports" / "EXP-001c_report.md"

    results_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    runner = EXP001cRunner(dataset_path=dataset_file)
    raw_data = runner.run_diagnostic(checkpoint_file=results_file)

    summary = EXP001cRunner.compute_summary(raw_data)
    report_md = EXP001cRunner.generate_report(summary, raw_data)

    report_file.write_text(report_md, encoding="utf-8")
    print(f"\n✅ Saved EXP-001c results: {results_file}")
    print(f"✅ Generated EXP-001c report: {report_file}")
    print("\n" + report_md)

if __name__ == "__main__":
    main()
