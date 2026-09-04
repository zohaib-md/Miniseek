#!/usr/bin/env python3
"""
MiniSeek Unified Command-Line Interface.
Professional Developer CLI styled with modern Purple / Violet Cyber typography.
"""

import os
import sys
import argparse
import time
import platform
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from miniseek.core.config import Config, DEFAULT_CONFIG
from miniseek.core.security import PathSecurity, SecurityError
from miniseek.llm import OllamaProvider
from miniseek.ui import (
    Style, paint, purple, bright_purple, deep_purple, neon_purple,
    green, bright_green, amber, red, bright_red, gray, dim, bold, white, bright_white,
    GLYPH_CHECK, GLYPH_CROSS, GLYPH_WARN, GLYPH_INFO, GLYPH_DOT,
    GLYPH_ARROW, GLYPH_CHEVRON, GLYPH_DIAMOND, GLYPH_BLOCK,
    badge, badge_purple, badge_success, badge_warning, badge_error, badge_info,
    success_line, error_line, warn_line, info_line, step_line, divider,
    print_banner, render_card, render_key_values, render_table, render_progress_bar
)


def format_bytes(bytes_count: int) -> str:
    """Formats bytes into human-readable string."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def resolve_target_path(user_path: str) -> Optional[Path]:
    """Resolves target path, with seamless fallback to bundled repo samples if applicable."""
    target = Path(user_path).expanduser().resolve()
    if target.exists():
        return target
    # Check if user meant bundled samples in repo root
    repo_root = Path(__file__).resolve().parent.parent
    clean_path = user_path.lstrip("./")
    bundled = (repo_root / clean_path).resolve()
    if bundled.exists():
        return bundled
    return None


# ============================================================================
# Subcommand Handlers
# ============================================================================

def cmd_version(args: argparse.Namespace) -> int:
    """Prints MiniSeek version, environment diagnostics, and hardware profile."""
    ollama_host = getattr(args, "host", DEFAULT_CONFIG.ollama_host)

    # Probe Ollama connection
    ollama_status_str = f"{gray('○')} {gray('Offline / Not Running')}"
    models_str = gray("None")
    try:
        req = urllib.request.Request(f"{ollama_host.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            import json
            data = json.loads(resp.read().decode())
            installed_models = [m.get("name") for m in data.get("models", [])]
            ollama_status_str = f"{bright_green('●')} {green(bold('Connected'))} {gray(f'({len(installed_models)} models)')}"
            if installed_models:
                models_str = ", ".join(purple(m) for m in installed_models)
    except Exception:
        pass

    items = [
        ("MiniSeek Version", f"{bright_purple(bold('1.0.0'))} {badge('STABLE', Style.BG_PURPLE)}"),
        ("Python Runtime", f"{white(platform.python_version())} {gray(f'({platform.python_implementation()})')}"),
        ("Host Platform", f"{white(platform.system())} {gray(f'{platform.release()} ({platform.machine()})')}"),
        ("Target Profile", f"{bright_purple(bold('Apple Silicon M1'))} {gray('(8 GB Unified Memory)')}"),
        ("Ollama Server", f"{white(ollama_host)}"),
        ("Ollama Status", ollama_status_str),
        ("Installed Models", models_str),
        ("Operating Invariant", f"{dim('Model proposes • Harness validates • Python executes')}"),
        ("External Bloat", f"{bright_green('Zero dependencies')} {gray('(pure standard library)')}"),
    ]

    print_banner("System Diagnostics & Environment Profile")
    render_key_values(items, width=72, title="Environment Diagnostics")
    print()
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Executes deterministic filesystem scan."""
    from miniseek.applications.janitor.scanner import FileScanner

    target = resolve_target_path(args.path)
    if not target or not target.is_dir():
        error_line(f"Target directory does not exist or is not a directory: {Path(args.path).resolve()}")
        return 1

    print_banner(f"Scanning Directory: {target.name}")

    scanner = FileScanner()
    res = scanner.scan(target, include_hidden=args.hidden)

    duration_ms = res.scan_duration_sec * 1000
    timing_str = f"{bright_purple(bold(f'{duration_ms:.2f} ms'))}"

    metrics = [
        ("Target Path", white(str(target))),
        ("Files Discovered", bold(bright_white(str(res.total_files)))),
        ("Total Storage", bright_purple(format_bytes(res.total_bytes))),
        ("Symlinks Skipped", amber(str(len(res.skipped_symlinks))) if res.skipped_symlinks else green("0 (Safe)")),
        ("Scan Latency", timing_str),
    ]
    render_key_values(metrics, width=72, title="Scan Summary")

    # Extension breakdown
    ext_counts: Dict[str, int] = {}
    for f in res.files:
        ext_label = f.extension if f.extension else "(no extension)"
        ext_counts[ext_label] = ext_counts.get(ext_label, 0) + 1

    if ext_counts:
        print()
        headers = ["Extension", "Files", "Share", "Distribution"]
        rows = []
        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
        total_f = max(1, res.total_files)

        for ext, count in sorted_exts[:12]:
            pct = count / total_f
            pct_str = f"{pct * 100:.1f}%"
            bar_len = int(round(16 * pct))
            bar_visual = purple("■" * bar_len) + paint("·" * (16 - bar_len), Style.SLATE_PURPLE)
            rows.append([purple(ext), str(count), gray(pct_str), bar_visual])

        render_table(headers, rows, alignments=["left", "right", "right", "left"])

    if res.skipped_symlinks:
        print()
        warn_line(f"Skipped {len(res.skipped_symlinks)} symlinks to preserve boundary integrity:")
        for sym in res.skipped_symlinks[:5]:
            print(f"    {GLYPH_CHEVRON} {gray(sym.relative_path)} -> {amber(str(sym.symlink_target))}")
        if len(res.skipped_symlinks) > 5:
            print(f"    {dim(f'... and {len(res.skipped_symlinks) - 5} more symlinks')}")

    print()
    return 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    """Performs multi-stage buffered SHA-256 duplicate analysis."""
    from miniseek.applications.janitor.scanner import FileScanner

    target = resolve_target_path(args.path)
    if not target or not target.is_dir():
        error_line(f"Target directory does not exist: {Path(args.path).resolve()}")
        return 1

    print_banner(f"SHA-256 Deduplication Analysis: {target.name}")

    scanner = FileScanner()
    scan_res = scanner.scan(target, include_hidden=False)
    duplicates = scan_res.duplicate_groups

    if not duplicates:
        render_card(
            "Deduplication Verdict",
            [
                f"{GLYPH_CHECK} {bright_green(bold('Zero Duplicate Files Detected'))}",
                f"{dim('All')} {bold(str(scan_res.total_files))} {dim('files have distinct SHA-256 content hashes.')}",
                f"{gray('Reclaimable Space : 0 B (100% Storage Efficiency)')}"
            ],
            width=72,
            border_color=Style.GREEN
        )
        print()
        return 0

    total_wasted = sum(d.wasted_bytes for d in duplicates)
    reclaim_badge = badge(f"RECLAIMABLE: {format_bytes(total_wasted)}", Style.BG_AMBER, Style.WHITE)

    summary_items = [
        ("Target Path", white(str(target))),
        ("Duplicate Groups", bold(bright_white(str(len(duplicates))))),
        ("Wasted Space", f"{bright_red(bold(format_bytes(total_wasted)))}  {reclaim_badge}"),
        ("Detection Engine", gray("Streaming 64KB chunked SHA-256")),
    ]
    render_key_values(summary_items, width=72, title="Duplicate Groups Detected")
    print()

    headers = ["#", "SHA-256 Hash", "Copies", "File Size", "Wasted Space", "Primary File"]
    rows = []
    for idx, grp in enumerate(duplicates[:10], 1):
        first_rel = Path(grp.files[0].path).relative_to(target)
        rows.append([
            str(idx),
            gray(grp.sha256[:12] + "..."),
            bold(str(len(grp.files))),
            format_bytes(grp.size_bytes),
            bright_red(format_bytes(grp.wasted_bytes)),
            white(str(first_rel)[:28])
        ])

    render_table(headers, rows, alignments=["center", "left", "right", "right", "right", "left"])
    print()
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    """Performs semantic categorization, plan freezing, and transactional execution."""
    from miniseek.applications.janitor.scanner import FileScanner
    from miniseek.applications.janitor.categorizer import SemanticCategorizer
    from miniseek.applications.janitor.planner import PlanBuilder
    from miniseek.harness.transaction import TransactionExecutor

    target = resolve_target_path(args.path)
    if not target or not target.is_dir():
        error_line(f"Target directory does not exist: {Path(args.path).resolve()}")
        return 1

    config = Config(
        model_name=args.model or DEFAULT_CONFIG.model_name,
        ollama_host=args.host or DEFAULT_CONFIG.ollama_host
    )

    mode_badge = badge("DRY RUN", Style.BG_PURPLE) if args.dry_run else badge("LIVE RUN", Style.BG_GREEN)
    print_banner(f"Semantic File Reorganization  {mode_badge}")

    scanner = FileScanner(config=config)
    scan_res = scanner.scan(target, include_hidden=False)

    if scan_res.total_files == 0:
        info_line("Target directory contains no files to organize.")
        return 0

    info_line(f"Scanning {bold(str(scan_res.total_files))} files with model {purple(bold(config.model_name))}...")
    llm = OllamaProvider(model_name=config.model_name, host=config.ollama_host)
    categorizer = SemanticCategorizer(llm=llm, config=config)

    categorization_results = []
    print()
    for idx, f in enumerate(scan_res.files, 1):
        pbar = render_progress_bar(idx, scan_res.total_files, width=16)
        print(f" {pbar}  {f.name[:24]:<24} ", end="", flush=True)

        cat, telemetry = categorizer.categorize_file(f, root_dir=target)
        dest = categorizer.get_destination_path(f, cat, target)
        categorization_results.append({
            "file_info": f,
            "category": cat,
            "destination_path": dest,
            "telemetry": telemetry
        })

        if cat == "NEEDS_REVIEW":
            print(f"❯ {amber('NEEDS_REVIEW')} {dim('(abstained)')}")
        else:
            print(f"❯ {bright_purple(bold(cat))}")

    # Build plan
    plan = PlanBuilder.build_plan(
        root_path=target,
        categorization_results=categorization_results,
        model_metadata={"model": config.model_name},
        scanner=scanner
    )

    print()
    plan_items = [
        ("Plan ID", purple(plan.plan_id)),
        ("Plan Hash", gray(plan.plan_hash[:20] + "... ") + badge("SHA-256", Style.BG_PURPLE)),
        ("Move Operations", bold(str(len(plan.operations)))),
        ("Abstained (Needs Review)", amber(str(len(plan.needs_review)))),
        ("Execution Status", badge("FROZEN", Style.BG_PURPLE)),
    ]
    render_key_values(plan_items, width=72, title="Frozen Plan Specification")

    # Render Preview Table
    if plan.operations:
        print()
        headers = ["Source File", "Target Category", "Destination Path"]
        rows = []
        for op in plan.operations[:8]:
            src_rel = Path(op.source_path).name
            rows.append([white(src_rel), bright_purple(op.category), gray(op.relative_destination)])
        if len(plan.operations) > 8:
            rows.append([dim(f"... and {len(plan.operations) - 8} more"), dim("..."), dim("...")])
        render_table(headers, rows)

    if args.dry_run:
        print()
        success_line(f"Dry run complete. Plan {purple(plan.plan_hash[:12])} verified. Zero files modified.")
        print()
        return 0

    if not plan.operations:
        print()
        info_line("No files require moving. All files either classified or marked NEEDS_REVIEW.")
        return 0

    if not args.auto_approve:
        print()
        try:
            prompt_str = f" {GLYPH_ARROW} Proceed with executing {bold(str(len(plan.operations)))} operations? {gray('[y/N]')}: "
            confirm = input(prompt_str).strip().lower()
            if confirm not in ("y", "yes"):
                warn_line("Operation cancelled by user.")
                return 0
        except KeyboardInterrupt:
            print("\nAborted.")
            return 1

    print()
    info_line("Executing plan transactions deterministically...")
    executor = TransactionExecutor(root_dir=target, scanner=scanner)
    manifest = executor.execute_plan(plan)

    status_badge = badge_success("COMMITTED") if manifest.status == "COMMITTED" else badge_error(manifest.status)
    result_items = [
        ("Run ID", purple(bold(manifest.run_id))),
        ("Execution Status", status_badge),
        ("Completed Moves", bright_green(bold(f"{manifest.operations_completed} / {len(manifest.operations)}"))),
        ("Failed Operations", bright_red(str(manifest.operations_failed)) if manifest.operations_failed else green("0")),
        ("Audit Manifest", gray(str(target / '.miniseek' / 'history' / f'{manifest.run_id}.json'))),
    ]

    print()
    render_key_values(result_items, width=72, title="Transaction Execution Verdict")
    print(f"\n {gray('To rollback this run at any time:')} {bright_purple(f'miniseek undo {manifest.run_id} --path {target}')}\n")
    return 0 if manifest.operations_failed == 0 else 1


def cmd_history(args: argparse.Namespace) -> int:
    """Lists past execution runs and audit manifests."""
    from miniseek.harness.history import HistoryManager

    target = Path(args.path or os.getcwd()).resolve()
    runs = HistoryManager.list_runs(target)

    print_banner(f"Execution History Audit: {target.name}")

    if not runs:
        render_card(
            "Run History",
            [
                f"{GLYPH_INFO} {dim('No execution history found in this directory.')}",
                f"{gray('Audit manifests will be stored in:')} {white(str(target / '.miniseek' / 'history'))}"
            ],
            width=72
        )
        print()
        return 0

    headers = ["Run ID", "Date / Time", "Operations", "Status", "Plan ID"]
    rows = []
    for r in runs:
        status_raw = r.status
        if status_raw == "COMMITTED":
            status_p = badge("COMMITTED", Style.BG_GREEN)
        elif status_raw in ("UNDONE", "ROLLED_BACK"):
            status_p = badge("UNDONE", Style.BG_AMBER)
        else:
            status_p = badge(status_raw, Style.BG_PURPLE)

        rows.append([
            purple(r.run_id),
            gray(r.timestamp[:19].replace("T", " ")),
            bold(str(len(r.operations))),
            status_p,
            gray(r.plan_id[:16] + "...")
        ])

    render_table(headers, rows, alignments=["left", "left", "right", "center", "left"])
    print(f"\n {gray('Total recorded runs:')} {bold(str(len(runs)))}\n")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    """Safely reverts a previous run in reverse order."""
    from miniseek.harness.history import HistoryManager
    from miniseek.harness.undo import UndoEngine

    target = Path(args.path or os.getcwd()).resolve()
    manifest = HistoryManager.get_run(args.run_id, root_dir=target)

    if not manifest:
        error_line(f"Run '{args.run_id}' not found in {target / '.miniseek' / 'history'}")
        return 1

    print_banner(f"Reverse-Order Undo Rollback")

    info_items = [
        ("Target Run ID", purple(args.run_id)),
        ("Original Status", badge(manifest.status, Style.BG_PURPLE)),
        ("Total Operations", bold(str(len(manifest.operations)))),
        ("Prime Invariant", dim("Never overwrites newer user files merely to undo")),
    ]
    render_key_values(info_items, width=72, title="Rollback Target Specification")
    print()

    engine = UndoEngine()
    result = engine.execute_undo(manifest, root_dir=target)

    status_badge = badge_success("UNDONE") if result.status == "UNDONE" else badge_warning(result.status)
    verdict_items = [
        ("Undo Status", status_badge),
        ("Operations Undone", bright_green(bold(str(result.operations_undone)))),
        ("Conflicts Detected", amber(bold(str(result.operations_conflict)))),
        ("Not Applicable", gray(str(result.operations_not_applicable))),
    ]
    render_key_values(verdict_items, width=72, title="Undo Execution Results")

    if result.conflict_details:
        print()
        warn_line("Conflicts Encountered (User work preserved non-destructively):")
        for c in result.conflict_details:
            print(f"    {GLYPH_CHEVRON} {amber(str(c))}")

    print()
    return 0 if result.operations_conflict == 0 else 1


def cmd_expenses(args: argparse.Namespace) -> int:
    """Ingests documents and synthesizes expense reports with exact Decimal math."""
    from miniseek.applications.synthesizer.cli import SynthesizerCLI

    target = resolve_target_path(args.path)
    if not target:
        error_line(f"Target path does not exist: {Path(args.path).resolve()}")
        return 1
    out_dir = Path(args.output).resolve() if args.output else None

    config = Config(
        model_name=args.model or DEFAULT_CONFIG.model_name,
        ollama_host=args.host or DEFAULT_CONFIG.ollama_host
    )

    print_banner(f"Private Expense Synthesizer")

    items = [
        ("Document Source", white(str(target))),
        ("Semantic Model", purple(bold(config.model_name))),
        ("Arithmetic Engine", f"{bright_green('Exact Decimal')} {dim('(Zero LLM Math)')}"),
        ("Security Boundary", green("Untrusted XML Delimiters (100% Contained)")),
    ]
    render_key_values(items, width=72, title="Synthesizer Configuration")
    print()

    llm = OllamaProvider(model_name=config.model_name, host=config.ollama_host)
    cli = SynthesizerCLI(llm=llm, config=config)
    cli.process_path(target, output_dir=out_dir, verbose=True)
    print()
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Launches interactive local AI agent session."""
    from miniseek.tools import WorkspaceSandbox, ToolRegistry
    from miniseek.agent import MiniSeekAgent, PlanningAgent
    from miniseek.memory import MemoryStore
    from miniseek.eval import EvaluationLogger

    target_ws = Path(args.workspace or os.getcwd()).resolve()
    target_ws.mkdir(parents=True, exist_ok=True)

    model_name = args.model or "qwen2.5:1.5b"
    llm = OllamaProvider(model_name=model_name, host=args.host or DEFAULT_CONFIG.ollama_host)
    sandbox = WorkspaceSandbox(workspace_path=str(target_ws))
    memory = MemoryStore(store_path=str(target_ws / ".miniseek_memory.json"))
    tools = ToolRegistry(sandbox=sandbox, memory=memory)
    eval_logger = EvaluationLogger()

    mode = args.mode.lower()
    if mode == "planning":
        agent = PlanningAgent(llm=llm, tools=tools, max_steps=10)
    else:
        mode = "react"
        agent = MiniSeekAgent(llm=llm, tools=tools, max_steps=10)

    print_banner(f"Interactive Agent Laboratory")

    items = [
        ("Reasoning Mode", badge_purple(mode.upper())),
        ("Local Model", purple(bold(model_name))),
        ("Sandbox Path", white(str(target_ws))),
        ("Commands", gray("'mode' (toggle) • 'memory' (view) • 'exit' (quit)")),
    ]
    render_key_values(items, width=72, title="Session Initialized")

    while True:
        try:
            print()
            prompt = f"{bright_purple('miniseek')} {gray('❯')} "
            user_input = input(prompt).strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                info_line("Exiting session.")
                break
            if user_input.lower() == "mode":
                if mode == "react":
                    mode = "planning"
                    agent = PlanningAgent(llm=llm, tools=tools, max_steps=10)
                    success_line(f"Switched mode to {bold('Plan-First')}")
                else:
                    mode = "react"
                    agent = MiniSeekAgent(llm=llm, tools=tools, max_steps=10)
                    success_line(f"Switched mode to {bold('ReAct')}")
                continue
            if user_input.lower() == "memory":
                print()
                render_card("Persistent Memory Store", [memory.get_summary()], width=72)
                continue

            metrics = agent.run(user_input)
            eval_logger.log_run(
                task=user_input,
                model_name=model_name,
                agent_mode=mode,
                metrics=metrics
            )
        except KeyboardInterrupt:
            print("\n")
            info_line("Interrupted. Exiting session.")
            break
        except Exception as e:
            error_line(f"Agent Error: {e}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Runs deterministic offline benchmark evaluation."""
    from miniseek.evaluation.benchmark import BenchmarkRunner
    from miniseek.applications.janitor.categorizer import SemanticCategorizer

    dataset_path = Path(args.dataset or "evaluation/datasets/organizer/golden_standard.json").resolve()
    if not dataset_path.exists():
        error_line(f"Dataset file not found: {dataset_path}")
        return 1

    print_banner(f"Benchmark Runner: {dataset_path.name}")

    config = Config(
        model_name=args.model or DEFAULT_CONFIG.model_name,
        ollama_host=args.host or DEFAULT_CONFIG.ollama_host
    )
    llm = OllamaProvider(model_name=config.model_name, host=config.ollama_host)
    categorizer = SemanticCategorizer(llm=llm, config=config)

    samples = BenchmarkRunner.load_dataset(dataset_path)
    info_line(f"Loaded {bold(str(len(samples)))} evaluation samples. Executing offline benchmark...")

    import tempfile
    with tempfile.TemporaryDirectory() as tmp_root:
        metrics = BenchmarkRunner.evaluate(categorizer, samples, Path(tmp_root))
        report = BenchmarkRunner.format_report(metrics)
        print("\n" + report)

        if args.output:
            out_file = Path(args.output).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                import json
                json.dump(metrics.to_dict(), f, indent=2)
            success_line(f"Saved benchmark results: {out_file}")

    return 0


# ============================================================================
# Hermes-Style Help Screen
# ============================================================================

def print_custom_help() -> None:
    """Renders a sleek Hermes-style organized help screen."""
    print_banner("Deterministic Edge AI Agent Harness")

    print(f" {bold(white('USAGE:'))}  {bright_purple('miniseek')} {purple('<command>')} {gray('[flags]')}\n")

    # Command Groups
    groups = [
        ("CORE FILESYSTEM OPERATIONS", [
            ("scan", "<path>", "Deterministic directory inspection, file counts & extensions"),
            ("dedupe", "<path>", "Streaming SHA-256 duplicate finder & wasted space metrics"),
            ("organize", "<path>", "Semantic file categorization, plan freezing & safe moves"),
        ]),
        ("STATE & AUDIT MANAGEMENT", [
            ("history", "[--path]", "Inspect past organization runs and audit manifests"),
            ("undo", "<run-id>", "Conservative reverse-order rollback of a previous run"),
        ]),
        ("AGENT APPLICATIONS", [
            ("expenses", "<path>", "Ingest receipts/CSVs & synthesize reports with Decimal math"),
            ("agent", "[--mode]", "Interactive local AI agent playground (ReAct vs Plan-First)"),
        ]),
        ("EVALUATION & DIAGNOSTICS", [
            ("benchmark", "[--dataset]", "Run reproducible offline accuracy and adversarial benchmarks"),
            ("version", "", "Display host diagnostics, environment profile & Ollama status"),
        ])
    ]

    for grp_title, cmds in groups:
        print(f" {bold(bright_purple(grp_title))}")
        print(paint(" " + "─" * 68, Style.SLATE_PURPLE))
        for cmd_name, arg_str, desc in cmds:
            name_styled = bold(white(cmd_name.ljust(11)))
            arg_styled = purple(arg_str.ljust(13))
            print(f"   {name_styled} {arg_styled} {desc}")
        print()

    # Common Flags
    print(f" {bold(bright_purple('GLOBAL FLAGS'))}")
    print(paint(" " + "─" * 68, Style.SLATE_PURPLE))
    print(f"   {bold(white('-h, --help'))}           Show this formatted help manual")
    print(f"   {bold(white('-V, --version'))}        Show system version and exit")
    print(f"   {bold(white('--host <url>'))}         Ollama API endpoint {gray('(default: http://127.0.0.1:11434)')}")
    print()

    # Examples
    print(f" {bold(bright_purple('PRACTICAL EXAMPLES'))}")
    print(paint(" " + "─" * 68, Style.SLATE_PURPLE))
    print(f"   {dim('# Inspect folder sizes & extension metrics')}")
    print(f"   {bright_purple('miniseek scan')} {white('./samples')}\n")
    print(f"   {dim('# Reclaim wasted storage from duplicate files')}")
    print(f"   {bright_purple('miniseek dedupe')} {white('~/Downloads')}\n")
    print(f"   {dim('# Preview semantic organization without touching any files')}")
    print(f"   {bright_purple('miniseek organize')} {white('./messy_folder')} {purple('--dry-run')}\n")
    print(f"   {dim('# Extract expenses with exact Decimal math (zero LLM math)')}")
    print(f"   {bright_purple('miniseek expenses')} {white('./receipts')} {purple('--output ./reports')}\n")
    print(f"   {dim('# Launch interactive agent laboratory')}")
    print(f"   {bright_purple('miniseek agent')} {purple('--mode planning')}\n")

    print(f" {gray('Documentation & Research:')} {purple('https://github.com/zohaib-md/Miniseek')}\n")


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser."""
    parser = argparse.ArgumentParser(prog="miniseek", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-V", "--version", action="store_true")
    parser.add_argument("--host", type=str, default=DEFAULT_CONFIG.ollama_host)

    subparsers = parser.add_subparsers(dest="command")

    p_scan = subparsers.add_parser("scan", add_help=False)
    p_scan.add_argument("path", type=str, nargs="?", default=".")
    p_scan.add_argument("--hidden", action="store_true")

    p_dedupe = subparsers.add_parser("dedupe", add_help=False)
    p_dedupe.add_argument("path", type=str, nargs="?", default=".")

    p_org = subparsers.add_parser("organize", add_help=False)
    p_org.add_argument("path", type=str, nargs="?", default=".")
    p_org.add_argument("--model", "-m", type=str, default=None)
    p_org.add_argument("--dry-run", "-d", action="store_true")
    p_org.add_argument("--auto-approve", "-y", action="store_true")

    p_hist = subparsers.add_parser("history", add_help=False)
    p_hist.add_argument("--path", "-p", type=str, default=None)

    p_undo = subparsers.add_parser("undo", add_help=False)
    p_undo.add_argument("run_id", type=str, nargs="?", default=None)
    p_undo.add_argument("--path", "-p", type=str, default=None)

    p_exp = subparsers.add_parser("expenses", add_help=False)
    p_exp.add_argument("path", type=str, nargs="?", default=".")
    p_exp.add_argument("--output", "-o", type=str, default=None)
    p_exp.add_argument("--model", "-m", type=str, default=None)

    p_agent = subparsers.add_parser("agent", add_help=False)
    p_agent.add_argument("--mode", type=str, choices=["react", "planning"], default="react")
    p_agent.add_argument("--model", "-m", type=str, default="qwen2.5:1.5b")
    p_agent.add_argument("--workspace", "-w", type=str, default=None)

    p_bench = subparsers.add_parser("benchmark", add_help=False)
    p_bench.add_argument("--dataset", type=str, default=None)
    p_bench.add_argument("--model", "-m", type=str, default=None)
    p_bench.add_argument("--output", "-o", type=str, default=None)

    subparsers.add_parser("version", add_help=False)

    return parser


def main() -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args()

    if args.help or (not args.command and not args.version):
        print_custom_help()
        return 0

    if args.version or args.command == "version":
        return cmd_version(args)

    command_handlers = {
        "scan": cmd_scan,
        "dedupe": cmd_dedupe,
        "organize": cmd_organize,
        "history": cmd_history,
        "undo": cmd_undo,
        "expenses": cmd_expenses,
        "agent": cmd_agent,
        "benchmark": cmd_benchmark,
    }

    handler = command_handlers.get(args.command)
    if handler:
        try:
            return handler(args)
        except KeyboardInterrupt:
            print()
            warn_line("Interrupted by user.")
            return 130
        except Exception as e:
            error_line(f"Command Error: {e}")
            return 1
    else:
        print_custom_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
