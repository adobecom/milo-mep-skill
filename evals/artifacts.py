"""Authoring-case workspaces and automatic checks for the manifest .xlsx an answer writes.

Fixture HTML marks interesting elements with data-eval="id" so simulated results
can name them; the copy given to the answering agent has those labels stripped.
"""

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals/fixtures/authoring"
NEUTRAL_WORKSPACE = ROOT / "evals/workspace"
sys.path.insert(0, str(ROOT / "skills/milo-mep/scripts"))

LABEL = re.compile(r'\s+data-eval="[^"]*"')
TEXT_SUFFIXES = {".html", ".json", ".md", ".txt", ".csv"}
# personalization.js MANIFEST_KEYS: every other experiences column is an experience.
MANIFEST_KEYS = {"action", "selector", "pagefilter", "page filter", "page filter optional",
                 "country filter", "country filter optional"}
RE_KEY_REPLACE = re.compile(r"[^a-z0-9\- _,&=:]")
SPEC_KEYS = {"path", "info", "columns", "rows", "preserve", "simulate", "forbid_lint"}
EXPECT_KEYS = {"page", "visitor", "experience", "changes", "unchanged", "placeholders", "metadata"}
IGNORED_DIRS = {".github", ".git", ".copilot", ".agents", ".claude", "node_modules", "__pycache__"}


def lower_alpha(text):
    """personalization.js toLowerAlpha for column headers."""
    text = str(text).lower()
    if "countryip" in text or "previouspage" in text:
        return re.sub(r"[^a-z0-9\- _,&=:()/*]", "", text)
    return RE_KEY_REPLACE.sub("", text)


def strip_labels(text):
    return LABEL.sub("", text)


def _compile(pattern, where):
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{where}: pattern must be nonempty text")
    re.compile(pattern, re.I | re.S)


def _fixture(path, where):
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(FIXTURES) or not resolved.is_file():
        raise ValueError(f"{where}: fixture must be a file under evals/fixtures/authoring: {path}")
    return resolved


def _relative(path, where):
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path \
            or any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError(f"{where}: invalid relative path {path!r}")
    return path


def _row_matchers(matchers, where):
    if not isinstance(matchers, list):
        raise ValueError(f"{where} must be an array")
    for matcher in matchers:
        if not isinstance(matcher, dict) or not matcher:
            raise ValueError(f"{where}: each row matcher must be a nonempty object")
        for key, pattern in matcher.items():
            _compile(pattern, f"{where}.{key}")


def labels_in(html):
    return set(re.findall(r'data-eval="([^"]*)"', html))


def validate_case(case):
    """Validate a case's workspace_files and artifact spec (raises ValueError)."""
    cid = case["id"]
    dests = set()
    for item in case.get("workspace_files", []):
        if not isinstance(item, dict) or set(item) != {"src", "dest"}:
            raise ValueError(f"{cid}: workspace_files entries need exactly src and dest")
        _fixture(item["src"], cid)
        dest = _relative(item["dest"], cid)
        if dest in dests or dest.split("/")[0] in IGNORED_DIRS:
            raise ValueError(f"{cid}: duplicate or reserved workspace destination {dest}")
        dests.add(dest)
    spec = case.get("artifact")
    if spec is None:
        if "reference_artifact" in case:
            raise ValueError(f"{cid}: reference_artifact requires artifact")
        return
    if not case["activate"]:
        raise ValueError(f"{cid}: negative cases cannot require an artifact")
    if not isinstance(spec, dict) or set(spec) - SPEC_KEYS or "path" not in spec:
        raise ValueError(f"{cid}: artifact needs path and only {sorted(SPEC_KEYS)}")
    _compile(spec["path"], f"{cid}.artifact.path")
    ref = case.get("reference_artifact")
    if not isinstance(ref, dict) or set(ref) not in ({"path", "write"}, {"path", "edit"}) \
            or not re.fullmatch(spec["path"], _relative(ref["path"], cid), re.I):
        raise ValueError(f"{cid}: reference_artifact needs a path matching artifact.path and write or edit")
    if "edit" in ref and ref["path"] not in {i["dest"] for i in case.get("workspace_files", [])}:
        raise ValueError(f"{cid}: reference_artifact edit must target a workspace file")
    for key, pattern in spec.get("info", {}).items():
        _compile(pattern, f"{cid}.artifact.info.{key}")
    if "columns" in spec:
        _compile(spec["columns"], f"{cid}.artifact.columns")
    _row_matchers(spec.get("rows", []), f"{cid}.artifact.rows")
    for pattern in spec.get("forbid_lint", []):
        _compile(pattern, f"{cid}.artifact.forbid_lint")
    if "preserve" in spec:
        preserve = spec["preserve"]
        if not isinstance(preserve, dict) or set(preserve) - {"source", "except"} or "source" not in preserve:
            raise ValueError(f"{cid}: artifact.preserve needs source and optional except")
        _fixture(preserve["source"], f"{cid}.artifact.preserve")
        _row_matchers(preserve.get("except", []), f"{cid}.artifact.preserve.except")
    if "simulate" in spec:
        sim = spec["simulate"]
        if not isinstance(sim, dict) or set(sim) != {"spec", "expect"} or not sim["expect"]:
            raise ValueError(f"{cid}: artifact.simulate needs spec and a nonempty expect")
        spec_path = _fixture(sim["spec"], f"{cid}.artifact.simulate")
        pages = json.loads(spec_path.read_text())["pages"]
        known = {}
        for page in pages:
            html = (spec_path.parent / page["htmlFile"]).read_text() if "htmlFile" in page else page["html"]
            known[page["url"]] = ({v["id"] for v in page["visitors"]}, labels_in(html))
        for expect in sim["expect"]:
            where = f"{cid}.artifact.simulate.expect"
            if not isinstance(expect, dict) or set(expect) - EXPECT_KEYS or not {"page", "visitor", "experience"} <= set(expect):
                raise ValueError(f"{where}: needs page, visitor, experience and only {sorted(EXPECT_KEYS)}")
            if expect["page"] not in known or expect["visitor"] not in known[expect["page"]][0]:
                raise ValueError(f"{where}: unknown page/visitor {expect['page']} {expect['visitor']}")
            labels = known[expect["page"]][1]
            _compile(expect["experience"], where)
            for change in expect.get("changes", []):
                options = change.get("any") if isinstance(change, dict) and set(change) == {"any"} else [change]
                if not isinstance(options, list) or not options:
                    raise ValueError(f"{where}: changes.any must be a nonempty array")
                for option in options:
                    if not isinstance(option, dict) or set(option) - {"action", "target", "content"} \
                            or not {"action", "target"} <= set(option):
                        raise ValueError(f"{where}: changes need action and target (or any: [...])")
                    _compile(option["action"], where)
                    if "content" in option:
                        _compile(option["content"], where)
                    targets = option["target"] if isinstance(option["target"], list) else [option["target"]]
                    if not targets or not set(targets) <= labels:
                        raise ValueError(f"{where}: unknown target {option['target']}")
            if not set(expect.get("unchanged", [])) <= labels:
                raise ValueError(f"{where}: unknown unchanged label")
            for group in ("placeholders", "metadata"):
                for key, pattern in expect.get(group, {}).items():
                    _compile(pattern, f"{where}.{group}.{key}")


def workspace_listing(case):
    return [item["dest"] for item in case.get("workspace_files", [])]


def _seed_bytes(src):
    path = ROOT / src
    if path.suffix in TEXT_SUFFIXES:
        text = strip_labels(path.read_text())
        if "data-eval" in text:
            raise ValueError(f"unstripped grader label in {src}")
        return text.encode()
    return path.read_bytes()


def seed_files(case):
    """Relative path -> bytes for the neutral workspace plus this case's fixtures."""
    files = {p.relative_to(NEUTRAL_WORKSPACE).as_posix(): p.read_bytes()
             for p in NEUTRAL_WORKSPACE.rglob("*") if p.is_file()}
    for item in case.get("workspace_files", []):
        files[item["dest"]] = _seed_bytes(item["src"])
    return files


def write_workspace(case, out_dir):
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"workspace directory is not empty: {out}")
    for rel, data in seed_files(case).items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return sorted(seed_files(case))


def collect(case, workspace, out_dir):
    """Copy files the answer created or changed into out_dir/<case id>/ and list them for the capture."""
    seed = seed_files(case)
    workspace = Path(workspace)
    found = []
    for path in sorted(workspace.rglob("*")):
        rel = path.relative_to(workspace)
        if not path.is_file() or path.is_symlink() or rel.parts[0] in IGNORED_DIRS:
            continue
        data = path.read_bytes()
        if seed.get(rel.as_posix()) == data:
            continue
        target = Path(out_dir) / case["id"] / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        found.append({"path": rel.as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
    return found


def _cells(manifest):
    for sheet in manifest.values():
        for row in sheet["rows"]:
            yield from (str(v) for v in row.values())


def _row_matches(row, matcher):
    by_key = {lower_alpha(k): str(v).strip() for k, v in row.items()}
    return all(re.fullmatch(p, by_key.get(lower_alpha(k), ""), re.I | re.S) for k, p in matcher.items())


_SIMULATIONS = {}


def _run_simulator(manifest, spec_path):
    key = (json.dumps(manifest, sort_keys=True), str(spec_path))
    if key not in _SIMULATIONS:
        _SIMULATIONS[key] = _simulate(manifest, spec_path)
    return copy.deepcopy(_SIMULATIONS[key])


def _simulate(manifest, spec_path):
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required to lint and simulate artifacts")
    with tempfile.TemporaryDirectory() as tmp:
        manifest_file = Path(tmp) / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))
        cmd = [node, str(ROOT / "evals/simulate.mjs"), "--manifest", str(manifest_file)]
        if spec_path:
            cmd += ["--spec", str(spec_path)]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if done.returncode:
        raise RuntimeError(f"simulator failed: {done.stderr.strip()[-500:]}")
    return json.loads(done.stdout)


def _check_preserve(manifest, preserve, failures):
    from mep_xlsx import read_manifest
    original = read_manifest(str(ROOT / preserve["source"]))
    for name, sheet in original.items():
        if name == "readme":
            continue
        rows = manifest.get(name, {}).get("rows", [])
        for row in sheet["rows"]:
            if name == "helix-experiences" and any(_row_matches(row, m) for m in preserve.get("except", [])):
                continue
            wanted = {k: str(v).strip() for k, v in row.items()}
            if not any(all(str(r.get(k, "")).strip() == v for k, v in wanted.items()) for r in rows):
                failures.append(f"existing {name} row changed or removed: {json.dumps(wanted)}")


def _entries(result):
    return result.get("commands", []) + result.get("fragments", [])


def _check_expect(results, expect, failures):
    where = f"{expect['visitor']} on {expect['page']}"
    result = next((r for r in results if r.get("page") == expect["page"] and r.get("id") == expect["visitor"]), None)
    if result is None or "error" in result:
        failures.append(f"simulation {where}: {result.get('error') if result else 'no result'}")
        return
    if not re.fullmatch(expect["experience"], result["experience"], re.I):
        failures.append(f"simulation {where}: experience {result['experience']!r} does not match {expect['experience']!r}")
        return
    entries = _entries(result)
    def applied(option):
        targets = set(option["target"] if isinstance(option["target"], list) else [option["target"]])
        return any(re.fullmatch(option["action"], e["action"], re.I)
                   and targets & set(e.get("matched", []))
                   and ("content" not in option or re.search(option["content"], e.get("content") or "", re.I | re.S))
                   for e in entries)

    for change in expect.get("changes", []):
        options = change["any"] if "any" in change else [change]
        if not any(applied(option) for option in options):
            failures.append(f"simulation {where}: none of " + "; ".join(
                f"{o['action']} on {o['target']}" + (f" with /{o['content']}/" if "content" in o else "")
                for o in options))
    for label in expect.get("unchanged", []):
        if any(label in e.get("matched", []) for e in entries):
            failures.append(f"simulation {where}: {label} should be unchanged")
    for key, pattern in expect.get("placeholders", {}).items():
        value = result["placeholders"].get(key)
        if value is None or not re.fullmatch(pattern, str(value).strip(), re.I | re.S):
            failures.append(f"simulation {where}: placeholder {key}={value!r} does not match {pattern!r}")
    metadata = {m["selector"].lower(): m["val"] for m in result["global"].get("updatemetadata", [])}
    for key, pattern in expect.get("metadata", {}).items():
        value = metadata.get(key.lower())
        if value is None or not re.search(pattern, value, re.I):
            failures.append(f"simulation {where}: metadata {key}={value!r} does not match {pattern!r}")


def summarize(manifest, simulation):
    lines = []
    for name in ("helix-info", "helix-experiences", "helix-placeholders"):
        sheet = manifest.get(name)
        if not sheet:
            continue
        lines.append(f"[{name}] " + " | ".join(sheet["columns"]))
        lines += ["  " + " | ".join(str(row.get(c, "")) for c in sheet["columns"]) for row in sheet["rows"]]
    for finding in simulation.get("lint", []):
        if finding["sev"] != "info":
            lines.append(f"lint {finding['sev']} {finding['where']}: {finding['msg']}")
    for result in simulation.get("results", []):
        head = f"simulated {result.get('id')} on {result.get('page')}: "
        if "error" in result:
            lines.append(head + result["error"])
            continue
        changes = [f"{e['action']} {e.get('matched') or e.get('error') or 'nothing'}" for e in _entries(result)]
        lines.append(head + f"{result['experience']}; " + ("; ".join(changes) or "no changes"))
    return "\n".join(lines)


def check(case, response, artifacts_dir):
    """Automatic artifact failures (not waivable) and a text summary for judges."""
    spec, cid = case["artifact"], case["id"]
    if artifacts_dir is None:
        return ["artifact directory missing"], ""
    items = response.get("artifacts")
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return ["artifacts list missing"], ""
    failures, candidates = [], []
    for item in items:
        try:
            rel = _relative(item.get("path"), "artifact")
        except ValueError as error:
            failures.append(str(error))
            continue
        path = Path(artifacts_dir) / cid / rel
        if not path.is_file():
            failures.append(f"artifact file missing: {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            failures.append(f"artifact hash mismatch: {rel}")
        elif rel.lower().endswith(".xlsx"):
            candidates.append((rel, path))
    named = [c for c in candidates if re.fullmatch(spec["path"], c[0], re.I)]
    if len(named) != 1:
        return failures + [f"expected exactly one manifest .xlsx matching {spec['path']!r}; got {[c[0] for c in candidates]}"], ""
    rel, path = named[0]
    from mep_xlsx import read_manifest
    try:
        manifest = read_manifest(str(path))
    except Exception as error:  # noqa: BLE001 - any unreadable workbook is an artifact failure
        return failures + [f"{rel} is not a readable workbook: {error}"], ""
    for sheet in ("helix-info", "helix-experiences", "readme"):
        if sheet not in manifest:
            failures.append(f"{rel}: missing {sheet} sheet (start from the template)")
    if any("data-eval" in cell for cell in _cells(manifest)):
        failures.append(f"{rel}: uses grader-only data-eval labels")
    info = {str(r.get("key", "")).strip().lower(): str(r.get("value", "")).strip()
            for r in manifest.get("helix-info", {}).get("rows", [])}
    for key, pattern in spec.get("info", {}).items():
        if not re.fullmatch(pattern, info.get(key.lower(), ""), re.I):
            failures.append(f"{rel}: info {key}={info.get(key.lower(), '')!r} does not match {pattern!r}")
    experiences = manifest.get("helix-experiences", {"columns": [], "rows": []})
    columns = [lower_alpha(c) for c in experiences["columns"] if c.strip() and lower_alpha(c) not in MANIFEST_KEYS]
    # Experience headers in priority order, joined with " | ".
    if "columns" in spec and not re.fullmatch(spec["columns"], " | ".join(columns), re.I):
        failures.append(f"{rel}: experience columns {' | '.join(columns)!r} do not match {spec['columns']!r}")
    for matcher in spec.get("rows", []):
        if not any(_row_matches(row, matcher) for row in experiences["rows"]):
            failures.append(f"{rel}: no experiences row matches {json.dumps(matcher)}")
    if "preserve" in spec:
        _check_preserve(manifest, spec["preserve"], failures)
    sim_spec = spec.get("simulate")
    try:
        simulation = _run_simulator(manifest, ROOT / sim_spec["spec"] if sim_spec else None)
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return failures + [f"{rel}: {error}"], summarize(manifest, {})
    for finding in simulation["lint"]:
        if finding["sev"] == "error":
            failures.append(f"{rel}: lint error {finding['where']}: {finding['msg']}")
        elif any(re.search(p, finding["msg"], re.I) for p in spec.get("forbid_lint", [])):
            failures.append(f"{rel}: lint {finding['sev']} {finding['where']}: {finding['msg']}")
    for result in simulation["results"]:
        if "error" in result or result["experience"] == "default":
            continue
        for entry in _entries(result):
            if entry.get("error") or (not entry.get("inBlock") and not entry.get("matched")):
                failures.append(f"simulation {result['id']} on {result['page']}: {entry['action']} "
                                f"{entry['selector']!r} matched nothing" + (f" ({entry['error']})" if entry.get("error") else ""))
    if sim_spec:
        for expect in sim_spec["expect"]:
            _check_expect(simulation["results"], expect, failures)
    return failures, f"Artifact {rel}:\n" + summarize(manifest, simulation)
