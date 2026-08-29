import json
import time
from pathlib import Path
from typing import Dict, Any, List

class EvaluationLogger:
    """Logs MiniSeek agent experiment telemetry to a lightweight JSONL file."""

    def __init__(self, log_path: str = "/Users/mohammadzohaib/Desktop/Miniseek/experiments_log.jsonl"):
        self.log_file = Path(log_path)

    def log_run(self, task: str, model_name: str, agent_mode: str, metrics: Dict[str, Any]):
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "task": task,
            "model": model_name,
            "agent_mode": agent_mode,
            "status": metrics.get("status", "UNKNOWN"),
            "steps": metrics.get("steps", 0),
            "tool_calls": metrics.get("tool_calls", 0),
            "failed_tool_calls": metrics.get("failed_tool_calls", 0),
            "execution_time_sec": metrics.get("execution_time_sec", 0.0),
            "plan_steps": metrics.get("plan_steps", None),
            "plan_time_sec": metrics.get("plan_time_sec", None),
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        print(f"[EvaluationLogger] Metrics logged to {self.log_file.name}")

    def print_comparison(self, records: List[Dict[str, Any]]):
        """Pretty-prints a side-by-side comparison table of experiment results."""
        if not records:
            return

        print("\n" + "═" * 70)
        print("EXPERIMENT COMPARISON TABLE")
        print("═" * 70)
        header = f"{'Metric':<25} "
        for r in records:
            header += f"{'│ ' + r['agent_mode']:<20}"
        print(header)
        print("─" * 70)

        metrics = [
            ("Status", "status"),
            ("Steps", "steps"),
            ("Tool Calls", "tool_calls"),
            ("Failed Tool Calls", "failed_tool_calls"),
            ("Plan Steps", "plan_steps"),
            ("Plan Time (s)", "plan_time_sec"),
            ("Total Time (s)", "execution_time_sec"),
        ]

        for label, key in metrics:
            row = f"{label:<25} "
            for r in records:
                val = r.get(key, "—")
                if val is None:
                    val = "—"
                row += f"│ {str(val):<18}"
            print(row)

        print("═" * 70 + "\n")
