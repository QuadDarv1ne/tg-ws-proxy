#!/usr/bin/env python3
"""
macOS launcher for TG WS Proxy tray application.

Requirements:
    pip install -r requirements.txt

Usage:
    python macos.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tray import main

if __name__ == "__main__":
    main()
