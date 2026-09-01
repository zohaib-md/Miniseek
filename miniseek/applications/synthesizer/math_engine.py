import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple, Set

from miniseek.applications.synthesizer.types import (
    RawExtractedTransaction,
    NormalizedTransaction,
    ExtractionStatus,
    FieldProvenance
)

class ExpenseNormalizer:
    """
    Deterministic normalizer for financial transaction fields:
    - Parses amount strings into exact Python Decimal (no floats).
    - Normalizes currency symbols to ISO 4217 codes.
    - Normalizes dates to ISO 8601 with explicit ambiguity detection.
    """

    CURRENCY_SYMBOL_MAP: Dict[str, str] = {
        "$": "USD",
        "usd": "USD",
        "us$": "USD",
        "₹": "INR",
        "rs": "INR",
        "rs.": "INR",
        "inr": "INR",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
        "cad": "CAD",
        "c$": "CAD",
        "aud": "AUD",
        "a$": "AUD",
        "jpy": "JPY",
        "¥": "JPY"
    }

    @classmethod
    def parse_amount(cls, raw_amount: Optional[str]) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Extracts and converts raw amount text into an exact Python Decimal.
        Handles $45.50, ₹1,249.00, 1.249,50 EUR, etc.
        Returns (Decimal, detected_currency_symbol) or (None, None).
        """
        if not raw_amount:
            return None, None

        text = raw_amount.strip()
        detected_curr = None

        # Check for currency symbols in the text
        for symbol, code in cls.CURRENCY_SYMBOL_MAP.items():
            if symbol in text.lower():
                detected_curr = code
                break

        # Remove currency symbols and non-numeric/punctuation characters
        cleaned = re.sub(r"[^\d,\.\-]", "", text).strip()
        if not cleaned:
            return None, detected_curr

        # Handle European decimal comma vs standard decimal dot
        # e.g., 1.249,50 -> 1249.50
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # European: 1.249,50
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Standard: 1,249.50
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                # Likely decimal comma: 45,50
                cleaned = cleaned.replace(",", ".")
            else:
                # Thousands comma: 1,249
                cleaned = cleaned.replace(",", "")

        try:
            val = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if val < 0:
                # Negative amount or refund
                return val, detected_curr
            return val, detected_curr
        except InvalidOperation:
            return None, detected_curr

    @classmethod
    def normalize_currency(cls, raw_currency: Optional[str], fallback: str = "USD") -> str:
        """Normalizes raw currency string to ISO 4217 code."""
        if not raw_currency:
            return fallback

        norm = raw_currency.strip().lower()
        if norm in cls.CURRENCY_SYMBOL_MAP:
            return cls.CURRENCY_SYMBOL_MAP[norm]

        # Check if already a 3-letter uppercase ISO code
        if len(norm) == 3 and norm.isalpha():
            return norm.upper()

        return fallback

    @classmethod
    def normalize_date(cls, raw_date: Optional[str]) -> Tuple[Optional[str], bool]:
        """
        Normalizes date strings to ISO 8601 (YYYY-MM-DD).
        Returns (normalized_date, is_ambiguous).
        """
        if not raw_date:
            return None, False

        text = raw_date.strip()

        # 1. ISO format: YYYY-MM-DD
        iso_match = re.match(r"^(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})$", text)
        if iso_match:
            y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}", False

        # 2. Month name format: Aug 14, 2026 or 14 August 2026
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        for m_name, m_num in months.items():
            if m_name in text.lower():
                # Extract year and day numbers
                nums = re.findall(r"\b\d+\b", text)
                year = next((int(n) for n in nums if len(n) == 4), None)
                day = next((int(n) for n in nums if len(n) <= 2 and 1 <= int(n) <= 31), None)
                if year and day:
                    return f"{year:04d}-{m_num:02d}-{day:02d}", False

        # 3. Two-digit date: MM/DD/YYYY or DD/MM/YYYY
        slash_match = re.match(r"^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})$", text)
        if slash_match:
            p1, p2, y = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            if p1 > 12 and 1 <= p2 <= 12:
                # Clearly DD/MM/YYYY (e.g. 25/08/2026)
                return f"{y:04d}-{p2:02d}-{p1:02d}", False
            elif p2 > 12 and 1 <= p1 <= 12:
                # Clearly MM/DD/YYYY (e.g. 08/25/2026)
                return f"{y:04d}-{p1:02d}-{p2:02d}", False
            elif 1 <= p1 <= 12 and 1 <= p2 <= 12:
                # Ambiguous: e.g. 05/06/2026 (May 6 or June 5) -> default US format but flag ambiguous
                return f"{y:04d}-{p1:02d}-{p2:02d}", True

        return None, True

    @classmethod
    def normalize_transaction(
        cls,
        raw_tx: RawExtractedTransaction,
        source_file: str = "document"
    ) -> NormalizedTransaction:
        """Converts a raw extracted transaction into a validated, normalized transaction."""
        # Amount parsing
        amount_dec, detected_curr = cls.parse_amount(raw_tx.amount_str)
        curr = cls.normalize_currency(raw_tx.currency_str or detected_curr)

        # Date normalization
        norm_date, is_ambiguous = cls.normalize_date(raw_tx.date_str)

        # Status adjustment
        status = raw_tx.status
        if amount_dec is None:
            amount_dec = Decimal("0.00")
            status = ExtractionStatus.NEEDS_REVIEW
        elif is_ambiguous:
            status = ExtractionStatus.AMBIGUOUS

        tx_id = f"tx-{uuid.uuid4().hex[:8]}"

        return NormalizedTransaction(
            transaction_id=tx_id,
            source_file=source_file,
            vendor=raw_tx.vendor or "UNKNOWN_VENDOR",
            date=norm_date,
            amount=amount_dec,
            currency=curr,
            category=raw_tx.category,
            status=status,
            provenance=raw_tx.provenance
        )


class DecimalMathEngine:
    """
    Exact financial arithmetic and aggregation engine using Python Decimal.
    - Zero floating point numbers.
    - Enforces isolated multi-currency computation (USD, INR, EUR never mixed).
    """

    @classmethod
    def calculate_currency_breakdown(
        cls,
        transactions: List[NormalizedTransaction]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Computes exact financial metrics grouped strictly by currency.
        Returns:
        {
          "USD": {
            "total_amount": Decimal("142.50"),
            "transaction_count": 3,
            "category_totals": {"Software_Cloud": Decimal("142.50"), ...},
            "average_transaction": Decimal("47.50")
          },
          "INR": { ... }
        }
        """
        breakdown: Dict[str, Dict[str, Any]] = {}

        # Group by currency
        by_curr: Dict[str, List[NormalizedTransaction]] = {}
        for tx in transactions:
            curr = tx.currency or "UNKNOWN"
            if curr not in by_curr:
                by_curr[curr] = []
            by_curr[curr].append(tx)

        for curr, tx_list in by_curr.items():
            total = Decimal("0.00")
            category_sums: Dict[str, Decimal] = {}

            for tx in tx_list:
                total += tx.amount
                cat = tx.category or "UNCATEGORIZED"
                category_sums[cat] = category_sums.get(cat, Decimal("0.00")) + tx.amount

            count = len(tx_list)
            avg = (total / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if count > 0 else Decimal("0.00")

            breakdown[curr] = {
                "currency": curr,
                "total_amount": total,
                "transaction_count": count,
                "category_totals": category_sums,
                "average_transaction": avg
            }

        return breakdown
