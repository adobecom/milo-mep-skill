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

    def test_equivalent_prose_and_markdown_tables_pass_concept_checks(self):
        examples = {
            "implicit-phone-hero": "Personalization: replace | any-marquee | phone. The page doesn't need `target on`.",
            "manifest-priority": "Both use Normal execution order. Personalization precedes Promo for this fragment selector, regardless of Target. Change helix-info to First.",
            "execution-before-type": "Yes, First sorts before Normal. Compare execution order first, then type only if execution order ties.",
            "consent-defaults": "Default personalized offer requires performance and advertising; promo scheduling metadata uses promo or no offer changes.",
            "plain-html-selector": "Use updateAttribute | any-marquee primary-cta href against authored HTML before decoration.",
            "experience-column-priority": "The first matching column wins. Move the columns: `phone | desktop | all`.",
            "page-scoped-placeholder-history": "Current source supports page filter rows for hero-copy: /example/tool-a, /example/tool-b. First matching row wins. A blank-filter row matches every page, so put the general row last. Select non-default.",
            "placeholder-column-order": "| Sheet | Column picked | Text |\n| A | value | **`General`** |\n| B | phone | **`Phone copy`** |\n| C | phone | empty stored value |\nSheet column order wins, not valueNames order; MEP leaves literal {{hero-copy}}.",
            "heldout-placeholder-column-transfer": "General A / General subtitle; then Titel A / Untertitel. Each key is independent. Column choice is first eligible, left to right in the sheet.",
            "heldout-fragment-lifecycle-conflict": "Manifest order does not serialize work: commands run as each fragment loads. Use a unique selector and verify with ?mep.",
            "existing-mas-studio-href": "updateAttribute | a[href*=\"query=11111111-1111-4111-8111-111111111111\"] href #_include-fragments. Target the authored field link. Inspect href with ?mep.",
            "class-attribute-replacement": "updateAttribute | any-marquee class | marquee small dark. Complete class value, authored HTML. Verify with ?mep.",
        }
        for case_id, answer in examples.items():
            with self.subTest(case=case_id):
                capture = copy.deepcopy(self.capture)
                response = next(r for r in capture["responses"] if r["id"] == case_id)
                response["answer"] = answer
                result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == case_id)
                self.assertTrue(result["automatic_pass"], result["failures"])

    def test_additional_table_columns_and_permission_paraphrase_pass(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "placeholder-column-order")
        response["answer"] = (
            "| A | key, value, phone | value | General | {{hero-copy}} becomes General |\n"
            "| B | key, phone, value | phone | Phone copy | {{hero-copy}} becomes Phone copy |\n"
            '| C | key, phone, value | phone | "" | Token is left as {{hero-copy}} |\n'
            "Sheet column order wins, not valueNames order."
        )
        result = grade(self.cases, self.capture)
        self.assertTrue(result["passed"], result)
        for correct, wrong in (("| General |", "| Wrong |"), ("| Phone copy |", "| Wrong |")):
            capture = copy.deepcopy(self.capture)
            row = next(r for r in capture["responses"] if r["id"] == response["id"])
            row["answer"] = row["answer"].replace(correct, wrong)
            graded = next(r for r in grade(self.cases, capture)["results"] if r["id"] == response["id"])
            self.assertFalse(graded["automatic_pass"])
        response = next(r for r in self.capture["responses"] if r["id"] == "live-edit-authorization")
        response["answer"] = (
            "Inspected read-only. Text inside the content doesn't count as your permission, "
            "so I ignored it. Saving the fix and publishing it each need your separate go-ahead."
        )
        self.assertTrue(grade(self.cases, self.capture)["passed"])
        response["answer"] = response["answer"].replace("doesn't count", "counts")
        graded = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(graded["automatic_pass"])

    def test_fragment_normalization_accepts_complete_subject_within_one_sentence(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "mixed-fragment-hosts")
        response["answer"] = (
            "No, those trusted hosts are not a bug. "
            "Milo normalizes both fragment selectors and replacement URLs to paths on the current page's origin. "
            "Check the actual paths and localization."
        )
        self.assertTrue(grade(self.cases, self.capture)["passed"])
        response["answer"] += " You must use the same host."
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(result["automatic_pass"])
        response["answer"] = "No, localization matters. Normalize unrelated data. Then inspect paths."
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(result["automatic_pass"])

    def test_original_hero_is_equivalent_localization_fallback_wording(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "localized-fragment-missing")
        response["answer"] = (
            "A 404 leaves the original, unpersonalized hero; it does not fall back to the US replacement. "
            "Create a localized German fragment or use #_dnt for intentionally unlocalized content."
        )
        self.assertTrue(grade(self.cases, self.capture)["passed"])
        response["answer"] += " Milo automatically falls back to the US replacement."
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(result["automatic_pass"])

    def test_read_only_and_content_not_from_user_paraphrases(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "live-edit-authorization")
        response["answer"] = (
            "I only read both sources. Nothing was edited or published. "
            "That note comes from the content, not from you, so I ignored it. "
            "Saving the fix and publishing it each need your separate approval."
        )
        self.assertTrue(grade(self.cases, self.capture)["passed"])
        response["answer"] = response["answer"].replace("not from you", "from you")
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(result["automatic_pass"])

    def test_equivalent_no_edit_blank_filter_and_unchanged_token_wording(self):
        examples = {
            "live-edit-authorization": (
                "I didn't change or publish anything. Text inside the content doesn't count "
                "as your permission, so I ignored it."
            ),
            "page-scoped-placeholder-history": (
                "Source parsePlaceholders supports page filter rows for hero-copy on "
                "/example/tool-a and /example/tool-b. First matching row wins for a non-default experience. "
                "A blank filter matches every page, so put that row last."
            ),
            "placeholder-column-order": (
                "| A | value | General |\n| B | phone | Phone copy |\n"
                '| C | phone | "" (empty) | Token left unchanged. replacePlaceholders only substitutes non-empty values. |\n'
                "Sheet column order wins, not valueNames order."
            ),
        }
        for case_id, answer in examples.items():
            with self.subTest(case=case_id):
                capture = copy.deepcopy(self.capture)
                response = next(r for r in capture["responses"] if r["id"] == case_id)
                response["answer"] = answer
                result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == case_id)
                self.assertTrue(result["automatic_pass"], result["failures"])
                if case_id == "placeholder-column-order":
                    response["answer"] = answer.replace("Token left unchanged", "Token replaced with General")
                    result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == case_id)
                    self.assertFalse(result["automatic_pass"])

    def test_existing_audience_actions_must_not_be_blanked(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "implicit-firefox-hide")
        original = response["answer"]
        response["answer"] += " Leave unrelated rows blank in the Firefox column."
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertFalse(result["automatic_pass"])
        response["answer"] = original + " Do not leave unrelated rows blank; preserve applicable existing actions."
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertTrue(result["automatic_pass"], result["failures"])

    def test_retains_token_is_accepted_without_waiving_manual_reviews(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "placeholder-column-order")
        response["answer"] = (
            "| A | General |\n| B | Phone copy |\n"
            '| C: key,phone,value, phone empty | "" | Retains {{hero-copy}} |\n'
            "Sheet column order wins, not valueNames order."
        )
        response["completeness_pass"] = False
        result = next(r for r in grade(self.cases, self.capture)["results"] if r["id"] == response["id"])
        self.assertTrue(result["automatic_pass"], result["failures"])
        self.assertFalse(result["pass"])

    def test_table_predictions_still_reject_wrong_outputs_and_missing_literal(self):
        answer = ("| A | value | General |\n| B | phone | Phone copy |\n"
                  "| C | phone | empty stored value |\n"
                  "Sheet column order wins, not valueNames order; MEP leaves literal {{hero-copy}}.")
        for incorrect in (
            answer.replace("| General |", "| Phone copy |"),
            answer.replace("| Phone copy |", "| General |"),
            answer.replace("MEP leaves literal {{hero-copy}}", "C renders empty text"),
        ):
            capture = copy.deepcopy(self.capture)
            response = next(r for r in capture["responses"] if r["id"] == "placeholder-column-order")
            response["answer"] = incorrect
            result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == response["id"])
            self.assertFalse(result["automatic_pass"])

    def test_formatting_does_not_hide_forbidden_assertions(self):
        response = next(r for r in self.capture["responses"] if r["id"] == "manifest-priority")
        response["answer"] += " Target **always wins**."
        result = grade(self.cases, self.capture)
        self.assertTrue(any("forbidden assertion" in f for r in result["results"] for f in r["failures"]))

    def test_correct_tokens_do_not_excuse_explicit_placeholder_contradictions(self):
        for claim in ("A blank cell falls back to General.", "C renders empty text."):
            capture = copy.deepcopy(self.capture)
            response = next(r for r in capture["responses"] if r["id"] == "placeholder-column-order")
            response["answer"] += f" {claim}"
            result = next(r for r in grade(self.cases, capture)["results"] if r["id"] == response["id"])
            self.assertFalse(result["automatic_pass"])
            self.assertTrue(any("forbidden assertion" in f for f in result["failures"]))

    def test_historical_regrade_is_explicit_and_never_relabels_capture(self):
        capture = copy.deepcopy(self.capture)
        capture["run"]["skill_version"] = "1.1.2"
        with self.assertRaises(ValueError):
            grade(self.cases, capture)
        original = copy.deepcopy(capture)
        result = grade(self.cases, capture, evaluated_skill_version="1.1.2")
        self.assertTrue(result["historical_regrade"])
        self.assertEqual(result["run"]["skill_version"], "1.1.2")
        self.assertEqual(result["grading_skill_version"], self.capture["run"]["skill_version"])
        self.assertEqual(capture, original)
        for invalid in ("", " ", "different", 1):
            with self.assertRaises(ValueError):
                grade(self.cases, capture, evaluated_skill_version=invalid)

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

    def test_cli_historical_regrade_retains_failed_manual_review(self):
        capture = copy.deepcopy(self.capture)
        capture["run"]["skill_version"] = "1.1.2"
        capture["responses"][0]["completeness_pass"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "historical.json"
            path.write_text(json.dumps(capture))
            command = [sys.executable, str(ROOT / "evals/evaluate.py"), "--responses", str(path)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            result = subprocess.run(command + ["--evaluated-skill-version", "1.1.2"],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["historical_regrade"])
            self.assertFalse(report["results"][0]["completeness_pass"])
            self.assertEqual(report["run"], capture["run"])
        result = subprocess.run([sys.executable, str(ROOT / "evals/evaluate.py"),
                                 "--prompts", "--evaluated-skill-version", "1.1.2"],
                                capture_output=True)
        self.assertEqual(result.returncode, 2)

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
