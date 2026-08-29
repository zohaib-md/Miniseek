# MiniSeek 🚀

> **Lightweight Local AI Agent Laboratory on Edge Hardware (Apple Silicon M1 / 8 GB RAM)**

MiniSeek is an experimental playground and practical AI agent laboratory designed from absolute zero to answer one core question:

> **How far can we push a lightweight local AI agent on limited hardware (8 GB RAM, 256 GB SSD) using Harness Engineering?**

---

## 🎯 Core Operating Principle

> **Python owns deterministic correctness, safety, validation, state, and execution. The model is used only where semantic interpretation is required.**
>
> **The model proposes. The harness validates. Python executes.**

---

## 🛠️ System & Design Constraints

* **Target Hardware**: MacBook Air M1 (8 GB Unified RAM, 256 GB SSD)
* **Inference Backend**: Ollama (`qwen2.5:1.5b` Q4 quantized)
  * Download Size: **~986 MB** (preserves tight disk space)
  * RAM Footprint: **< 1.8 GB RAM** during inference
  * Inference Speed: **~45 - 55 tokens/second** on Apple Metal GPU
* **Zero Cloud APIs**: 100% offline, $0.00 cost, private on-device execution.
* **Pure Python Core**: Zero dependency on heavy AI frameworks (no LangChain, AutoGen, or CrewAI).

---

## 🏛️ Architecture Overview

```text
                               ┌─────────────────────────┐
                               │      MiniSeek CLI       │
                               │  (scan, duplicates,     │
                               │   organize, undo, ...)  │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │   Pipeline Controller   │
                               │ (Generic Orchestrator)  │
                               └──────┬───────────┬──────┘
                                      │           │
                    ┌─────────────────▼──┐     ┌──▼─────────────────┐
                    │    Application:    │     │    Application:    │
                    │    File Janitor    │     │ Expense Synthesizer│
                    │ (Milestones 1-5)   │     │    (Subsequent)    │
                    └─────────────────┬──┘     └──┬─────────────────┘
                                      │           │
                               ┌──────▼───────────▼──────┐
                               │   Deterministic Core    │
                               │ ─────────────────────── │
                               │ • Path & Symlink Guard  │
                               │ • SHA-256 Deduplication │
                               │ • Layered Validation    │
                               │ • Transaction Manager   │
                               │ • Exact Math Engine     │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │     Semantic Layer      │
                               │ (Micro-Task Dispatcher) │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │   Local Model / Engine  │
                               │ (Qwen 2.5 1.5B / Ollama)│
                               └─────────────────────────┘
```

---

## 📊 Roadmap & Progress

- [x] **Stage 0-1**: Environment inspection & local model inference (`Ollama` + `Qwen 2.5 1.5B`).
- [x] **Stage 2-5**: Zero-dependency Python LLM client & sandboxed tool registry.
- [x] **Stage 6-8**: Autonomous agent loop, live telemetry, and persistent cross-turn memory.
- [x] **Stage 9-14**: 7 Architectural benchmarks & experiments (ReAct vs. Plan-First, JSON grammar modes, loop detection).
- [x] **Milestone 1**: Deterministic scanner & multi-stage SHA-256 duplicate engine with canonical path & symlink security.
- [ ] **Milestone 2**: Semantic categorization & 5-layer validation engine.
- [ ] **Milestone 3**: Plan freezing, dry-run previews, and transactional execution.
- [ ] **Milestone 4**: Multi-run history and robust undo rollback.
- [ ] **Milestone 5**: Golden dataset benchmarks and adversarial test suite.

---

## 🧪 Testing

Run the automated test suite:

```bash
python3 -m unittest discover tests
```

---

## 📄 License

MIT License. Built with ❤️ for developers and creators on edge hardware.
