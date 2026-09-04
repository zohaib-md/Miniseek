#!/usr/bin/env python3
"""
Convenience entry point for MiniSeek CLI.
Redirects directly to miniseek.cli:main().
"""
import sys
from miniseek.cli import main

if __name__ == "__main__":
    sys.exit(main())
