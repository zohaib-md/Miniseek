from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from miniseek.applications.synthesizer.types import (
    NormalizedTransaction,
    ExtractionStatus
)
from miniseek.applications.synthesizer.math_engine import DecimalMathEngine

@dataclass
class CurrencySummary:
    """Summary of financial metrics for a single currency."""
    currency: str
    total_amount: Decimal
    transaction_count: int
    category_totals: Dict[str, Decimal]
    average_transaction: Decimal
    top_category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency": self.currency,
            "total_amount": str(self.total_amount),
            "transaction_count": self.transaction_count,
            "category_totals": {k: str(v) for k, v in self.category_totals.items()},
            "average_transaction": str(self.average_transaction),
            "top_category": self.top_category
        }

@dataclass
class AggregationSummary:
    """Complete multi-currency financial aggregation summary."""
    total_documents: int
    total_transactions: int
    clean_transactions_count: int
    needs_review_count: int
    duplicate_candidates_count: int
    currency_summaries: Dict[str, CurrencySummary] = field(default_factory=dict)
    all_transactions: List[NormalizedTransaction] = field(default_factory=list)
    needs_review_transactions: List[NormalizedTransaction] = field(default_factory=list)
    duplicate_groups: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "total_transactions": self.total_transactions,
            "clean_transactions_count": self.clean_transactions_count,
            "needs_review_count": self.needs_review_count,
            "duplicate_candidates_count": self.duplicate_candidates_count,
            "currency_summaries": {k: v.to_dict() for k, v in self.currency_summaries.items()},
            "duplicate_groups": self.duplicate_groups,
            "needs_review": [t.to_dict() for t in self.needs_review_transactions]
        }

class ExpenseAggregator:
    """
    Deterministic aggregator for multi-document financial extractions:
    - Detects possible duplicate transactions using multi-factor matching.
    - Preserves all transactions (never silently deletes duplicates).
    - Aggregates metrics strictly within isolated currency buckets.
    """

    @classmethod
    def aggregate(
        cls,
        transactions: List[NormalizedTransaction],
        total_documents: int = 1
    ) -> AggregationSummary:
        """
        Runs multi-factor duplicate detection and multi-currency aggregation.
        """
        # Step 1: Detect duplicate candidates
        annotated_txs, dup_groups = cls.detect_duplicates(transactions)

        # Step 2: Separate clean vs needs_review
        clean_txs = [t for t in annotated_txs if t.status != ExtractionStatus.NEEDS_REVIEW]
        needs_review_txs = [t for t in annotated_txs if t.status == ExtractionStatus.NEEDS_REVIEW]

        # Step 3: Compute isolated currency metrics
        currency_breakdowns = DecimalMathEngine.calculate_currency_breakdown(clean_txs)
        currency_summaries: Dict[str, CurrencySummary] = {}

        for curr, data in currency_breakdowns.items():
            cat_totals = data["category_totals"]
            top_cat = max(cat_totals.items(), key=lambda x: x[1])[0] if cat_totals else None

            currency_summaries[curr] = CurrencySummary(
                currency=curr,
                total_amount=data["total_amount"],
                transaction_count=data["transaction_count"],
                category_totals=cat_totals,
                average_transaction=data["average_transaction"],
                top_category=top_cat
            )

        dup_count = sum(1 for t in annotated_txs if t.is_duplicate_candidate)

        return AggregationSummary(
            total_documents=total_documents,
            total_transactions=len(transactions),
            clean_transactions_count=len(clean_txs),
            needs_review_count=len(needs_review_txs),
            duplicate_candidates_count=dup_count,
            currency_summaries=currency_summaries,
            all_transactions=annotated_txs,
            needs_review_transactions=needs_review_txs,
            duplicate_groups=dup_groups
        )

    @classmethod
    def detect_duplicates(
        cls,
        transactions: List[NormalizedTransaction]
    ) -> Tuple[List[NormalizedTransaction], List[Dict[str, Any]]]:
        """
        Multi-factor deterministic duplicate detection:
        Match key: (normalized_vendor, normalized_date, amount, currency)
        Flags transactions without deleting them.
        """
        seen_keys: Dict[Tuple[str, str, Decimal, str], List[NormalizedTransaction]] = {}
        for tx in transactions:
            # Build normalized composite key
            norm_vendor = tx.vendor.strip().lower()
            norm_date = tx.date or "NO_DATE"
            key = (norm_vendor, norm_date, tx.amount, tx.currency)

            if key not in seen_keys:
                seen_keys[key] = []
            seen_keys[key].append(tx)

        duplicate_groups: List[Dict[str, Any]] = []

        for key, tx_list in seen_keys.items():
            if len(tx_list) > 1:
                # Flag duplicates
                vendor, date, amount, curr = key
                dup_info = {
                    "vendor": vendor,
                    "date": date,
                    "amount": str(amount),
                    "currency": curr,
                    "occurrences_count": len(tx_list),
                    "sources": list(set(t.source_file for t in tx_list)),
                    "transaction_ids": [t.transaction_id for t in tx_list]
                }
                duplicate_groups.append(dup_info)

                # Mark each transaction in group (except first if desired, or all as candidate)
                for idx, t in enumerate(tx_list):
                    t.is_duplicate_candidate = True
                    other_sources = [other.source_file for other in tx_list if other != t]
                    t.duplicate_reason = (
                        f"Possible duplicate ({len(tx_list)} matches): "
                        f"Same vendor '{t.vendor}', date '{t.date}', and amount {t.currency} {t.amount} "
                        f"found in {', '.join(set(other_sources)) or 'same file'}."
                    )

        return transactions, duplicate_groups
