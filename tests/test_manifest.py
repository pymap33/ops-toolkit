"""Guards against manifest drift: a new opstoolkit/*.py module or data/*.json
file added without regenerating opstoolkit/manifest.json, which is what the
browser's Pyodide loader actually fetches.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_manifest import MANIFEST_PATH, collect_data_files, collect_modules


def test_manifest_exists():
    assert MANIFEST_PATH.exists(), (
        "opstoolkit/manifest.json is missing -- run scripts/generate_manifest.py"
    )


def test_manifest_modules_match_directory():
    manifest = json.loads(MANIFEST_PATH.read_text())
    actual = collect_modules()
    assert manifest["modules"] == actual, (
        f"manifest module list is stale (manifest={manifest['modules']!r}, "
        f"actual={actual!r}). Run scripts/generate_manifest.py and commit the result."
    )


def test_manifest_data_matches_directory():
    manifest = json.loads(MANIFEST_PATH.read_text())
    actual = collect_data_files()
    assert manifest["data"] == actual, (
        f"manifest data list is stale (manifest={manifest['data']!r}, "
        f"actual={actual!r}). Run scripts/generate_manifest.py and commit the result."
    )
