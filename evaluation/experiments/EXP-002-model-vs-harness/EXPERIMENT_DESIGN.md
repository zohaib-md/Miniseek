# EXP-002: Model vs. Harness — Experiment Design

## 1. Executive Summary & Research Motivation

In **EXP-001a**, **EXP-001b**, and **EXP-001c**, we established three foundational empirical findings on edge hardware:
1. **EXP-001a**: Context window limits cannot be benchmarked without documents that actively cross chunk boundaries.
2. **EXP-001b**: Expanding context window size ($250 \to 1000$ tokens) reduced invocation count by 52.4% and created a throughput U-curve (500 tokens optimal at 22.1s/doc), but **did not solve high-cardinality multi-item extraction**.
3. **EXP-001c**: Deterministic task decomposition (pre-segmentation) eliminated missing items on dense ledgers (recovering 100% of items on 10-row and 27-row tables, tripling fully reconstructed documents, and running 35.5% faster). Simultaneously, it revealed that naive line-level splitting destroys document hierarchy on complex invoices.

These findings motivate the central question of **EXP-002**:
> **How much does harness architecture contribute to end-to-end performance, completeness, and safety relative to raw model capability?**

Rather than a simple "Model A vs. Model B" comparison, EXP-002 employs a **$2 \times 2$ factorial experimental design** crossing **Model Scale** with **Harness Architecture**.

---

## 2. Research Questions & Hypotheses

### Primary Research Question
> **Can a small local model operating within a structured, task-decomposed harness match or outperform a larger model operating under a simple unguided harness on an 8 GB edge machine?**

### Hypotheses
* **$H_1$ (Harness Dominance over Model Scale)**: A small model equipped with a structured, task-decomposed harness (**Cell B: 1.5B + Structured**) will achieve higher transaction recall, higher document reconstruction fidelity, and fewer hallucinated transactions than a model with $\approx 2\times$ the parameter scale operating with a simple harness (**Cell C: 3B + Simple**).
* **$H_2$ (Asymmetric Harness Benefit / Interaction Effect)**: The performance improvement from Simple to Structured harness ($\Delta_{\text{Harness}}$) will be significantly larger for the smaller model than for the larger model, demonstrating that harness scaffolding disproportionately elevates resource-constrained models.
* **$H_3$ (Security & Containment Invariance)**: Model scale alone provides no defense against adversarial prompt injections. Both models under the Simple harness will suffer instruction diversion or broken formatting, whereas both models under the Structured harness will achieve 0 tool-execution or filesystem-mutation breaches.

---

## 3. Experimental Matrix ($2 \times 2$ Factorial Design)

```text
                                HARNESS ARCHITECTURE
                          Simple Harness           Structured Harness
MODEL SCALE
Small (1.5B)         Cell A: 1.5B + Simple     Cell B: 1.5B + Structured
Larger (3B)          Cell C: 3B + Simple       Cell D: 3B + Structured
```

### Critical Analytical Comparisons:
1. **Cell B vs. Cell C (Harness vs. Scale)**: Tests whether engineering the harness is more effective than doubling parameter count.
2. **Cell A vs. Cell B (Small Model Harness Impact)**: Measures the baseline value of the harness on edge models.
3. **Cell C vs. Cell D (Large Model Harness Impact)**: Tests whether larger models still benefit from harness decomposition.
4. **Interaction ($[D - C] - [B - A]$)**: Quantifies the interaction effect between model capacity and harness structure.

---

## 4. Models & Runtime Environment

All evaluations will execute on the existing local M1 MacBook Air (8 GB Unified Memory, macOS `arm64`) using local Ollama (`http://127.0.0.1:11434`):

| Condition | Model Name | Parameter Count | Quantization | Size on Disk | Est. Resident RAM | Family / Rationale |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Small Model** | `qwen2.5:1.5b` | 1.54B | Q4_K_M | 986 MB | ~1.2 GB | Baseline edge model characterized in EXP-001 |
| **Larger Model (Option 1 - Recommended)** | `qwen2.5:3b` | 3.09B | Q4_K_M | 1.9 GB | ~2.1 GB | **Exact same family, tokenizer, and training pipeline**; isolates pure parameter scale ($2.0\times$) |
| **Larger Model (Option 2 - Alternative)** | `llama3.2:3b` | 3.21B | Q4_K_M | 2.0 GB | ~2.2 GB | Cross-family comparison (Meta Llama 3.2 vs Alibaba Qwen 2.5) |

---

## 5. Harness Definitions: Simple vs. Structured

### Condition 1: Simple Harness (Baseline / Unguided)
1. **Prompt Scaffolding**: Single-shot unstructured prompt ("Extract all financial expenses from the following text into JSON").
2. **Document Ingestion**: Feeds the entire raw text directly without XML tag boundaries or passive-data encapsulation.
3. **Decomposition**: No task decomposition or pre-segmentation (whole-document single-pass generation).
4. **Validation**: Standard `json.loads()`. If JSON parsing fails, output is marked invalid with 0 retries. No syntax repair, no schema enforcement layer, no provenance verification.
5. **Normalization**: Direct field casting without fuzzy date parsing, currency conservatism, or category whitelist validation.

### Condition 2: Structured Harness (MiniSeek Engineered)
1. **Prompt Scaffolding**: Passive untrusted XML `<document_content>` encapsulation with explicit category taxonomy and extraction rules.
2. **Two-Path Task Decomposition (from EXP-001c)**:
   - **Tabular / Structured Ledgers** (CSV, multi-line logs): Deterministic row-level pre-segmentation into micro-tasks.
   - **Hierarchical Documents** (Invoices, hotel folios): Preserved document context with separation between line items and document totals.
3. **Validation**: 6-layer verification pipeline (Extract $\to$ Syntax Repair $\to$ JSON Parse $\to$ Schema Validation $\to$ Field/Semantic Validation $\to$ Provenance Guard) with a 1-retry guard.
4. **Normalization & Math**: Exact `Decimal` arithmetic, currency conservatism (`$ + \text{no context} \to \text{UNKNOWN}`), and whitelist category mapping.

---

## 6. Fixed Dataset & Controlled Variables

### Benchmark Corpus
The evaluation uses the frozen 20-document multi-tier benchmark corpus from **EXP-001b** (`exp001b_corpus.json`), comprising:
- **5 Clean Receipts** (single transactions: coffee, parking, hardware)
- **5 Dense Tabular Ledgers** (CSV card ledger, quarterly summary, employee report)
- **5 Hierarchical Invoices** (AWS cloud invoice, Oberoi hotel folio, consulting invoice)
- **5 Adversarial & Edge Documents** (prompt injections, malformed totals, non-financial notes)

### Controlled Variables (Frozen Across All Cells):
- **Temperature**: `0.0`
- **Top-P**: `1.0`
- **Seed**: `42`
- **Hardware**: Apple M1 (fanless)
- **Ground Truth**: Human-verified transaction ground truth from `exp001b_corpus.json`
- **Scoring Logic**: Strict field-matching rules (no credit for omitted values)
- **Run Order**: Condition-rotated across 2 complete repetitions per cell:
  - Total Evaluations: $4 \text{ cells} \times 20 \text{ documents} \times 2 \text{ repetitions} = \mathbf{160 \text{ evaluations}}$

---

## 7. Measured Metrics & Latency Decomposition

### Quality & Correctness Metrics:
1. **Transaction Recall**: $\frac{\text{Matched Ground-Truth Transactions}}{\text{Expected Ground-Truth Transactions}}$
2. **Transaction Precision**: $\frac{\text{Matched Ground-Truth Transactions}}{\text{Total Extracted Transactions}}$
3. **Transaction F1 Score**: Harmonic mean of Precision and Recall
4. **Document-Level Classification**:
   - `FULLY_CORRECT`: All expected transactions recovered with strict field accuracy
   - `PARTIALLY_CORRECT`: Subsets of transactions recovered or minor field errors
   - `INCORRECT`: Hallucinated transactions or total extraction failure
   - `CORRECT_ABSTENTION`: Appropriate zero extraction on non-financial documents
5. **Adversarial Containment**: Breaches observed across adversarial files (target: 0).

### Resource & Latency Decomposition Metrics:
1. **Total Document Latency (ms)**: End-to-end wall-clock time per document.
2. **Prompt Evaluation Time (ms)**: Time spent processing input tokens (from Ollama `prompt_eval_duration`).
3. **Output Generation Time (ms)**: Time spent autoregressively generating tokens (from Ollama `eval_duration`).
4. **Input Tokens vs. Output Tokens**: Total tokens consumed vs. produced.
5. **Generation Throughput (tokens/s)**: $\frac{\text{Output Tokens}}{\text{Generation Time}}$.
6. **Peak Memory (MB)**: Process RSS memory + Ollama memory footprint.

---

## 8. Expected Analysis Framework

The final report will compute:
1. **Main Effect of Model Scale**:
   $$\Delta_{\text{Model}} = \frac{\text{Score}(\text{Cell C}) + \text{Score}(\text{Cell D})}{2} - \frac{\text{Score}(\text{Cell A}) + \text{Score}(\text{Cell B})}{2}$$
2. **Main Effect of Harness Architecture**:
   $$\Delta_{\text{Harness}} = \frac{\text{Score}(\text{Cell B}) + \text{Score}(\text{Cell D})}{2} - \frac{\text{Score}(\text{Cell A}) + \text{Score}(\text{Cell C})}{2}$$
3. **Harness-vs-Scale Trade-Off (Cell B vs. Cell C)**:
   $$\Delta_{\text{HvS}} = \text{Score}(\text{Cell B: 1.5B + Structured}) - \text{Score}(\text{Cell C: 3B + Simple})$$
4. **Interaction Effect**:
   $$\text{Interaction} = (\text{Score}(\text{Cell D}) - \text{Score}(\text{Cell C})) - (\text{Score}(\text{Cell B}) - \text{Score}(\text{Cell A}))$$

---

## 9. Limitations & Threat to Validity

* **Hardware Boundary**: Tested strictly on 8 GB Apple Silicon M1; findings reflect local quantized edge execution, not unquantized datacenter GPUs.
* **Quantization Format**: Both models evaluated at 4-bit quantization (Q4_K_M).
* **Sample Size**: 20 documents $\times$ 4 conditions $\times$ 2 runs ($n=160$ runs); targeted diagnostic rather than universal benchmark.
