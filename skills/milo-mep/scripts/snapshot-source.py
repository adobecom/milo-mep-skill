#!/usr/bin/env python3
"""Refresh the bundled milo source snapshot (assets/source/) from a branch and
rewrite assets/source/SOURCE_VERSION with the pinned commit.

    python3 scripts/snapshot-source.py [--branch main]

Fetches every file listed in scripts/source-manifest.txt (bundled-basename ->
repo-path). Run this when check-source-drift.py reports drift you've decided to
adopt — then review reference facts, re-run the linter/evals, and repackage.
Uses urllib (a shell curl-in-loop is unreliable in some sandboxes).
"""
import urllib.request, json, os, sys, datetime

BRANCH = "main"
if "--branch" in sys.argv:
    BRANCH = sys.argv[sys.argv.index("--branch") + 1]

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
RAW = f"https://raw.githubusercontent.com/adobecom/milo/{BRANCH}/"
API = f"https://api.github.com/repos/adobecom/milo/commits/{BRANCH}"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "milo-mep-snapshot"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()

def main():
    manifest = [ln.split() for ln in open(os.path.join(HERE, "source-manifest.txt")) if ln.strip()]
    meta = json.loads(fetch(API).decode())
    sha, cdate = meta["sha"], meta["commit"]["committer"]["date"]
    ok = fail = 0
    for base, path in manifest:
        try:
            data = fetch(RAW + path)
            if len(data) < 150:
                raise ValueError(f"suspiciously small ({len(data)}B)")
            open(os.path.join(SKILL, "assets/source", base), "wb").write(data)
            print(f"  ok  {base:32s} {len(data)}B"); ok += 1
        except Exception as e:
            print(f"  FAIL {base}: {e}"); fail += 1
    if fail:
        print(f"\n{fail} file(s) failed — snapshot NOT updated cleanly; fix and re-run.", file=sys.stderr)
        return 1
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    open(os.path.join(SKILL, "assets/source/SOURCE_VERSION"), "w").write(
f"""milo source snapshot
branch:      {BRANCH}
commit:      {sha}
committed:   {cdate}
snapshotted: {now}

Bundled files under assets/source/ (flat names) map to milo repo paths via
scripts/source-manifest.txt. Freshness is MANUAL: run
`python3 scripts/check-source-drift.py` before re-publishing the skill (or
whenever milo may have changed); if it flags drift, adopt it with
`python3 scripts/snapshot-source.py`, review the affected references, re-run the
linter/evals, and repackage. References cite these by function name (stable);
line numbers are indicative and may drift between snapshots.
""")
    print(f"\nSnapshot updated to {BRANCH}@{sha[:12]} ({ok} files). SOURCE_VERSION rewritten.")
    print("Next: review references + source-notes.md, re-run linter/evals, then ./package-milo-mep.sh")
    return 0

if __name__ == "__main__":
    sys.exit(main())
