import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from miniseek.core.types import FileInfo, ScanResult
from miniseek.core.config import Config, DEFAULT_CONFIG
from miniseek.core.security import PathSecurity, SecurityError
from miniseek.llm import LLMProvider
from miniseek.harness.validation import CategorizationValidator, ValidationResult

class SemanticStatus:
    """Explicit semantic status outcomes for file categorization."""
    CLASSIFIED = "CLASSIFIED"
    UNCATEGORIZED = "UNCATEGORIZED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INVALID = "INVALID"

@dataclass
class CategorizationTelemetry:
    """Observable metadata recorded for every semantic categorization micro-task."""
    file_name: str
    extension: str
    size_bytes: int
    model_name: str
    runtime: str
    prompt_version: str
    semantic_status: str
    final_category: str
    confidence: Optional[float]
    evidence_used: List[str]
    destination_path: Optional[str]
    raw_response: str
    retry_count: int
    is_valid: bool
    validation_error: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class SemanticCategorizer:
    """
    Harness-Guided Micro-Task Semantic Categorizer:
    1. Prepares minimal, bounded evidence (name, extension, size, snippet).
    2. Enforces native JSON grammar and explicit model abstention (NEEDS_REVIEW / UNCATEGORIZED).
    3. Runs canonical 6-layer validation with maximum 1 retry.
    4. Deterministically maps category -> target directory (NEEDS_REVIEW yields NO MOVE).
    """

    PROMPT_VERSION = "v1.1"
    RUNTIME_NAME = "ollama"

    # Predefined deterministic category folder mapping
    # Note: NEEDS_REVIEW maps to None (NO MOVE - excluded from proposals)
    CATEGORY_FOLDER_MAP: Dict[str, Optional[str]] = {
        "Documents": "Documents",
        "Receipts_Invoices": "Receipts_Invoices",
        "Media_Images": "Media_Images",
        "Code": "Code",
        "Archives_Data": "Archives_Data",
        "UNCATEGORIZED": "UNCATEGORIZED",
        "NEEDS_REVIEW": None
    }

    SYSTEM_PROMPT = """You are a precise file categorization assistant.
Classify the given file based ONLY on the evidence provided into one of the allowed categories.
If the evidence is ambiguous or contradictory, you MUST select 'NEEDS_REVIEW'.
Respond with a single valid JSON object."""

    def __init__(self, llm: LLMProvider, config: Optional[Config] = None):
        self.llm = llm
        self.config = config or DEFAULT_CONFIG

    def _build_prompt(self, file_info: FileInfo) -> str:
        """Constructs a bounded micro-prompt keeping context strictly within budget."""
        preview_text = file_info.preview if file_info.preview else "(No text preview available)"
        categories_formatted = "\n".join([f"- {cat}" for cat in self.config.allowed_categories])

        return f"""Classify this file into exactly one allowed category.

Evidence:
- File Name: {file_info.name}
- Extension: {file_info.extension if file_info.extension else '(None)'}
- Size: {file_info.size_bytes} bytes
- Content Preview: {preview_text}

Allowed Categories:
{categories_formatted}

Guideline on Abstention:
- If the file purpose is unclear, ambiguous, or contradictory, choose 'NEEDS_REVIEW'.
- If the file does not match common categories, choose 'UNCATEGORIZED'.

Respond ONLY with this JSON structure:
{{
    "category": "<one of the exact categories listed above>",
    "confidence": 0.9,
    "evidence_used": ["filename", "extension", "preview"]
}}"""

    def categorize_file(self, file_info: FileInfo, root_dir: Optional[Path] = None) -> Tuple[str, CategorizationTelemetry]:
        """
        Classifies a single file using micro-task dispatch, layered validation, and 1-retry guard.
        """
        start_time = time.time()
        prompt = self._build_prompt(file_info)
        messages = [{"role": "user", "content": prompt}]

        retry_count = 0
        validation_err: Optional[str] = None
        raw_response = ""

        # Step 1: Initial LLM Inference
        resp = self.llm.chat(messages, system=self.SYSTEM_PROMPT)
        raw_response = resp.get("content", "")
        val_result = CategorizationValidator.validate(raw_response, self.config.allowed_categories)

        # Step 2: 1-Retry Guard on Validation Failure
        if not val_result.is_valid:
            retry_count = 1
            validation_err = f"[{val_result.error_stage}] {val_result.error_message}"
            retry_prompt = (
                f"Your previous response failed validation with error: {val_result.error_message}\n"
                f"You MUST output ONLY a valid JSON object with a valid category from: "
                f"{list(self.config.allowed_categories)}. Example:\n"
                f'{{"category": "Documents", "confidence": 0.85, "evidence_used": ["extension"]}}'
            )
            messages.append({"role": "assistant", "content": raw_response})
            messages.append({"role": "user", "content": retry_prompt})

            retry_resp = self.llm.chat(messages, system=self.SYSTEM_PROMPT)
            raw_response = retry_resp.get("content", "")
            val_result = CategorizationValidator.validate(raw_response, self.config.allowed_categories)

        duration_ms = int((time.time() - start_time) * 1000)

        # Step 3: Determine Semantic Status & Category
        if val_result.is_valid and val_result.parsed_data:
            final_category = val_result.parsed_data["category"]
            confidence = val_result.parsed_data.get("confidence")
            evidence_used = val_result.parsed_data.get("evidence_used", ["filename", "extension"])
            is_valid = True

            if final_category == "NEEDS_REVIEW":
                semantic_status = SemanticStatus.NEEDS_REVIEW
            elif final_category == "UNCATEGORIZED":
                semantic_status = SemanticStatus.UNCATEGORIZED
            else:
                semantic_status = SemanticStatus.CLASSIFIED
        else:
            # Fallback on unrecoverable validation failure
            final_category = "NEEDS_REVIEW"
            confidence = 0.0
            evidence_used = []
            validation_err = f"[{val_result.error_stage}] {val_result.error_message}"
            semantic_status = SemanticStatus.INVALID
            is_valid = False

        # Step 4: Deterministic Python Destination Derivation (Never from model)
        dest_path = None
        if root_dir is not None:
            try:
                dest_path_obj = self.get_destination_path(root_dir, file_info.name, final_category)
                dest_path = str(dest_path_obj) if dest_path_obj is not None else None
            except SecurityError as sec_err:
                dest_path = None
                final_category = "NEEDS_REVIEW"
                semantic_status = SemanticStatus.INVALID
                is_valid = False
                validation_err = f"[safety] Path security violation for filename '{file_info.name}': {sec_err}"

        telemetry = CategorizationTelemetry(
            file_name=file_info.name,
            extension=file_info.extension,
            size_bytes=file_info.size_bytes,
            model_name=self.config.model_name,
            runtime=self.RUNTIME_NAME,
            prompt_version=self.PROMPT_VERSION,
            semantic_status=semantic_status,
            final_category=final_category,
            confidence=confidence,
            evidence_used=evidence_used,
            destination_path=dest_path,
            raw_response=raw_response,
            retry_count=retry_count,
            is_valid=is_valid,
            validation_error=validation_err,
            duration_ms=duration_ms
        )

        return final_category, telemetry

    @classmethod
    def get_destination_path(cls, root_dir: Path, file_name: str, category: str) -> Optional[Path]:
        """
        Deterministic Python mapping from validated category to safe destination path.
        - The model NEVER dictates filesystem paths.
        - 'NEEDS_REVIEW' yields None (NO MOVE - excluded from proposals).
        """
        folder_name = cls.CATEGORY_FOLDER_MAP.get(category)
        if folder_name is None:
            # Explicit abstention: NO MOVE
            return None

        # Resolve path and verify within root boundary
        target_path = root_dir / folder_name / file_name
        return PathSecurity.validate_within_root(target_path, root_dir)

    def categorize_scan(self, scan_result: ScanResult) -> List[Dict[str, Any]]:
        """Categorizes all regular files from a scan result."""
        results = []
        root_path = Path(scan_result.root_path)

        for f in scan_result.files:
            category, telemetry = self.categorize_file(f, root_dir=root_path)
            dest_path = self.get_destination_path(root_path, f.name, category)
            results.append({
                "file_info": f,
                "category": category,
                "destination_path": str(dest_path) if dest_path is not None else None,
                "telemetry": telemetry
            })

        return results
