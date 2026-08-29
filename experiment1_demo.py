#!/usr/bin/env python3
"""
MiniSeek Experiment 1: Autonomous Bug Fix & Verification Loop
Demonstrates MiniSeek identifying test failures, reading code, fixing bugs, verifying tests pass,
and logging experiment telemetry to JSONL.
"""

from miniseek.llm import OllamaProvider
from miniseek.tools import WorkspaceSandbox, ToolRegistry
from miniseek.agent import MiniSeekAgent
from miniseek.eval import EvaluationLogger

def main():
    # 1. Local LLM Provider
    model_name = "qwen2.5:1.5b"
    llm = OllamaProvider(model_name=model_name)

    # 2. Workspace Sandbox (/workspace) & Tools
    sandbox = WorkspaceSandbox(workspace_path="/Users/mohammadzohaib/Desktop/Miniseek/workspace")
    tools = ToolRegistry(sandbox=sandbox)

    # 3. MiniSeek Agent & Evaluation Logger
    eval_logger = EvaluationLogger()
    agent = MiniSeekAgent(llm=llm, tools=tools, max_steps=10)

    # 4. User Experiment Task
    task = "Find why the tests are failing by running 'python3 -m unittest test_calculator.py', inspect and fix the problem in calculator.py, and verify that the tests pass."
    
    # 5. Execute Agent Loop
    metrics = agent.run(task)

    # 6. Record Telemetry to JSONL Evaluation Log
    eval_logger.log_run(task=task, model_name=model_name, metrics=metrics)

if __name__ == "__main__":
    main()
