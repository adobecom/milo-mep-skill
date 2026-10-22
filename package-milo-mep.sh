#!/bin/sh
set -eu

if [ "$#" -ne 0 ]; then
  echo "Usage: $0" >&2
  exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 - "$ROOT" <<'PY'
import os
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(sys.argv[1])
skill = root / "skills" / "milo-mep"
output = root / "milo-mep.skill"
if not (skill / "SKILL.md").is_file():
    raise SystemExit(f"Missing skill entry point: {skill / 'SKILL.md'}")

with tempfile.TemporaryDirectory(prefix=".milo-mep-package-", dir=root) as temp:
    archive = Path(temp) / output.name
    count = 0
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for directory, dirs, files in os.walk(skill, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs
                if name not in {"evals", "__pycache__"} and not name.startswith(".")
            )
            for name in dirs + files:
                path = Path(directory) / name
                if path.is_symlink():
                    raise SystemExit(f"Cannot package symlink: {path}")
            for name in sorted(files):
                path = Path(directory) / name
                if name.startswith(".") or path.suffix in {".pyc", ".pyo", ".skill"}:
                    continue
                bundle.write(path, path.relative_to(skill.parent).as_posix())
                count += 1
    archive.replace(output)

print(f"Created {output} ({count} files, {output.stat().st_size} bytes)")
PY
