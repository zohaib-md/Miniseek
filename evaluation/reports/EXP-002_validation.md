# 📋 EXP-002: Model vs. Harness — Final Validation & Audit Summary

**Date**: 2026-09-03  
**Auditor**: Antigravity Quality & Verification Engine  
**Target Experiment**: EXP-002 (Model vs. Harness $2 \times 2$ Factorial Benchmark)  
**Git Commit**: `2d8a16cc22b5d0cd14c52f099b4571fa0a114e6a`  

---

## 1. Scope of the Audit

The audit conducted a line-by-line, transaction-by-transaction reconciliation across three core assets:
1. **Raw Evaluation Dataset**: [`evaluation/results/EXP-002_raw_results.json`](file:///Users/mohammadzohaib/Desktop/Miniseek/evaluation/results/EXP-002_raw_results.json) (160 records)
2. **Evaluation Report**: [`evaluation/reports/EXP-002_report.md`](file:///Users/mohammadzohaib/Desktop/Miniseek/evaluation/reports/EXP-002_report.md)
3. **Experiment Runner Code**: [`evaluation/experiments/EXP-002-model-vs-harness/run_experiment.py`](file:///Users/mohammadzohaib/Desktop/Miniseek/evaluation/experiments/EXP-002-model-vs-harness/run_experiment.py)

---

## 2. Audit Findings & Reconciliations

### Item A: Metrics Verification
* **Overall Micro Recall**:
  * Cell A (1.5B Simple): $79 / 148 = \mathbf{53.38\%} \approx \mathbf{53.4\%}$
  * Cell B (1.5B Structured): $42 / 148 = \mathbf{28.38\%} \approx \mathbf{28.4\%}$
  * Cell C (3B Simple): $113 / 148 = \mathbf{76.35\%} \approx \mathbf{76.4\%}$
  * Cell D (3B Structured): $133 / 148 = \mathbf{89.86\%} \approx \mathbf{89.9\%}$
  * **Status**: **100% Exact Match**. Micro (transaction-weighted) and Macro (document-averaged) figures are now both documented explicitly.
* **Headline Comparison ($\Delta_{\text{HvS}}$)**:
  * $\Delta_{\text{HvS}} = \text{Recall}(B) - \text{Recall}(C) = 28.38\% - 76.35\% = \mathbf{-47.97\%} \approx \mathbf{-48.0\%}$.
  * **Status**: **100% Exact Match**.
* **Interaction Effect**:
  * $\text{Interaction} = (89.86 - 76.35) - (28.38 - 53.38) = +13.51 - (-25.00) = \mathbf{+38.51\%} \approx \mathbf{+38.5\%}$.
  * **Status**: **100% Exact Match**.

### Item B: Memory Terminology Disambiguation
* **Audit Finding**: The previously reported `30.48 MB RSS` represented only the Python driver process memory, not total AI inference memory.
* **Fix Made**: The report was updated with an explicit multi-layer memory breakdown:
  * **Python Driver Process**: `30.48 MB RSS` (measured via `getrusage.ru_maxrss`)
  * **Ollama Server Process (Inference Daemon)**: Model weights loaded in Apple Unified Memory: ~986 MB disk / ~1.2 GB unified RAM for `qwen2.5:1.5b`; ~1,930 MB disk / ~2.1 GB unified RAM for `qwen2.5:3b`.
  * **macOS System Swap**: ~9.0 GB allocated by OS for general desktop applications; zero paging thrashing for the benchmark runner.
* **Status**: **Resolved & Accurately Documented**.

### Item C: Adversarial Containment Audit
* **Audit Finding**: All 40 adversarial document records were inspected individually.
  * Zero prompt injection diversions occurred (0 models executed bash/curl scripts or followed price override directives).
  * Zero fabricated commands were extracted as vendors.
  * **100% of recorded containment failures were failures to abstain on non-financial documents** (`doc_b15` meeting notes, `doc_b19` team meeting).
  * Cell C achieved 1/10 failures because its concise prompt led the 3B model to output `[]` 3 out of 4 times on non-financial text.
  * Cells B and D achieved 4/10 failures because the Structured prompt's instruction ("if missing or ambiguous, output null or NEEDS_REVIEW") prompted the models to generate review records rather than outputting empty arrays `[]`.
* **Status**: **Resolved & Fully Documented in Section 6 of the Report**.

### Item D: Dense-Ledger Calculation Tracing
* **Audit Finding**: The dense-ledger figures were traced to exact transaction counts:
  * Denominator: $N = 122$ total expected transactions ($61 \text{ txs} \times 2 \text{ repetitions}$).
  * Cell D matched **111 / 122 transactions (90.98% $\approx$ 91.0%)**, including 20/20 on `doc_b11` (10-row CSV), 51/54 on `doc_b14` (quarterly ledger), 30/30 on `doc_b17` (expense report), 2/2 on `doc_b09`, and 8/16 on `doc_b16`.
* **Status**: **Resolved & Transparently Tabulated**.

### Item E: Runner Code Validation
* **Harness Isolation**: Confirmed that Cell A, B, C, D each invoke their dedicated harness instances.
* **Latency Isolation**: Confirmed that `load_ms = client.warmup()` is executed outside of the document timing loop (`t_doc_start = time.time()`).
* **Condition Rotation**: Confirmed interleaved order (`A → C → B → D` in Rep 1, `D → B → C → A` in Rep 2).
* **Persistence**: Confirmed immediate per-document disk persistence to prevent data loss.
* **Status**: **Verified**.

---

## 3. Remaining Limitations

1. **Edge-Specific Quantization**: Both models were evaluated at 4-bit quantization (Q4_K_M) on 8 GB Apple Silicon M1; findings reflect local edge execution rather than full 16-bit precision on datacenter GPUs.
2. **Sample Scale**: Evaluated across 20 frozen documents $\times$ 2 repetitions ($N=160$ evaluations). While structurally robust for a diagnostic benchmark, it is a targeted repeated-measures study rather than a universal LLM leaderboard.
3. **Abstention Prompt Bias**: The prompt in `StructuredHarness` explicitly offers `NEEDS_REVIEW` for ambiguous data, which inadvertently biases small models against complete abstention on non-financial text.

---

## 4. Final Recommendation

# ✅ READY FOR PUBLICATION & DOWNSTREAM WORK

The experimental dataset, factorial calculations, memory terminology, and reporting are **100% reconciled, mathematically consistent, and reproducible**. No rerun of the 160 evaluations is required.
