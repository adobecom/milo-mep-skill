#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -p 'test_*.py'
node skills/milo-mep/scripts/build-lint-html.mjs --check
git --no-pager diff --check
