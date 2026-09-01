import io
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional

from miniseek.applications.synthesizer.aggregator import (
    AggregationSummary,
    CurrencySummary
)
from miniseek.applications.synthesizer.types import NormalizedTransaction

class ExpenseReporter:
    """
    Deterministic offline financial report generator:
    - Generates Markdown summaries with exact Decimal calculations.
    - Generates CSV exports for spreadsheets.
    - Generates JSON audit trails for compliance.
    """

    @classmethod
    def render_markdown_report(cls, summary: AggregationSummary, title: str = "MiniSeek Expense Synthesis Report") -> str:
        """Renders a comprehensive, auditable Markdown report."""
        lines = [
            f"# 📊 {title}",
            "",
            "## 📌 Executive Summary",
            f"- **Total Documents Ingested**: {summary.total_documents}",
            f"- **Total Transactions Extracted**: {summary.total_transactions}",
            f"- **Clean Validated Transactions**: {summary.clean_transactions_count}",
            f"- **Duplicate Candidates Flagged**: {summary.duplicate_candidates_count}",
            f"- **Transactions Requiring Review**: {summary.needs_review_count}",
            ""
        ]

        # Multi-Currency Summaries
        if not summary.currency_summaries:
            lines.extend(["_No clean transactions extracted._", ""])
        else:
            lines.append("## 💵 Financial Breakdown by Currency")
            for curr, c_sum in sorted(summary.currency_summaries.items()):
                lines.extend([
                    f"### Currency: **{curr}**",
                    f"- **Total Expenditure**: `{curr} {c_sum.total_amount:,.2f}`",
                    f"- **Transaction Count**: {c_sum.transaction_count}",
                    f"- **Average Transaction**: `{curr} {c_sum.average_transaction:,.2f}`",
                    f"- **Primary Spending Category**: `{c_sum.top_category or 'N/A'}`",
                    "",
                    "#### Category Distribution",
                    f"| Category | Total ({curr}) | Share (%) |",
                    "|---|---|---|"
                ])

                for cat, amt in sorted(c_sum.category_totals.items(), key=lambda x: x[1], reverse=True):
                    pct = (amt / c_sum.total_amount * Decimal("100.00")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if c_sum.total_amount > 0 else Decimal("0.0")
                    lines.append(f"| {cat} | `{curr} {amt:,.2f}` | {pct}% |")
                lines.append("")

        # Duplicate Candidates Section
        if summary.duplicate_groups:
            lines.extend([
                "## ⚠️ Duplicate Candidates for User Review",
                "> **Note**: MiniSeek never silently deletes potential duplicates. Review the matched transactions below.",
                ""
            ])
            for idx, dup in enumerate(summary.duplicate_groups, start=1):
                lines.extend([
                    f"**Duplicate Group #{idx}**: `{dup['currency']} {dup['amount']}` at **{dup['vendor']}** (Date: {dup['date']})",
                    f"- **Occurrences**: {dup['occurrences_count']} found in files: `{'`, `'.join(dup['sources'])}`",
                    f"- **Transaction IDs**: {', '.join(dup['transaction_ids'])}",
                    ""
                ])

        # Needs Review / Ambiguous Section
        if summary.needs_review_transactions:
            lines.extend([
                "## 🔍 Transactions Requiring Review (Abstained)",
                "| ID | Source File | Vendor | Extracted Amount | Reason / Evidence |",
                "|---|---|---|---|---|"
            ])
            for t in summary.needs_review_transactions:
                ev = t.provenance.get("amount", t.provenance.get("vendor", None))
                snippet = ev.evidence_snippet if ev else "Ambiguous or incomplete data"
                lines.append(f"| `{t.transaction_id}` | `{t.source_file}` | {t.vendor} | `{t.currency} {t.amount}` | {snippet} |")
            lines.append("")

        # Itemized Ledger
        lines.extend([
            "## 📝 Itemized Transaction Ledger",
            "| ID | Date | Vendor | Category | Amount | Source | Status |",
            "|---|---|---|---|---|---|---|"
        ])
        for t in summary.all_transactions:
            flag = "⚠️ DUP" if t.is_duplicate_candidate else t.status.value
            lines.append(
                f"| `{t.transaction_id}` | {t.date or '—'} | {t.vendor} | {t.category} | "
                f"`{t.currency} {t.amount:,.2f}` | `{t.source_file}` | {flag} |"
            )
        lines.append("")

        lines.extend([
            "---",
            "*Report generated deterministically by MiniSeek Expense Synthesizer.*"
        ])

        return "\n".join(lines)

    @classmethod
    def render_csv_export(cls, summary: AggregationSummary) -> str:
        """Exports normalized transactions to standard CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Transaction_ID",
            "Date",
            "Vendor",
            "Category",
            "Amount",
            "Currency",
            "Status",
            "Is_Duplicate",
            "Duplicate_Reason",
            "Source_File"
        ])

        for t in summary.all_transactions:
            writer.writerow([
                t.transaction_id,
                t.date or "",
                t.vendor,
                t.category,
                str(t.amount),
                t.currency,
                t.status.value,
                "YES" if t.is_duplicate_candidate else "NO",
                t.duplicate_reason or "",
                t.source_file
            ])

        return output.getvalue()

    @classmethod
    def render_json_audit(cls, summary: AggregationSummary) -> str:
        """Exports full machine-readable JSON summary for audit logs."""
        return json.dumps(summary.to_dict(), indent=2)
