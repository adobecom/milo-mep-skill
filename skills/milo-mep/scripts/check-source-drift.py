#!/usr/bin/env python3
"""Check the bundled milo source snapshot (assets/source/) against the live
`main` branch and flag drift — especially in the functions/symbols the skill's
references cite. Run manually or on a schedule.

    python3 scripts/check-source-drift.py [--branch main] [--ignore-incidental]

Exit code 0 = in sync, 1 = drift found (files changed), 2 = fetch error.
With --ignore-incidental, drift that touches no cited symbol and no file under
libs/features/personalization/ exits 0 (it is still printed). Prints, per
changed file, which cited symbols moved so a maintainer knows which reference
facts to re-verify. Does NOT modify anything — it only reports.
"""
import glob, urllib.request, json, os, sys, re

BRANCH = "main"
if "--branch" in sys.argv:
    BRANCH = sys.argv[sys.argv.index("--branch") + 1]
IGNORE_INCIDENTAL = "--ignore-incidental" in sys.argv
CORE_PREFIX = "libs/features/personalization/"

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
RAW = f"https://raw.githubusercontent.com/adobecom/milo/{BRANCH}/"
API = f"https://api.github.com/repos/adobecom/milo/commits/{BRANCH}"

# Symbols the references cite as source-of-truth. If the lines defining/using
# these change, the corresponding skill facts likely need review.
CITED = [
    "normalizePath", "isDamContent", "PERSONALIZATION_TAGS", "PHONE_SIZE",
    "getSelectedElements", "handleCommands", "registerInBlockActions",
    "deleteMarkedEls", "replaceInner", "replacepage", "matchGlob",
    "getMepEnablement", "enablePersonalizationV2", "parseNestedPlaceholders",
    "parsePlaceholders", "createContent", "getEntitlements", "getXLGListURL",
    "insertInlineFrag", "C1_BLOCKS", "C2_BLOCKS", "DO_NOT_INLINE",
    "mepMasStudioUrls", "decorateSectionAnalytics", "addIds", "parseMepParam",
    "variantOverride", "TRACKED_MANIFEST_TYPE", "COMMANDS", "CREATE_CMDS",
    "GLOBAL_CMDS", "FLAGS", "includeGnav", "includeFragments",
]

def referenced_symbols():
    """Backticked camelCase/CONSTANT names in the references that the snapshot defines."""
    source = "".join(open(p, encoding="utf-8", errors="replace").read()
                     for p in glob.glob(os.path.join(SKILL, "assets/source/*.js")))
    defined = set(re.findall(r"(?:function\s+|(?:const|let)\s+)([A-Za-z_]\w{6,})\b", source))
    docs = "".join(open(p, encoding="utf-8").read()
                   for p in glob.glob(os.path.join(SKILL, "references/*.md")) + [os.path.join(SKILL, "SKILL.md")])
    named = {t for t in re.findall(r"`([A-Za-z_]\w{6,})(?:\(\))?`", docs)
             if re.search(r"[a-z][A-Z]|^[A-Z0-9]+_[A-Z0-9_]+$", t)}
    return sorted(defined & named)


CITED = sorted(set(CITED) | set(referenced_symbols()))


def classify(changed):
    """Split (base, path, moved) entries into review-needed and incidental."""
    review = [c for c in changed if c[2] or c[1].startswith(CORE_PREFIX)]
    return review, [c for c in changed if c not in review]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "milo-mep-drift"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")

def cited_lines(text):
    """Map each cited symbol -> set of lines mentioning it (order-independent)."""
    out = {}
    for sym in CITED:
        out[sym] = {ln.strip() for ln in text.splitlines() if sym in ln}
    return out

def read_source_version():
    p = os.path.join(SKILL, "assets/source/SOURCE_VERSION")
    if not os.path.exists(p):
        return None
    for ln in open(p):
        if ln.startswith("commit:"):
            return ln.split(":", 1)[1].strip()
    return None

def main():
    manifest = [ln.split() for ln in open(os.path.join(HERE, "source-manifest.txt")) if ln.strip()]
    try:
        head = json.loads(fetch(API))["sha"]
    except Exception as e:
        print(f"ERROR: could not reach GitHub API: {e}", file=sys.stderr)
        return 2

    pinned = read_source_version()
    print(f"tracked branch : {BRANCH}")
    print(f"snapshot commit: {pinned}")
    print(f"main HEAD       : {head}")
    print(f"{'UP TO DATE' if pinned == head else 'BEHIND — main has moved since the snapshot'}\n")

    changed = []
    for base, path in manifest:
        local_p = os.path.join(SKILL, "assets/source", base)
        local = open(local_p, encoding="utf-8", errors="replace").read() if os.path.exists(local_p) else ""
        try:
            remote = fetch(RAW + path)
        except Exception as e:
            print(f"ERROR: could not fetch {path}: {e}", file=sys.stderr)
            return 2
        if local == remote:
            continue
        # which cited symbols' lines changed?
        lo, ro = cited_lines(local), cited_lines(remote)
        moved = [s for s in CITED if lo[s] != ro[s]]
        changed.append((base, path, moved))

    if not changed:
        print("✓ No drift — bundled snapshot matches main for all tracked files.")
        return 0

    review, incidental = classify(changed)
    print(f"⚠ {len(changed)} file(s) changed vs main:\n")
    for base, path, moved in changed:
        print(f"  • {base}  ({path})")
        if moved:
            print(f"      cited symbols changed: {', '.join(moved)}")
            print(f"      → re-verify the reference facts that cite these.")
        elif path.startswith(CORE_PREFIX):
            print(f"      (personalization feature file — review even without cited symbols)")
        else:
            print(f"      (no cited symbols in the changed lines — likely incidental)")
    if IGNORE_INCIDENTAL and not review:
        print("\nOnly incidental drift; no review required (--ignore-incidental).")
        return 0
    print("\nNext: review the diffs, update the affected references + source-notes.md,")
    print("re-run the linter and evals, then re-snapshot (re-run the fetch) and bump")
    print("assets/source/SOURCE_VERSION, and repackage.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
