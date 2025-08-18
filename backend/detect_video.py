#!/usr/bin/env python3
"""
AI-generated video detection using SlowFast models.

This is the main CLI entry point for the refactored video detection system.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from slowfast_detection.cli import main

if __name__ == "__main__":
    sys.exit(main())
