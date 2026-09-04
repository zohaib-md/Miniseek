# 📖 MiniSeek CLI Reference Manual

The `miniseek` CLI provides local-first, deterministic tools for filesystem management, deduplication, semantic organization, financial document synthesis, and local AI agent interaction.

---

## 🚀 Global Options

```bash
miniseek [--version | -V] [--host HOST] <subcommand> [options]
```

* `--version`, `-V`: Prints version, Python runtime, host OS architecture, and Ollama connection status.
* `--host HOST`: Custom Ollama API server endpoint (default: `http://127.0.0.1:11434`).

---

## 🛠️ Subcommands Summary

| Subcommand | Description | LLM Required? |
| :--- | :--- | :---: |
| [`miniseek scan`](#1-miniseek-scan) | Deterministic directory inspection, extensions, and symlink audit | ❌ No |
| [`miniseek dedupe`](#2-miniseek-dedupe) | Multi-stage SHA-256 duplicate finder & wasted space calculator | ❌ No |
| [`miniseek organize`](#3-miniseek-organize) | Semantic file categorization, plan freezing & safe transaction execution | ✅ Yes |
| [`miniseek history`](#4-miniseek-history) | View past organization audit manifests and execution logs | ❌ No |
| [`miniseek undo`](#5-miniseek-undo) | Safe, conservative reverse-order rollback of previous runs | ❌ No |
| [`miniseek expenses`](#6-miniseek-expenses) | Ingest receipts/invoices/CSVs and synthesize auditable reports | ✅ Yes |
| [`miniseek agent`](#7-miniseek-agent) | Interactive local AI agent playground (ReAct vs Plan-First) | ✅ Yes |
| [`miniseek benchmark`](#8-miniseek-benchmark) | Run deterministic offline accuracy and adversarial benchmarks | ✅ Yes |
| [`miniseek version`](#9-miniseek-version) | Print diagnostic status and hardware environment profile | ❌ No |

---

## 1. `miniseek scan`

Deterministically scans a target directory, extracts file sizes, classifies extensions, and audits directory boundaries without following directory symlinks.

```bash
miniseek scan <path> [--hidden]
```

### Options:
* `path`: Absolute or relative path to target directory.
* `--hidden`: Include hidden files (dotfiles) and hidden directories.

### Example:
```bash
miniseek scan ./my_folder
```

---

## 2. `miniseek dedupe`

Detects exact byte duplicates using a high-performance multi-stage pipeline:
1. Size-based candidate pre-filtering (eliminates disk I/O on unique files).
2. Streaming 64 KB chunked SHA-256 hashing.
3. Exact mathematical computation of wasted bytes: $\text{size} \times (\text{count} - 1)$.

```bash
miniseek dedupe <path>
```

### Example:
```bash
miniseek dedupe ~/Downloads
```

---

## 3. `miniseek organize`

Classifies files into semantic categories (`Documents`, `Receipts_Invoices`, `Media_Images`, `Code`, `Archives_Data`, `UNCATEGORIZED`, `NEEDS_REVIEW`) using a local quantized model, freezes the proposal into an immutable plan, and executes transactional file moves.

```bash
miniseek organize <path> [--model MODEL] [--dry-run | -d] [--auto-approve | -y]
```

### Options:
* `path`: Target directory to organize.
* `--model MODEL`, `-m MODEL`: Local model tag in Ollama (default: `qwen2.5:1.5b` or `qwen2.5:3b`).
* `--dry-run`, `-d`: Preview the plan, target destinations, and cryptographic hash without modifying any files.
* `--auto-approve`, `-y`: Proceed with execution without interactive confirmation.

### Invariants:
* **Zero Path Authority**: The model never specifies filesystem paths; Python derives them safely.
* **Explicit Abstention**: Files marked `NEEDS_REVIEW` are strictly excluded from move operations.

### Example:
```bash
# Preview plan safely
miniseek organize ./MessyFolder --dry-run

# Execute with approval
miniseek organize ./MessyFolder
```

---

## 4. `miniseek history`

Lists all recorded organization runs from `.miniseek/history/`.

```bash
miniseek history [--path PATH]
```

### Options:
* `--path PATH`, `-p PATH`: Root directory where organization was performed (default: current working directory).

---

## 5. `miniseek undo`

Safely reverts an organization run in reverse order (`C ➔ B ➔ A`).

```bash
miniseek undo <run-id> [--path PATH]
```

### Options:
* `run_id`: The identifier of the run to revert (e.g. `run-20260904-1234abcd`).
* `--path PATH`, `-p PATH`: Root directory containing the `.miniseek/history/` directory.

### The Prime Undo Invariant:
* *MiniSeek never overwrites newer user data merely to undo itself.*
* If destination files were modified, moved, or deleted after the original run, the operation is flagged as a safe `CONFLICT` and skipped.

---

## 6. `miniseek expenses`

Processes unorganized receipts, invoices, statements, CSVs, and markdown ledgers, extracts transaction entities, parses exact amounts, isolates currencies, and exports executive Markdown and CSV summaries.

```bash
miniseek expenses <path> [--output OUTPUT] [--model MODEL]
```

### Options:
* `path`: File or directory containing financial documents.
* `--output OUTPUT`, `-o OUTPUT`: Destination directory for reports (default: `./reports`).
* `--model MODEL`, `-m MODEL`: Local model tag.

### Invariants:
* **Zero LLM Math**: Python's `Decimal` module performs all calculations; the model is never allowed to sum or multiply numbers.
* **Multi-Currency Isolation**: USD, EUR, and INR totals are strictly aggregated in separate buckets.

---

## 7. `miniseek agent`

Launches the interactive local AI agent playground on Apple Silicon.

```bash
miniseek agent [--mode {react,planning}] [--model MODEL] [--workspace WORKSPACE]
```

### Options:
* `--mode`: Reasoning mode:
  * `react`: Fast iterative Thought $\to$ Action $\to$ Observation loop.
  * `planning`: Generates an upfront multi-step plan before execution (reduces tool churn on debugging).
* `--workspace WORKSPACE`, `-w WORKSPACE`: Path to the sandboxed scratch workspace.
* In-session commands: `mode` (toggle mode), `memory` (view stored facts), `exit` (quit).

---

## 8. `miniseek benchmark`

Executes reproducible evaluation benchmarks against golden standard or adversarial datasets without modifying the filesystem.

```bash
miniseek benchmark [--dataset DATASET] [--output OUTPUT]
```

---

## 9. `miniseek version`

Displays local environment diagnostics, Python version, platform architecture, and Ollama server status.

```bash
miniseek version
```
