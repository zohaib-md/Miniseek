import json
from pathlib import Path
from typing import List, Optional, Union

from miniseek.core.types import RunManifest, OperationRecord

class HistoryManager:
    """
    Manages multi-run history stored in .miniseek/history/.
    Provides listing, lookup, and rendering of run manifests.
    """

    @classmethod
    def get_history_dir(cls, root_dir: Union[str, Path]) -> Path:
        return Path(root_dir) / ".miniseek" / "history"

    @classmethod
    def list_runs(cls, root_dir: Union[str, Path]) -> List[RunManifest]:
        """Lists all run manifests, sorted by timestamp (newest first)."""
        history_dir = cls.get_history_dir(root_dir)
        if not history_dir.exists():
            return []

        manifests = []
        for f in sorted(history_dir.glob("run-*.json"), reverse=True):
            try:
                manifest = cls.load_manifest(f)
                manifests.append(manifest)
            except Exception:
                continue
        return manifests

    @classmethod
    def get_run(cls, run_id: str, root_dir: Union[str, Path]) -> Optional[RunManifest]:
        """Loads a specific run manifest by run_id."""
        history_dir = cls.get_history_dir(root_dir)
        if not history_dir.exists():
            return None

        # Try exact filename match first
        exact_path = history_dir / f"{run_id}.json"
        if exact_path.exists():
            return cls.load_manifest(exact_path)

        # Search by run_id field in all manifests
        for f in history_dir.glob("run-*.json"):
            try:
                manifest = cls.load_manifest(f)
                if manifest.run_id == run_id:
                    return manifest
            except Exception:
                continue
        return None

    @classmethod
    def load_manifest(cls, manifest_path: Path) -> RunManifest:
        """Loads and reconstructs a RunManifest from a JSON file."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        operations = [
            OperationRecord(
                op_id=op["op_id"],
                type=op["type"],
                source_original=op["source_original"],
                destination_created=op["destination_created"],
                sha256=op["sha256"],
                size_bytes=op["size_bytes"],
                mtime=op["mtime"],
                status=op.get("status", "COMPLETED"),
                undo_status=op.get("undo_status"),
                undo_error=op.get("undo_error")
            )
            for op in data.get("operations", [])
        ]

        return RunManifest(
            run_id=data["run_id"],
            plan_id=data["plan_id"],
            plan_hash=data["plan_hash"],
            timestamp=data["timestamp"],
            root_path=data["root_path"],
            status=data["status"],
            operations=operations
        )

    @classmethod
    def save_manifest(cls, manifest: RunManifest, root_dir: Union[str, Path]) -> Path:
        """Persists a run manifest (used for incremental undo state updates)."""
        history_dir = cls.get_history_dir(root_dir)
        history_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = history_dir / f"{manifest.run_id}.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)
        return manifest_path

    @classmethod
    def render_history(cls, manifests: List[RunManifest]) -> str:
        """Renders an ASCII history table."""
        lines = [
            "═" * 78,
            "                     MINISEEK RUN HISTORY",
            "═" * 78,
            f"{'RUN ID':<36} {'DATE':<22} {'OPS':<6} {'STATUS':<20}",
            "─" * 78
        ]

        if not manifests:
            lines.append("  (No runs recorded)")
        else:
            for m in manifests:
                run_short = m.run_id[:34]
                date_str = m.timestamp[:19]
                ops_count = len(m.operations)
                lines.append(f"{run_short:<36} {date_str:<22} {ops_count:<6} {m.status:<20}")

        lines.extend([
            "═" * 78,
            f"  Total runs: {len(manifests)}",
            "═" * 78
        ])
        return "\n".join(lines)
