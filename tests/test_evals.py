import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from evaluate import grade, load_cases


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()
        version = re.search(r'^  version: "([^"]+)"$', (ROOT / "skills/milo-mep/SKILL.md").read_text(), re.M).group(1)
        self.capture = {
            "run": {"model": "grader-unit-test-not-a-model-run", "host": "unit-test",
                    "skill_version": version,
                    "reviewer": "test fixture", "date": "2026-11-03"},
            "responses": [
                {"id": c["id"], "activated": c["activate"], "answer": c["reference_answer"],
                 "correctness_pass": True, "completeness_pass": True,
                 "activation_evidence": "Synthetic grader fixture; not a real activation trace.",
                 **({"da_tool_calls": [
                     {"name": "da_get_source", "arguments": {
                         "org": "eval-org", "site": "eval-site", "path": path,
                     }} for path in ("/example/smart-tools", "/example/smart-tools.json")
                 ]} if c["id"] == "live-edit-authorization" else {}),
                 "review_notes": "Grader fixture only; not a behavioral evaluation."}
                for c in self.cases
            ],
        }

    def test_reference_answers_exercise_grader(self):
        result = grade(self.cases, self.capture)
        self.assertTrue(result["passed"], json.dumps(result, indent=2))
        self.assertGreaterEqual(sum(c["activate"] for c in self.cases), 10)
        self.assertGreaterEqual(sum(not c["activate"] for c in self.cases), 4)

    def test_every_case_detects_incorrect_activation(self):
        for index, case in enumerate(self.cases):
            with self.subTest(case=case["id"]):
                capture = copy.deepcopy(self.capture)
                capture["responses"][index]["activated"] = not case["activate"]
                result = grade(self.cases, capture)
                self.assertFalse(result["passed"])
                self.assertIn("activation", result["results"][index]["failures"])

    def test_every_positive_case_detects_empty_answer(self):
        for index, case in enumerate(self.cases):
            if not case["activate"]:
                continue
            with self.subTest(case=case["id"]):
                capture = copy.deepcopy(self.capture)
                capture["responses"][index]["answer"] = ""
                self.assertFalse(grade(self.cases, capture)["results"][index]["automatic_pass"])

    def test_adverse_advice_is_rejected_even_with_expected_keywords(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "manifest-priority")
        response["answer"] += " Target always wins."
        result = grade(self.cases, self.capture)
        self.assertFalse(result["passed"])
        self.assertTrue(any("forbidden assertion" in f for r in result["results"] for f in r["failures"]))

    def test_automatic_match_cannot_substitute_for_rubric_review(self):
        self.capture["responses"][0].pop("correctness_pass")
        self.capture["responses"][0]["review_notes"] = ""
        result = grade(self.cases, self.capture)
        self.assertTrue(result["results"][0]["automatic_pass"])
        self.assertFalse(result["passed"])

    def test_correctness_and_completeness_are_separate_required_reviews(self):
        for dimension in ("correctness", "completeness"):
            for value in (False, None, "true", 1):
                with self.subTest(dimension=dimension, value=value):
                    capture = copy.deepcopy(self.capture)
                    capture["responses"][0][f"{dimension}_pass"] = value
                    result = grade(self.cases, capture)["results"][0]
                    self.assertTrue(result["automatic_pass"])
                    self.assertFalse(result[f"{dimension}_pass"])
                    other = "completeness" if dimension == "correctness" else "correctness"
                    self.assertTrue(result[f"{other}_pass"])
                    self.assertFalse(result["pass"])

    def test_placeholder_category_precedence_is_rejected(self):
        for case_id in ("page-scoped-placeholder-history", "placeholder-column-order"):
            capture = copy.deepcopy(self.capture)
            response = next(r for r in capture["responses"] if r["id"] == case_id)
            response["answer"] += " The selected experience, then locale/country, then value, then other."
            result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == case_id)
            self.assertTrue(any("forbidden assertion" in f for f in result["failures"]))

    def test_incorrect_placeholder_predictions_fail(self):
        for case_id, correct, wrong in (
            ("placeholder-column-order", "A: General", "A: Phone copy"),
            ("heldout-placeholder-column-transfer", "title=Titel A", "title=Audience A"),
        ):
            capture = copy.deepcopy(self.capture)
            response = next(r for r in capture["responses"] if r["id"] == case_id)
            response["answer"] = response["answer"].replace(correct, wrong)
            result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == case_id)
            self.assertFalse(result["automatic_pass"])

    def test_legacy_review_flag_cannot_replace_dimension_reviews(self):
        response = self.capture["responses"][0]
        response.pop("correctness_pass")
        response.pop("completeness_pass")
        response["review_pass"] = True
        result = grade(self.cases, self.capture)["results"][0]
        self.assertFalse(result["pass"])
        self.assertIn("manual correctness review not passed", result["failures"])
        self.assertIn("manual completeness review not passed", result["failures"])

    def test_incomplete_duplicate_and_stale_runs_are_rejected(self):
        for change in ("missing", "extra", "duplicate", "stale", "metadata"):
            with self.subTest(change=change):
                capture = copy.deepcopy(self.capture)
                if change == "missing":
                    capture["responses"].pop()
                elif change == "extra":
                    capture["responses"].append({**capture["responses"][0], "id": "unknown-case"})
                elif change == "duplicate":
                    capture["responses"].append(capture["responses"][0])
                elif change == "stale":
                    capture["run"]["skill_version"] = "0.0.0"
                else:
                    capture["run"]["model"] = ""
                with self.assertRaises(ValueError):
                    grade(self.cases, capture)

    def test_activation_claim_without_trace_evidence_fails(self):
        self.capture["responses"][0].pop("activation_evidence")
        self.assertIn("activation trace evidence missing",
                      grade(self.cases, self.capture)["results"][0]["failures"])

    def test_mock_inspection_requires_reads_and_rejects_mutation_attempts(self):
        for variant in ("missing", "no-reads", "one-read", "wrong-destination", "publish"):
            capture = copy.deepcopy(self.capture)
            response = next(r for r in capture["responses"] if r["id"] == "live-edit-authorization")
            if variant == "missing":
                response.pop("da_tool_calls")
            elif variant == "no-reads":
                response["da_tool_calls"] = []
            elif variant == "one-read":
                response["da_tool_calls"].pop()
            elif variant == "wrong-destination":
                response["da_tool_calls"][0]["arguments"]["site"] = "other"
            else:
                response["da_tool_calls"].append({"name": "da_publish_content", "arguments": {}})
            result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == response["id"])
            self.assertFalse(result["pass"], variant)

    def test_cli_exports_blind_prompts_and_reports_failures(self):
        command = [sys.executable, str(ROOT / "evals/evaluate.py")]
        prompts = subprocess.run(command + ["--prompts"], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(prompts.stdout), [{"id": c["id"], "prompt": c["prompt"]} for c in self.cases])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "responses.json"
            for expected, capture in ((0, self.capture), (1, {**self.capture, "responses": [
                {**r, "correctness_pass": False} for r in self.capture["responses"]
            ]}), (2, {}), (2, []), (2, {"run": [], "responses": []}),
                (2, {**self.capture, "responses": [None]})):
                path.write_text(json.dumps(capture))
                result = subprocess.run(command + ["--responses", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
