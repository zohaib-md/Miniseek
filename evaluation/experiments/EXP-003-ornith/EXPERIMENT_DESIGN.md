# EXP-003: Ornith-9B Local Feasibility Study — Experiment Design

## 1. Objective & Research Question

The objective of this study is to determine whether a quantized **Ornith-9B** model can run **locally and usefully** on an Apple MacBook Air M1 with 8 GB Unified Memory.

> **Central Research Question**:
> *Can a 9-billion parameter model (Ornith-9B, ~5.24 GB Q4_K_M) execute locally on an 8 GB unified memory machine under real-world financial extraction tasks without inducing severe memory swapping, thermal throttling, unworkable latency, or process termination?*

This is strictly a **feasibility study**, not yet a full benchmark. We do not assume that a model file size of 5.24 GB means the system only requires 5 GB of RAM; the operating system, display server, and KV cache all compete for the same unified memory pool.

---

## 2. Experimental Phases

### Phase 1: Environment & Model Discovery
* Inspect existing local infrastructure, Ollama version, and model formats.
* Establish the primary serving route: **Ollama (`llama.cpp` Metal backend)** for clean, reproducible integration with MiniSeek's existing LLM provider abstraction.
* Record model architecture, quantization, context size, and memory requirements.

### Phase 2: Local Feasibility & Stress Test
* Execute model loading and measure:
  * Model load duration (`load_duration_ms`).
  * Process memory: Python process RSS (`getrusage`).
  * System memory & swap: `sysctl vm.swapusage` before and during inference.
  * Baseline generation: 1-token warmup ping.
  * Progressive context stress test: Evaluate model behavior at 250, 500, 1,000, and 2,000 input characters, recording:
    * Prompt ingestion latency (`prompt_eval_duration_ms`).
    * Output generation latency (`eval_duration_ms`).
    * Generation throughput (`eval_count / (eval_duration_ms / 1000)`).
    * Swap delta (MB).

### Phase 3: Minimal Capability Smoke Test
Once basic inference is confirmed, evaluate extraction performance against MiniSeek's canonical schema using **4 representative documents** from `exp001b_corpus.json`:
1. **Clean Receipt** (`doc_b01: quick_coffee.txt`): Single-item ground truth baseline.
2. **Dense Tabular Ledger** (`doc_b11: corporate_card_10rows.csv`): 10-row tabular completeness.
3. **Hierarchical Invoice** (`doc_b07: aws_monthly_invoice.txt`): Multi-service line charges with grand total.
4. **Adversarial / Injection** (`doc_b06: prompt_injection.txt`): Passive containment and instruction resistance.

Measure:
* Transaction Recall & Precision.
* Schema adherence (valid JSON array of transaction objects).
* Generation latency (wall-clock ms).
* Memory pressure and swap behavior.

### Phase 4: Research Decision Framework
At the conclusion of the feasibility tests, classify the outcome into one of three explicit verdicts:
* **Verdict A: Viable** — The model executes with acceptable stability, sub-120s document latency, minimal swap churn (<1 GB active delta), and adequate schema validity. $\to$ Recommend proceeding to a full EXP-003 benchmark.
* **Verdict B: Technically Runnable but Impractical** — The model runs, but heavy swap activity (>2 GB delta), thermal throttling, high generation latency (>180s per document), or memory pressure make production use unfeasible. $\to$ Record as a legitimate empirical limitation; do not force a benchmark.
* **Verdict C: Not Viable** — The model crashes due to Out-Of-Memory (OOM) errors, triggers operating system instability, or fails to complete basic tasks. $\to$ Document failure boundaries and stop.

---

## 3. Hardware & Runtime Boundary Controls

* **Platform**: Apple MacBook Air M1 (8-core CPU, 7-core GPU, 8 GB Unified Memory, fanless, macOS `arm64`).
* **Backend**: Local Ollama HTTP API (`v0.33.0`).
* **Inference Settings**: `temperature = 0.0`, `top_p = 1.0`, `seed = 42`.
* **Timeout Guards**: 180s HTTP timeout with 240s retry window; fail-safe error containment to prevent benchmark crashes.
* **Safety Invariant**: No production application code in `miniseek/` or completed artifacts in `EXP-002` will be modified during this feasibility study.
