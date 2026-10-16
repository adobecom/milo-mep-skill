---
name: milo-mep
description: >-
  Understand, read, author, and QA MEP (Milo Experiments and Personalization) —
  the Excel/JSON manifests that show, swap, hide, or replace content on
  adobe.com pages built on Milo/EDS without editing the page source. Use
  whenever the task involves a Milo/adobe.com page and any of: an MEP manifest
  (its helix-experiences / helix-info / helix-placeholders tabs, or its
  published .json/.xlsx); personalization tags or audiences (browser, device,
  locale/geo, login state, URL params, entitlements, previouspage, countryIP);
  A/B tests, promos, or Adobe Target activities on a Milo page; enabling MEP via
  "personalization" or "target" page metadata (including target-on
  Lighthouse/performance impact); the ?mep preview parameter, the MEP button, or
  "highlight changes"; naming or placing manifests and fragments; or debugging
  why an experience isn't applying. Applies even when the user doesn't say
  "MEP" (e.g. "show a different hero on mobile vs desktop for the acrobat page",
  or "hide the promo banner for Firefox on /de/creativecloud"). Do NOT use for
  Adobe Target or A/B tests outside Milo (e.g. email subject lines),
  personalizing emails or CRM messages, spreadsheets merely named "manifest"
  (e.g. a shipping manifest .xlsx), building web/React components or fixing a
  Milo block's CSS, SEO/hreflang, analytics reporting, page publishing / CDN
  cache, generic feature-flag rollouts, or writing marketing copy.
---

# Milo Experiments and Personalization (MEP)

## What MEP is

MEP lets authors modify a Milo/EDS page — swap, add, hide, or replace content —
**without editing the source page**, driven by an Excel **manifest** that
publishes to JSON and is applied at runtime in the browser. It powers three
use cases:

- **Personalization** — show different content by browser, OS, device, locale,
  login state, entitlement, URL parameter, or geo.
- **Promotions** — time-boxed offers (Black Friday, etc.).
- **A/B testing** — measured experiments, usually via Adobe Target.

The manifest is authored as an Excel file in SharePoint, published to JSON by
EDS, and referenced from a page's `personalization` metadata (and `target`
metadata when Adobe Target is involved). At runtime Milo parses the manifest
and applies each row's action to the matching selector for the qualifying
experience.

## How to use this skill

MEP has a lot of surface area, so the details live in focused reference files.
**Read only the ones the current task needs** — don't load everything up front.
Start here to orient, then follow the pointers.

| Task | Read |
|---|---|
| Explain a concept, term, or how MEP behaves | this file; `references/concepts.md` for depth |
| **Interpret** an existing manifest (xlsx/json) | `references/interpret-output-format.md` (how to present it), plus `references/manifest-schema.md`, then `references/actions.md`, `references/selectors.md`, `references/personalization-tags.md` as needed |
| **Author / design** a new manifest from a goal | start from `assets/mep-manifest-template.xlsx` (the official base), all of the above **plus** `references/conventions.md` (naming/folders) |
| **Enable** MEP on a page | `references/enable-and-qa.md` |
| **QA / troubleshoot** (why isn't it applying?) | `references/enable-and-qa.md` |
| Explain the **MEP button** / `?mep` preview (what it does + how it works) | `references/mep-button.md` |
| Want a worked, real example | `references/example-manifest.md` |
| Read/write a manifest **.xlsx** file | `scripts/mep_xlsx.py` (see `references/xlsx-io.md`) |
| **Validate / lint** a manifest | published `.json`: `node scripts/lint.mjs <file\|URL>` (add `--check-links` to verify fragment paths) or open `scripts/lint.html`; `.xlsx`: `python scripts/lint_manifest.py <file>`. See `references/linting.md`. |
| Replace **M@S cards / CaaS / content in nested fragments** | `references/mas-caas-fragments.md` |
| Need exact/edge-case behavior (the source of truth) | `references/source-notes.md`; grep `assets/source/personalization.js` |

If the user is working against live files in SharePoint/DA and a suitable MCP
is available, use it to read/write; otherwise work from pasted xlsx content or
the published `.json` (fetch the `.aem.live` URL — the `.aem.page` preview URL
requires auth).

**Reading/writing manifest `.xlsx` files:** use the bundled
`scripts/mep_xlsx.py` (openpyxl vendored in `scripts/vendor/`, no install
needed) — `read` normalizes an xlsx or published `.json` to columns+rows, and
`write` builds a new manifest from the template preserving the `readme`/styles.
Don't hand-parse xlsx (empty cells shift columns). See `references/xlsx-io.md`.

## Response style (all tasks)

MEP answers get dense fast. Optimize for a reader skimming on Slack. Follow
these for every response:

- **Lead with the answer.** Open with a one-line verdict — the root cause and
  the fix, or the bottom line — before any explanation. Never make the reader
  hunt for it.
- **Show the fix as code.** Put corrected selectors, rows, values, and URLs in
  code blocks/tables, not buried in a sentence.
- **Short sections with bold labels; one idea per bullet.** Prefer a labeled
  list over a paragraph. Keep sentences short.
- **Rank by likelihood.** When listing causes or fixes, put the most probable
  first and stop where it stops being plausible — don't pad.
- **Explain the *why* briefly, once.** Two or three sentences on the mechanism,
  tied to any "works when X, fails when Y" signal. Don't repeat it across
  sections.
- **End with how to verify** (usually the `?mep` + Highlight Changes step).

Task-specific shapes: interpret → `references/interpret-output-format.md`;
troubleshoot → the answer format in `references/enable-and-qa.md`.

## Manifest anatomy (quick orientation)

An MEP manifest is a multi-sheet workbook. The three sheets that publish to
JSON (Excel tab names are prefixed `helix-`, e.g. `helix-experiences`; the
published JSON drops the prefix → `experiences`):

- **info** — manifest-level settings (`manifest-type`, `manifest-execution-order`,
  `manifest-override-name`, `manifest-consent-type`,
  `manifest-country-restriction`).
- **experiences** — the heart of the manifest. Each **row** is one change:
  an `action`, a `selector` (where), optional page/country filters, and then one
  column **per experience** whose header is a personalization tag or Target
  activity name. Experience columns are ordered **highest priority first**;
  a user qualifies for the **first** matching column only.
- **placeholders** — key/value substitutions (`{{key}}`) for copy and
  localization.

A `readme` tab is informational only and is not published.

Read `references/manifest-schema.md` before interpreting or authoring — it has
the exact columns, accepted values, and JSON shape.

## The four things this skill does

### 1. Understand / explain
Answer from this file and `references/concepts.md`. Be precise about the
difference between MEP-native personalization (no Target needed: device, OS,
browser, locale, login, params, geo) and Target-dependent features (A/B tests,
AAM/Target segments). Note the performance tradeoff: `target on` blocks page
build; MEP alone is cheap.

### 2. Interpret a manifest
Given an xlsx or json, produce a reading that **leads with business framing and
backs it with rigor** — follow the template in
`references/interpret-output-format.md`. In short: open with a plain-language
TL;DR and a `segment → experience` summary (decode audience/offer names into
likely intent, clearly marked as inference), then a detailed row-level walk
(actions, selectors, flags, geo), then **Errors** (verified, with evidence) and
**Opportunities**. Walk sheets info → experiences → placeholders, and run the
don't-miss checks (consent default, no-op rows, page-filter regex typos,
undefined placeholders) from the format doc and `references/enable-and-qa.md`.
Never flag fragment-URL domains (they're normalized — see `selectors.md`).

### 3. Author / design a manifest
**Start from the official template** at `assets/mep-manifest-template.xlsx` —
copy it as the base for any new manifest. It already contains the `helix-info`
sheet (with the STEP prompts; default `manifest-type` is `Promo`), a
`helix-experiences` header row (`action`, `selector`, `page filter (optional)`,
and a default `all` experience column), an empty `helix-placeholders`, and the
`readme`. Fill the sheets and **keep the `readme` tab**. When writing an actual
`.xlsx`, use `scripts/mep_xlsx.py write` (copies the template and injects rows);
don't build a workbook from scratch (that loses the readme and formatting). See
`references/xlsx-io.md`.

Turn a goal ("A/B test the hero CTA for logged-in users on the US Photoshop
page") into concrete rows: set the manifest type, name the file per
`references/conventions.md`, pick the right selector (prefer simplified,
"goldilocks" specificity), the right action, and the right experience-column
header(s) (rename/add columns beyond the default `all`). Also show it as a table
the user can paste into Excel, and state the filename and folder it lives in.

### 4. QA / troubleshoot
Build `?mep` preview URLs, reason about why an experience isn't applying
(priority order, page filter mismatch, wrong selector against **plain** HTML,
Target off, missing localized fragment), and validate a manifest with the
linter (`node scripts/lint.mjs <json|URL>` or `scripts/lint.html`; xlsx via
`python scripts/lint_manifest.py <file>` — see `references/linting.md`). Present
the answer in the **troubleshooting answer format**
(Verdict → fix-as-code → brief Why → ranked "other things to check" → Verify)
and the causes menu — both in `references/enable-and-qa.md`.

## Ground rules that prevent most mistakes

- **Selectors run against plain (pre-decoration) HTML**, not the rendered page.
  Inspect the source HTML, not the finished DOM.
- **Be as vague as possible while still unique** (the "goldilocks" method).
  Prefer simplified selectors (`any-marquee primary-cta`) over brittle chains.
- **MEP targets the first match by default**; add `#_all` to hit every match.
- **Experience-column order is priority**; a user gets the first column they
  match. Put the most specific/important experiences leftmost.
- **Localization is automatic**: manifests are *not* localized. A GEO page
  reuses the US manifest and Milo looks for a same-named local fragment; if
  none exists, the default (unpersonalized) content shows. Use `#_dnt` or
  placeholders to opt a fragment out of localized lookup.
- **Manifest priority on a page** = the order the manifest URLs are listed in
  `personalization` metadata (top = highest).

## Source authority

The **ultimate** source of truth is the Milo source code. Prefer a **live local
checkout** if one exists — it's fresher than any snapshot. Check
`libs/features/personalization/` under a local Milo repo; it's commonly at
`~/git/milo/libs/features/personalization/` (try that path
first, else look for a `milo` checkout, else fall back to the bundled snapshot).
A snapshot is bundled in `assets/source/`, **pinned to a specific `main` commit**
recorded in `assets/source/SOURCE_VERSION` — so the skill works offline and its
facts are reproducible. The snapshot covers every file the references cite, not
just `personalization.js` (also `preview.js`, `utils.js`, `merch.js`,
`fragment.js`, `lingo.js`, `martech/attributes.js`, etc.); the
bundled-name → repo-path map is `scripts/source-manifest.txt`.
`references/source-notes.md` distills the exact tags, actions, flags, selectors,
matching/priority, consent gating, and promo behavior — consult that (or grep the
source) for any edge case or when a doc seems vague or dated. When the docs and
the source disagree, the source wins.

**Keeping the snapshot fresh (milo changes fast).** Don't fetch source live per
invocation — the distilled references are the product, and end users may have no
network/checkout. Freshness is a **manual, maintainer-side** step (there's no
auto-update: updating the snapshot only refreshes *this* install + the rebuilt
`.skill`; other installs need a re-publish). Before re-publishing (or whenever
milo may have changed): run `python3 scripts/check-source-drift.py` — it diffs
the bundled snapshot against `main` and flags which **cited symbols** changed.
On drift: adopt it with `python3 scripts/snapshot-source.py`, review/update the
affected references + `source-notes.md`, re-run the linter and evals, then
run `./package-milo-mep.sh` from the repository root and redistribute the
generated `milo-mep.skill`. Directory-based installs do not need packaging.

Current syntax otherwise follows the public Milo docs
(https://milo.adobe.com/docs/authoring/features/mep/). Adobe-internal
conventions (naming, folder layout, localization philosophy, team/Slack) come
from the internal wiki and are captured in `references/conventions.md`. Some
older internal docs use legacy action names (`replaceContent`, `replaceFragment`,
`removeContent`, `insertContentBefore/After`) and `martech` metadata — these map
to the current `replace`, `remove`, `insertBefore/After` actions and `target`
metadata. Prefer the current names.
