"""Test path setup for the app's container-oriented package layout."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "automation_inspector"
sys.path.insert(0, str(APP_ROOT))
