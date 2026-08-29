#!/usr/bin/env python3
"""
MiniSeek Experiment 2: ReAct vs Plan-First Agent Benchmark
═══════════════════════════════════════════════════════════

Question:
  "Does forcing a 1.5B model to create an explicit plan before acting
   reduce unnecessary steps and tool calls compared to ReAct?"

Method:
  1. Reset workspace to a known buggy state (calculator.py has a * instead of /)
  2. Run Agent A (ReAct) on the bug-fix task → record metrics
  3. Reset workspace again to the same buggy state
  4. Run Agent B (Plan-First) on the same task → record metrics
  5. Print a side-by-side comparison table

Both agents use the same model (qwen2.5:1.5b), same tools, same sandbox.
"""

import shutil
from pathlib import Path
from miniseek.llm import OllamaProvider
from miniseek.tools import WorkspaceSandbox, ToolRegistry
from miniseek.agent import MiniSeekAgent, PlanningAgent
from miniseek.eval import EvaluationLogger

# ─── Constants ───────────────────────────────────────────────
WORKSPACE = "/Users/mohammadzohaib/Desktop/Miniseek/workspace"
MODEL = "qwen2.5:1.5b"
TASK = (
    "Find why the tests are failing by running "
    "'python3 -m unittest test_calculator.py', "
    "inspect and fix the problem in calculator.py, "
    "and verify that the tests pass."
)

# ─── Buggy source files to reset between runs ───────────────

CALCULATOR_BUGGY = """\
def add(a, b):
    return a + b

def divide(a, b):
    'Divides a by b. Raises ValueError if b is 0.'
    if b == 0:
        raise ValueError('Cannot divide by zero')
    return a * b  # BUG: multiplication instead of division
"""

TEST_FILE = """\
import unittest
from calculator import add, divide

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(3, 4), 7)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)

if __name__ == '__main__':
    unittest.main()
"""


def reset_workspace():
    """Resets calculator.py to the buggy version and restores the test file."""
    ws = Path(WORKSPACE)
    # Clear pycache to avoid stale bytecode
    pycache = ws / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)

    (ws / "calculator.py").write_text(CALCULATOR_BUGGY)
    (ws / "test_calculator.py").write_text(TEST_FILE)
    print("[Benchmark] Workspace reset to buggy state.\n")


def main():
    print("=" * 70)
    print("  MINISEEK EXPERIMENT 2: ReAct vs Plan-First Agent Benchmark")
    print("=" * 70)
    print(f"  Model : {MODEL}")
    print(f"  Task  : {TASK[:80]}...")
    print("=" * 70)

    llm = OllamaProvider(model_name=MODEL)
    eval_logger = EvaluationLogger()
    results = []

    # ─── Run A: ReAct Agent ──────────────────────────────────
    print("\n\n" + "▶" * 35)
    print("  AGENT A: ReAct (Standard)")
    print("▶" * 35)
    reset_workspace()
    sandbox_a = WorkspaceSandbox(workspace_path=WORKSPACE)
    tools_a = ToolRegistry(sandbox=sandbox_a)
    agent_a = MiniSeekAgent(llm=llm, tools=tools_a, max_steps=10)
    metrics_a = agent_a.run(TASK)
    metrics_a["agent_mode"] = "react"
    eval_logger.log_run(task=TASK, model_name=MODEL, agent_mode="react", metrics=metrics_a)
    results.append(metrics_a)

    # ─── Run B: Planning Agent ───────────────────────────────
    print("\n\n" + "▶" * 35)
    print("  AGENT B: Plan-First")
    print("▶" * 35)
    reset_workspace()
    sandbox_b = WorkspaceSandbox(workspace_path=WORKSPACE)
    tools_b = ToolRegistry(sandbox=sandbox_b)
    agent_b = PlanningAgent(llm=llm, tools=tools_b, max_steps=10)
    metrics_b = agent_b.run(TASK)
    metrics_b["agent_mode"] = "planning"
    eval_logger.log_run(task=TASK, model_name=MODEL, agent_mode="planning", metrics=metrics_b)
    results.append(metrics_b)

    # ─── Comparison ──────────────────────────────────────────
    eval_logger.print_comparison(results)


if __name__ == "__main__":
    main()
