# Linting a Manifest

Validate a manifest against the known failure modes. **The rules live once** in
`scripts/lint-core.mjs` (dependency-free JS); every entry point below uses it,
so they never drift.

## Entry points

| Input | Command / tool | Needs |
|---|---|---|
| Published `.json` (file) | `node scripts/lint.mjs manifest.json` | Node |
| Published `.json` (live URL) | `node scripts/lint.mjs https://…/manifest.json` | Node |
| Published `.json` (no install) | open `scripts/lint.html` in a browser — paste JSON or fetch a URL | just a browser |
| Source `.xlsx` | `python scripts/lint_manifest.py manifest.xlsx` | Python + Node |
| Normalized JSON (pipe) | `python scripts/mep_xlsx.py read x.xlsx \| node scripts/lint.mjs -` | Python + Node |

- **`scripts/lint.html`** is self-contained (the rules are inlined), so it works
  by double-clicking — no server, offline. Good for a quick check or sharing
  with non-devs. Regenerate it after editing the rules: `node
  scripts/build-lint-html.mjs`.
- **`lint_manifest.py`** just reads the `.xlsx` (via `mep_xlsx`) and pipes the
  normalized JSON into `node scripts/lint.mjs -` — so xlsx linting uses the same
  JS rules. It requires Node; without Node, use `lint.html` on the published
  `.json` instead.
- Exit code is non-zero when any **error**-level finding is reported (useful in
  CI on the published `.json`).

### Link checking (opt-in)

Add **`--check-links`** to also fetch every fragment path and flag 404s:

```
node scripts/lint.mjs https://…/manifest.json --check-links
node scripts/lint.mjs local.json --check-links --base https://main--dc--adobecom.aem.live
```

It resolves each fragment's **path against the manifest's origin** (that's where
Milo resolves it at runtime — the fragment's own host is stripped by
`normalizePath`), then GETs it. `404` → **error** (the fragment won't load — that
experience falls back to default); `401/403`/timeouts → **info** ("couldn't
verify"). When linting a local file, pass `--base <origin>` so relative/absolute
paths can be resolved. Caveat: a 404 can be a legitimately preview-only /
unpublished fragment — it means "not found at the resolved production path."

`lint.html` also has a **"Check fragment links"** button (with a base-origin
field), but it's **best-effort**: browser fetches are subject to CORS, so it can
only read a status when the fragment host allows cross-origin requests —
otherwise it reports "couldn't verify (CORS)". Use the Node CLI for
authoritative 404 results.

## What it checks

**Errors** (block; likely broken):
- unrecognized/misspelled **sheet name** (`experienxes` → "did you mean
  'experiences'?") and a **missing `experiences` sheet**
- unknown/misspelled **action** (`remvoe` → "did you mean 'remove'?")
- an action that **requires a selector** but has none (replace/remove/insert*/
  updateAttribute/updateMetadata)
- a row with a **selector/values but no action** (silently skipped at runtime)
- an **`all` column that isn't last** (matches everyone; columns to its right
  never apply)
- page filter that won't **compile as regex**, has a **backslash**, has a
  **`/` inside a locale group** (`be_fr/ca_fr` → `be_fr|ca_fr`; path-alternations
  like `(/|/homepage/x)` are allowed), or has a
  **comma** (it's a single regex, not a list — `**/uk/**, **/it/**` →
  `**/(uk|it)/**`; a `{n,m}` quantifier is not flagged)
- **untrusted** fragment/script URL host (dropped at runtime)
- **fragment not found (404)** with `--check-links`

**Warnings** (likely mistakes):
- **no-op row** (an action with no value in any experience column → does nothing)
- `remove` value not exactly `true`/`false`/`1` (a typo like `flse`/`0`/`false `
  inverts intent)
- **backslash in a fragment path/URL** (auto-corrected for absolute URLs, breaks
  relative)
- **whitespace inside the locale group** (`jp `), a **lone `*`**, or a page
  filter **not starting with `/`, `**`, or a `(` group** (anchored match won't
  hit a path)
- unknown **`#_` flag** (`#_include-fragmnets`)
- experience header that's a **near-miss of a built-in tag** (`deskotp` →
  `desktop`) — skipped for compound/prefixed headers to spare entitlement tags
- **duplicate** experience column header
- `updateAttribute` selector with **no attribute** appended (or a
  `javascript:`/`data:` href value, which is rejected at runtime)
- a global action (replacePage/useBlockCode/insertScript) with a **stray
  selector**; an **insertScript preview URL** (doesn't adjust preview→prod);
  a **fragment-looking value not starting with `/` or `https://`** (injected as
  literal text, not fetched); two+ **replacePage** rows that **share a page
  filter** (or are all blank) — only the first applies per page (rows with
  distinct page filters are fine)
- `updateFramework` value that isn't a foundation code (`c1`/`c2`)
- undefined `{{placeholder}}`; over-long or non-lowercase-dashed
  `manifest-override-name`

**Info**: missing `manifest-marketing-action` (type-aware consent default);
override-name on a non-Personalization manifest; US-exact page filter whose
siblings use `**` (a likely missing `**`).

It deliberately does **not** flag verified non-issues: mixed fragment-URL
domains (normalized away), `prepend`/`append` on fragment selectors, or `1` vs
`TRUE` for `remove`.

## Files

- `lint-core.mjs` — the rules (canonical; Node + browser).
- `lint.mjs` — Node CLI (file / URL / stdin; `--check-links`).
- `lint-ui.js` — the browser UI wiring (buttons, render, best-effort link check).
- `lint.html` — self-contained browser tool (generated; inlines core + UI).
- `build-lint-html.mjs` — regenerates `lint.html` from `lint-core.mjs` + `lint-ui.js`.
- `lint_manifest.py` — xlsx convenience wrapper (reads xlsx → runs the JS rules).
