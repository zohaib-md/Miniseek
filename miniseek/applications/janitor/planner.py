import os
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from miniseek.core.types import (
    Plan, PlanItem, NeedsReviewItem, ScanResult, FileInfo, PlanStatus
)
from miniseek.core.security import PathSecurity
from miniseek.applications.janitor.scanner import FileScanner

class PlanBuilder:
    """
    Constructs, canonicalizes, renders, and persists immutable reorganization plans.
    - Ensures NEEDS_REVIEW files are strictly excluded from move operations.
    - Generates deterministic plan_hash for cryptographic audit.
    - Formats non-mutating dry-run previews.
    """

    @classmethod
    def build_plan(
        cls,
        root_path: Union[str, Path],
        categorization_results: List[Dict[str, Any]],
        model_metadata: Optional[Dict[str, Any]] = None,
        scanner: Optional[FileScanner] = None
    ) -> Plan:
        """Assembles an immutable Plan from categorized scan results."""
        canonical_root = PathSecurity.get_canonical_path(root_path)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        unique_id = uuid.uuid4().hex[:8]
        plan_id = f"plan-{timestamp}-{unique_id}"
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        file_scanner = scanner or FileScanner()

        operations: List[PlanItem] = []
        needs_review: List[NeedsReviewItem] = []
        op_counter = 1

        # Sort items deterministically by relative path
        sorted_items = sorted(categorization_results, key=lambda x: x["file_info"].relative_path)

        for item in sorted_items:
            f_info: FileInfo = item["file_info"]
            category: str = item["category"]
            dest_path: Optional[str] = item.get("destination_path")
            telemetry = item.get("telemetry")

            # 1. Needs Review / Abstention -> Strictly Excluded from move operations
            if category == "NEEDS_REVIEW" or dest_path is None:
                needs_review.append(
                    NeedsReviewItem(
                        file_path=f_info.path,
                        relative_path=f_info.relative_path,
                        reason=telemetry.validation_error if (telemetry and telemetry.validation_error) else "Model abstained / ambiguous evidence",
                        evidence={
                            "name": f_info.name,
                            "extension": f_info.extension,
                            "size_bytes": f_info.size_bytes,
                            "preview": f_info.preview
                        }
                    )
                )
                continue

            # 2. Valid Categorized File -> Construct Executable PlanItem
            # Ensure SHA-256 is present for pre-flight identity verification
            sha256 = f_info.sha256
            if not sha256:
                sha256 = file_scanner.compute_sha256(Path(f_info.path)) or "unknown_sha256"
                f_info.sha256 = sha256

            # Ensure destination is within approved root
            canonical_dest = PathSecurity.validate_within_root(dest_path, canonical_root)

            # Skip operation if source is already at destination
            if Path(f_info.path) == canonical_dest:
                continue

            operations.append(
                PlanItem(
                    operation_id=op_counter,
                    source_path=str(Path(f_info.path)),
                    destination_path=str(canonical_dest),
                    category=category,
                    source_sha256=sha256,
                    source_size=f_info.size_bytes
                )
            )
            op_counter += 1

        # Instantiate unhashed plan
        plan = Plan(
            plan_id=plan_id,
            plan_hash="",
            root_path=str(canonical_root),
            created_at=created_at,
            status=PlanStatus.VALIDATED,
            operations=operations,
            needs_review=needs_review,
            model_metadata=model_metadata or {}
        )

        # Freeze and compute cryptographic plan hash
        plan.plan_hash = plan.compute_hash()
        return plan

    @classmethod
    def render_dry_run(cls, plan: Plan, scan_result: Optional[ScanResult] = None) -> str:
        """Renders an ASCII dry-run preview table."""
        lines = [
            "═" * 78,
            "                   MINISEEK DRY-RUN PROPOSAL PREVIEW",
            "═" * 78,
            f"  Plan ID   : {plan.plan_id}",
            f"  Plan Hash : {plan.plan_hash[:16]}...{plan.plan_hash[-8:]}",
            f"  Root Dir  : {plan.root_path}",
            f"  Created At: {plan.created_at}",
            "─" * 78
        ]

        if scan_result:
            lines.extend([
                "📊 SCAN & STORAGE SUMMARY",
                f"  • Total Scanned Files : {scan_result.total_files}",
                f"  • Total Directory Size: {cls._format_size(scan_result.total_bytes)}",
                f"  • Exact Duplicate Sets: {len(scan_result.duplicate_groups)} (Wasted: {cls._format_size(scan_result.total_wasted_bytes)})",
                f"  • Skipped Symlinks    : {len(scan_result.skipped_symlinks)}",
                "─" * 78
            ])

        lines.extend([
            f"📦 PROPOSED FILE MOVES ({len(plan.operations)} operations)",
            f"{'ID':<4} {'Source File':<32} {'→ Category':<20} {'Size':<10}",
            "─" * 78
        ])

        if not plan.operations:
            lines.append("  (No files require moving — workspace already organized)")
        else:
            for op in plan.operations:
                src_name = Path(op.source_path).name
                size_str = cls._format_size(op.source_size)
                lines.append(f"{op.operation_id:<4} {src_name[:30]:<32} → {op.category:<18} {size_str:<10}")

        if plan.needs_review:
            lines.extend([
                "─" * 78,
                f"⚠️  NEEDS REVIEW / ABSTAINED (NO MOVE — {len(plan.needs_review)} files)",
                f"{'File':<36} {'Reason':<40}",
                "─" * 78
            ])
            for nr in plan.needs_review:
                lines.append(f"{nr.relative_path[:34]:<36} {nr.reason[:38]:<40}")

        if scan_result and scan_result.skipped_symlinks:
            lines.extend([
                "─" * 78,
                f"🔗 SKIPPED SYMLINKS ({len(scan_result.skipped_symlinks)} files)",
                "─" * 78
            ])
            for sym in scan_result.skipped_symlinks:
                lines.append(f"  • {sym.relative_path} → (target: {sym.symlink_target or 'unknown'})")

        lines.extend([
            "═" * 78,
            "🔒 DRY-RUN ONLY: No filesystem modifications were made.",
            "   To execute this plan, use: miniseek organize <dir> --apply",
            "═" * 78
        ])

        return "\n".join(lines)

    @classmethod
    def save_plan(cls, plan: Plan, root_dir: Union[str, Path]) -> Path:
        """Persists the frozen plan artifact to .miniseek/plans/."""
        plans_dir = Path(root_dir) / ".miniseek" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / f"plan-{plan.plan_id}.json"

        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2)

        return plan_file

    @classmethod
    def load_plan(cls, plan_file: Path) -> Plan:
        """Loads and reconstructs a frozen plan artifact from disk."""
        with open(plan_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        operations = [
            PlanItem(
                operation_id=item["operation_id"],
                source_path=item["source_path"],
                destination_path=item["destination_path"],
                category=item["category"],
                source_sha256=item["source_sha256"],
                source_size=item["source_size"],
                status=item.get("status", "PENDING"),
                error_message=item.get("error_message")
            )
            for item in data.get("operations", [])
        ]

        needs_review = [
            NeedsReviewItem(
                file_path=item["file_path"],
                relative_path=item.get("relative_path", Path(item["file_path"]).name),
                reason=item["reason"],
                evidence=item.get("evidence", {})
            )
            for item in data.get("needs_review", [])
        ]

        return Plan(
            plan_id=data["plan_id"],
            plan_hash=data["plan_hash"],
            root_path=data["root_path"],
            created_at=data["created_at"],
            status=data.get("status", PlanStatus.VALIDATED),
            operations=operations,
            needs_review=needs_review,
            model_metadata=data.get("model_metadata", {})
        )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
