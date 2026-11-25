#!/usr/bin/env python3
"""Compatibility wrapper. Prefer: python -m soulforge.ui_server"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from soulforge.ui_server import main

if __name__ == "__main__":
    raise SystemExit(main())
