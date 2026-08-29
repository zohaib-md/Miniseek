from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class FileInfo:
    """Metadata for a scanned file."""
    path: str
    relative_path: str
    name: str
    extension: str
    size_bytes: int
    mtime: float
    sha256: Optional[str] = None
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DuplicateGroup:
    """Group of files that share identical SHA-256 hashes."""
    sha256: str
    size_bytes: int
    files: List[FileInfo] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Wasted disk space = size * (count - 1)."""
        if len(self.files) > 1:
            return self.size_bytes * (len(self.files) - 1)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "wasted_bytes": self.wasted_bytes,
            "files": [f.to_dict() for f in self.files]
        }

@dataclass
class ScanResult:
    """Complete summary of a deterministic directory scan."""
    root_path: str
    total_files: int
    total_bytes: int
    files: List[FileInfo] = field(default_factory=list)
    skipped_symlinks: List[FileInfo] = field(default_factory=list)
    duplicate_groups: List[DuplicateGroup] = field(default_factory=list)
    scan_duration_sec: float = 0.0

    @property
    def total_wasted_bytes(self) -> int:
        return sum(dg.wasted_bytes for dg in self.duplicate_groups)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_path": self.root_path,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "total_wasted_bytes": self.total_wasted_bytes,
            "scan_duration_sec": self.scan_duration_sec,
            "files_count": len(self.files),
            "skipped_symlinks_count": len(self.skipped_symlinks),
            "duplicate_groups_count": len(self.duplicate_groups),
            "files": [f.to_dict() for f in self.files],
            "skipped_symlinks": [f.to_dict() for f in self.skipped_symlinks],
            "duplicate_groups": [dg.to_dict() for dg in self.duplicate_groups]
        }

@dataclass
class PlanItem:
    """A single proposed file move action within an immutable plan."""
    source_path: str
    destination_path: str
    category: str
    evidence: Dict[str, Any]
    sha256: str
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Plan:
    """An immutable, validated reorganization plan with cryptographic plan hash."""
    plan_id: str
    plan_hash: str
    root_path: str
    items: List[PlanItem] = field(default_factory=list)
    created_at: str = ""
    model_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "root_path": self.root_path,
            "created_at": self.created_at,
            "model_metadata": self.model_metadata,
            "items": [item.to_dict() for item in self.items]
        }

@dataclass
class OperationRecord:
    """Record of an executed filesystem operation."""
    op_id: int
    type: str  # "MOVE"
    source_original: str
    destination_created: str
    sha256: str
    size_bytes: int
    mtime: float
    status: str = "COMPLETED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RunManifest:
    """Committed record of an executed run for multi-run history and safe undo."""
    run_id: str
    plan_id: str
    plan_hash: str
    timestamp: str
    root_path: str
    status: str  # "COMMITTED", "FAILED", "ROLLED_BACK", "PARTIALLY_ROLLED_BACK"
    operations: List[OperationRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "timestamp": self.timestamp,
            "root_path": self.root_path,
            "status": self.status,
            "operations": [op.to_dict() for op in self.operations]
        }
