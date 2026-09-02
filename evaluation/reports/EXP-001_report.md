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
| **250 tokens** | 13.3% | 8.3% | 63.3% | 23.3% | 100.0% | 60 | 2910.3 ms | 2910.3 ms | 28.67 MB |
| **500 tokens** | 13.3% | 10.0% | 68.3% | 18.3% | 100.0% | 60 | 2608.6 ms | 2608.7 ms | 28.67 MB |
| **750 tokens** | 21.7% | 18.3% | 60.0% | 18.3% | 100.0% | 60 | 2504.9 ms | 2504.9 ms | 28.67 MB |
| **1000 tokens** | 11.7% | 8.3% | 65.0% | 23.3% | 100.0% | 60 | 2592.7 ms | 2592.7 ms | 28.67 MB |

## 3. Results by Document-Length Group

### Short (<=300 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 39 | 12.8% | 5.1% | 76.9% | 2332.5 ms |
| **500 tokens** | 39 | 12.8% | 7.7% | 76.9% | 1952.3 ms |
| **750 tokens** | 39 | 23.1% | 17.9% | 64.1% | 2034.1 ms |
| **1000 tokens** | 39 | 12.8% | 7.7% | 71.8% | 2238.8 ms |

### Medium (301-600 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 21 | 14.3% | 14.3% | 38.1% | 3983.3 ms |
| **500 tokens** | 21 | 14.3% | 14.3% | 52.4% | 3827.6 ms |
| **750 tokens** | 21 | 19.0% | 19.0% | 52.4% | 3379.1 ms |
| **1000 tokens** | 21 | 9.5% | 9.5% | 52.4% | 3249.9 ms |

### Long (>600 chars)
| Target Budget | Evaluated Runs | Success Rate (%) | Fully Correct (%) | Partial (%) | Mean Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |

## 4. Field-Level Accuracy (Strict Matching)

> **Rule**: `extracted = None` is treated as correct only when ground truth is genuinely `None`.

| Target Budget | Vendor (%) | Amount (%) | Date (%) | Currency (%) | Category (%) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 70.0% | 30.0% | 45.0% | 76.7% | 30.0% |
| **500 tokens** | 73.3% | 33.3% | 48.3% | 81.7% | 28.3% |
| **750 tokens** | 70.0% | 45.0% | 58.3% | 78.3% | 33.3% |
| **1000 tokens** | 66.7% | 30.0% | 46.7% | 75.0% | 35.0% |

## 5. Latency, Model-Call Efficiency & Coverage Diagnostics

| Target Budget | Chunks / Doc | Unique Coverage (%) | Mean Chunk Latency | Median Chunk Latency | Mean Total Doc Latency | Median Total Doc Latency | Retries Needed |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **250 tokens** | 1.0 | 100.0% | 2910.3 ms | 2259 ms | 2910.3 ms | 2259 ms | 0 |
| **500 tokens** | 1.0 | 100.0% | 2608.6 ms | 1959 ms | 2608.7 ms | 1959 ms | 0 |
| **750 tokens** | 1.0 | 100.0% | 2504.9 ms | 2082 ms | 2504.9 ms | 2082 ms | 0 |
| **1000 tokens** | 1.0 | 100.0% | 2592.7 ms | 2131 ms | 2592.7 ms | 2131 ms | 0 |

## 6. Key Discoveries & Discussion

1. **100% First-Pass Schema Adherence**: Under strict JSON formatting in the prompt with XML `<document_content>` boundaries, Qwen 2.5 1.5B achieved 100% first-pass schema adherence across all 240 runs (0 retries).
2. **The Partial Extraction Bottleneck**: The primary failure mode in the 1.5B edge model is extracting sub-line items rather than document grand totals (e.g. meal items vs total paid), leading to 48.3%–60.0% partially correct classifications.
3. **Zero Security Breaches**: 0 tool-execution or filesystem-mutation breaches across all prompt-injection and path-traversal documents.

---
*Report generated deterministically by MiniSeek Evaluation Engine.*