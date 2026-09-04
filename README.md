# MiniSeek

<p align="center">
  <b>A Lightweight, Local-First AI Agent Laboratory on Edge Hardware</b><br>
  <i>Deterministic Harness Engineering on Apple Silicon (M1 / 8 GB Unified Memory)</i><br>
  100% Offline | Zero Cloud APIs | Zero Third-Party Framework Dependencies | Pure Python 3.9+
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/Tests-138%20Passing%20(0.13s)-brightgreen.svg" alt="Tests: 138 Passing"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Hardware-Apple%20M1%20(8GB)-orange.svg" alt="Target Hardware">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20(Stdlib)-success.svg" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Architecture-Deterministic%20Harness-informational.svg" alt="Architecture">
</p>

---

## Executive Summary

MiniSeek is an experimental systems engineering laboratory and lightweight agent harness designed for resource-constrained edge hardware. Operating entirely offline on an Apple MacBook Air M1 (8 GB RAM, 256 GB SSD, fanless), MiniSeek evaluates how far deterministic software engineering can compensate for model parameter scale.

Rather than relying on heavyweight agent orchestration frameworks, cloud endpoints, or external vector databases, MiniSeek is implemented using only the Python standard library. It pairs small local models (1.5B to 3.1B parameters) running via Ollama and Apple Metal GPU acceleration with strict deterministic validation gates, transaction journals, and exact arithmetic engines.

### The Core Operating Invariant

> **"Python owns deterministic correctness, safety, validation, state, and execution. The model is used only where semantic interpretation is required."**
>
> **The model proposes. The harness validates. Python executes.**

---

## Core Architectural Invariants

MiniSeek enforces seven non-negotiable architectural invariants across all subcommands and pipelines:

1. **Zero Direct Execution Authority**:
   Probabilistic language models never hold direct execution privileges over the filesystem, system shells, or network sockets. The model generates structured semantic proposals; Python evaluates, sanitizes, and executes them.

2. **Zero Model Mathematics**:
   Small quantized language models frequently hallucinate basic arithmetic and financial calculations. In MiniSeek, the model is strictly limited to extracting raw numeric and entity tokens. Python parses values into standard library `decimal.Decimal` objects and performs all arithmetic with complete precision.

3. **Zero Path Authority**:
   When categorizing files, the model is prohibited from emitting filesystem paths or directory hierarchies. It emits only predefined semantic category tokens (such as `Documents` or `Receipts_Invoices`). Python deterministically maps approved categories to sandbox directories and enforces boundary checks.

4. **Explicit Abstention as a First-Class State**:
   When document context is ambiguous, corrupted, or low-confidence, the model is instructed to emit an explicit `NEEDS_REVIEW` token. The harness translates this into an immutable no-move guarantee, excluding the target file from modification and queueing it for human inspection.

5. **Plan Freezing and Transactional Safety**:
   No file modification occurs during analysis. MiniSeek compiles proposed operations into an immutable, cryptographically hashed JSON execution plan (`plan_hash`). Execution requires pre-flight state validation: verifying source file existence, checking destination collision paths, and recalculating source content hashes. Any divergence aborts the transaction immediately.

6. **The Prime Undo Invariant**:
   MiniSeek never overwrites newer user files merely to undo an earlier run. Rollbacks process recorded transaction journals in reverse order, verifying destination integrity before restoring original files. If an external conflict is detected, MiniSeek preserves user state and halts the rollback.

7. **Zero Third-Party Dependency Footprint**:
   The entire core architecture (filesystem traversal, multi-stage duplicate detection, JSON schema repair, transaction journals, CLI interfaces, and testing) relies exclusively on Python standard library modules (`os`, `sys`, `pathlib`, `hashlib`, `json`, `decimal`, `sqlite3`, `unittest`).

---

## System Architecture

```text
                                +---------------------------+
                                |       MiniSeek CLI        |
                                |  (scan, dedupe, organize, |
                                |   undo, expenses, agent)  |
                                +-------------+-------------+
                                              |
                                +-------------v-------------+
                                |    Pipeline Controller    |
                                |   (Generic Orchestrator)  |
                                +------+-------------+------+
                                       |             |
                    +------------------v--+       +--v------------------+
                    |    Application:     |       |    Application:     |
                    |    File Janitor     |       | Expense Synthesizer |
                    |  (Milestones 1-5)   |       |  (Zero LLM Math)    |
                    +------------------+--+       +--+------------------+
                                       |             |
                                +------v-------------v------+
                                |    Deterministic Core     |
                                | ------------------------- |
                                | * Path & Symlink Barrier  |
                                | * SHA-256 Deduplication   |
                                | * 6-Layer Validation Gate |
                                | * Transaction Manager     |
                                | * Decimal Math Engine     |
                                +-------------+-------------+
                                              |
                                +-------------v-------------+
                                |      Semantic Layer       |
                                |  (Micro-Task Dispatcher)  |
                                +-------------+-------------+
                                              |
                                +-------------v-------------+
                                |    Local Model Engine     |
                                |   (Ollama / Metal GPU)    |
                                +---------------------------+
```

### The Canonical 6-Layer Validation Pipeline

Every raw generation emitted by local models passes through six deterministic validation gates before acceptance:

```text
[RAW MODEL OUTPUT]
       |
       v
[Layer 1: Boundary Extraction]
       Strips markdown fences, preambles, and conversational artifacts.
       |
       v
[Layer 2: Safe Syntax Repair]
       Repairs trailing commas, missing delimiters, and unescaped quotes.
       |
       v
[Layer 3: Structural JSON Parse]
       Enforces standard deserialization via Python json.loads().
       |
       v
[Layer 4: Schema Validation]
       Verifies required keys, value types, and confidence ranges [0.0, 1.0].
       |
       v
[Layer 5: Semantic Validation]
       Enforces category whitelist membership and domain constraints.
       |
       v
[Layer 6: Security Boundary Isolation]
       Neutralizes path traversal attempts (../../) and enforces root containment.
       |
       v
[VERIFIED SEMANTIC PROPOSAL]
```

---

## Empirical Research Findings

MiniSeek was developed alongside rigorous empirical benchmarking on an Apple MacBook Air M1 (8 GB Unified Memory, fanless). The findings challenge common assumptions regarding model size, context windows, and software engineering in local agent systems.

### Benchmark Summary

| Experiment | Focus Area | Evaluated Conditions | Key Takeaway |
| :--- | :--- | :--- | :--- |
| **EXP-001b** | Context Window Budgeting | 250 vs 500 vs 750 vs 1000 tokens | **500 tokens is the latency sweet spot.** Larger windows degrade decoding speed without improving multi-item extraction. |
| **EXP-001c** | Task Granularity | Monolithic Single-Shot vs Micro-Tasking | **27 micro-calls completed 64.5s faster than 1 giant call (-35.5% latency)** while tripling document recovery (+300%). |
| **EXP-002** | Model Scale vs Harness | 2x2 Factorial (1.5B vs 3.1B x Simple vs Structured) | Harness cannot invent perception a 1.5B model lacks, but acts as a **+38.5% force multiplier** once past the 3B parameter threshold. |
| **EXP-003** | Edge Hardware Ceiling | 9B Model Feasibility on 8 GB Unified Memory | **3B parameters is the practical upper limit for 8 GB M1 hardware.** 9B models induce massive swap thrashing (>5.2 GB) and thermal throttling. |

### Key Discoveries

#### 1. The Latency U-Curve (EXP-001b)
Evaluating 240 document extractions across four context budgets revealed that total latency forms a U-curve:
* **250 tokens**: Fragmented context caused excessive roundtrips (143 calls, 29.7s total document latency).
* **1000 tokens**: KV cache overhead reduced generation throughput (30.1s per chunk, 33.1s total document latency).
* **500 tokens**: Achieved the optimal balance between token density and autoregressive decoding throughput (22.1s total document latency, 100% schema validity).

#### 2. The Granularity Inversion (EXP-001c)
On dense financial ledgers (such as 27 items across complex layouts), single-shot context expansion resulted in dropped rows (recovering only 19.5 of 27 items). Deterministic pre-segmentation into isolated single-row micro-tasks:
* Recovered 27 out of 27 items (100% entity recall).
* Tripled fully reconstructed documents (+300%).
* Completed **64.5s faster** (117.2s vs 181.7s) because reading input takes only 8.2% of edge execution time, while generation accounts for 91.8%. Compact generation outputs kept decoding at maximum memory bandwidth.

#### 3. The Capability Threshold and Harness Multiplier (EXP-002)
A 160-evaluation factorial benchmark tested model scale against software harness architecture:
* On a 1.5B model, structured harness validation reduced hallucinated recall from 53.4% to 28.4% by strictly demoting ambiguous guesses to `NEEDS_REVIEW`. Software cannot manufacture semantic understanding absent in the weights.
* On a 3.1B model, the structured harness acted as a massive amplifier:
  * Recall climbed from **76.4% to 89.9%**.
  * Precision climbed from **61.4% to 85.8%**.
  * Complete document accuracy surged from **27.5% to 67.5%**.
  * Dense ledger recall reached **91.0%** (111 of 122 items).

#### 4. The 8 GB Memory Barrier (EXP-003)
Testing a 9B model (`ornith:9b`, 5.24 GB weight footprint) on an 8 GB unified memory machine demonstrated severe system-level bottlenecks:
* macOS swap memory expanded by more than 5.2 GB, causing severe disk thrashing.
* Autoregressive throughput dropped into thermal and memory stalls.
* **Conclusion**: 3B parameters represents the physical capability and performance ceiling for responsive local agents on 8 GB unified memory architectures.

---

## Installation & Setup

MiniSeek requires Python 3.9 or higher and has zero external package dependencies beyond the Python standard library.

### 1. Clone the Repository

```bash
git clone https://github.com/zohaib-md/Miniseek.git
cd Miniseek
```

### 2. Configure the CLI Launcher

MiniSeek includes a standalone launcher in `bin/miniseek`:

```bash
# Make launcher executable
chmod +x bin/miniseek

# Link into user PATH (optional)
mkdir -p ~/.local/bin
ln -sf "$(pwd)/bin/miniseek" ~/.local/bin/miniseek
```

Alternatively, invoke MiniSeek directly using standard Python:

```bash
python3 miniseek_cli.py --help
# or
python3 -m miniseek.cli --help
```

### 3. Configure Local LLM Backend (Optional for Semantic Operations)

For semantic categorization, document synthesis, and interactive agent modes, ensure Ollama is installed and running locally:

```bash
# Install Ollama (macOS)
brew install ollama

# Pull recommended edge models
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
```

Deterministic operations (`scan`, `dedupe`, `history`, `undo`, `version`) function completely offline with zero model dependency.

---

## CLI Command Reference

### Command Summary

| Command | Primary Function | Deterministic Guarantee | Local LLM Required |
| :--- | :--- | :--- | :--- |
| `miniseek scan <path>` | Directory inspection, extensions, symlink audit | 100% Deterministic | No |
| `miniseek dedupe <path>` | Multi-stage streaming SHA-256 duplicate detection | 100% Deterministic | No |
| `miniseek organize <path>` | Semantic file organization with plan freeze | Harness-Guided | Yes |
| `miniseek history` | Audit trail of past organization runs | 100% Deterministic | No |
| `miniseek undo <run-id>` | Safe, reverse-order transactional rollback | 100% Deterministic | No |
| `miniseek expenses <path>` | Financial document ingestion with Decimal math | Zero LLM Math | Yes |
| `miniseek agent` | Interactive local agent laboratory | Sandboxed Execution | Yes |
| `miniseek benchmark` | Offline benchmark evaluation runner | 100% Deterministic | Yes |
| `miniseek version` | Environment profile and diagnostic check | 100% Deterministic | No |

---

### Command Details and Examples

#### 1. Deterministic Directory Scanner: `miniseek scan`

Recursively scans directory contents, analyzes file sizes, maps extension distributions, and audits symlink boundaries without traversing directory symlinks:

```bash
# Scan a folder with default settings
miniseek scan ./samples

# Include hidden files and dotfiles
miniseek scan ./samples --hidden
```

#### 2. Multi-Stage Duplicate Detection: `miniseek dedupe`

Identifies duplicate files using a three-stage zero-waste pipeline:
1. Size-based candidate pre-filtering (eliminates disk I/O on unique file sizes).
2. Streaming 64 KB chunked SHA-256 hashing.
3. Exact mathematical computation of reclaimable storage: `size * (count - 1)`.

```bash
miniseek dedupe ~/Downloads
```

#### 3. Semantic Organization: `miniseek organize`

Classifies unstructured files into standardized categories (`Documents`, `Receipts_Invoices`, `Media_Images`, `Code`, `Archives_Data`), freezes the proposal into an immutable plan, and executes transactional moves:

```bash
# Preview plan, target paths, and cryptographic plan hash without moving files
miniseek organize ./MessyFolder --dry-run

# Execute organization with interactive confirmation
miniseek organize ./MessyFolder

# Execute using a specific local model with auto-approval
miniseek organize ./MessyFolder --model qwen2.5:3b --auto-approve
```

#### 4. Audit History: `miniseek history`

Displays an auditable log of past organization runs, including timestamp, plan hash, affected file counts, and run identifiers:

```bash
miniseek history
```

#### 5. Transactional Rollback: `miniseek undo`

Reverses a previous organization run in reverse chronological order. Before each move, it verifies destination file integrity via SHA-256 and ensures the original source path is unoccupied:

```bash
miniseek undo <run-id>
```

#### 6. Financial Expense Synthesizer: `miniseek expenses`

Processes unstructured receipts, invoices, and CSV files. Employs micro-task decomposition to extract raw line items and passes all currency amounts to Python standard `decimal.Decimal` engine:

```bash
miniseek expenses ./samples/receipts --output ./reports
```

#### 7. Interactive Agent Playground: `miniseek agent`

Provides an interactive CLI interface to compare ReAct reasoning loops against Plan-First execution models with persistent cross-turn memory:

```bash
# Launch planning-mode agent
miniseek agent --mode planning

# Launch standard reactive agent
miniseek agent --mode react
```

#### 8. System Diagnostics: `miniseek version`

Displays the local runtime environment, OS architecture, memory profile, and Ollama connection status:

```bash
miniseek version
```

---

## Repository Structure

```text
Miniseek/
|-- bin/
|   `-- miniseek                      # Standalone shell launcher
|-- docs/
|   |-- ARCHITECTURE.md               # Detailed system design and invariants
|   |-- CLI_REFERENCE.md              # Complete CLI subcommand specification
|   `-- RESEARCH_FINDINGS.md          # Empirical benchmarks and data tables
|-- evaluation/
|   |-- benchmarks/                   # Standard benchmark harness and runner
|   |-- datasets/                     # Synthetic financial and document suites
|   `-- experiments/                  # Reproducible test scripts (EXP-001 to EXP-003)
|-- miniseek/
|   |-- __init__.py
|   |-- cli.py                        # Unified command-line interface
|   |-- ui.py                         # Terminal rendering and table formatting
|   |-- agent/                        # Autonomous loop, memory, and telemetry
|   |-- applications/
|   |   |-- janitor/                  # File categorization and planning
|   |   `-- synthesizer/              # Receipt ingestion and Decimal math
|   |-- core/
|   |   |-- dedupe.py                 # Multi-stage SHA-256 duplicate engine
|   |   |-- path_security.py          # Symlink barriers and path traversal guards
|   |   |-- scanner.py                # Deterministic directory walker
|   |   |-- transaction.py            # Plan freezing and execution journal
|   |   |-- undo.py                   # Reverse-order transactional rollback
|   |   `-- validation.py             # Canonical 6-layer validation pipeline
|   `-- models/                       # Zero-dependency local Ollama HTTP client
|-- samples/                          # Sample receipts, invoices, and test folders
|-- tests/                            # Comprehensive automated test suite
|-- miniseek_cli.py                   # Root entry-point wrapper
|-- pyproject.toml                    # Package build specification
|-- run_tests.py                      # Test runner
`-- README.md                         # Project documentation
```

---

## Testing & Verification

MiniSeek includes an automated test suite covering all deterministic core modules, security boundaries, validation layers, transaction lifecycles, and edge conditions.

Run the test suite using standard Python:

```bash
python3 run_tests.py
```

Expected test suite output:

```text
Ran 138 tests in 0.127s

OK
=======================================================
Total Tests Run: 138
Errors: 0, Failures: 0
Overall Status: SUCCESS (ALL PASS)
=======================================================
```

Key test coverage areas:
* **Path Security**: Verification of canonical realpath resolution, symlink evasion prevention, and traversal rejection.
* **6-Layer Validation**: Unit tests for code-fence extraction, syntax repair, schema enforcement, category whitelisting, and bounds checking.
* **Transaction Durability**: Verification of atomic manifests, pre-flight collision rejection, and rollback ordering.
* **Adversarial Injection**: Validation of prompt injection containment, ensuring injected instructions in documents remain passive text.
* **Decimal Precision**: Exact accounting validation across multi-currency ledgers with zero floating-point drift.

---

## Documentation Links

* [CLI Reference Manual](docs/CLI_REFERENCE.md): Full documentation for all commands, parameters, and flags.
* [System Architecture Specification](docs/ARCHITECTURE.md): Deep architectural overview, design philosophy, and security models.
* [Empirical Research Findings](docs/RESEARCH_FINDINGS.md): Detailed benchmark methodology, raw data, and statistical analysis.
* [Contributing Guidelines](CONTRIBUTING.md): Code standards, commit conventions, and development practices.
* [License](LICENSE): MIT License terms.

---

## License

MiniSeek is open-source software licensed under the [MIT License](LICENSE).
