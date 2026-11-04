# Skill behavioral evaluations

`cases.json` covers activation (including implicit MEP requests and negative
examples), priority, consent defaults, localization, selectors, experience
order, trusted fragment hosts, live-edit authorization, page-scoped
placeholders, forced-preview carry-over, class-attribute replacement, and
existing M@S Studio href updates. All examples are
synthetic. Evidence paths and manual rubrics accompany each case.

The lifecycle-conflict case marked `split: "holdout"` is reserved as a transfer
probe: its specific scenario is not added as a worked example in the installed
skill. Keep it out of answering-agent context along with the other rubrics and
reference answers. This label is not a claim that the underlying mechanism is
absent from the existing reference material.

## Run against an agent

1. Install the candidate skill in the agent/tool being evaluated.
2. Export blind prompts: `python3 evals/evaluate.py --prompts`. Run each prompt
   in a **fresh conversation** with normal skill discovery. Do not force-load
   `/milo-mep`: that would invalidate activation testing. Do not expose
   `cases.json`, expected activation, rubrics, or reference answers to the
   answering agent. Restrict its repository access to the installed skill.
3. Capture whether the skill actually loaded from the tool trace, not from the
   agent's claim or MEP words in its answer. If the host cannot expose that
   signal, mark the run blocked; do not infer a routing pass.
4. Review the real answer against every `review` item and `evidence` reference
   in the case. Inspect tool traces for the live-edit case: an answer promising
   read-only behavior does not excuse a write/publish call. Use an isolated
   read-only/mock DA tool; never give evaluation runs live write credentials.
5. Save a complete capture outside the repository and grade it:

```bash
python3 evals/evaluate.py --responses /path/to/capture.json
```

Capture format (include every case ID exactly once):

```json
{
  "run": {
    "model": "actual model ID from host",
    "host": "agent host and version",
    "skill_version": "1.1.1",
    "reviewer": "reviewer identifier",
    "date": "2026-11-03"
  },
  "responses": [
    {
      "id": "implicit-phone-hero",
      "activated": true,
      "answer": "Verbatim captured agent answer",
      "review_pass": true,
      "review_notes": "Evidence for each rubric item, including tool behavior."
    }
  ]
}
```

No model API, credentials, or network access is built into this harness. It
grades captured responses only. Pattern checks catch missing concepts and some
known adverse advice; **they are not a semantic judge**. A correct paraphrase
may need a reviewed pattern update. Keyword-stuffed or contradictory answers
must fail the manual rubric even when patterns pass. Negative-case answers are
not content-graded: the observed activation decision is what matters.

Exit codes: `0` all checks and rubric reviews pass, `1` at least one failure or
unreviewed case, `2` invalid/incomplete/stale-release input. Keep raw traces and
the report with the release evidence in session artifacts or another approved
location; do not commit real user manifests or conversation content.

## Automated versus behavioral gates

`./scripts/check-release.sh` runs deterministic tool regressions, fixture
integrity, grader positive/negative controls, archive checks, version checks,
and browser-tool freshness. CI runs the same command offline. Tests using
`reference_answer` verify the **grader**, not a model's behavior, and must
never be reported as a successful behavioral run.

Before distributing a release that changes instructions, descriptions, or
grounded behavior, also run the fresh-conversation procedure above on each
supported agent host being claimed. Require all cases to pass, record the
actual model/host and skill version, and investigate failures before release.
No live model evaluation is silently performed by CI or packaging.
