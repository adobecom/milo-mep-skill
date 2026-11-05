# milo-mep — changelog

Notable changes to the skill. Newest first. (Maintainer aid; not read at
runtime.)

## 2026-11-06

**Skill release 1.1.10 — leaner entry point and evaluation tooling (unreleased candidate)**
- Trimmed `SKILL.md`: condensed template, xlsx, linter, and source-authority
  text that duplicated the routing table or references, and moved
  maintainer-only snapshot refresh steps to the repository README. The
  answer checklist, ground rules, and live-edit boundaries are unchanged.
- `check-source-drift.py` now also tracks symbols cited in backticks across
  `SKILL.md` and references, separates personalization-feature changes from
  incidental ones (`--ignore-incidental`), and fails when a fetch fails.
  A weekly repository workflow runs it.
- Evaluation harness: quote-backed judge verdicts and check waivers (reject
  patterns stay unwaivable), offline judge-prompt export, repeat-run pass
  rates, and a neutral answering workspace fixture.
- Corrected stale references found while mining community questions: the
  `mepgeolocation` gate no longer exists (Milo resolves `countryip` on every
  MEP page; documented country precedence and that `not countryip(...)`
  matches when no country is detected), and `media2` counts siblings under
  one parent rather than page order (use `section2 media`). Added
  pinned-source tests for both.
- Added five synthetic cases (33 total) from recurring community themes:
  regular cases for the two corrections, and held-out cases for single-`*`
  page filters, promo `?instant` time zones, and `postlcp` first-section
  limits, with adverse controls. The held-out scenarios are not in the skill.
- From the first targeted runs: the answer checklist now asks for matching and
  non-matching checks for page filters and promo schedules (a promo outside
  its window loads as Default unless forced), and for corrected selectors in a
  complete example row. Source notes now state that schedule bounds are
  inclusive and that a blank `start`/`end` is open-ended rather than disabled,
  with a pinned-source test. Corrected the `country-not-list` reference answer:
  `?akamaiLocale` outranks the country cookie.
- Fresh cross-model behavioral evaluation remains required before distribution.

## 2026-11-05

**Skill release 1.1.9 — consolidated answer checklist and refreshed source (validated)**
- Refreshed the bundled Milo snapshot to `main` at `3960bb8`. Documented the
  preview-only `meplcp` LCP Img Check and the in-block M@S `pzn` replacement
  parameter; replaced stale source line citations with function names.
- Documented source behavior: a forced `?mep` variant wins over consent and
  country-restriction Default; info values are case-sensitive and unknown
  values sort as Normal/Promo; a manifest with no info tab uses
  `personalized offer` consent regardless of source.
- Consolidated duplicated `SKILL.md` selector, existing-manifest, verification,
  and placeholder rules into one Answer checklist without dropping requirements.
- Gave synthetic example 1 an observable phone/desktop result and
  metadata-append guidance.
- Added six held-out cases and one negative case (28 total), with adverse
  controls. The live-edit case is now graded against the mock DA audit
  (`--da-audit`) instead of trusting captured tool calls.
- Added pinned-source tests for manifest priority sorting and first-match
  command completion.
- After the first targeted Sol run (`ee45f37`), added a country/consent-gate
  checklist item (spoof with `akamaiLocale`, compare in/out-of-scope
  countries, keep the manifest unforced). The forced-preview and row-country
  cases therefore no longer test untuned transfer. Also accepted equivalent
  "forcing"/"all five rows" wording, rejected only asserted "MEP is broken",
  and dropped two over-strict review items (naming the template; a uniqueness
  check for a selector the user did not propose). A rubric-only follow-up
  (`14e363d`) accepted "advertising accepted", "treats … as Normal", and
  spoofed-country comparison without `?mep`, and replaced the LCP report-format
  disclosure with "do not invent it".
- After the targeted Opus run (`ae989e8`), added a fragment-swap ground rule,
  forbade reclassifying consent to make an
  experience appear, extended selector checks to user-supplied selectors being
  diagnosed, and moved "no Target change is needed" into the checklist so it
  applies to authoring answers. The lifecycle and remove-typo cases now also
  informed instructions. Accepted "I only read …" and "matches exactly one
  intended CTA" as equivalent wording.
- After the targeted Sol run (`2995f0a`), corrected the gate item: forcing
  bypasses consent and `manifest-country-restriction`, not row-level
  page/country filters. Added an adverse control for that overstatement and
  accepted consent-state tables and "matches exactly the one intended CTA".
- After the 2995f0a Opus review, corrected the fragment-swap rule: the first
  sorted swap wins per selector, and a later-sorted swap keyed on an earlier
  replacement path redirects it (forward chaining only), per
  `consolidateObjects()`. Added a pinned-source test. Selector checks now name
  rows being corrected; accepted "Accept all" consent cells and
  "file/text isn't your permission" wording.
- Validated with fresh runs of all 28 cases on candidate `d51db0e` (Copilot CLI
  1.0.105, medium effort), graded with `fff9eee` and `--da-audit`.
  GPT-6.1 Sol: 28/28 on activation, automatic, correctness, and completeness.
  Claude Opus 5.5: 28/28 on completeness and 27/28 elsewhere. On
  `negative-component-css` it invoked the skill, then declined correctly with
  no changes. That happened in 1 of 6 fresh runs; the 5 reruns did not invoke
  it. The miss was accepted as an occasional activation miss.
- The held-out forced-preview, row-country, fragment-lifecycle, remove-typo,
  and missing-info cases informed fixes during this cycle, so they no longer
  measure untuned transfer.

## 2026-11-04

**Skill release 1.1.8 — explicit selector verification (validated)**
- Required uniqueness checks for illustrative and nested-fragment selectors,
  including first-match completion and observable Highlight Changes QA.
- Accepted equivalent no-edit, blank-filter-last, and unchanged-token wording
  in evaluation screens without relaxing manual or DA trace gates.
- Validated with fresh runs of all 21 cases on GPT-6.1 Sol and Claude Opus 5.5
  (Copilot CLI 1.0.105, medium effort): 21/21 on activation, automatic,
  correctness, and completeness under grader `33b7094`.

**Skill release 1.1.7 — safe authoring alternatives and complete priority (unreleased candidate, superseded)**
- Required inspection and preserved audience actions before offering an
  existing-manifest edit; removed the unsafe one-row fallback for unseen files.
- Required the stable equal-setting tiebreaker in priority explanations.
- Accepted equivalent read-only and source-is-not-user-approval wording in
  grading, with adverse controls; no safety/manual gates were waived.
- Fresh cross-model behavioral evaluation remains required before distribution.

**Skill release 1.1.6 — additive-change verification (unreleased candidate, superseded)**
- Made conflict inspection and preservation QA explicit in the response
  checklist when proposing an additional manifest, not just in ground rules.
- Fresh cross-model behavioral evaluation remains required before distribution.

**Skill release 1.1.5 — preserve existing audience actions (unreleased candidate, superseded)**
- Clarified that experience selection is manifest-wide and blank cells never
  inherit another experience's actions.
- When adding an audience, preserve applicable existing actions or propose an
  isolated manifest with existing metadata retained and conflicts checked.
- Added pinned-source coverage and an adverse evaluation control for blanking
  unrelated rows in an existing manifest.
- Fresh cross-model behavioral evaluation remains required before distribution.

**Skill release 1.1.4 — prediction scope and verification (unreleased candidate, superseded)**
- Made stored value, MEP substitution, and unverified final page rendering
  distinct in the entry point, including when reading runtime source directly.
- Required page/experience-specific QA for prediction-only answers and each
  compared column layout, not only authoring/troubleshooting answers.
- Added the exact phone qualification threshold and OR condition to the entry
  point, backed by pinned-source boundary regressions.
- Fresh cross-model behavioral evaluation remains required before distribution.

**Skill release 1.1.3 — placeholder rendering correction (unreleased candidate, superseded)**
- Corrected empty placeholder guidance: the selected value is stored empty,
  but MEP's truthy-only replacement leaves the literal token unchanged.
  Other page placeholder pipelines require separate verification.
- Reinforced concrete proposed examples, authored/plain-HTML matching,
  destination-specific permission reporting, and placeholder QA outcomes.
- Made evaluation patterns accept equivalent wording and Markdown tables,
  with adverse controls and unchanged mandatory manual/trace checks.
- Added explicit historical regrading without relabeling original captures.
  Regrading 1.1.2 answers is not a behavioral evaluation of this candidate;
  fresh cross-model evaluation remains required before distribution.

**Skill release 1.1.2 — evaluation-driven precision (unreleased candidate, superseded)**
- Added reversed-column placeholder counterexamples and an explicit warning
  that the lookup list does not define value-column precedence.
- Reinforced replacement-URL `#_dnt` placement, preview filter boundaries,
  unique authored selectors, and observable QA outcomes.
- Added column-order prediction and held-out transfer evaluations; separated
  required manual correctness and completeness decisions in evaluation reports.
- Live cross-model behavioral evaluation remains required before distribution.
- Clarified URL query/hash preservation, existing Target settings, and
  conditional verification outcomes; discouraged speculative republishing.
- Added a synthetic MCP source-injection fixture and trace requirements so an
  answer-only refusal cannot pass as a completed tool-response evaluation.

## 2026-11-03

**Skill release 1.1.1 — source-verified troubleshooting**
- Documented page-filtered placeholder rows, first-matching-key semantics,
  column-order value selection, and default-experience behavior. Older advice
  that page-specific placeholder copy is unavailable is not current.
- Added a warning when an unscoped placeholder row shadows later rows for the
  same key, without flagging valid scoped duplicates and last fallbacks.
- Added forced-preview carry-over diagnosis: a nonempty `mep` parameter can
  attach a manifest on another page; hiding the panel does not clear it.
- Added pinned-source behavioral regressions and three synthetic agent eval
  cases, including a held-out nested-fragment lifecycle transfer probe.
- Used original community Q&A retrieved through Glean to verify the pilot
  findings; documented existing M@S Studio href updates and whole-value class
  updates, with two more synthetic evals and pinned-source attribute regressions.
  Raw conversations and internal provenance are not distributed with the skill.
- Corrected the synthetic phone example: qualification requires mobile-device
  detection plus the screen-size condition, not just a narrow desktop viewport.

**Skill release 1.1.0 — reliability and distribution**
- Added an installed release identifier in `SKILL.md`, separate from the Milo
  runtime source pin. Preserved the installed concise activation description,
  keeping it within the Agent Skills description length limit.
- Added offline linter/CLI, XLSX round-trip, template-preservation, archive,
  release-identity, and generated-browser freshness regressions with a shared
  local/CI release gate.
- Added 14 behavioral evaluation cases with blind prompt export, captured-run
  grading, negative controls, evidence, and mandatory manual rubric review.
  Grader fixture tests are explicitly not live model evaluation results.
- Made shared-content inspection read-only by default; require explicit
  authorization for writes and separate preview/publish/move/delete operations,
  with destination freshness checks and confirmation of tool success.
- Added compact synthetic native-personalization, Target/Promo priority, and
  missing-localized-fragment examples.
- Fixed XLSX authoring silently omitting consent/country keys absent from the
  official template: supported missing info keys are appended without
  rebuilding the workbook; unknown keys now fail explicitly.

**MEP vs Target priority**
- Added an explicit cross-source answer: Execution Order first, then Type
  (`Personalization` before `Promo` when execution order ties), with examples
  and `helix-info` authoring guidance.
- Corrected metadata-order-only guidance across the entry point and references;
  URL order only breaks ties after execution order and type.
- Clarified drawer numbering versus priority and action-specific final results,
  grounded in the bundled manifest sort and application code.

## 2026-10-16

**Optional distribution archive**
- Added repository-root `package-milo-mep.sh` to build `milo-mep.skill` for
  manual distribution, excluding hidden files, evals, and Python caches.

**Milo source refresh**
- Refreshed the bundled source snapshot to `main` at `5ac9112` and added the
  MEP Next sources used by preview/geo-spoofing guidance.
- Updated consent and country documentation for `manifest-consent-type`,
  `manifest-country-restriction`, legacy key aliases, and row-level country
  filters. Updated the linter's missing-consent default guidance accordingly.
- Refreshed source notes for fragment media reuse, configured `allowedOrigins`,
  entitlement fallback, and field-level MAS overrides.

## 2026-07-31

**Source-snapshot freshness (manual)**
- Pinned the bundled snapshot to a `main` commit in `assets/source/SOURCE_VERSION`
  and **expanded it** to every file the references cite (added `utils.js`,
  `merch.js`, `mas-mep-utils.js`, `fragment.js`, `lingo.js`, `martech/attributes.js`,
  `martech.js`, `getUserEntitlements.js`, `georouting.js`) — mapped via
  `scripts/source-manifest.txt`.
- Added `scripts/check-source-drift.py` (diffs the snapshot against `main`, flags
  changed cited symbols) and `scripts/snapshot-source.py` (re-fetch + re-pin).
  Freshness is **manual/maintainer-side** — run the drift check before
  re-publishing; there is no auto-update to already-installed copies.
- Sanitized the worked example (`assets/example-manifest.json` +
  `references/example-manifest.md`) to synthetic values.

## 2026-07-30

**Hardening pass**
- Documented the full set of enablement metadata keys (`personalization-v2`,
  `personalization-roc`, `manifestnames`+`schedule`, `xlg`, `ajo`,
  `mepgeolocation`, `mep-marketing-decrease`) beyond `personalization`/`target`
  (`enable-and-qa.md`), incl. the logged-out persV2 "on, no inline path" case.
- Added a `package-milo-mep.sh` build script (excludes evals/, `__pycache__`,
  `*.pyc`) and this changelog; renumbered the troubleshooting causes list.
- Tuned the skill description for auto-trigger accuracy.

**Selector / behavior coverage** — `#_inline` renders undecorated unless
re-decorated; aria-label via replacement content or `updateAttribute`;
M@S-card-in-nested-DA-fragment reliability caveat; the `#_mep-lingo` flag;
`phone`/`PHONE_SIZE` exact definition; tag/segment intake process; DA region
preview (`?dapreview=on`); test/demo promo sheet placement.

**Linter** — fixed two false-positives (path-alternation page filters like
`(/|/x)`; multiple `replacePage` scoped to different page filters); added a
comma-in-page-filter rule.

**Manifest coverage** — manifest naming rules, `/products/` no-rewrite,
modals-are-fragments, scheduled promos (`all`), `daa-lh` analytics,
`in-block:merch-card-collection`, `section-metadata` vs `metadata`,
`in-block:global`, gnav promo swap, CaaS fragment-swap, MEP-is-live-only.

## Earlier

- **Linter** (`scripts/lint-core.mjs`, single source of rules) across Node CLI
  (`lint.mjs`), browser (`lint.html`), and xlsx (`lint_manifest.py`), with opt-in
  `--check-links` fragment-404 checking.
- **xlsx read/write** (`scripts/mep_xlsx.py` + vendored openpyxl) preserving the
  template's dropdowns/styles via byte-preserving zip surgery.
- **Initial skill** — SKILL.md + 14 references, grounded in the Milo
  `personalization` source (bundled under `assets/source/`; a live local checkout
  preferred), plus the official manifest template.
