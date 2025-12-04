#!/usr/bin/env python3
"""
TrufflePiggie - GitHub OSINT Tool for Secret Discovery
Entry point wrapper for easy execution.

Usage:
    python trufflepiggie.py -q "example.com" -o results.json
    python trufflepiggie.py --help
"""

import sys
from pathlib import Path

# Ensure the src directory is in the path
sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == "__main__":
    sys.exit(main())

