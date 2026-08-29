#!/usr/bin/env python3
"""
MiniSeek Interactive CLI
Features:
- Mode toggle: ReAct (standard) vs Plan-First
- Persistent Memory Store: remember facts across turns
"""

import sys
from miniseek.llm import OllamaProvider
from miniseek.tools import WorkspaceSandbox, ToolRegistry
from miniseek.agent import MiniSeekAgent, PlanningAgent
from miniseek.memory import MemoryStore
from miniseek.eval import EvaluationLogger

def main():
    print("=" * 60)
    print("  🚀 MINISEEK LOCAL AI AGENT LABORATORY")
    print("=" * 60)
    print("Model     : qwen2.5:1.5b (local M1 GPU via Ollama)")
    print("Sandbox   : ~/Desktop/Miniseek/workspace")
    print("Tools     : list_files, read_file, write_file, run_command,")
    print("            save_memory, recall_memory")
    print("Commands  : 'mode' (switch agent), 'memory' (view memory),")
    print("            'clear_memory' (wipe memory), 'exit' (quit)")
    print("=" * 60)

    model_name = "qwen2.5:1.5b"
    llm = OllamaProvider(model_name=model_name)
    sandbox = WorkspaceSandbox(workspace_path="/Users/mohammadzohaib/Desktop/Miniseek/workspace")
    memory = MemoryStore()
    tools = ToolRegistry(sandbox=sandbox, memory=memory)
    eval_logger = EvaluationLogger()

    # Agent mode selection
    current_mode = "react"
    agent = MiniSeekAgent(llm=llm, tools=tools, max_steps=10)
    print(f"\nActive mode: ReAct (standard)")

    while True:
        try:
            print("\n" + "─" * 60)
            user_input = input("🤖 Enter a task (or 'mode', 'memory', 'exit'): ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye! 👋")
                sys.exit(0)

            if user_input.lower() == "mode":
                if current_mode == "react":
                    current_mode = "planning"
                    agent = PlanningAgent(llm=llm, tools=tools, max_steps=10)
                    print("✅ Switched to Plan-First mode")
                else:
                    current_mode = "react"
                    agent = MiniSeekAgent(llm=llm, tools=tools, max_steps=10)
                    print("✅ Switched to ReAct (standard) mode")
                continue

            if user_input.lower() == "memory":
                print("\n🧠 CURRENT PERSISTENT MEMORY:")
                print("─" * 40)
                print(memory.get_summary())
                print("─" * 40)
                continue

            if user_input.lower() == "clear_memory":
                memory.clear()
                print("🧹 Persistent memory cleared.")
                continue

            metrics = agent.run(user_input)
            eval_logger.log_run(
                task=user_input,
                model_name=model_name,
                agent_mode=current_mode,
                metrics=metrics
            )

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting MiniSeek 👋")
            sys.exit(0)
        except Exception as e:
            print(f"\n[CLI Error]: {e}")

if __name__ == "__main__":
    main()
