# milo-mep-skill

An AI agent **skill** for **MEP — Milo Experiments and Personalization**: the
Excel/JSON manifests that show, swap, hide, or replace content on **adobe.com**
pages built on **Milo/EDS** — *without editing the page source*.

The skill itself lives at [`skills/milo-mep/`](skills/milo-mep/) and follows the
[Agent Skills specification](https://agentskills.io/specification) (a `SKILL.md`
with frontmatter, plus `references/`, `scripts/`, and `assets/`). It is indexed
by the [Adobe Skills Directory](https://github.com/OneAdobe/skills) and works in
Claude Code, the Claude desktop/chat app, and any Agent-Skills–compatible tool.

---

## What is MEP?

MEP lets authors modify a Milo/EDS page — **swap, add, hide, or replace
content** — driven by an Excel **manifest** that publishes to JSON and is applied
at runtime in the browser, with no change to the source page. It powers three
use cases:

- **Personalization** — different content by browser, OS, device, locale/geo,
  login state, entitlement, URL parameter, or `previouspage`.
- **Promotions** — time-boxed offers (Black Friday, etc.).
- **A/B testing** — measured experiments, usually via Adobe Target.

A manifest is authored in SharePoint/DA, published to JSON by EDS, and referenced
from a page's `personalization` (and `target`) metadata. At runtime Milo parses
the manifest and applies each row's action to the matching selector for the
qualifying experience. See the public docs:
<https://milo.adobe.com/docs/authoring/features/mep/>.

---

## What the skill does

It turns Claude into an MEP specialist across four tasks:

| # | Task | What you get |
|---|------|--------------|
| 1 | **Understand / explain** | Precise answers on MEP concepts, tags, and behavior — device/OS/browser, locale/geo, login state, URL params, entitlements, `previouspage`, `countryIP`; A/B tests and Adobe Target; the `target`-on performance tradeoff. |
| 2 | **Interpret** a manifest | Given an `.xlsx` or published `.json`, a business-framed reading: decode audiences/offers, walk every row (actions, selectors, page filters, flags, geo), then **verified errors** (with evidence) and **opportunities**. |
| 3 | **Author** a manifest | Turn a goal into concrete rows — starting from the official template — with correct naming/folders, "goldilocks" selectors, the right actions and experience columns, plus a paste-ready table and the target filename/folder. |
| 4 | **QA / troubleshoot** | Build `?mep` preview URLs, reason about why an experience isn't applying (priority order, page-filter mismatch, wrong selector against *plain* HTML, Target off, missing localized fragment), and lint the manifest. |

It applies **even when the user never says "MEP"** — e.g. *"show a different hero
on mobile vs desktop for the acrobat page"* or *"hide the promo banner for
Firefox on /de/creativecloud"*. It deliberately does **not** engage for
non-Milo Target, email/CRM personalization, spreadsheets merely named
"manifest," component/CSS work, SEO/hreflang, analytics reporting, or CDN/cache.

---

## Repository layout

```
milo-mep-skill/
├── skills/
│   └── milo-mep/               # the skill (this is what gets installed)
│       ├── SKILL.md            # entry point: orientation + a routing table
│       ├── references/         # 14 focused docs — read only what a task needs
│       ├── scripts/            # linter, xlsx read/write, source-drift tooling
│       ├── assets/             # official manifest template + pinned Milo source
│       └── CHANGELOG.md
└── README.md
```

### Reference docs (`skills/milo-mep/references/`)

The skill keeps its surface area out of `SKILL.md` and routes to focused files:

| File | Covers |
|------|--------|
| `concepts.md` | MEP concepts in depth (native personalization vs Target-dependent, login/entitlement granularity, scheduled promos) |
| `manifest-schema.md` | Exact sheet/column schema, accepted values, and JSON shape |
| `actions.md` | Every action (`replace`, `remove`, `insertBefore/After`, `updateAttribute`, …) incl. legacy-name mapping |
| `selectors.md` | Selector rules against **plain** HTML, the "goldilocks" method, `:has()`, `in-block:`, first-match vs `#_all` |
| `personalization-tags.md` | Tags, operators, and page filters — device/`PHONE_SIZE`, geo/`countryIP`, login, params; tag/segment intake |
| `enable-and-qa.md` | Enabling MEP (all metadata keys), and the troubleshooting answer format + ranked causes |
| `mep-button.md` | The `?mep` preview panel — what it does and how it works (incl. region/locale preview) |
| `mas-caas-fragments.md` | Replacing M@S cards, CaaS, and content in nested DA fragments |
| `conventions.md` | Adobe-internal naming, folders, localization philosophy, team/Slack |
| `interpret-output-format.md` | The output shape for interpreting a manifest |
| `example-manifest.md` | A worked, real end-to-end example |
| `xlsx-io.md` | Reading/writing `.xlsx` with the bundled `mep_xlsx.py` |
| `linting.md` | Linter rules and how to run each front-end |
| `source-notes.md` | Ground truth distilled from the Milo source |

### Scripts (`skills/milo-mep/scripts/`)

- **Linter** — one rule source (`lint-core.mjs`) behind three front-ends:
  `lint.mjs` (Node CLI), `lint.html` (browser), `lint_manifest.py` (xlsx). Opt-in
  `--check-links` verifies fragment paths resolve (no 404s).
- **xlsx I/O** — `mep_xlsx.py` reads an xlsx **or** published `.json` to
  columns+rows and writes a new manifest from the template, preserving the
  `readme`/dropdowns/styles (openpyxl vendored under `scripts/vendor/`, no install).
- **Source-drift tooling** — `check-source-drift.py` diffs the bundled snapshot
  against Milo `main` and flags changed **cited symbols**; `snapshot-source.py`
  re-fetches + re-pins. See *Grounding* below.

---

## Grounding & source of truth

The skill is grounded in the **Milo source**
([`adobecom/milo`](https://github.com/adobecom/milo),
`libs/features/personalization/`). It prefers a **live local checkout** if one
exists (freshest), otherwise a **pinned snapshot** bundled under
[`skills/milo-mep/assets/source/`](skills/milo-mep/assets/source/) — 16 files
(`personalization.js`, `utils.js`, `merch.js`, `preview.js`, `fragment.js`,
`lingo.js`, …), pinned to a specific `main` commit recorded in `SOURCE_VERSION`.
This keeps the skill working offline and its facts reproducible. **When the docs
and the source disagree, the source wins.**

### Keeping the snapshot fresh (manual)

Milo changes fast. Freshness is a deliberate **maintainer-side** step — there is
no live fetch per invocation, and updating the snapshot only refreshes *this*
copy (other installs need a re-publish). Before re-publishing, or whenever Milo
may have changed:

```bash
# flag whether any CITED source symbol changed vs main
python3 skills/milo-mep/scripts/check-source-drift.py

# adopt the latest main + re-pin SOURCE_VERSION, then review refs & re-lint
python3 skills/milo-mep/scripts/snapshot-source.py
```

---

## Installing the skill

The skill is the `skills/milo-mep/` directory. To use it in **Claude Code**,
place it under a skills directory it scans (`~/.claude/skills/` for user scope,
or `.claude/skills/` in a project):

```bash
git clone https://github.com/adobecom/milo-mep-skill.git
mkdir -p ~/.claude/skills
cp -R milo-mep-skill/skills/milo-mep ~/.claude/skills/milo-mep
# restart Claude Code; the skill loads as /milo-mep
```

Once installed it auto-triggers on MEP/Milo-personalization tasks, or invoke it
explicitly with `/milo-mep`. (Via the Adobe Skills Directory it can also be
discovered and installed through that site's flow.)

---

## Linting a manifest

```bash
# published JSON or a URL (add --check-links to verify fragment paths)
node skills/milo-mep/scripts/lint.mjs <manifest.json | https://…/manifest.json> --check-links

# an .xlsx manifest
python3 skills/milo-mep/scripts/lint_manifest.py <manifest.xlsx>
```

Or open `skills/milo-mep/scripts/lint.html` in a browser and paste the JSON.

---

## Development

- **Changelog** — notable changes are in
  [`skills/milo-mep/CHANGELOG.md`](skills/milo-mep/CHANGELOG.md).

---

## References

- MEP authoring docs — <https://milo.adobe.com/docs/authoring/features/mep/>
- Milo — <https://github.com/adobecom/milo>
- Agent Skills spec — <https://agentskills.io/specification>
- Adobe Skills Directory — <https://github.com/OneAdobe/skills>
