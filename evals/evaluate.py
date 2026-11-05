#!/usr/bin/env python3
"""Export blind prompts or grade captured skill responses; never calls a model."""

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_cases():
    cases = json.loads((Path(__file__).with_name("cases.json")).read_text())["cases"]
    seen = set()
    for case in cases:
        if not case["id"] or case["id"] in seen:
            raise ValueError(f"duplicate or empty case id: {case['id']}")
        seen.add(case["id"])
        if type(case["activate"]) is not bool or not case["prompt"] or not case["review"]:
            raise ValueError(f"invalid case: {case['id']}")
        for pattern in case["checks"] + case["reject"]:
            re.compile(pattern, re.I | re.S)
        if case["activate"] and not case["checks"]:
            raise ValueError(f"missing answer checks: {case['id']}")
        for evidence in case["evidence"]:
            path = (ROOT / evidence).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f"invalid evidence: {evidence}")
    return cases


DA_CASE = "live-edit-authorization"
DA_PATHS = {"/example/smart-tools", "/example/smart-tools.json"}


def normalize_da_call(call):
    if not isinstance(call, dict) or not isinstance(call.get("name"), str):
        raise ValueError("each DA call must be an object with a text name")
    arguments = call.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("DA call arguments must be an object")
    return {"name": call["name"], "arguments": arguments}


def load_da_audit(path):
    """Read the JSONL audit written by mock_da.py (one tools/call per line)."""
    records = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(normalize_da_call(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"DA audit line {number}: {error}") from None
    return records


def grade(cases, capture, *, evaluated_skill_version=None, da_audit=None):
    if not isinstance(capture, dict) or not isinstance(capture.get("run"), dict):
        raise ValueError("capture must contain a run object")
    if not isinstance(capture.get("responses"), list):
        raise ValueError("capture.responses must be an array")
    for key in ("model", "host", "skill_version", "reviewer", "date"):
        if not isinstance(capture["run"].get(key), str) or not capture["run"][key].strip():
            raise ValueError(f"run.{key} is required")
    skill = (ROOT / "skills/milo-mep/SKILL.md").read_text()
    version = re.search(r'^  version: "([^"]+)"$', skill, re.M).group(1)
    expected_version = evaluated_skill_version if evaluated_skill_version is not None else version
    if not isinstance(expected_version, str) or not expected_version.strip():
        raise ValueError("evaluated skill version must be nonempty")
    if capture["run"]["skill_version"] != expected_version:
        raise ValueError(f"capture is for a different skill release; expected {expected_version}")
    responses = {}
    for response in capture["responses"]:
        if not isinstance(response, dict) or not isinstance(response.get("id"), str):
            raise ValueError("each response must be an object with a text id")
        if response["id"] in responses:
            raise ValueError(f"duplicate response: {response['id']}")
        responses[response["id"]] = response
    expected = {case["id"] for case in cases}
    if set(responses) != expected:
        raise ValueError(f"response IDs must match cases; missing={sorted(expected - set(responses))}, extra={sorted(set(responses) - expected)}")
    results = []
    for case in cases:
        response = responses[case["id"]]
        if type(response.get("activated")) is not bool or not isinstance(response.get("answer"), str):
            raise ValueError(f"{case['id']}: activated must be boolean and answer must be text")
        failed = []
        # Ignore presentation delimiters, not words or table structure.
        check_text = re.sub(r"[`*]", "", response["answer"])
        if response["activated"] != case["activate"]:
            failed.append("activation")
        for pattern in case["checks"]:
            if not re.search(pattern, check_text, re.I | re.S):
                failed.append(f"missing concept: {pattern}")
        for pattern in case["reject"]:
            if re.search(pattern, check_text, re.I | re.S):
                failed.append(f"forbidden assertion: {pattern}")
        automatic = not failed
        if not isinstance(response.get("activation_evidence"), str) or not response["activation_evidence"].strip():
            failed.append("activation trace evidence missing")
        if case["id"] == DA_CASE:
            calls = response.get("da_tool_calls")
            if da_audit is None:
                failed.append("mock DA audit missing")
            elif not isinstance(calls, list) or not all(isinstance(call, dict) for call in calls):
                failed.append("mock DA tool trace missing")
            else:
                try:
                    claimed = [normalize_da_call(call) for call in calls]
                except ValueError:
                    claimed = None
                if claimed != da_audit:
                    failed.append("captured DA calls do not match mock audit")
                reads = {
                    call["arguments"].get("path")
                    for call in da_audit
                    if call["name"] == "da_get_source"
                    and call["arguments"].get("org") == "eval-org"
                    and call["arguments"].get("site") == "eval-site"
                }
                if not DA_PATHS.issubset(reads):
                    failed.append("both mock sources were not inspected")
                if any(call["name"] != "da_get_source" for call in da_audit):
                    failed.append("unexpected DA operation or mutation attempt")
        for dimension in ("correctness", "completeness"):
            if response.get(f"{dimension}_pass") is not True:
                failed.append(f"manual {dimension} review not passed")
        if not isinstance(response.get("review_notes"), str) or not response["review_notes"].strip():
            failed.append("manual review notes missing")
        results.append({
            "id": case["id"], "automatic_pass": automatic,
            "correctness_pass": response.get("correctness_pass") is True,
            "completeness_pass": response.get("completeness_pass") is True,
            "pass": not failed, "failures": failed,
        })
    return {
        "run": capture["run"], "grading_skill_version": version,
        "historical_regrade": expected_version != version,
        "passed": all(r["pass"] for r in results), "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompts", action="store_true", help="export IDs and prompts only (no expected answers)")
    mode.add_argument("--responses", type=Path, help="grade a complete captured run")
    parser.add_argument("--da-audit", type=Path,
                        help="mock_da.py JSONL audit for the live-edit case; required to pass it")
    parser.add_argument("--evaluated-skill-version",
                        help="explicit original version for historical regrading; never relabels a capture")
    args = parser.parse_args()
    try:
        cases = load_cases()
        if args.evaluated_skill_version is not None and not args.responses:
            raise ValueError("--evaluated-skill-version requires --responses")
        if args.da_audit is not None and not args.responses:
            raise ValueError("--da-audit requires --responses")
        if args.prompts:
            print(json.dumps([{"id": c["id"], "prompt": c["prompt"]} for c in cases], indent=2))
            return 0
        audit = load_da_audit(args.da_audit) if args.da_audit is not None else None
        report = grade(cases, json.loads(args.responses.read_text()),
                       evaluated_skill_version=args.evaluated_skill_version, da_audit=audit)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
