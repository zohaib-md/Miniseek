import uuid
import time
from enum import Enum
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple

class ExtractionStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    NEEDS_REVIEW = "NEEDS_REVIEW"

ALLOWED_EXPENSE_CATEGORIES: Tuple[str, ...] = (
    "Software_Cloud",
    "Meals_Dining",
    "Travel_Transport",
    "Office_Hardware",
    "Utilities_Services",
    "Professional_Legal",
    "UNCATEGORIZED",
    "NEEDS_REVIEW"
)

@dataclass
class FieldProvenance:
    """Lightweight audit trail for an individual extracted field."""
    raw_value: str
    source_file: str
    evidence_snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RawExtractedTransaction:
    """Raw semantic extraction output directly from the model / parser."""
    vendor: Optional[str]
    date_str: Optional[str]
    amount_str: Optional[str]
    currency_str: Optional[str]
    category: str
    status: ExtractionStatus = ExtractionStatus.EXTRACTED
    provenance: Dict[str, FieldProvenance] = field(default_factory=dict)
    confidence: Optional[float] = None
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["provenance"] = {k: v.to_dict() for k, v in self.provenance.items()}
        return d

@dataclass
class NormalizedTransaction:
    """Clean, validated transaction with exact Decimal arithmetic representation."""
    transaction_id: str
    source_file: str
    vendor: str
    date: Optional[str]  # ISO format "YYYY-MM-DD" or None if AMBIGUOUS/UNKNOWN
    amount: Decimal      # Exact Python Decimal, never float
    currency: str        # ISO 4217 code e.g. "INR", "USD", "EUR"
    category: str
    status: ExtractionStatus
    provenance: Dict[str, FieldProvenance] = field(default_factory=dict)
    is_duplicate_candidate: bool = False
    duplicate_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "source_file": self.source_file,
            "vendor": self.vendor,
            "date": self.date,
            "amount": str(self.amount),
            "currency": self.currency,
            "category": self.category,
            "status": self.status.value,
            "provenance": {k: v.to_dict() for k, v in self.provenance.items()},
            "is_duplicate_candidate": self.is_duplicate_candidate,
            "duplicate_reason": self.duplicate_reason
        }

@dataclass
class DocumentExtractionResult:
    """Result of processing a single financial document."""
    source_file: str
    status: ExtractionStatus
    transactions: List[NormalizedTransaction] = field(default_factory=list)
    raw_extractions: List[RawExtractedTransaction] = field(default_factory=list)
    unparsed_lines: List[str] = field(default_factory=list)
    raw_response: str = ""
    retry_count: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "status": self.status.value,
            "transaction_count": len(self.transactions),
            "transactions": [t.to_dict() for t in self.transactions],
            "unparsed_lines": self.unparsed_lines,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message
        }
