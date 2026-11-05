#!/usr/bin/env python3
"""Export blind prompts or judge prompts, or grade captured skill responses; never calls a model."""

import argparse
import hashlib
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


def normalize_text(text):
    """Text used for pattern checks and quote verification."""
    return re.sub(r"[`*]", "", text)


def quote_in(quote, answer):
    squash = lambda text: " ".join(normalize_text(text).split()).casefold()
    return isinstance(quote, str) and bool(quote.strip()) and squash(quote) in squash(answer)


def judge_failures(case, response, missed):
    """Validate optional judge output: per-review-item verdicts and quote-backed check waivers."""
    failed, waived = [], []
    verdicts = response.get("review_verdicts")
    if verdicts is not None:
        items = [v.get("item") if isinstance(v, dict) else None for v in verdicts] if isinstance(verdicts, list) else None
        if items is None or sorted(i for i in items if type(i) is int) != list(range(len(case["review"]))) \
                or len(items) != len(case["review"]):
            failed.append("review verdicts must cover each review item exactly once")
        else:
            for verdict in verdicts:
                if verdict.get("pass") is not True:
                    failed.append(f"review item {verdict['item']} failed")
                elif verdict.get("quote") is not None and not quote_in(verdict["quote"], response["answer"]):
                    failed.append(f"review item {verdict['item']} quote not found in answer")
                if not isinstance(verdict.get("note"), str) or not verdict["note"].strip():
                    failed.append(f"review item {verdict['item']} note missing")
    waivers = response.get("check_waivers", [])
    if not isinstance(waivers, list):
        return failed + ["check waivers must be an array"], waived
    for waiver in waivers:
        index = waiver.get("check") if isinstance(waiver, dict) else None
        if type(index) is not int or not 0 <= index < len(case["checks"]):
            failed.append(f"invalid check waiver: {index!r}")
        elif index not in missed:
            failed.append(f"check {index} waived but not missed")
        elif not quote_in(waiver.get("quote"), response["answer"]):
            failed.append(f"check {index} waiver quote not found in answer")
        elif not isinstance(waiver.get("reason"), str) or not waiver["reason"].strip():
            failed.append(f"check {index} waiver reason missing")
        else:
            waived.append(index)
    return failed, sorted(set(waived))


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
        check_text = normalize_text(response["answer"])
        if response["activated"] != case["activate"]:
            failed.append("activation")
        missed = [i for i, pattern in enumerate(case["checks"]) if not re.search(pattern, check_text, re.I | re.S)]
        judge_failed, waived = judge_failures(case, response, missed)
        for index in missed:
            if index not in waived:
                failed.append(f"missing concept: {case['checks'][index]}")
        for pattern in case["reject"]:
            if re.search(pattern, check_text, re.I | re.S):
                failed.append(f"forbidden assertion: {pattern}")
        automatic = not failed
        failed += judge_failed
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
            "id": case["id"], "automatic_pass": automatic, "waived_checks": waived,
            "correctness_pass": response.get("correctness_pass") is True,
            "completeness_pass": response.get("completeness_pass") is True,
            "pass": not failed, "failures": failed,
        })
    return {
        "run": capture["run"], "grading_skill_version": version,
        "historical_regrade": expected_version != version,
        "passed": all(r["pass"] for r in results),
        "waived_check_count": sum(len(r["waived_checks"]) for r in results), "results": results,
    }


def aggregate(reports, min_pass_rate=1.0):
    """Per-case pass rates across independent captures of the same release."""
    versions = {r["run"]["skill_version"] for r in reports}
    if len(versions) != 1:
        raise ValueError(f"captures mix skill versions: {sorted(versions)}")
    cases = []
    for index, first in enumerate(reports[0]["results"]):
        passes = sum(r["results"][index]["pass"] for r in reports)
        rate = passes / len(reports)
        cases.append({"id": first["id"], "passes": passes, "runs": len(reports),
                      "rate": round(rate, 4), "pass": rate >= min_pass_rate})
    return {"captures": len(reports), "min_pass_rate": min_pass_rate,
            "passed": all(c["pass"] for c in cases), "cases": cases}


JUDGE_SCHEMA = {
    "id": "case id",
    "review_verdicts": [{"item": 0, "pass": True, "quote": "verbatim answer excerpt or null", "note": "why"}],
    "check_waivers": [{"check": 0, "quote": "verbatim answer excerpt", "reason": "same concept, different words"}],
    "correctness_pass": True,
    "completeness_pass": True,
    "review_notes": "summary of the evidence checked",
}


def judge_prompts(cases, capture):
    """Self-contained prompts for an independent judge conversation (no model call here)."""
    responses = {r.get("id"): r for r in capture.get("responses", []) if isinstance(r, dict)}
    prompts = []
    for case in cases:
        response = responses.get(case["id"])
        if not case["activate"] or response is None or not isinstance(response.get("answer"), str):
            continue
        text = normalize_text(response["answer"])
        missed = [i for i, pattern in enumerate(case["checks"]) if not re.search(pattern, text, re.I | re.S)]
        lines = [
            "You are grading one answer from the milo-mep skill. Judge it independently against the Milo source;",
            "do not trust the answer's own claims. Read the evidence files (paths are relative to the",
            "milo-mep-skill repository) before deciding. Do not edit anything.",
            "",
            f"Case: {case['id']}",
            f"User prompt:\n{case['prompt']}",
            f"Answer:\n<<<\n{response['answer']}\n>>>",
            "",
            "Review items (each must pass; quote the answer verbatim where it satisfies an item,",
            "or use null when the item is about something the answer must not do):",
            *[f"  {i}. {item}" for i, item in enumerate(case["review"])],
            f"Evidence: {', '.join(case['evidence'])}",
        ]
        if missed:
            lines += [
                "",
                "These automatic concept checks did not match. Waive one only if the answer states the same",
                "concept in other words; give the verbatim quote that does so. Otherwise do not waive it:",
                *[f"  {i}. {case['checks'][i]}" for i in missed],
            ]
        lines += [
            "",
            "correctness_pass: every factual claim, value and proposed action agrees with the evidence.",
            "completeness_pass: every requested deliverable and review item is covered, including a concrete",
            "expected QA result. Reply with only this JSON object:",
            json.dumps({**JUDGE_SCHEMA, "id": case["id"]}, indent=2),
        ]
        prompts.append({"id": case["id"], "prompt": "\n".join(lines)})
    return prompts


JUDGE_FIELDS = ("review_verdicts", "check_waivers", "correctness_pass", "completeness_pass", "review_notes")


def apply_judgments(capture, judgments):
    """Merge judge outputs into a capture without touching answers, activation, or traces."""
    merged = json.loads(json.dumps(capture))
    by_id = {r["id"]: r for r in merged["responses"]}
    for judgment in judgments:
        if not isinstance(judgment, dict) or judgment.get("id") not in by_id:
            raise ValueError(f"judgment for unknown case: {judgment.get('id') if isinstance(judgment, dict) else judgment!r}")
        extra = set(judgment) - {"id", *JUDGE_FIELDS}
        if extra:
            raise ValueError(f"{judgment['id']}: judgments may only set {', '.join(JUDGE_FIELDS)}; got {sorted(extra)}")
        by_id[judgment["id"]].update({k: judgment[k] for k in JUDGE_FIELDS if k in judgment})
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompts", action="store_true", help="export IDs and prompts only (no expected answers)")
    mode.add_argument("--responses", type=Path, nargs="+",
                      help="grade one or more complete captured runs (several = repeat runs)")
    mode.add_argument("--judge-prompts", type=Path, metavar="CAPTURE",
                      help="export judge prompts for a capture's activated answers")
    mode.add_argument("--apply-judgments", type=Path, nargs=2, metavar=("CAPTURE", "JUDGMENTS"),
                      help="print the capture with judge fields merged in")
    parser.add_argument("--da-audit", type=Path, nargs="+",
                        help="mock_da.py JSONL audit per capture, in the same order; required for the live-edit case")
    parser.add_argument("--min-pass-rate", type=float, default=1.0,
                        help="with several captures, the per-case pass rate required (default 1.0)")
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
        if args.judge_prompts:
            print(json.dumps(judge_prompts(cases, json.loads(args.judge_prompts.read_text())), indent=2))
            return 0
        if args.apply_judgments:
            capture, judgments = (json.loads(p.read_text()) for p in args.apply_judgments)
            print(json.dumps(apply_judgments(capture, judgments), indent=2))
            return 0
        if args.da_audit is not None and len(args.da_audit) != len(args.responses):
            raise ValueError("give one --da-audit per --responses capture, in the same order")
        if not 0 < args.min_pass_rate <= 1:
            raise ValueError("--min-pass-rate must be in (0, 1]")
        digests = [hashlib.sha256(p.read_bytes()).hexdigest() for p in args.responses]
        if len(set(digests)) != len(digests):
            raise ValueError("the same capture was given more than once")
        audits = [load_da_audit(p) for p in args.da_audit] if args.da_audit else [None] * len(args.responses)
        reports = [grade(cases, json.loads(p.read_text()),
                         evaluated_skill_version=args.evaluated_skill_version, da_audit=audit)
                   for p, audit in zip(args.responses, audits)]
        if len(reports) == 1:
            print(json.dumps(reports[0], indent=2))
            return 0 if reports[0]["passed"] else 1
        summary = aggregate(reports, args.min_pass_rate)
        print(json.dumps({"aggregate": summary, "runs": reports}, indent=2))
        return 0 if summary["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
