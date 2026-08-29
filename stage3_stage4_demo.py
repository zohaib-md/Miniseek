#!/usr/bin/env python3
"""
Stage 3 & Stage 4 Demo: First Agent & First Tool (list_files)
Demonstrates the agent receiving a user query, deciding to invoke `list_files()`,
observing the directory contents, and generating a final answer.
"""

from miniseek.llm import OllamaProvider
from miniseek.tools import WorkspaceSandbox, ToolRegistry
from miniseek.agent import MiniSeekAgent

def main():
    # 1. Initialize local LLM Provider
    llm = OllamaProvider(model_name="qwen2.5:1.5b")

    # 2. Initialize Workspace Sandbox & Tool Registry
    sandbox = WorkspaceSandbox(workspace_path="/Users/mohammadzohaib/Desktop/Miniseek/workspace")
    tools = ToolRegistry(sandbox=sandbox)

    # 3. Create Agent
    agent = MiniSeekAgent(llm=llm, tools=tools)

    # 4. Run Task
    user_task = "What files and folders are currently inside my workspace?"
    final_answer = agent.run(user_task)

    print("\nFINAL ANSWER RETURNED TO USER:")
    print("-" * 50)
    print(final_answer)
    print("-" * 50)

if __name__ == "__main__":
    main()
