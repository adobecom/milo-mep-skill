#!/usr/bin/env python3
"""
Lint an MEP manifest — convenience wrapper that adds .xlsx support to the
canonical JS rule engine (lint-core.mjs). The rules live in ONE place (JS, so
Node/browser and this wrapper never drift); this just reads the .xlsx (via
mep_xlsx) and pipes the normalized JSON into `node lint.mjs -`.

    python lint_manifest.py <manifest.xlsx|manifest.json>

Requires Node. Equivalent manual commands:
    node scripts/lint.mjs <manifest.json | URL>
    python scripts/mep_xlsx.py read <file.xlsx> | node scripts/lint.mjs -
Or lint a published .json in the browser with scripts/lint.html (no Node).
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    node = shutil.which("node")
    lint_js = os.path.join(HERE, "lint.mjs")
    if not node:
        sys.stderr.write(
            "Error: Node.js not found. Lint the published .json in a browser via "
            "scripts/lint.html, or install Node and run:\n"
            "  python scripts/mep_xlsx.py read <file.xlsx> | node scripts/lint.mjs -\n")
        return 2
    if path.lower().endswith(".json"):
        return subprocess.call([node, lint_js, path])
    from mep_xlsx import read_manifest
    manifest = read_manifest(path)
    return subprocess.run([node, lint_js, "-"],
                          input=json.dumps(manifest), text=True).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
