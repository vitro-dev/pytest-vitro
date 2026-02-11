"""Pytest vitro configs package."""

from __future__ import annotations

import json
from pathlib import Path

LOGGING_CONFIG = json.loads(
    (Path(__file__).parent / "logging.json").read_text(encoding="utf-8"),
)
