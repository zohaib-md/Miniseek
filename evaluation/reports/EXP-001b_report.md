# 📊 EXP-001: Context Budget Evaluation (Pilot Report)

> **Pilot Notice**: This report contains measured empirical data from an exploratory pilot ($4 \text{ conditions} \times 20 \text{ documents} \times 3 \text{ repetitions} = 240 \text{ evaluations}$).

## 1. System & Model Configuration
- **Model**: `qwen2.5:1.5b` (Q4_K_M)
- **Runtime Backend**: `Ollama (HTTP API)`
- **Temperature**: `0.0` | **Top-P**: `1.0`
- **Fixed Prompt Overhead**: `~366 tokens` (constant across all conditions)
- **Corpus Size**: `20 documents`
- **Total Evaluations**: `240 runs`

## 2. Aggregate Results Summary

| Target Budget | Overall Success (%) | Fully Correct (%) | Partial (%) | Incorrect (%) | First-Pass Validity (%) | Model Calls | Mean Chunk Latency | Mean Total Doc Latency | Peak RAM |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 5.0% | 1.7% | 68.3% | 26.7% | 96.7% | 143 | 12626.8 ms | 29673.9 ms | 29.61 MB |
| **500 tokens** | 3.3% | 1.7% | 68.3% | 28.3% | 100.0% | 87 | 15228.3 ms | 22081.5 ms | 29.61 MB |
| **750 tokens** | 5.0% | 5.0% | 56.7% | 38.3% | 98.3% | 73 | 20580.9 ms | 24697.3 ms | 29.61 MB |
| **1000 tokens** | 11.7% | 3.3% | 58.3% | 30.0% | 96.7% | 68 | 30090.1 ms | 33099.5 ms | 29.61 MB |

## 3. Chunk Distribution & Model Call Efficiency

> **Chunk Reconstruction Mechanism**: Each chunk is processed independently via a separate model call. Extracted transactions are concatenated (`list.extend`). No second-pass reconciliation, deduplication, or cross-chunk merging is performed.

| Target Budget | Multi-Chunk Docs | Mean Chunks/Doc | Total Model Calls | Total Chunks |
| :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 33/60 | 2.35 | 143 | 141 |
| **500 tokens** | 21/60 | 1.45 | 87 | 87 |
| **750 tokens** | 12/60 | 1.2 | 73 | 72 |
| **1000 tokens** | 6/60 | 1.1 | 68 | 66 |

## 4. Results by Document-Length Group

### Short (<=300 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 12 | 16.7% | 0.0% | 66.7% | 3015.2 ms |
| **500 tokens** | 12 | 8.3% | 0.0% | 75.0% | 3699.6 ms |
| **750 tokens** | 12 | 8.3% | 8.3% | 66.7% | 4021.6 ms |
| **1000 tokens** | 12 | 25.0% | 8.3% | 66.7% | 3347.9 ms |

### Medium (301-600 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 6 | 16.7% | 16.7% | 66.7% | 3297.5 ms |
| **500 tokens** | 6 | 16.7% | 16.7% | 66.7% | 8172.3 ms |
| **750 tokens** | 6 | 16.7% | 16.7% | 66.7% | 4871.5 ms |
| **1000 tokens** | 6 | 16.7% | 16.7% | 83.3% | 5109.7 ms |

### Long (>600 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 42 | 0.0% | 0.0% | 69.0% | 41058.7 ms |
| **500 tokens** | 42 | 0.0% | 0.0% | 66.7% | 29320.5 ms |
| **750 tokens** | 42 | 2.4% | 2.4% | 52.4% | 33437.0 ms |
| **1000 tokens** | 42 | 7.1% | 0.0% | 52.4% | 45598.5 ms |

## 5. Field-Level Accuracy (Strict Matching)

> **Rule**: `extracted = None` is treated as correct only when ground truth is genuinely `None`.

| Target Budget | Vendor (%) | Amount (%) | Date (%) | Currency (%) | Category (%) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 66.7% | 31.7% | 30.0% | 75.0% | 16.7% |
| **500 tokens** | 63.3% | 38.3% | 31.7% | 75.0% | 18.3% |
| **750 tokens** | 60.0% | 33.3% | 31.7% | 63.3% | 15.0% |
| **1000 tokens** | 61.7% | 26.7% | 33.3% | 66.7% | 21.7% |

## 6. Latency, Model-Call Efficiency & Coverage Diagnostics

| Target Budget | Chunks / Doc | Unique Coverage (%) | Mean Chunk Latency | Median Chunk Latency | Mean Total Doc Latency | Median Total Doc Latency | Retries Needed |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 2.35 | 99.9% | 12626.8 ms | 4182 ms | 29673.9 ms | 5485 ms | 2 |
| **500 tokens** | 1.45 | 100.0% | 15228.3 ms | 4813 ms | 22081.5 ms | 5585 ms | 0 |
| **750 tokens** | 1.2 | 100.0% | 20580.9 ms | 4862 ms | 24697.3 ms | 5013 ms | 1 |
| **1000 tokens** | 1.1 | 100.0% | 30090.1 ms | 4886 ms | 33099.5 ms | 4560 ms | 2 |

## 7. Key Discoveries & Discussion

### 1. The Context Budget Trade-Off Curve (Latency vs. Call Efficiency)
The experiment demonstrated a clear trade-off between semantic chunk capacity and execution efficiency:
- **Chunk Reduction**: Moving from 250 tokens to 1000 tokens reduced total model calls from **143 calls to 68 calls** (a **52.4% reduction** in inference invocations).
- **Per-Chunk Latency Scaling**: Chunk latency scaled near-linearly with budget size:
  - 250 tokens: **12.6s** per chunk
  - 500 tokens: **15.2s** per chunk
  - 750 tokens: **20.6s** per chunk
  - 1000 tokens: **30.1s** per chunk
- **The Total Document Latency U-Curve**: Because small budgets require more calls while large budgets require longer inference per call, total document processing time followed a distinct U-curve:
  - 250 tokens: **29.7s** (penalized by 2.35 calls/document)
  - **500 tokens: 22.1s (minimum total document latency)**
  - 750 tokens: **24.7s**
  - 1000 tokens: **33.1s** (penalized by heavy 30s+ inference on 3,500-char chunks)

### 2. High Schema Adherence Across Budgets
- First-pass schema adherence remained high across all conditions (**96.7% to 100.0%**), with 500 tokens achieving **100.0% first-pass validity** (0 retries across 60 evaluations).
- Across all 240 evaluations, only 5 retries were triggered across the entire benchmark, proving that the prompt XML encapsulation and 6-step validator remain robust even when documents are heavily chunked.

### 3. The Limits of Mechanism C (Independent Chunk Concatenation)
- On long multi-item documents (>600 chars), the fully correct extraction rate was between **0.0% and 7.1%**, while partially correct was **52.4% to 69.0%**.
- Under Mechanism C, chunks are processed independently with simple concatenation (`list.extend`). When an invoice or quarterly ledger contains 10 to 27 line items, the 1.5B edge model extracts a subset from each chunk, but lacks cross-chunk entity resolution or item completeness tracking.
- This demonstrates that **semantic context budgeting alone cannot solve multi-line ledger extraction** in small models; deterministic row-level ingestion or second-pass reconciliation is required for high completeness.

### 4. Hardware Stress on 8 GB Apple M1
- When processing 1000-token chunks on large documents (`doc_b14`, `doc_b16`, `doc_b17`), single inference calls exceeded 120–180 seconds under sustained thermal load, triggering the HTTP retry guard (up to 240s).
- Resident process memory for the Python harness remained strictly bounded at **29.61 MB** throughout the multi-hour test.

---
*Report generated deterministically by MiniSeek Evaluation Engine.*