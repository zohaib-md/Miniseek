import json
from pathlib import Path
from typing import Dict, List, Any, Optional

class MemoryStore:
    """Persistent structured memory store for MiniSeek agents."""

    def __init__(self, memory_file_path: str = "/Users/mohammadzohaib/Desktop/Miniseek/workspace/.miniseek_memory.json"):
        self.memory_file = Path(memory_file_path)
        self.memories: Dict[str, List[str]] = self._load()

    def _load(self) -> Dict[str, List[str]]:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self):
        """Persists memories to disk."""
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, indent=2)

    def add_fact(self, category: str, fact: str):
        """Adds a fact under a specific category (e.g. 'conventions', 'learnings', 'environment')."""
        cat = category.strip().lower()
        if cat not in self.memories:
            self.memories[cat] = []
        if fact not in self.memories[cat]:
            self.memories[cat].append(fact)
            self.save()

    def get_summary(self) -> str:
        """Formats all stored memories for inclusion in system prompt."""
        if not self.memories:
            return "(No persistent memories stored yet)"
        
        lines = []
        for cat, facts in self.memories.items():
            lines.append(f"[{cat.upper()}]:")
            for f in facts:
                lines.append(f"  • {f}")
        return "\n".join(lines)

    def clear(self):
        """Clears all stored memories."""
        self.memories = {}
        if self.memory_file.exists():
            self.memory_file.unlink()
