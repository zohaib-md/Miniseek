#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from miniseek.applications.synthesizer.cli import SynthesizerCLI

def main():
    parser = argparse.ArgumentParser(
        prog="miniseek",
        description="MiniSeek: Local-First Deterministic AI Agent Harness"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # miniseek expenses <path>
    expenses_parser = subparsers.add_parser("expenses", help="Ingest and synthesize expenses from documents")
    expenses_parser.add_argument("path", type=str, help="Directory or file path to process")
    expenses_parser.add_argument("--output", "-o", type=str, default=None, help="Output directory for reports")

    args = parser.parse_args()

    if args.command == "expenses":
        target = Path(args.path)
        out_dir = Path(args.output) if args.output else None
        cli = SynthesizerCLI()
        cli.process_path(target, output_dir=out_dir, verbose=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
