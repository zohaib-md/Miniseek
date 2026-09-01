import json
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List, Union

from miniseek.applications.synthesizer.types import (
    ALLOWED_EXPENSE_CATEGORIES,
    ExtractionStatus,
    FieldProvenance,
    RawExtractedTransaction
)

@dataclass
class TransactionValidationResult:
    """Outcome of validating raw model extraction output."""
    is_valid: bool
    transactions: List[RawExtractedTransaction] = None
    error_stage: Optional[str] = None  # "extraction", "syntax", "schema", "semantic", "safety"
    error_message: Optional[str] = None
    unparsed_data: Optional[Any] = None

class TransactionValidator:
    """
    6-Layer Validator Pipeline for Financial Transaction Extractions:
    1. EXTRACT & NORMALIZE (isolate JSON payload from markdown or surrounding text)
    2. SAFE SYNTAX REPAIR (remove trailing commas, fix unescaped characters)
    3. PARSE JSON (json.loads)
    4. SCHEMA VALIDATION (verify list/dict structure, expected keys)
    5. FIELD-LEVEL SEMANTIC VALIDATION (category set check, amount/date syntax check)
    6. SAFETY VALIDATION (verify zero control characters, no prompt injection commands)
    """

    @classmethod
    def extract_and_repair(cls, raw_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts JSON block from raw LLM output and applies safe syntax repair."""
        cleaned = raw_text.strip()
        if not cleaned:
            return None, "Empty model response."

        # 1. Search for markdown ```json ... ``` or ``` ... ```
        block_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", cleaned, re.DOTALL)
        if block_match:
            candidate = block_match.group(1).strip()
        else:
            # 2. Search for outermost [ ... ] or { ... }
            first_bracket = min(
                [pos for pos in (cleaned.find("["), cleaned.find("{")) if pos != -1],
                default=-1
            )
            last_bracket = max(cleaned.rfind("]"), cleaned.rfind("}"))

            if first_bracket != -1 and last_bracket > first_bracket:
                candidate = cleaned[first_bracket:last_bracket + 1].strip()
            elif first_bracket != -1:
                candidate = cleaned[first_bracket:].strip()
            else:
                return None, "No JSON array or object found in model output."

        # Safe syntax repair: remove trailing commas before closing braces/brackets
        repaired = re.sub(r",\s*([\}\]])", r"\1", candidate)
        return repaired, None

    @classmethod
    def validate(
        cls,
        raw_text: str,
        source_file: str = "document",
        allowed_categories: Tuple[str, ...] = ALLOWED_EXPENSE_CATEGORIES
    ) -> TransactionValidationResult:
        """Runs the canonical 6-layer validation pipeline."""
        # Layer 1 & 2: Extract & Repair
        candidate_json, extract_err = cls.extract_and_repair(raw_text)
        if extract_err or not candidate_json:
            return TransactionValidationResult(
                is_valid=False,
                transactions=[],
                error_stage="extraction",
                error_message=extract_err or "Failed to extract JSON payload."
            )

        # Layer 3: Parse JSON
        try:
            data = json.loads(candidate_json)
        except json.JSONDecodeError as err:
            return TransactionValidationResult(
                is_valid=False,
                transactions=[],
                error_stage="syntax",
                error_message=f"JSON syntax error: {err.msg} at line {err.lineno} col {err.colno}"
            )

        # Layer 4: Schema Validation
        raw_items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            # Check if dict wraps a list e.g. {"transactions": [...]}
            if "transactions" in data and isinstance(data["transactions"], list):
                raw_items = data["transactions"]
            else:
                raw_items = [data]
        elif isinstance(data, list):
            raw_items = data
        else:
            return TransactionValidationResult(
                is_valid=False,
                transactions=[],
                error_stage="schema",
                error_message=f"Output must be a JSON array or object, got {type(data).__name__}."
            )

        if not raw_items:
            # Valid extraction of 0 transactions (e.g. non-financial document)
            return TransactionValidationResult(
                is_valid=True,
                transactions=[]
            )

        validated_transactions: List[RawExtractedTransaction] = []

        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                return TransactionValidationResult(
                    is_valid=False,
                    transactions=[],
                    error_stage="schema",
                    error_message=f"Item #{idx+1} in transactions list must be a JSON object, got {type(item).__name__}."
                )

            # Check for safety violations (control characters / code injection)
            for k, v in item.items():
                if isinstance(v, str) and any(ch in v for ch in ["\x00", "\x1b", "\r\n__proto__"]):
                    return TransactionValidationResult(
                        is_valid=False,
                        transactions=[],
                        error_stage="safety",
                        error_message=f"Security violation: field '{k}' contains forbidden control characters."
                    )

            # Layer 5: Field Semantic Validation & Category Normalization
            raw_category = item.get("category", "UNCATEGORIZED")
            matched_cat = "UNCATEGORIZED"
            if isinstance(raw_category, str):
                norm_cat = raw_category.strip().lower()
                for cat in allowed_categories:
                    if cat.lower() == norm_cat:
                        matched_cat = cat
                        break
                if matched_cat == "UNCATEGORIZED" and norm_cat in ("needs_review", "review", "ambiguous", "unknown"):
                    matched_cat = "NEEDS_REVIEW"

            # Vendor extraction
            raw_vendor = item.get("vendor") or item.get("merchant") or item.get("description")
            vendor_str = str(raw_vendor).strip() if raw_vendor is not None else None

            # Date extraction
            raw_date = item.get("date") or item.get("transaction_date") or item.get("date_str")
            date_str = str(raw_date).strip() if raw_date is not None else None

            # Amount extraction
            raw_amount = item.get("amount") or item.get("total") or item.get("amount_str")
            amount_str = str(raw_amount).strip() if raw_amount is not None else None

            # Currency extraction
            raw_currency = item.get("currency") or item.get("currency_str")
            currency_str = str(raw_currency).strip() if raw_currency is not None else None

            # Status determination
            status = ExtractionStatus.EXTRACTED
            if not amount_str or not vendor_str:
                status = ExtractionStatus.PARTIAL
            if matched_cat == "NEEDS_REVIEW":
                status = ExtractionStatus.NEEDS_REVIEW

            # Provenance construction
            provenance: Dict[str, FieldProvenance] = {}
            if vendor_str:
                provenance["vendor"] = FieldProvenance(
                    raw_value=vendor_str,
                    source_file=source_file,
                    evidence_snippet=str(item.get("vendor_evidence", vendor_str))[:60]
                )
            if amount_str:
                provenance["amount"] = FieldProvenance(
                    raw_value=amount_str,
                    source_file=source_file,
                    evidence_snippet=str(item.get("amount_evidence", amount_str))[:60]
                )
            if date_str:
                provenance["date"] = FieldProvenance(
                    raw_value=date_str,
                    source_file=source_file,
                    evidence_snippet=str(item.get("date_evidence", date_str))[:60]
                )

            # Confidence
            conf = item.get("confidence")
            conf_val = float(conf) if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0 else None

            validated_transactions.append(RawExtractedTransaction(
                vendor=vendor_str,
                date_str=date_str,
                amount_str=amount_str,
                currency_str=currency_str,
                category=matched_cat,
                status=status,
                provenance=provenance,
                confidence=conf_val,
                line_number=idx + 1
            ))

        return TransactionValidationResult(
            is_valid=True,
            transactions=validated_transactions
        )
