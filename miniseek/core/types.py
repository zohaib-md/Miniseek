import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

class PlanStatus:
    """Execution lifecycle state machine for reorganization plans."""
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    ROLLED_BACK = "ROLLED_BACK"
    PARTIALLY_ROLLED_BACK = "PARTIALLY_ROLLED_BACK"

class OperationStatus:
    """Per-operation state machine for discrete filesystem actions."""
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ROLLED_BACK = "ROLLED_BACK"

class UndoStatus:
    """Per-operation undo state machine."""
    PENDING = "UNDO_PENDING"
    UNDONE = "UNDONE"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class RunUndoStatus:
    """Run-level undo state machine: COMMITTED -> UNDOING -> UNDONE."""
    UNDOING = "UNDOING"
    UNDONE = "UNDONE"
    UNDO_PARTIAL = "UNDO_PARTIAL"
    UNDO_FAILED = "UNDO_FAILED"

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
class NeedsReviewItem:
    """Record of an abstained or ambiguous file excluded from move operations."""
    file_path: str
    relative_path: str
    reason: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class PlanItem:
    """A single proposed file move action within an immutable plan."""
    operation_id: int
    source_path: str
    destination_path: str
    category: str
    source_sha256: str
    source_size: int
    status: str = OperationStatus.PENDING
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Plan:
    """An immutable, validated reorganization plan with cryptographic plan hash."""
    plan_id: str
    plan_hash: str
    root_path: str
    created_at: str
    status: str = PlanStatus.VALIDATED
    operations: List[PlanItem] = field(default_factory=list)
    needs_review: List[NeedsReviewItem] = field(default_factory=list)
    model_metadata: Dict[str, Any] = field(default_factory=dict)

    def canonical_dict(self) -> Dict[str, Any]:
        """Deterministic canonical representation for hashing and audit."""
        return {
            "plan_id": self.plan_id,
            "root_path": self.root_path,
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "source_path": op.source_path,
                    "destination_path": op.destination_path,
                    "category": op.category,
                    "source_sha256": op.source_sha256,
                    "source_size": op.source_size
                }
                for op in sorted(self.operations, key=lambda x: x.operation_id)
            ],
            "needs_review": [
                {
                    "file_path": nr.file_path,
                    "reason": nr.reason
                }
                for nr in sorted(self.needs_review, key=lambda x: x.file_path)
            ]
        }

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 of the canonical plan structure."""
        canonical_json = json.dumps(self.canonical_dict(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "root_path": self.root_path,
            "created_at": self.created_at,
            "status": self.status,
            "model_metadata": self.model_metadata,
            "operations_count": len(self.operations),
            "needs_review_count": len(self.needs_review),
            "operations": [op.to_dict() for op in self.operations],
            "needs_review": [nr.to_dict() for nr in self.needs_review]
        }

@dataclass
class ExecutionResult:
    """Outcome of a transactional plan execution run."""
    plan_id: str
    plan_hash: str
    status: str
    operations_total: int
    operations_completed: int
    operations_failed: int
    operations_blocked: int
    executed_operations: List[PlanItem] = field(default_factory=list)
    error_message: Optional[str] = None
    manifest_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "status": self.status,
            "operations_total": self.operations_total,
            "operations_completed": self.operations_completed,
            "operations_failed": self.operations_failed,
            "operations_blocked": self.operations_blocked,
            "error_message": self.error_message,
            "manifest_path": self.manifest_path,
            "executed_operations": [op.to_dict() for op in self.executed_operations]
        }

@dataclass
class OperationRecord:
    """Record of an executed filesystem operation, with undo tracking."""
    op_id: int
    type: str  # "MOVE"
    source_original: str
    destination_created: str
    sha256: str
    size_bytes: int
    mtime: float
    status: str = "COMPLETED"
    undo_status: Optional[str] = None
    undo_error: Optional[str] = None

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
    status: str  # "COMMITTED", "FAILED", "PARTIALLY_EXECUTED", "ROLLED_BACK", "PARTIALLY_ROLLED_BACK"
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

@dataclass
class UndoResult:
    """Outcome of a safe undo operation on a specific run."""
    run_id: str
    status: str  # RunUndoStatus values
    operations_total: int
    operations_undone: int
    operations_conflict: int
    operations_not_applicable: int
    conflict_details: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "operations_total": self.operations_total,
            "operations_undone": self.operations_undone,
            "operations_conflict": self.operations_conflict,
            "operations_not_applicable": self.operations_not_applicable,
            "conflict_details": self.conflict_details,
            "error_message": self.error_message
        }
