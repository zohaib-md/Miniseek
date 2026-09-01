import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from miniseek.core.types import (
    RunManifest, OperationRecord, UndoResult,
    UndoStatus, RunUndoStatus, PlanStatus
)
from miniseek.harness.history import HistoryManager
from miniseek.applications.janitor.scanner import FileScanner

class UndoEngine:
    """
    Safe, conservative undo engine for MiniSeek run manifests.

    Core invariant:
        MiniSeek never overwrites newer user data merely to undo itself.

    Undo operates exclusively from the persisted run manifest. No model
    inference, re-categorization, or destination regeneration occurs.

    For each operation (processed in reverse order):
    1. Verify the destination file still represents the file MiniSeek created
       (sha256, size_bytes match; mtime as supporting evidence).
    2. Verify the original source path is not occupied by a different file.
    3. Only if both checks pass, move the file back.
    4. Persist manifest state incrementally after each operation.
    """

    def __init__(self, scanner: Optional[FileScanner] = None):
        self.scanner = scanner or FileScanner()

    def execute_undo(
        self,
        manifest: RunManifest,
        root_dir: Union[str, Path]
    ) -> UndoResult:
        """
        Executes safe undo for a specific run, processing operations in reverse order.
        Persists manifest state incrementally for crash recovery.
        """
        root_path = Path(root_dir)

        # Validate run is eligible for undo
        if manifest.status not in (PlanStatus.COMMITTED, PlanStatus.PARTIALLY_EXECUTED):
            return UndoResult(
                run_id=manifest.run_id,
                status=RunUndoStatus.UNDO_FAILED,
                operations_total=len(manifest.operations),
                operations_undone=0,
                operations_conflict=0,
                operations_not_applicable=len(manifest.operations),
                error_message=f"Run '{manifest.run_id}' has status '{manifest.status}' and is not eligible for undo."
            )

        # Filter to only COMPLETED operations (FAILED ops have nothing to undo)
        completed_ops = [op for op in manifest.operations if op.status == "COMPLETED"]
        non_completed = [op for op in manifest.operations if op.status != "COMPLETED"]

        # Mark non-completed operations as NOT_APPLICABLE
        for op in non_completed:
            op.undo_status = UndoStatus.NOT_APPLICABLE

        # Process in REVERSE order
        reversed_ops = list(reversed(completed_ops))

        manifest.status = RunUndoStatus.UNDOING
        HistoryManager.save_manifest(manifest, root_path)

        undone_count = 0
        conflict_count = 0
        conflict_details: List[Dict[str, Any]] = []
        had_error = False

        for op in reversed_ops:
            op.undo_status = UndoStatus.PENDING

            # Step 1: Verify destination file is unchanged
            dst = Path(op.destination_created)
            conflict_reason = self._check_destination_integrity(op, dst)

            if conflict_reason:
                op.undo_status = UndoStatus.CONFLICT
                op.undo_error = conflict_reason
                conflict_count += 1
                conflict_details.append({
                    "op_id": op.op_id,
                    "destination": op.destination_created,
                    "source_original": op.source_original,
                    "reason": conflict_reason
                })
                HistoryManager.save_manifest(manifest, root_path)
                continue

            # Step 2: Verify original source path is not occupied
            src_original = Path(op.source_original)
            if src_original.exists():
                op.undo_status = UndoStatus.CONFLICT
                reason = f"Original path '{src_original}' is occupied by another file. Will not overwrite."
                op.undo_error = reason
                conflict_count += 1
                conflict_details.append({
                    "op_id": op.op_id,
                    "destination": op.destination_created,
                    "source_original": op.source_original,
                    "reason": reason
                })
                HistoryManager.save_manifest(manifest, root_path)
                continue

            # Step 3: Execute the reverse move
            try:
                src_original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src_original))

                # Post-undo verification
                if not src_original.exists():
                    raise RuntimeError(f"Post-undo verification failed: '{src_original}' does not exist after move.")
                if dst.exists():
                    raise RuntimeError(f"Post-undo verification failed: '{dst}' still exists after move.")

                restored_sha = self.scanner.compute_sha256(src_original)
                if restored_sha != op.sha256:
                    raise RuntimeError(f"Post-undo verification failed: restored file hash mismatch.")

                op.undo_status = UndoStatus.UNDONE
                undone_count += 1

            except Exception as err:
                op.undo_status = UndoStatus.CONFLICT
                op.undo_error = str(err)
                conflict_count += 1
                conflict_details.append({
                    "op_id": op.op_id,
                    "destination": op.destination_created,
                    "source_original": op.source_original,
                    "reason": str(err)
                })
                had_error = True

            # Persist incrementally after each operation
            HistoryManager.save_manifest(manifest, root_path)

        # Determine final undo status
        total_applicable = len(completed_ops)
        not_applicable_count = len(non_completed)

        if undone_count == total_applicable and total_applicable > 0:
            final_status = RunUndoStatus.UNDONE
        elif undone_count > 0:
            final_status = RunUndoStatus.UNDO_PARTIAL
        else:
            final_status = RunUndoStatus.UNDO_FAILED

        manifest.status = final_status
        HistoryManager.save_manifest(manifest, root_path)

        return UndoResult(
            run_id=manifest.run_id,
            status=final_status,
            operations_total=len(manifest.operations),
            operations_undone=undone_count,
            operations_conflict=conflict_count,
            operations_not_applicable=not_applicable_count,
            conflict_details=conflict_details
        )

    def _check_destination_integrity(self, op: OperationRecord, dst: Path) -> Optional[str]:
        """
        Verifies that the destination file is the same file MiniSeek created.
        Returns None if eligible for undo, or a conflict reason string.
        """
        if not dst.exists():
            return f"Destination '{dst}' no longer exists (manually deleted?)."

        if dst.is_symlink():
            return f"Destination '{dst}' is now a symlink."

        # Size check
        current_size = dst.stat().st_size
        if current_size != op.size_bytes:
            return (
                f"Destination '{dst.name}' size changed "
                f"({current_size} != {op.size_bytes}). File was modified by user."
            )

        # SHA-256 content check
        current_sha = self.scanner.compute_sha256(dst)
        if current_sha != op.sha256:
            return (
                f"Destination '{dst.name}' content hash changed. "
                f"File was modified by user."
            )

        return None
