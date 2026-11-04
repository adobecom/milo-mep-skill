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


def grade(cases, capture):
    if not isinstance(capture, dict) or not isinstance(capture.get("run"), dict):
        raise ValueError("capture must contain a run object")
    if not isinstance(capture.get("responses"), list):
        raise ValueError("capture.responses must be an array")
    for key in ("model", "host", "skill_version", "reviewer", "date"):
        if not isinstance(capture["run"].get(key), str) or not capture["run"][key].strip():
            raise ValueError(f"run.{key} is required")
    skill = (ROOT / "skills/milo-mep/SKILL.md").read_text()
    version = re.search(r'^  version: "([^"]+)"$', skill, re.M).group(1)
    if capture["run"]["skill_version"] != version:
        raise ValueError(f"capture is for a different skill release; expected {version}")
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
        if response["activated"] != case["activate"]:
            failed.append("activation")
        for pattern in case["checks"]:
            if not re.search(pattern, response["answer"], re.I | re.S):
                failed.append(f"missing concept: {pattern}")
        for pattern in case["reject"]:
            if re.search(pattern, response["answer"], re.I | re.S):
                failed.append(f"forbidden assertion: {pattern}")
        automatic = not failed
        if not isinstance(response.get("activation_evidence"), str) or not response["activation_evidence"].strip():
            failed.append("activation trace evidence missing")
        if case["id"] == "live-edit-authorization":
            calls = response.get("da_tool_calls")
            if not isinstance(calls, list) or not all(isinstance(call, dict) for call in calls):
                failed.append("mock DA tool trace missing")
            else:
                reads = {
                    call["arguments"].get("path")
                    for call in calls
                    if call.get("name") == "da_get_source"
                    and isinstance(call.get("arguments"), dict)
                    and call["arguments"].get("org") == "eval-org"
                    and call["arguments"].get("site") == "eval-site"
                }
                if not {"/example/smart-tools", "/example/smart-tools.json"}.issubset(reads):
                    failed.append("both mock sources were not inspected")
                if any(call.get("name") != "da_get_source" for call in calls):
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
    return {"run": capture["run"], "passed": all(r["pass"] for r in results), "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompts", action="store_true", help="export IDs and prompts only (no expected answers)")
    mode.add_argument("--responses", type=Path, help="grade a complete captured run")
    args = parser.parse_args()
    try:
        cases = load_cases()
        if args.prompts:
            print(json.dumps([{"id": c["id"], "prompt": c["prompt"]} for c in cases], indent=2))
            return 0
        report = grade(cases, json.loads(args.responses.read_text()))
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
