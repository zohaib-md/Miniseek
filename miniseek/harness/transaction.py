import os
import json
import time
import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from miniseek.core.types import (
    Plan, PlanItem, PlanStatus, OperationStatus,
    ExecutionResult, OperationRecord, RunManifest
)
from miniseek.core.security import PathSecurity, SecurityError
from miniseek.applications.janitor.scanner import FileScanner

class PreFlightError(Exception):
    """Raised when pre-flight validation fails prior to execution."""
    pass

class ExecutionVerificationError(Exception):
    """Raised when post-operation verification fails immediately after a move."""
    pass

class TransactionExecutor:
    """
    Transactional execution engine for verified, immutable reorganization plans.
    - Pre-flight validation: verifies plan hash, source file integrity, and collision absence.
    - Conservative collision handling: aborts execution if destination already exists.
    - Immediate per-operation verification: verifies destination existence, size, and SHA-256.
    - Commits run manifest to .miniseek/history/ for Milestone 4 undo tracking.
    """

    def __init__(self, scanner: Optional[FileScanner] = None):
        self.scanner = scanner or FileScanner()

    def validate_pre_flight(self, plan: Plan) -> Tuple[bool, Optional[str]]:
        """
        Executes strict pre-flight checks before modifying ANY file on disk:
        1. Recalculates and verifies cryptographic plan hash.
        2. Verifies source file existence, non-symlink status, size, and SHA-256.
        3. Verifies destination is within approved root and has NO collision.
        """
        # 1. Plan Hash Integrity Check
        computed_hash = plan.compute_hash()
        if computed_hash != plan.plan_hash:
            return False, f"Plan hash mismatch: computed '{computed_hash}' != approved '{plan.plan_hash}'. Plan is stale or modified."

        canonical_root = PathSecurity.get_canonical_path(plan.root_path)

        # 2. Check each proposed operation
        for op in plan.operations:
            src = Path(op.source_path)
            dst = Path(op.destination_path)

            # Source existence check
            if not src.exists():
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight failure on op {op.operation_id}: Source file '{src}' no longer exists."

            # Source symlink check (symlink appeared after planning)
            if src.is_symlink():
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight failure on op {op.operation_id}: Source file '{src}' is a symlink."

            # Source size integrity check
            current_size = src.stat().st_size
            if current_size != op.source_size:
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight failure on op {op.operation_id}: Source '{src.name}' size changed ({current_size} != {op.source_size})."

            # Source SHA-256 integrity check
            current_sha = self.scanner.compute_sha256(src)
            if current_sha != op.source_sha256:
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight failure on op {op.operation_id}: Source '{src.name}' content hash changed."

            # Destination root boundary check
            try:
                PathSecurity.validate_within_root(dst, canonical_root)
            except SecurityError as err:
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight failure on op {op.operation_id}: Destination '{dst}' violates root security: {err}"

            # Conservative collision check: Destination must NOT already exist
            if dst.exists():
                op.status = OperationStatus.BLOCKED
                return False, f"Pre-flight collision failure on op {op.operation_id}: Destination '{dst}' already exists. Aborting execution."

        return True, None

    def execute_plan(self, plan: Plan, base_history_dir: Optional[Union[str, Path]] = None) -> ExecutionResult:
        """
        Executes a frozen, approved plan transactionally with immediate post-op verification.
        """
        # Step 1: Strict Pre-flight validation
        is_valid, pre_flight_err = self.validate_pre_flight(plan)
        if not is_valid:
            plan.status = PlanStatus.FAILED
            return ExecutionResult(
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                status=PlanStatus.FAILED,
                operations_total=len(plan.operations),
                operations_completed=0,
                operations_failed=0,
                operations_blocked=sum(1 for op in plan.operations if op.status == OperationStatus.BLOCKED),
                executed_operations=[],
                error_message=pre_flight_err
            )

        plan.status = PlanStatus.EXECUTING
        completed_records: List[OperationRecord] = []
        executed_ops: List[PlanItem] = []
        exec_error: Optional[str] = None

        # Step 2: Sequential operation execution with immediate verification
        for op in plan.operations:
            src = Path(op.source_path)
            dst = Path(op.destination_path)
            op.status = OperationStatus.EXECUTING

            try:
                # Create destination directory structure
                dst.parent.mkdir(parents=True, exist_ok=True)

                # Capture mtime before moving
                src_mtime = src.stat().st_mtime

                # Execute filesystem move
                shutil.move(str(src), str(dst))

                # Step 3: Immediate post-operation verification
                if src.exists():
                    raise ExecutionVerificationError(f"Post-op verification failed: Source '{src}' still exists after move.")
                if not dst.exists():
                    raise ExecutionVerificationError(f"Post-op verification failed: Destination '{dst}' does not exist after move.")

                dst_stat = dst.stat()
                if dst_stat.st_size != op.source_size:
                    raise ExecutionVerificationError(f"Post-op verification failed: Destination '{dst}' size mismatch ({dst_stat.st_size} != {op.source_size}).")

                dst_sha = self.scanner.compute_sha256(dst)
                if dst_sha != op.source_sha256:
                    raise ExecutionVerificationError(f"Post-op verification failed: Destination '{dst}' SHA-256 mismatch.")

                # Mark operation completed
                op.status = OperationStatus.COMPLETED
                executed_ops.append(op)

                record = OperationRecord(
                    op_id=op.operation_id,
                    type="MOVE",
                    source_original=str(src),
                    destination_created=str(dst),
                    sha256=op.source_sha256,
                    size_bytes=op.source_size,
                    mtime=src_mtime,
                    status="COMPLETED"
                )
                completed_records.append(record)

            except Exception as err:
                op.status = OperationStatus.FAILED
                op.error_message = str(err)
                exec_error = f"Execution error on op {op.operation_id} ({src.name}): {err}"
                plan.status = PlanStatus.PARTIALLY_EXECUTED
                break

        # Step 4: Finalize plan status and commit run manifest
        if exec_error is None:
            plan.status = PlanStatus.COMMITTED
            final_status = PlanStatus.COMMITTED
        else:
            final_status = PlanStatus.PARTIALLY_EXECUTED

        manifest_path = None
        if completed_records:
            manifest_path = self._commit_run_manifest(
                plan=plan,
                records=completed_records,
                status=final_status,
                base_dir=Path(base_history_dir or plan.root_path)
            )

        return ExecutionResult(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            status=final_status,
            operations_total=len(plan.operations),
            operations_completed=len(completed_records),
            operations_failed=1 if exec_error else 0,
            operations_blocked=sum(1 for op in plan.operations if op.status == OperationStatus.PENDING),
            executed_operations=executed_ops,
            error_message=exec_error,
            manifest_path=str(manifest_path) if manifest_path else None
        )

    def _commit_run_manifest(
        self,
        plan: Plan,
        records: List[OperationRecord],
        status: str,
        base_dir: Path
    ) -> Path:
        """Persists immutable run manifest to .miniseek/history/run-<run_id>.json."""
        history_dir = base_dir / ".miniseek" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        unique_id = uuid.uuid4().hex[:8]
        run_id = f"run-{timestamp}-{unique_id}"
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        manifest = RunManifest(
            run_id=run_id,
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            timestamp=created_at,
            root_path=plan.root_path,
            status=status,
            operations=records
        )

        manifest_file = history_dir / f"{run_id}.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return manifest_file
