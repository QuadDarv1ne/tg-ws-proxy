#!/usr/bin/env python3
"""
Linux launcher for TG WS Proxy tray application.

Requirements:
    pip install -r requirements.txt
    sudo apt install python3-pil python3-pil.imagetk libappindicator3-1

Usage:
    python linux.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tray import main

if __name__ == "__main__":
    main()
