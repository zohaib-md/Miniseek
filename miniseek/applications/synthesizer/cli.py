import os
import sys
import time
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any, Optional

from miniseek.llm import LLMProvider, OllamaProvider
from miniseek.core.config import Config, DEFAULT_CONFIG
from miniseek.core.security import PathSecurity, SecurityError
from miniseek.applications.synthesizer.ingestion import DocumentIngestionEngine, IngestedDocument
from miniseek.applications.synthesizer.extractor import SemanticExpenseExtractor
from miniseek.applications.synthesizer.math_engine import ExpenseNormalizer, DecimalMathEngine
from miniseek.applications.synthesizer.aggregator import ExpenseAggregator, AggregationSummary
from miniseek.applications.synthesizer.reporter import ExpenseReporter
from miniseek.applications.synthesizer.types import NormalizedTransaction, ExtractionStatus

class SynthesizerCLI:
    """
    Real-world Command-Line Interface for the Expense Synthesizer.
    Executes the complete deterministic + semantic extraction pipeline:
    ingest -> extract -> normalize -> aggregate -> report.
    """

    def __init__(self, llm: Optional[LLMProvider] = None, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG
        self.llm = llm or OllamaProvider(model_name=self.config.model_name, host=self.config.ollama_host)
        self.extractor = SemanticExpenseExtractor(llm=self.llm, config=self.config)

    def process_path(
        self,
        target_path: Path,
        output_dir: Optional[Path] = None,
        verbose: bool = True
    ) -> AggregationSummary:
        """Processes all documents in target_path and generates authoritative reports."""
        target_path = PathSecurity.get_canonical_path(target_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Path does not exist: {target_path}")

        files_to_process: List[Path] = []
        if target_path.is_file():
            files_to_process.append(target_path)
        else:
            for root, _, files in os.walk(target_path):
                for f in sorted(files):
                    if f.startswith("."):
                        continue
                    files_to_process.append(Path(root) / f)

        if verbose:
            print("═" * 70)
            print("   MINISEEK EXPENSE SYNTHESIZER — PROCESSING RUN")
            print("═" * 70)
            print(f"Target Directory: {target_path}")
            print(f"Documents Found:  {len(files_to_process)}")
            print("─" * 70)

        all_normalized_transactions: List[NormalizedTransaction] = []
        ingested_count = 0

        for f in files_to_process:
            doc = DocumentIngestionEngine.ingest_file(f, root_dir=target_path.parent if target_path.is_file() else target_path)
            if doc.error_message:
                if verbose:
                    print(f"  ⚠️  [SKIPPED] {doc.file_name}: {doc.error_message}")
                continue

            ingested_count += 1
            raw_txs, telemetries = self.extractor.extract_from_document(doc)

            for tx in raw_txs:
                norm_tx = ExpenseNormalizer.normalize_transaction(tx, source_file=doc.file_name)
                all_normalized_transactions.append(norm_tx)

            if verbose:
                status_icon = "📄" if not doc.is_scanned_pdf else "🖼️"
                print(f"  {status_icon}  {doc.file_name:<35} -> {len(raw_txs)} transactions extracted")

        # Aggregate metrics
        summary = ExpenseAggregator.aggregate(all_normalized_transactions, total_documents=ingested_count)

        # Generate Reports
        out_dir = output_dir or (target_path / ".miniseek" / "reports" if target_path.is_dir() else target_path.parent / ".miniseek" / "reports")
        out_dir.mkdir(parents=True, exist_ok=True)

        md_report = ExpenseReporter.render_markdown_report(summary)
        csv_report = ExpenseReporter.render_csv_export(summary)
        json_report = ExpenseReporter.render_json_audit(summary)

        md_path = out_dir / "expense_report.md"
        csv_path = out_dir / "expense_report.csv"
        json_path = out_dir / "expense_report.json"

        md_path.write_text(md_report, encoding="utf-8")
        csv_path.write_text(csv_report, encoding="utf-8")
        json_path.write_text(json_report, encoding="utf-8")

        if verbose:
            print("═" * 70)
            print("                 SYNTHESIS SUMMARY")
            print("═" * 70)
            print(f"  • Files Processed:             {summary.total_documents}")
            print(f"  • Transactions Extracted:      {summary.total_transactions}")
            print(f"  • Clean Validated:             {summary.clean_transactions_count}")
            print(f"  • Possible Duplicates:         {summary.duplicate_candidates_count}")
            print(f"  • Needs Review:                {summary.needs_review_count}")
            print("─" * 70)
            print("CURRENCY TOTALS (EXACT DECIMAL ARITHMETIC)")
            for curr, c_sum in sorted(summary.currency_summaries.items()):
                print(f"  • {curr:<6} Total: {curr} {c_sum.total_amount:>12,.2f}  ({c_sum.transaction_count} txs, avg: {c_sum.average_transaction})")
            print("─" * 70)
            print("REPORTS GENERATED DETERMINISTICALLY:")
            print(f"  📁 Markdown: {md_path}")
            print(f"  📊 CSV:      {csv_path}")
            print(f"  🧾 JSON:     {json_path}")
            print("═" * 70)

        return summary
