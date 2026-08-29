#!/usr/bin/env python3
"""
MiniSeek Experiment 7: Persistent Memory Benchmark
══════════════════════════════════════════════════

Question:
  "Does persistent cross-turn memory allow the agent to remember project conventions
   and recall them in subsequent independent sessions without file search overhead?"

Method:
  Turn 1: Agent learns facts and saves them to persistent memory via `save_memory`.
  Turn 2: A brand new Agent instance is initialized with memory loaded from disk.
          We ask the new agent to recall the project rules and conventions.
"""

from miniseek.llm import OllamaProvider
from miniseek.tools import WorkspaceSandbox, ToolRegistry
from miniseek.agent import MiniSeekAgent
from miniseek.memory import MemoryStore
from miniseek.eval import EvaluationLogger

def main():
    print("=" * 70)
    print("  MINISEEK EXPERIMENT 7: Persistent Memory Benchmark")
    print("=" * 70)

    model_name = "qwen2.5:1.5b"
    llm = OllamaProvider(model_name=model_name)
    sandbox = WorkspaceSandbox(workspace_path="/Users/mohammadzohaib/Desktop/Miniseek/workspace")
    memory = MemoryStore()
    tools = ToolRegistry(sandbox=sandbox, memory=memory)
    eval_logger = EvaluationLogger()

    # ─── TURN 1: Learning & Storing Memory ──────────────────
    print("\n" + "▶" * 35)
    print("  TURN 1: Teaching the Agent Project Conventions")
    print("▶" * 35)
    
    agent1 = MiniSeekAgent(llm=llm, tools=tools, max_steps=5)
    task1 = "Save into memory that our project conventions require functions to have type hints, and that tests must be written with pytest."
    metrics1 = agent1.run(task1)
    eval_logger.log_run(task=task1, model_name=model_name, agent_mode="react_memory_save", metrics=metrics1)

    print(f"\n[Disk Check] Active Memory on Disk:")
    print(memory.get_summary())

    # ─── TURN 2: Fresh Agent Instance Recalling Facts ───────
    print("\n\n" + "▶" * 35)
    print("  TURN 2: Fresh Agent Instance Recalls Facts From Disk")
    print("▶" * 35)

    # Initialize a fresh memory store and agent instance
    fresh_memory = MemoryStore()
    fresh_tools = ToolRegistry(sandbox=sandbox, memory=fresh_memory)
    agent2 = MiniSeekAgent(llm=llm, tools=fresh_tools, max_steps=5)

    task2 = "What are our project conventions regarding function signatures and test runners?"
    metrics2 = agent2.run(task2)
    eval_logger.log_run(task=task2, model_name=model_name, agent_mode="react_memory_recall", metrics=metrics2)

if __name__ == "__main__":
    main()
