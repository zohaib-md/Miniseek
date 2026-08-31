import json
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List

@dataclass
class ValidationResult:
    """Outcome of layered validation on model categorization response."""
    is_valid: bool
    parsed_data: Optional[Dict[str, Any]] = None
    error_stage: Optional[str] = None  # "extraction", "syntax", "schema", "semantic", "safety"
    error_message: Optional[str] = None

class CategorizationValidator:
    """
    Canonical layered validator for model categorization outputs:
    1. EXTRACT (Isolate candidate JSON block)
    2. SAFE SYNTAX REPAIR (Clean trailing commas/formatting safely)
    3. PARSE JSON (json.loads into dictionary)
    4. SCHEMA VALIDATION (Check required keys, data types, no reliance on reasoning)
    5. SEMANTIC VALIDATION (Verify category is in allowed set including abstentions)
    6. SAFETY VALIDATION (Verify no path-injection or control characters)
    """

    @classmethod
    def extract_and_repair(cls, raw_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts candidate JSON payload and applies safe syntax normalization."""
        cleaned = raw_text.strip()
        if not cleaned:
            return None, "Empty model response."

        # 1. Search for markdown ```json ... ``` or ``` ... ```
        block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if block_match:
            candidate = block_match.group(1).strip()
        else:
            # 2. Extract outermost { ... }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end > start:
                candidate = cleaned[start:end + 1].strip()
            elif start != -1 and end == -1:
                # Text begins a JSON object but was unclosed / truncated
                candidate = cleaned[start:].strip()
            else:
                return None, "No JSON object found in model output."

        # Safe syntax repair: remove trailing commas before closing braces/brackets
        repaired = re.sub(r",\s*([\}\]])", r"\1", candidate)
        return repaired, None

    @classmethod
    def validate(cls, raw_text: str, allowed_categories: Tuple[str, ...]) -> ValidationResult:
        """Runs the canonical validation pipeline in strict order."""
        # Layer 1 & 2: Extract & Safe Syntax Repair
        candidate_json, extract_err = cls.extract_and_repair(raw_text)
        if extract_err or not candidate_json:
            return ValidationResult(
                is_valid=False,
                error_stage="extraction",
                error_message=extract_err or "Failed to extract JSON candidate."
            )

        # Layer 3: Parse JSON
        try:
            data = json.loads(candidate_json)
        except json.JSONDecodeError as err:
            return ValidationResult(
                is_valid=False,
                error_stage="syntax",
                error_message=f"JSON syntax error: {err.msg} at line {err.lineno} col {err.colno}"
            )

        # Layer 4: Schema Validation
        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                error_stage="schema",
                error_message=f"Output must be a JSON object, got {type(data).__name__}."
            )

        if "category" not in data:
            return ValidationResult(
                is_valid=False,
                error_stage="schema",
                error_message="Missing required field: 'category'."
            )

        category_val = data["category"]
        if not isinstance(category_val, str) or not category_val.strip():
            return ValidationResult(
                is_valid=False,
                error_stage="schema",
                error_message="Field 'category' must be a non-empty string."
            )

        # Optional confidence validation (telemetry only)
        if "confidence" in data and data["confidence"] is not None:
            conf = data["confidence"]
            if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
                return ValidationResult(
                    is_valid=False,
                    error_stage="schema",
                    error_message=f"Field 'confidence' must be a number between 0.0 and 1.0, got {conf}."
                )
            data["confidence"] = float(conf)

        # Optional evidence_used validation (telemetry only)
        if "evidence_used" in data and data["evidence_used"] is not None:
            ev = data["evidence_used"]
            if not isinstance(ev, list):
                return ValidationResult(
                    is_valid=False,
                    error_stage="schema",
                    error_message="Field 'evidence_used' must be a list of strings."
                )
            data["evidence_used"] = [str(x) for x in ev]

        # Layer 5: Semantic Validation (Is category in allowed set?)
        normalized_category = category_val.strip()
        matched_cat = None
        for allowed in allowed_categories:
            if allowed.lower() == normalized_category.lower():
                matched_cat = allowed
                break

        if not matched_cat:
            return ValidationResult(
                is_valid=False,
                error_stage="semantic",
                error_message=f"Invalid category '{category_val}'. Allowed categories: {list(allowed_categories)}."
            )
        
        data["category"] = matched_cat

        # Layer 6: Safety Validation (Ensure no path-injection / control characters)
        forbidden_chars = ["/", "\\", "..", ":", "~", "$", "\x00"]
        for ch in forbidden_chars:
            if ch in normalized_category:
                return ValidationResult(
                    is_valid=False,
                    error_stage="safety",
                    error_message=f"Security violation: category contains forbidden character '{ch}'."
                )

        return ValidationResult(
            is_valid=True,
            parsed_data=data
        )
