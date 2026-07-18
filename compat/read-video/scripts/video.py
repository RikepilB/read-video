"""Forward legacy read-video CLI calls to the canonical Voidscape engine."""
from __future__ import annotations

import os
import runpy
from pathlib import Path


LEGACY_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = LEGACY_ROOT.parent
CANONICAL = SKILLS_ROOT / "voidscape" / "scripts" / "video.py"
LEGACY_WORKSPACE = LEGACY_ROOT / "workspace.json"

if not CANONICAL.exists():
    raise SystemExit("Voidscape is not installed next to this read-video compatibility skill. Re-run install-skill.")
if LEGACY_WORKSPACE.exists():
    os.environ.setdefault("VOIDSCAPE_WORKSPACE_PATH", str(LEGACY_WORKSPACE))

runpy.run_path(str(CANONICAL), run_name="__main__")
