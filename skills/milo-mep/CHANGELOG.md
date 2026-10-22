# milo-mep — changelog

Notable changes to the skill. Newest first. (Maintainer aid; not read at
runtime.)

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
