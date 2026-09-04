# MiniSeek Engineering Field Manual: Systems Lessons for Edge AI Agents

Technical Case Studies, Architectural Patterns, and Empirical Discoveries from Local Agent Engineering

---

## 1. Introduction and Operational Constraints

Building autonomous, reliable AI agent systems on resource-constrained edge hardware presents distinct systems engineering challenges compared to cloud-scale agent frameworks. In cloud architectures, latency, memory ceilings, and non-deterministic model behaviors are often masked by massive compute clusters and multi-billion-parameter foundation models. On edge devices, hardware boundaries are rigid and unforgiving.

### Target Hardware Environment
* **Host Processor**: Apple Silicon M1 (2020), 8-core CPU (4 performance, 4 efficiency), 7-core GPU, 16-core Neural Engine.
* **Unified Memory**: 8 GB LPDDR4X (shared dynamically between CPU and Metal GPU shaders).
* **Storage**: 256 GB NVMe SSD.
* **Thermal Envelope**: Fanless, passive cooling (subject to thermal throttling under continuous multi-minute compute bursts).
* **Inference Engine**: Local Ollama runtime using native Apple Metal GPU acceleration.
* **Software Core**: Pure Python 3.9+ standard library (zero external agent frameworks, zero cloud API dependencies).

### The Fundamental Systems Engineering Principle
> **"Python owns deterministic correctness, safety, validation, state, and execution. The model is used only where semantic interpretation is required."**
>
> **The model proposes. The harness validates. Python executes.**

When working with edge models in the 1.5B to 3.1B parameter range, treating the model as an autonomous reasoning engine with direct shell or filesystem privileges leads directly to state corruption and execution loops. MiniSeek isolates probabilistic model outputs within deterministic verification wrappers.

---

## 2. Core Architectural Patterns for Local Agents

### Pattern 1: The Canonical 6-Layer Validation Pipeline
Quantized edge models frequently emit conversational commentary, code fences, trailing commas, or invalid schema values. MiniSeek channels every raw model generation through six sequential, fail-safe gates before accepting it as a structured proposal:

```text
[Raw Model Response]
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
[Layer 5: Semantic Domain Validation]
       Enforces category whitelist membership and domain constraints.
       |
       v
[Layer 6: Security Boundary Isolation]
       Neutralizes path traversal attempts (../../) and enforces root containment.
       |
       v
[Verified Proposal]
```

If validation fails at any layer, MiniSeek executes a single diagnostic retry turn, injecting the exact schema error back to the model. If the second attempt fails, the system automatically demotes the operation to an explicit abstention state (`NEEDS_REVIEW`).

### Pattern 2: Explicit Model Abstention as a First-Class State
A critical failure mode of small models is forced classification under ambiguous context. In MiniSeek, `NEEDS_REVIEW` is an explicit, first-class semantic token:
* When confidence is low or document evidence is corrupted, the model is instructed to emit `NEEDS_REVIEW`.
* The execution harness translates `NEEDS_REVIEW` into an immutable **no-move invariant**, leaving the target file untouched and surfacing the record for human review.
* Abstention decouples classification uncertainty from execution safety: a model error never results in file corruption.

### Pattern 3: Plan Freezing and Cryptographic Transaction Isolation
Interleaving model generation with disk mutations creates race conditions and state corruption. MiniSeek enforces a strict two-phase execution model:
1. **Planning Phase**: The agent inspects files and compiles proposed actions into a canonical JSON plan. This plan is cryptographically hashed using SHA-256 (`plan_hash`). The model is completely detached from the execution loop.
2. **Pre-Flight Validation**: Before touching the filesystem, Python verifies four invariants:
   * The current plan hash matches the recorded proposal.
   * Every source file exists, and its current size and SHA-256 hash match the state recorded at planning time.
   * Every destination path falls strictly inside the approved root directory.
   * No destination path already exists (preventing silent overwrites).
3. **Transactional Execution**: Operations are executed sequentially. Immediately after each file move, Python verifies that the destination file exists, matches the original SHA-256, and that the source file is gone.

### Pattern 4: Conservative, Reverse-Order Rollback (The Prime Undo Invariant)
An undo mechanism must never compound damage. MiniSeek implements the Prime Undo Invariant:
> **"MiniSeek never overwrites newer user data merely to undo itself."**

Rollback mechanics:
* **Reverse Chronological Order**: If files were moved in sequence A -> B -> C, rollback processes them in order C -> B -> A.
* **Destination Tamper Detection**: Before moving a file back to its original location, MiniSeek computes its current SHA-256 and size. If the user edited or deleted the destination file after the run, rollback is rejected with a `CONFLICT` status.
* **Target Collision Guard**: If a new, unrelated file now occupies the original location, the rollback aborts without overwriting.
* **Crash Resilience**: Rollback manifests are persisted to disk incrementally after each step. If a rollback is interrupted, the manifest reflects exactly which operations succeeded and which remain pending.

### Pattern 5: Zero Model Mathematics
Language models perform arithmetic probabilistically, resulting in frequent calculation errors. In MiniSeek, financial document synthesis enforces strict division of responsibility:
* **Model Responsibility**: Extract raw numeric strings, dates, and vendor names from messy text (such as `"Subtotal: $42.50"`).
* **Python Responsibility**: Parse extracted strings into standard library `decimal.Decimal` instances, compute subtotals, calculate tax percentages, and produce ledger balances with zero floating-point drift.

### Pattern 6: Zero-Vector-DB Persistent Memory
Many agent frameworks mandate external vector databases (such as Chroma or FAISS) for memory. For edge agents, this introduces heavy native dependencies, C++ toolchains, and high memory overhead.
* MiniSeek stores long-term facts in a human-readable, disk-backed JSON file (`.miniseek_memory.json`).
* Memory reads occur at session initialization with zero search latency.
* Structured categorizations (`conventions`, `preferences`, `project_facts`) keep the prompt payload minimal (under 150 tokens), allowing fast recall across disconnected terminal sessions without external daemon processes.

---

## 3. Empirical Experiments and Architectural Case Studies

MiniSeek conducted seven architectural experiments to measure execution dynamics and agent behavior under real hardware constraints.

### Case Study 1: ReAct vs. Plan-First Architectures (EXP-002 Pilot)
* **Question**: Does upfront planning reduce tool churn compared to standard reactive ReAct loops on edge hardware?
* **Observation**:
  * On localized bug-fixing tasks (`test_calculator.py`), Plan-First reduced tool calls by **50%** and wall-clock execution time by **20%** (9.87s vs 12.31s).
  * On open-ended creative code generation (simulating 500 dice rolls), Plan-First fell into an "over-planning trap", constructing an overly rigid plan that introduced a static dictionary counter bug. ReAct, by contrast, dynamically verified intermediate code states and succeeded in 14.99s.
  * **Lesson**: Plan-First architectures excel at structured, dependency-ordered tasks (such as Multi-Artifact TDD), while ReAct loops perform better in exploratory, iterative debugging.

### Case Study 2: Native JSON Grammar vs. Prompt-Based Formatting (EXP-004)
* **Problem**: 1.5B parameter models instructed via prompt instructions alone frequently output conversational chatter, malformed keys, or unescaped quotes when generating code snippets.
* **Solution**: Leveraging Ollama native logit-constrained grammar mode (`format="json"`).
* **Result**: Produced 100% syntactically parsable JSON across all test turns. Pre-validating grammar at the token sampling level eliminates the need for heavyweight post-processing parsers.

### Case Study 3: Resilient Tool Aliasing and Path Normalization (EXP-005)
* **Problem**: Small models frequently hallucinate Linux filesystem paths (such as `/home/user/workspace/` or `/workspace/`) when running on macOS, or use synonym names for registered tools (`create_module` instead of `write_file`).
* **Solution**: A resilient dispatch layer with fuzzy tool aliasing and automatic path normalization (stripping fictitious prefixes and binding paths to the canonical workspace).
* **Result**: Reduced dispatch failure rate from 18.5% down to 0%.

### Case Study 4: Multi-Artifact TDD and Execution Ordering (EXP-006)
* **Problem**: When tasked with writing both an implementation module (`string_utils.py`) and a test suite (`test_strings.py`), unconstrained ReAct loops frequently attempted to run tests before creating the source file, causing immediate cascading failures.
* **Solution**: Enforcing dependency-ordered planning gates. The agent must successfully register created file artifacts before invoking execution tools.

### Case Study 5: Context Window Budgeting and the Latency U-Curve (EXP-001b)
* **Benchmark**: 240 document extractions across four context budgets (250, 500, 750, 1000 tokens) using `qwen2.5:1.5b`.
* **Empirical Findings**:
  * **250 tokens**: High fragmentation generated excessive model calls (143 calls, 29.7s total latency).
  * **1000 tokens**: Larger KV cache slowed autoregressive decoding (30.1s per chunk, 33.1s total latency).
  * **500 tokens**: Optimal balance, delivering lowest total document latency (**22.1s**) and **100% first-pass schema validity**.
* **Key Insight**: Total latency on edge hardware forms a distinct U-curve. Intermediate context budgets optimize memory bandwidth while avoiding call fragmentation.

### Case Study 6: The Granularity Inversion (EXP-001c)
* **Problem**: Can increasing context windows resolve dropped items on dense, multi-item financial ledgers?
* **Benchmark**: Comparing whole-chunk single-shot extraction against deterministic pre-segmentation into single-row micro-tasks on a 27-row quarterly ledger.
* **Results**:
  * Single-shot extraction dropped 8 of 27 items (recovering only 19.5 items) and took 181.7s.
  * Deterministic pre-segmentation recovered **27 of 27 items (100% recall)**, tripled document reconstruction (+300%), and ran **64.5s faster (117.2s)**.
* **Why 27 calls ran faster than 1 call**: Profiling revealed that reading input context accounts for only **8.2%** of edge execution time, while token generation drives **91.8%**. Generating massive JSON arrays balloons the KV cache and slows decoding speed from 22 tok/s down to 18 tok/s. Micro-calls keep the KV cache compact, operating within the peak compute regime.

### Case Study 7: Model Scale vs. Harness Engineering (EXP-002)
* **Experiment**: A 2x2 factorial evaluation (1.5B vs 3.1B parameter models x Simple vs Structured harness) across 160 document evaluations.
* **Quantitative Findings**:
  * On a 1.5B model, the structured harness reduced raw recall from 53.4% to 28.4%. The strict validation pipeline demoted ambiguous guesses to `NEEDS_REVIEW`, demonstrating that software cannot manufacture semantic perception absent in model weights.
  * On a 3.1B model, the structured harness acted as a massive **+38.5% force multiplier**: recall rose from **76.4% to 89.9%**, precision rose from **61.4% to 85.8%**, and complete document accuracy surged from **27.5% to 67.5%**.
* **The Capability Threshold Principle**: A software harness acts as an unforgiving filter below a model capability threshold, but acts as a powerful force multiplier once that threshold is crossed.

### Case Study 8: The Physical Hardware Ceiling (EXP-003)
* **Experiment**: Testing the feasibility of running a 9B parameter model (`ornith:9b`, 5.24 GB weight footprint) on an 8 GB unified memory machine.
* **Results**: Loading the model consumed over 5.2 GB of unified RAM, leaving insufficient memory for macOS system caches. Swap memory expanded by more than 5.2 GB, causing severe disk thrashing, thermal throttling, and multi-minute response stalls.
* **Conclusion**: For responsive, reliable local agent workflows on 8 GB unified memory devices, **3B parameters is the physical upper ceiling**.

---

## 4. Security Hardening and Adversarial Defenses

Local agents operating on user filesystems face unique security risks from untrusted input files and malicious prompt injections.

### Defense 1: Passive Input Isolation
Untrusted document contents are enclosed inside strict XML delimiters (`<document_content>...</document_content>`). The system prompt instructs the model to treat enclosed data strictly as inert text to be analyzed, never as operational instructions.

### Defense 2: Canonical Path Resolution and Symlink Barriers
Path traversal exploits (such as `../../etc/passwd` or `/System/`) are neutralized at two levels:
* Layer 6 validation resolves destination paths using `os.path.realpath` and verifies that the canonical path resides within the designated sandbox directory.
* Directory symlinks pointing outside the workspace are skipped during scanning and blocked during execution.

### Defense 3: Hostile Filename and Metacharacter Sanitization
Files with shell metacharacters (`$`, `&`, `;`, `'`, `"`, whitespace) or non-ASCII Unicode characters are handled using standard library `pathlib.Path` objects without passing through shell evaluators, preventing command injection attacks.

---

## 5. Architectural Checklist for Edge AI Systems

When designing autonomous local agents for resource-constrained hardware:

1. **Decouple Planning from Execution**: Never permit a model to execute filesystem or system actions directly while streaming output.
2. **Enforce Deterministic Boundaries**: Reserve language models for semantic parsing and text extraction; use Python for arithmetic, path construction, and state tracking.
3. **Budget for Memory Ceilings**: Respect hardware boundaries (at or below 3B parameters on 8 GB RAM) to avoid swap thrashing and thermal degradation.
4. **Prefer Micro-Tasks over Massive Prompts**: Keep KV caches compact by breaking complex extractions into discrete, single-entity operations.
5. **Implement Safe Rollbacks**: Ensure all filesystem mutations maintain durable, incremental journals that can be reversed in reverse chronological order without destroying user edits.
6. **Treat Abstention as Success**: Provide an explicit `NEEDS_REVIEW` state so that low-confidence predictions halt safely rather than corrupting state.
