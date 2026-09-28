"""Generate opstoolkit/manifest.json -- the single source of truth for which
files the browser pages must fetch into the Pyodide virtual filesystem.

Same design as wacc-toolkit's manifest (which fixed a live-site
ModuleNotFoundError caused by a hand-maintained fetch list): the list is
generated from actual directory contents, so a forgotten update is not
possible. Run after adding, removing, or renaming any opstoolkit/*.py module
or data/*.json file, before committing.

Usage: python scripts/generate_manifest.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = REPO_ROOT / "opstoolkit"
DATA_DIR = REPO_ROOT / "data"
MANIFEST_PATH = PKG_DIR / "manifest.json"


def collect_modules() -> list[str]:
    return sorted(p.name for p in PKG_DIR.glob("*.py"))


def collect_data_files() -> list[str]:
    return sorted(p.name for p in DATA_DIR.glob("*.json"))


def main() -> None:
    manifest = {
        "generated": datetime.now(timezone.utc).date().isoformat(),
        "modules": collect_modules(),
        "data": collect_data_files(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}:")
    print(f"  modules: {manifest['modules']}")
    print(f"  data:    {manifest['data']}")


if __name__ == "__main__":
    main()
