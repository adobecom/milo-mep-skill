import copy
import json
from pathlib import Path
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
        self.capture = {
            "run": {"model": "grader-unit-test-not-a-model-run", "host": "unit-test",
                    "skill_version": "1.1.0",
                    "reviewer": "test fixture", "date": "2026-11-03"},
            "responses": [
                {"id": c["id"], "activated": c["activate"], "answer": c["reference_answer"],
                 "review_pass": True, "review_notes": "Grader fixture only; not a behavioral evaluation."}
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
        self.capture["responses"][0].pop("review_pass")
        self.capture["responses"][0]["review_notes"] = ""
        result = grade(self.cases, self.capture)
        self.assertTrue(result["results"][0]["automatic_pass"])
        self.assertFalse(result["passed"])

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

    def test_cli_exports_blind_prompts_and_reports_failures(self):
        command = [sys.executable, str(ROOT / "evals/evaluate.py")]
        prompts = subprocess.run(command + ["--prompts"], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(prompts.stdout), [{"id": c["id"], "prompt": c["prompt"]} for c in self.cases])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "responses.json"
            for expected, capture in ((0, self.capture), (1, {**self.capture, "responses": [
                {**r, "review_pass": False} for r in self.capture["responses"]
            ]}), (2, {}), (2, []), (2, {"run": [], "responses": []}),
                (2, {**self.capture, "responses": [None]})):
                path.write_text(json.dumps(capture))
                result = subprocess.run(command + ["--responses", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
