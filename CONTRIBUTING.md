# Contributing to MiniSeek 🚀

Thank you for your interest in contributing to **MiniSeek**!

MiniSeek is an experimental playground and practical AI agent laboratory exploring how far lightweight local models can be pushed on edge hardware (Apple Silicon M1, 8 GB RAM) through **Harness Engineering**.

---

## 🏛️ Core Architectural Invariants

Before contributing code, please ensure your changes adhere to MiniSeek's core design rules:

1. **The Model Proposes. The Harness Validates. Python Executes.**
   - Never grant the language model direct execution authority over the filesystem, shell, or network.
   - The model only outputs semantic suggestions (e.g. categories or entity strings).
   - Python validates proposals through the 6-layer pipeline before execution.

2. **Zero Heavy AI Framework Dependencies**:
   - The core library must remain **100% pure Python standard library** (no LangChain, AutoGen, CrewAI, or heavy ORMs).
   - All network calls to local inference engines (Ollama) must use Python's built-in `urllib.request`.

3. **Exact Mathematical Determinism**:
   - The LLM is strictly forbidden from performing arithmetic (no calculating totals, GST, or averages).
   - All mathematical operations must use Python's `decimal.Decimal` module to guarantee zero floating-point drift.

4. **Filesystem Safety & Symlink Security**:
   - All file operations must enforce canonical path validation (`os.path.realpath`) against approved sandbox roots.
   - Directory symlinks must never be traversed recursively; file symlinks must be safely reported and isolated.
   - File moves must adhere to the prime undo invariant: *MiniSeek never overwrites newer user files merely to undo itself.*

5. **100% Test Pass Rate**:
   - The test suite must remain lightning-fast (< 1 second) and passing at 100%.

---

## 🛠️ Development Setup

### Prerequisites
* Python 3.9+ (Python 3.11+ recommended)
* macOS with Apple Silicon (or Linux x86_64/arm64)
* [Ollama](https://ollama.ai) (optional for offline deterministic commands; required for semantic LLM inference)

### Repository Setup
```bash
# Clone the repository
git clone https://github.com/zohaib-md/Miniseek.git
cd Miniseek

# Make the launcher executable
chmod +x bin/miniseek

# (Optional) Link miniseek into your PATH
mkdir -p ~/.local/bin
ln -sf $(pwd)/bin/miniseek ~/.local/bin/miniseek
```

### Running Tests
MiniSeek includes a comprehensive, zero-dependency test suite:

```bash
# Run all 138 unit, security, and benchmark tests
python3 run_tests.py

# Or via standard unittest
python3 -m unittest discover tests
```

---

## 🧪 Benchmark & Dataset Guidelines

* All evaluation experiments must be reproducible and documented in `evaluation/`.
* When creating new golden test cases or adversarial datasets:
  - Ground-truth values must be validated against real-world sample documents.
  - Financial figures must be verifiable using exact Decimal arithmetic.
  - Adversarial samples (prompt injections, double extensions, traversal attacks) must have explicit expected outcomes.

---

## 📬 Submitting Changes

1. **Fork the repository** and create your branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Implement your changes**, ensuring clean formatting and docstrings.
3. **Add unit tests** in `tests/` covering both happy paths and edge/adversarial cases.
4. **Run the full test suite** (`python3 run_tests.py`) to verify 100% pass rate.
5. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git commit -m "feat(janitor): add support for custom category mapping rules"
   ```
6. **Push to your fork** and submit a Pull Request.

---

## 📄 License
By contributing to MiniSeek, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
