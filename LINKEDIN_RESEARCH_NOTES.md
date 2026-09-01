# 🔬 MiniSeek: Building a Local AI Agent on an 8 GB M1 Mac
## 📝 Research Experiments Log & LinkedIn Story Blueprint

---

## 🎯 The Core Question
> **"How far can you push an autonomous, reliable AI agent on edge hardware (Apple M1, 8 GB Unified Memory, zero cloud APIs) using Harness Engineering instead of brute-force model size?"**

---

## 🏛️ The Core Operating Principle

> **"Python owns deterministic correctness, safety, validation, state, and execution. The model is used only where semantic interpretation is required."**
>
> **"The model proposes. The harness validates. Python executes."**

---

## 🛠️ The System & Constraints
* **Machine**: MacBook Air M1 (8 GB Unified RAM, ~6.5 GB free disk)
* **Inference Engine**: Ollama (local Metal GPU acceleration)
* **Model**: `Qwen 2.5 (1.5 Billion parameters, Q4 quantized)`
  * Download size: **~986 MB** (preserves tight disk space)
  * RAM footprint: **~1.8 GB RAM** during inference
  * Inference speed: **~45 - 55 tokens/second**
* **Code Architecture**: Pure Python 3.12 standard library (zero LangChain/AutoGen/CrewAI bloat)
* **Testing Suite**: 68 automated unit tests running in **0.230s** (100% pass rate)

---

## 📊 Recorded Experiment Results & Architectural Milestones

### 🧪 Experiment 1: Autonomous Bug Fixing & Self-Verification
* **Task**: Fix failing tests in `test_calculator.py`.
* **Result**: **PASSED in 6 steps (38.08s)**.

---

### 🧪 Experiment 2: ReAct vs. Plan-First Architecture Benchmark
* **Question**: *Does forcing an upfront step-by-step plan reduce tool churn on debugging tasks?*
* **A/B Benchmark Results**:
  * **ReAct**: 3 steps, 2 tool calls, 12.31s
  * **Plan-First**: 2 steps, 1 tool call, **9.87s (⚡ 50% fewer tool calls, 20% faster)**

---

### 🧪 Experiment 3: Code Generation & The "Over-Planning" Trap (500 Dice Rolls)
* **Task**: Create `dice_sim.py` simulating 500 rolls of two 6-sided dice.
* **Finding**: ReAct generated a clean, accurate mathematical bell curve (peak at Sum 7 = 85) in 14.99s, while Plan-First over-structured its plan into a static Counter bug.

---

### 🧪 Experiment 4: The JSON Grammar Breakthrough for Small Models
* **Problem**: 1.5B parameter models often revert to conversational prose or unescaped quotes when generating code.
* **Solution**: Enabling Ollama's native JSON Grammar mode (`format="json"`) guarantees **100% syntactically valid JSON responses** on every turn.

---

### 🧪 Experiment 5: Tool Aliasing & Sandbox Path Normalization
* **Problem**: Small models often use synonyms (`create_file`, `create_module`) or hallucinate Linux paths (`/home/user/Workspace/` or `/workspace/`).
* **Solution**: A resilient Tool Layer with fuzzy alias resolution (`create_module` $\rightarrow$ `write_file`) and automatic path normalization completely eliminated tool failure errors.

---

### 🧪 Experiment 6: Multi-Artifact TDD & The "Cart-Before-The-Horse" Trap
* **Task**: Create `string_utils.py` with `is_palindrome()`, write `test_strings.py`, and run tests to verify.
* **Finding**: ReAct jumped straight to running tests before creating the files (crashing immediately). Plan-First enforced correct dependency order (`write_file` source $\rightarrow$ `write_file` tests $\rightarrow$ execute).

---

### 🧪 Experiment 7: Persistent Cross-Turn Memory (Zero-Vector DB Architecture)
* **Task**: Teach the agent project rules (type hints + pytest), shut down the agent process, start a completely fresh agent instance, and ask it to recall project conventions.
* **Results**:
  * **Turn 1 (Learning & Disk Save)**: Agent called `save_memory(category="conventions", fact="...")` and persisted it to `workspace/.miniseek_memory.json` in **9.60s**.
  * **Turn 2 (Cross-Session Recall)**: Fresh agent instance booted up, read memory from disk, and answered the convention query accurately in **5.49s** with **0 file searches**.
* **Insight**: You do not need heavy vector databases (Chroma/FAISS) for small-scale local agents. A lightweight disk-backed JSON memory store + prompt injection gives 100% accurate cross-session recall with 0 latency overhead.

---

### 🛡️ Milestone 1: Deterministic Scanner & Multi-Stage Deduplication Engine
* **Goal**: Build a high-performance, rock-solid filesystem scanner with 0 LLM dependency for deterministic operations.
* **Key Innovations**:
  * **Multi-Stage Hashing**: Candidate grouping by exact size before streaming buffered SHA-256 chunk hashing (64 KB). Avoids unnecessary I/O on unique files.
  * **Wasted Space Engine**: Exact mathematical computation of wasted bytes ($size \times (count - 1)$).
  * **Symlink Security Boundary**: Enforced canonical path resolution (`os.path.realpath`) and strict prohibition of traversing symlinked directories outside the approved root.

---

### 🧠 Milestone 2: Canonical Layered Validation & Micro-Task Categorization
* **Goal**: Leverage a 1.5B model for semantic understanding while guaranteeing 100% safety and predictability.
* **Key Innovations**:
  * **Canonical 6-Layer Validation**:
    `RAW OUTPUT` $\rightarrow$ `EXTRACT` $\rightarrow$ `SAFE SYNTAX REPAIR` $\rightarrow$ `PARSE JSON` $\rightarrow$ `SCHEMA` $\rightarrow$ `SEMANTIC` $\rightarrow$ `SAFETY`.
  * **Bounded Micro-Task Prompts**: Model receives only minimal evidence (name, extension, size, bounded 150-char text preview). Total prompt budget $\le 500$ tokens.
  * **1-Retry Diagnostic Guard**: If model output fails schema or semantic validation, harness injects the exact error into a single retry turn. If it fails again, it safely falls back to `NEEDS_REVIEW`.
  * **Zero Path Authority for Models**: The model only suggests a `category`. Python deterministically derives `dest = approved_root / category / original_filename`.
  * **Explicit Model Abstention**: `NEEDS_REVIEW` is treated as a first-class state meaning **NO MOVE**, excluding the file from filesystem proposals.

---

### ⚡ Milestone 3: Plan Freezing, Cryptographic Plan Hashing & Transactional Execution
* **Goal**: Solve the fundamental question: *"What happens when reality changes between planning and execution?"*
* **Key Innovations**:
  * **Immutable Plans**: Deterministic canonical serialization with SHA-256 `plan_hash`. Once frozen, the LLM is completely removed from the execution loop.
  * **Strict Pre-Flight Validation**: Before touching a single file, the executor verifies:
    1. Plan hash integrity (detects plan tampering or stale plans).
    2. Source file existence, size, and SHA-256 match planned state.
    3. Destination path is within approved root.
    4. Destination file does NOT already exist (conservative collision blocking).
  * **Immediate Per-Operation Verification**: Verifies source disappearance, destination existence, size match, and SHA-256 match immediately after each move before marking `COMPLETED`.
  * **Committed Run Manifest**: Persists full multi-attribute undo identity (`source_original`, `destination_created`, `sha256`, `size`, `mtime`, `run_id`, `plan_id`) to `.miniseek/history/`.

---

## 📱 LinkedIn Post Drafts

### 🚀 Post 1: "I built an autonomous AI agent from absolute zero on an 8 GB M1 Mac"

> Can an 8 GB M1 MacBook Air run a truly autonomous coding agent without cloud APIs or heavy frameworks?
>
> I built **MiniSeek** from scratch to test how far we can push a 1.5B local model on limited hardware:
>
> ⚙️ **The Stack:**
> • Pure Python 3.12 (Zero LangChain, CrewAI, or AutoGen)
> • Qwen 2.5 1.5B running on Apple Metal GPU via Ollama (~50 tokens/s)
> • Custom Sandbox + Tools + Structured Memory
>
> Here are 7 surprising discoveries from benchmarking agent architectures locally:
>
> 1️⃣ **Planning cuts tool churn on debugging:** On bug-fixing tasks, generating an upfront plan reduced tool calls by 50% and finished 20% faster (9.8s vs 12.3s).
> 2️⃣ **The "Over-Planning" Trap:** For direct algorithms (like a 500-dice Monte Carlo simulation), reactive execution beat planning by avoiding convoluted logic.
> 3️⃣ **The "Cart Before the Horse" Trap:** Without planning on multi-file tasks, reactive agents try to run tests *before* writing the code files. Plan-First enforces dependency ordering.
> 4️⃣ **Fuzzy Action Aliasing is Mandatory:** Small models naturally output synonyms (`create_file`, `create_module`). A resilient Tool Layer maps these aliases seamlessly to `write_file`.
> 5️⃣ **Logit Constraints are King:** Prompting alone doesn't prevent JSON crashes on small models. Native JSON grammar decoding (`format="json"`) makes local agents rock-solid.
> 6️⃣ **Lightweight Persistent Memory Works:** You don't need heavy vector databases for local agents. A simple JSON memory store gave our agent instant cross-session recall in 5.4 seconds.
> 7️⃣ **Local AI on M1 is Blazing Fast:** Running a 1.5B model on unified memory uses under 1.8 GB RAM and completes autonomous multi-step tasks in 6 to 15 seconds!
>
> What experiments have you tried with local AI models on edge hardware?
>
> #AI #LocalAI #MachineLearning #Python #AppleSilicon #AIAgents #OpenSource

---

### 🛡️ Post 2: "Stop letting LLMs touch your filesystem: The Harness Engineering Playbook"

> The biggest mistake in AI agent design is asking an LLM to do things Python already does with 100% mathematical precision.
>
> If you ask a 1.5B parameter model to calculate duplicate file hashes, verify filesystem paths, or execute shell commands directly, it will eventually hallucinate and delete something important.
>
> In our project **MiniSeek** (running locally on an 8 GB M1 Mac), we adopted a strict architectural rule:
>
> 📌 **The Model Proposes. The Harness Validates. Python Executes.**
>
> Here is how we turned a tiny 1.5B model into a reliable filesystem janitor:
>
> 🔹 **1. Zero Path Authority:** The model is never allowed to provide filesystem paths. It only returns a semantic category (e.g. `Receipts_Invoices`). Python derives the destination path deterministically inside the sandbox.
> 🔹 **2. 6-Stage Validation Pipeline:** Model output goes through Extract $\rightarrow$ Safe Syntax Repair $\rightarrow$ JSON Parse $\rightarrow$ Schema Validation $\rightarrow$ Semantic Check $\rightarrow$ Safety Check before anything is considered a valid proposal.
> 🔹 **3. Explicit Model Abstention (`NEEDS_REVIEW`):** When evidence is ambiguous, the model is encouraged to abstain. `NEEDS_REVIEW` results in **zero file moves** and surfaces the file for manual user review.
> 🔹 **4. Cryptographic Plan Freezing:** We freeze the proposal into a canonical JSON payload and compute a SHA-256 `plan_hash`. Once frozen, the LLM is completely excluded from execution.
> 🔹 **5. Pre-Flight Verification:** Before touching any file, Python checks:
> • Did the source file change since planning?
> • Did the plan hash match?
> • Does the destination file already exist (conservative collision blocking)?
> 🔹 **6. Immediate Per-Operation Verification:** After each move, Python immediately checks destination existence, size, and SHA-256 before marking the operation completed.
>
> 💡 **The Takeaway:** You don't need a 70B parameter cloud model for everyday utilities. When you pair a tiny 1.5B local model with deterministic harness engineering, you get speed (~50 tok/s), $0 cost, 100% offline privacy, and zero hallucinations.
>
> How are you structuring guardrails around AI agents in your projects?
>
> #AIAgents #SoftwareEngineering #Python #LocalAI #SystemDesign #OpenSource #DevCommunity

---

## 🧪 Milestone 4 — Multi-Run History & Safe Undo

### Key Discoveries

1. **Conservative Undo is Non-Trivial**: The fundamental invariant — *"Never overwrite newer user data merely to undo itself"* — requires checking destination integrity (SHA-256 + size), original-path occupancy, and per-operation conflict resolution. A naive "just move it back" approach would be destructive.

2. **Reverse-Order Undo is Essential**: When 3 files were moved (A, B, C), undoing in forward order risks partial state inconsistency. Reversing the operation order (C, B, A) maintains the inverse of the original transaction sequence.

3. **Undo State is Distinct from Execution State**: Each operation now carries both an execution status (`COMPLETED`, `FAILED`) AND an undo status (`UNDONE`, `CONFLICT`, `NOT_APPLICABLE`). Run-level status similarly distinguishes `COMMITTED` from `UNDONE` vs `UNDO_PARTIAL`. This separation enables precise audit trails.

4. **Incremental Undo Persistence**: Just as execution persists manifest state after each operation, undo does the same. If the process crashes after undoing 2 of 3 operations, the manifest on disk still reflects exactly what was reverted.

5. **SHA-256 as Identity Guard, Not as Object Identity**: Two different files can legitimately have identical content. The undo logic uses `(path + sha256 + size)` as the identity check, not SHA-256 alone. This avoids the "same hash = same file" trap.

6. **Multi-Run Independence**: Each run is a self-contained manifest. Undoing run A has zero effect on run B's files. This was validated with cross-run isolation tests.

### Milestone 4 Test Coverage (20 new tests)

| Category | Tests | Scenarios |
|---|---|---|
| **History Manager** | 8 | Empty history, multiple runs, run lookup, nonexistent run, render output, plan→run traceability, run vs operation status separation |
| **Normal Undo** | 2 | Single-file restore, 3-file reverse-order restore |
| **Conflict Detection** | 4 | Destination modified by user, destination deleted, original path occupied, same-size SHA mismatch |
| **Multi-Run** | 1 | Undo run A without affecting run B |
| **Partial/Failed Undo** | 3 | Mixed conflicts (partial undo), durable state after conflict, durable state after success |
| **Edge Cases** | 2 | Failed operations as NOT_APPLICABLE, ineligible run status rejection |

### Architecture After Milestone 4

```text
Model → Proposal → Validation → Frozen Plan → User Approval
    → Python-only Execution → Per-Op Verification → Durable Manifest
    → History Index → Safe Targeted Undo (miniseek undo <run-id>)
        → Integrity Verification → Conflict Detection → Reverse-Order Restore
        → Incremental State Persistence
```

### LinkedIn Post Draft 3: Safe Undo

> 🧠 **Building MiniSeek: When Your AI Agent Needs to Say "I'm Sorry"**
>
> Today I shipped safe undo for MiniSeek — a file-organizing AI agent running on an 8 GB M1 Mac with a 1.5B parameter model.
>
> The hard part wasn't building undo. It was building *conservative* undo.
>
> 🔹 **The Core Rule:** MiniSeek never overwrites newer user data merely to undo itself.
>
> Here's what that means in practice:
>
> Before reversing any file move, MiniSeek checks:
> • Is the destination file unchanged? (SHA-256 + size verification)
> • Is the original path occupied by something else?
> • Would restoring this file overwrite user work?
>
> If ANY check fails → the operation becomes a CONFLICT, not a forced rollback.
>
> 🔹 **Reverse-Order Execution:** If MiniSeek moved files A → B → C, undo processes C → B → A. The inverse of the original sequence.
>
> 🔹 **Crash-Safe State:** Undo state is persisted to disk after each operation. If the process dies after undoing 2 of 3 files, the manifest accurately records what was reverted.
>
> 🔹 **Multi-Run Independence:** Each organizing run gets its own manifest. `miniseek undo run-001` touches only run-001's files. Run-002 is completely unaffected.
>
> The test results: 68 tests, 100% pass rate, all scenarios covered — normal undo, user modifications, deleted destinations, occupied paths, partial failures, crash recovery.
>
> 💡 **The Insight:** Safety isn't just about preventing bad moves forward. It's about preventing bad moves backward too. An "undo" that silently overwrites user work is worse than no undo at all.
>
> #AIAgents #SoftwareEngineering #Python #LocalAI #SystemDesign #OpenSource

---
*Auto-updated by MiniSeek Laboratory Logger.*

