import os
import sys
import re
import json
import time
import subprocess
import resource
import urllib.request
import urllib.error
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def get_process_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return round(usage.ru_maxrss / (1024 * 1024), 2)
    return round(usage.ru_maxrss / 1024, 2)

def get_system_swap_mb() -> Dict[str, float]:
    """Reads system swap usage via sysctl vm.swapusage."""
    try:
        out = subprocess.check_output(["sysctl", "vm.swapusage"], text=True)
        # format: vm.swapusage: total = 10240.00M  used = 9053.75M  free = 1186.25M
        total_m = re.search(r"total\s*=\s*([\d.]+)M", out)
        used_m = re.search(r"used\s*=\s*([\d.]+)M", out)
        free_m = re.search(r"free\s*=\s*([\d.]+)M", out)
        return {
            "total_mb": float(total_m.group(1)) if total_m else 0.0,
            "used_mb": float(used_m.group(1)) if used_m else 0.0,
            "free_mb": float(free_m.group(1)) if free_m else 0.0
        }
    except Exception as e:
        return {"total_mb": 0.0, "used_mb": 0.0, "free_mb": 0.0, "error": str(e)}

class OrnithFeasibilityClient:
    def __init__(self, model_name: str = "ornith:9b", host: str = "http://127.0.0.1:11434", timeout: int = 180):
        self.model_name = model_name
        self.host = host.rstrip("/")
        self.timeout = timeout

    def get_metadata(self) -> Dict[str, Any]:
        url = f"{self.host}/api/show"
        data = json.dumps({"name": self.model_name}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                model_info = res.get("model_info", {})
                details = res.get("details", {})
                return {
                    "model_name": self.model_name,
                    "parameter_size": details.get("parameter_size", "unknown"),
                    "quantization_level": details.get("quantization_level", "unknown"),
                    "family": details.get("family", "unknown"),
                    "context_length": details.get("context_length") or model_info.get("qwen35.context_length") or model_info.get("qwen2.context_length") or 32768,
                    "embedding_length": details.get("embedding_length") or model_info.get("qwen35.embedding_length") or model_info.get("qwen2.embedding_length") or "unknown"
                }
        except Exception as e:
            return {"model_name": self.model_name, "error": str(e)}

    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None, num_predict: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.host}/api/chat"
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": payload_messages,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": 42
            }
        }
        if num_predict is not None:
            payload["options"]["num_predict"] = num_predict

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res = json.loads(response.read().decode("utf-8"))
                wall_ms = int((time.time() - t0) * 1000)
                return {
                    "success": True,
                    "content": res.get("message", {}).get("content", ""),
                    "model": res.get("model"),
                    "wall_latency_ms": wall_ms,
                    "total_duration_ms": res.get("total_duration", 0) // 1_000_000,
                    "load_duration_ms": res.get("load_duration", 0) // 1_000_000,
                    "prompt_eval_count": res.get("prompt_eval_count", 0),
                    "prompt_eval_duration_ms": res.get("prompt_eval_duration", 0) // 1_000_000,
                    "eval_count": res.get("eval_count", 0),
                    "eval_duration_ms": res.get("eval_duration", 0) // 1_000_000
                }
        except Exception as e:
            print(f"\n[OrnithClient] Request error ({e}), trying 240s retry guard...", flush=True)
            try:
                req_retry = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req_retry, timeout=240) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    wall_ms = int((time.time() - t0) * 1000)
                    return {
                        "success": True,
                        "content": res.get("message", {}).get("content", ""),
                        "model": res.get("model"),
                        "wall_latency_ms": wall_ms,
                        "total_duration_ms": res.get("total_duration", 0) // 1_000_000,
                        "load_duration_ms": res.get("load_duration", 0) // 1_000_000,
                        "prompt_eval_count": res.get("prompt_eval_count", 0),
                        "prompt_eval_duration_ms": res.get("prompt_eval_duration", 0) // 1_000_000,
                        "eval_count": res.get("eval_count", 0),
                        "eval_duration_ms": res.get("eval_duration", 0) // 1_000_000
                    }
            except Exception as e2:
                wall_ms = int((time.time() - t0) * 1000)
                return {
                    "success": False,
                    "content": "",
                    "model": self.model_name,
                    "wall_latency_ms": wall_ms,
                    "total_duration_ms": wall_ms,
                    "load_duration_ms": 0,
                    "prompt_eval_count": 0,
                    "prompt_eval_duration_ms": 0,
                    "eval_count": 0,
                    "eval_duration_ms": 0,
                    "error": str(e2)
                }

def run_feasibility_study() -> Dict[str, Any]:
    print("=" * 78)
    print("  MINISEEK — EXP-003: ORNITH-9B LOCAL FEASIBILITY STUDY")
    print("  Target Hardware: Apple MacBook Air M1 (8 GB Unified Memory, Fanless)")
    print("  Candidate Model: ornith:9b (~5.24 GB Q4_K_M GGUF)")
    print("=" * 78)

    client = OrnithFeasibilityClient(model_name="ornith:9b")

    # 1. Environment & Model Discovery
    print("\n[Phase 1] Discovering Model Metadata...")
    meta = client.get_metadata()
    print("  Model Name:", meta.get("model_name"))
    print("  Parameter Size:", meta.get("parameter_size"))
    print("  Quantization:", meta.get("quantization_level"))
    print("  Architecture Family:", meta.get("family"))
    print("  Context Length:", meta.get("context_length"))

    # Initial System & Swap State
    initial_swap = get_system_swap_mb()
    initial_rss = get_process_rss_mb()
    print(f"\n[Initial System State]")
    print(f"  System Swap Used: {initial_swap['used_mb']:.1f} MB / {initial_swap['total_mb']:.1f} MB")
    print(f"  Python Process RSS: {initial_rss:.2f} MB")

    # 2. Local Feasibility: Warmup & Load Measurement
    print("\n[Phase 2.1] Executing Initial Model Load & Warmup (1-token ping)...")
    t0_warmup = time.time()
    warmup_res = client.chat([{"role": "user", "content": "ping"}], num_predict=1)
    t_warmup = round(time.time() - t0_warmup, 2)

    post_warmup_swap = get_system_swap_mb()
    swap_delta_warmup = round(post_warmup_swap["used_mb"] - initial_swap["used_mb"], 1)

    print(f"  Warmup Completed: Success={warmup_res['success']}")
    print(f"  Reported load_duration: {warmup_res.get('load_duration_ms')} ms")
    print(f"  Wall-clock warmup latency: {t_warmup} s")
    print(f"  Swap Delta after model load: {swap_delta_warmup:+.1f} MB (Used: {post_warmup_swap['used_mb']:.1f} MB)")

    # 2.2 Progressive Context Stress Test
    print("\n[Phase 2.2] Progressive Context Stress Test...")
    context_tiers = [
        {"tier": "250 chars (~70 tokens)", "chars": 250},
        {"tier": "500 chars (~140 tokens)", "chars": 500},
        {"tier": "1000 chars (~285 tokens)", "chars": 1000},
        {"tier": "2000 chars (~570 tokens)", "chars": 2000}
    ]

    base_dummy_text = (
        "Acme Supplies invoice #9102 dated 2026-08-15. Item 1: Heavy duty stapler $15.50. "
        "Item 2: Printer paper case $42.00. Tax: $5.75. Shipping: $10.00. Subtotal: $57.50. "
        "Total balance due upon receipt: $73.25. Payment terms: Net 30. Direct inquiries to support@acme.example. "
    ) * 15

    progressive_results = []
    for ct in context_tiers:
        tier_text = base_dummy_text[:ct["chars"]]
        prompt = (
            f"Document:\n{tier_text}\n\n"
            f"Extract all transactions into JSON array with keys: vendor, date, amount. Respond ONLY with JSON:"
        )
        print(f"  • Running tier: {ct['tier']} ...", end="", flush=True)
        t_tier_start = time.time()
        res = client.chat([{"role": "user", "content": prompt}], num_predict=128)
        cur_swap = get_system_swap_mb()
        swap_delta = round(cur_swap["used_mb"] - initial_swap["used_mb"], 1)

        gen_time_s = max(0.001, res.get("eval_duration_ms", 0) / 1000)
        tok_s = round(res.get("eval_count", 0) / gen_time_s, 1)

        tier_record = {
            "tier": ct["tier"],
            "input_chars": ct["chars"],
            "success": res["success"],
            "wall_latency_ms": res.get("wall_latency_ms", 0),
            "prompt_eval_tokens": res.get("prompt_eval_count", 0),
            "prompt_eval_duration_ms": res.get("prompt_eval_duration_ms", 0),
            "output_tokens": res.get("eval_count", 0),
            "generation_duration_ms": res.get("eval_duration_ms", 0),
            "generation_tokens_per_sec": tok_s,
            "swap_used_mb": cur_swap["used_mb"],
            "swap_delta_mb": swap_delta,
            "error": res.get("error")
        }
        progressive_results.append(tier_record)
        print(f" Done ({tier_record['wall_latency_ms']}ms | {tok_s} tok/s | swap={swap_delta:+.1f}MB)")

    # 3. Minimal Capability Smoke Test (4 Representative Documents)
    print("\n[Phase 3] Minimal Capability Smoke Test (4 Representative Documents)...")
    corpus_path = REPO_ROOT / "evaluation" / "datasets" / "synthesizer" / "exp001b_corpus.json"
    with open(corpus_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    smoke_doc_ids = ["doc_b01", "doc_b11", "doc_b07", "doc_b06"]
    smoke_docs = [d for d in corpus if d["id"] in smoke_doc_ids]

    smoke_results = []
    for doc in smoke_docs:
        doc_id = doc["id"]
        doc_name = doc["document_name"]
        print(f"  • Evaluating {doc_id} ({doc_name}) ...", end="", flush=True)

        prompt = (
            f"Document:\n{doc['content']}\n\n"
            f"Extract all financial transactions into a JSON array of objects with keys: "
            f"vendor, date, amount, currency, category, confidence.\n"
            f"Respond ONLY with the JSON array:"
        )

        t_smoke_start = time.time()
        res = client.chat([{"role": "user", "content": prompt}])
        cur_swap = get_system_swap_mb()
        swap_delta = round(cur_swap["used_mb"] - initial_swap["used_mb"], 1)

        content = res.get("content", "").strip()
        parsed = []
        parse_error = None
        try:
            p_data = json.loads(content)
            if isinstance(p_data, list):
                parsed = p_data
            elif isinstance(p_data, dict):
                for k in ["transactions", "items", "expenses", "data"]:
                    if k in p_data and isinstance(p_data[k], list):
                        parsed = p_data[k]
                        break
                else:
                    parsed = [p_data]
        except Exception as pe:
            # bracket fallback
            m = re.search(r"\[.*\]", content, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parse_error = str(pe)
            else:
                parse_error = str(pe)

        # Scorer
        expected = doc.get("expected_transactions", [])
        matched = 0
        matched_exp = set()
        matched_ext = set()

        for exp_idx, exp in enumerate(expected):
            for ext_idx, ext in enumerate(parsed):
                if ext_idx in matched_ext or not isinstance(ext, dict):
                    continue
                v_ok = False
                if exp.get("vendor") and ext.get("vendor"):
                    if exp["vendor"].lower() in str(ext["vendor"]).lower() or str(ext["vendor"]).lower() in exp["vendor"].lower():
                        v_ok = True
                a_ok = False
                if exp.get("amount") is not None and ext.get("amount") is not None:
                    try:
                        clean_a = re.sub(r"[^\d.]", "", str(ext["amount"]))
                        if clean_a and Decimal(clean_a) == Decimal(str(exp["amount"])):
                            a_ok = True
                    except Exception:
                        a_ok = False
                elif exp.get("amount") is None and ext.get("amount") is None:
                    a_ok = True

                if v_ok and a_ok:
                    matched_exp.add(exp_idx)
                    matched_ext.add(ext_idx)
                    break

        matched = len(matched_exp)
        rec = round(matched / max(1, len(expected)) * 100, 1)
        prec = round(matched / max(1, len(parsed)) * 100, 1) if parsed else 0.0

        gen_time_s = max(0.001, res.get("eval_duration_ms", 0) / 1000)
        tok_s = round(res.get("eval_count", 0) / gen_time_s, 1)

        smoke_record = {
            "document_id": doc_id,
            "document_name": doc_name,
            "category_group": doc.get("category_group", ""),
            "expected_transactions": len(expected),
            "extracted_transactions": len(parsed),
            "matched_transactions": matched,
            "recall_pct": rec,
            "precision_pct": prec,
            "schema_valid": parse_error is None,
            "parse_error": parse_error,
            "wall_latency_ms": res.get("wall_latency_ms", 0),
            "input_tokens": res.get("prompt_eval_count", 0),
            "output_tokens": res.get("eval_count", 0),
            "generation_tokens_per_sec": tok_s,
            "swap_used_mb": cur_swap["used_mb"],
            "swap_delta_mb": swap_delta,
            "sample_output": content[:200]
        }
        smoke_results.append(smoke_record)
        print(f" Done ({rec}% recall | {tok_s} tok/s | {smoke_record['wall_latency_ms']}ms)")

    # 4. Phase 4: Feasibility Verdict Formulation
    print("\n[Phase 4] Computing Feasibility Verdict...")
    max_swap_delta = max([r["swap_delta_mb"] for r in progressive_results + smoke_results] + [swap_delta_warmup])
    avg_gen_speed = round(sum(r["generation_tokens_per_sec"] for r in smoke_results) / len(smoke_results), 1)
    avg_latency_ms = round(sum(r["wall_latency_ms"] for r in smoke_results) / len(smoke_results), 1)
    timeouts = sum(1 for r in smoke_results if r["wall_latency_ms"] >= 180000)

    # Classification logic
    if timeouts > 0 or max_swap_delta > 3000 or avg_gen_speed < 4.0:
        verdict = "VERDICT_C_NOT_VIABLE"
        verdict_desc = "Not Viable: Excessive memory pressure, swap thrashing, unworkable generation latency (<4 tok/s), or timeouts."
        recommend_benchmark = False
    elif max_swap_delta > 1000 or avg_latency_ms > 60000 or avg_gen_speed < 8.0:
        verdict = "VERDICT_B_RUNNABLE_BUT_IMPRACTICAL"
        verdict_desc = "Technically Runnable but Impractical: Model runs on M1, but induces substantial memory pressure/swap activity, high latency, or thermal degradation making full benchmarking impractical."
        recommend_benchmark = False
    else:
        verdict = "VERDICT_A_VIABLE"
        verdict_desc = "Viable: Model executes within acceptable stability, manageable swap delta (<1 GB), adequate generation speed (>8 tok/s), and valid schema adherence."
        recommend_benchmark = True

    print(f"  Result Verdict: {verdict}")
    print(f"  {verdict_desc}")

    report_data = {
        "metadata": {
            "experiment_id": "EXP-003",
            "name": "Ornith-9B Local Feasibility Study",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hardware": "Apple MacBook Air M1 (8 GB Unified Memory, macOS arm64)",
            "ollama_model": meta
        },
        "system_memory": {
            "initial_swap_mb": initial_swap,
            "initial_process_rss_mb": initial_rss,
            "warmup_load_duration_ms": warmup_res.get("load_duration_ms", 0),
            "warmup_wall_latency_ms": warmup_res.get("wall_latency_ms", 0),
            "warmup_swap_delta_mb": swap_delta_warmup,
            "max_swap_delta_mb": max_swap_delta
        },
        "progressive_context_results": progressive_results,
        "smoke_test_results": smoke_results,
        "verdict": {
            "classification": verdict,
            "description": verdict_desc,
            "recommend_full_benchmark": recommend_benchmark,
            "avg_generation_speed_tok_s": avg_gen_speed,
            "avg_document_latency_ms": avg_latency_ms,
            "timeouts": timeouts
        }
    }

    return report_data

def generate_report_markdown(data: Dict[str, Any]) -> str:
    m = data["metadata"]
    sm = data["system_memory"]
    om = m["ollama_model"]
    v = data["verdict"]

    lines = [
        "# 🔬 EXP-003: Ornith-9B Local Feasibility Study — Report",
        "",
        "> **Objective**: *Determine whether a quantized Ornith-9B model can execute locally and usefully on an Apple MacBook Air M1 (8 GB Unified Memory) without system instability, swap thrashing, or impractical latency.*",
        "",
        "## 1. Hardware & Environment Setup",
        "",
        "| Parameter | Specification | Notes |",
        "| :--- | :--- | :--- |",
        f"| **Host Machine** | {m['hardware']} | Fanless architecture, unified memory shared between CPU & Metal GPU |",
        f"| **Candidate Model** | `{om.get('model_name', 'ornith:9b')}` | {om.get('parameter_size', '9B')} parameters |",
        f"| **Quantization Format** | `{om.get('quantization_level', 'Q4_K_M')}` | 4-bit GGUF via llama.cpp Metal backend |",
        f"| **Model On-Disk Size** | ~5.24 GB (5,368 MB) | Stored in Ollama model blob store |",
        f"| **Context Length** | {om.get('context_length', 32768)} tokens | Reported by model metadata |",
        "| **Inference Controls** | `temperature = 0.0, top_p = 1.0, seed = 42` | Deterministic decoding |",
        "",
        "## 2. Initial Model Load & Memory State",
        "",
        "| Metric | Observed Value | Rationale / Diagnostic |",
        "| :--- | :---: | :--- |",
        f"| **Initial System Swap Used** | **{sm['initial_swap_mb']['used_mb']:.1f} MB** / {sm['initial_swap_mb']['total_mb']:.1f} MB | Background OS and desktop processes |",
        f"| **Python Process Resident RSS** | **{sm['initial_process_rss_mb']:.2f} MB** | Python driver process footprint |",
        f"| **Initial Model Load Duration** | **{sm['warmup_load_duration_ms']} ms** ({sm['warmup_wall_latency_ms']/1000:.1f}s) | Time required to map 5.24 GB model weights into Unified Memory |",
        f"| **Swap Delta After Initial Load** | **{sm['warmup_swap_delta_mb']:+.1f} MB** | Immediate swap activity upon allocating model weights |",
        f"| **Peak Swap Delta Observed** | **{sm['max_swap_delta_mb']:+.1f} MB** | Maximum swap increase observed during inference |",
        "",
        "## 3. Progressive Context Stress Test",
        "",
        "| Context Tier | Input Chars | Prompt Ingestion (ms) | Output Tokens | Gen Latency (ms) | Throughput (tok/s) | Total Latency (ms) | Swap Delta (MB) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ]

    for p in data["progressive_context_results"]:
        lines.append(
            f"| **{p['tier']}** | {p['input_chars']} | {p['prompt_eval_duration_ms']} ms | "
            f"{p['output_tokens']} | {p['generation_duration_ms']} ms | **{p['generation_tokens_per_sec']} tok/s** | "
            f"{p['wall_latency_ms']} ms | {p['swap_delta_mb']:+.1f} MB |"
        )

    lines.extend([
        "",
        "## 4. Minimal Capability Smoke Test (4 Representative Documents)",
        "",
        "| Document ID | Document Type | Expected | Extracted | Matched | Recall | Precision | Schema Valid | Throughput | Total Latency | Swap Delta |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])

    for s in data["smoke_test_results"]:
        lines.append(
            f"| **{s['document_id']}** (`{s['document_name']}`) | {s['category_group']} | "
            f"{s['expected_transactions']} | {s['extracted_transactions']} | {s['matched_transactions']} | "
            f"**{s['recall_pct']}%** | {s['precision_pct']}% | {'✅' if s['schema_valid'] else '❌'} | "
            f"**{s['generation_tokens_per_sec']} tok/s** | {s['wall_latency_ms']} ms | {s['swap_delta_mb']:+.1f} MB |"
        )

    lines.extend([
        "",
        "## 5. Feasibility Verdict & Research Decision",
        "",
        f"### **Final Verdict**: `{v['classification']}`",
        f"> **{v['description']}**",
        "",
        "### Key Quantitative Indicators:",
        f"- **Average Generation Speed**: **{v['avg_generation_speed_tok_s']} tokens/sec**",
        f"- **Average Document Latency**: **{v['avg_document_latency_ms']:.1f} ms** ({v['avg_document_latency_ms']/1000:.1f}s)",
        f"- **Peak Swap Expansion**: **{sm['max_swap_delta_mb']:+.1f} MB**",
        f"- **Timeouts / Out-Of-Memory Crashes**: **{v['timeouts']}**",
        f"- **Recommendation on Full EXP-003 Benchmark**: **{'PROCEED' if v['recommend_full_benchmark'] else 'DO NOT PROCEED (Negative Feasibility Confirmed)'}**",
        "",
        "## 6. Discussion & Engineering Takeaways",
        "",
        "*(Empirical discussion of M1 memory ceiling, swap pressure, and 9B behavior)*",
        "",
        "---",
        "*Report generated deterministically by MiniSeek Evaluation Engine.*"
    ])

    return "\n".join(lines)

def main():
    results_file = REPO_ROOT / "evaluation" / "results" / "EXP-003_feasibility.json"
    report_file = REPO_ROOT / "evaluation" / "reports" / "EXP-003_feasibility.md"

    results_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    data = run_feasibility_study()
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    report_md = generate_report_markdown(data)
    report_file.write_text(report_md, encoding="utf-8")

    print(f"\n✅ Saved feasibility raw results: {results_file}")
    print(f"✅ Generated feasibility report: {report_file}")
    print("\n" + report_md)

if __name__ == "__main__":
    main()
