# Enabling MEP & QA / Troubleshooting

## Enabling MEP on a page

MEP is turned on via **page metadata**. Two properties:

| metadata property | value | effect |
|---|---|---|
| `personalization` | manifest path(s), e.g. `/example/smart-tools.json` | Attaches manifest(s). Multiple allowed, comma- or line-break-separated. **Order = priority** (top highest). Low performance cost. |
| `target` | `on` / `postlcp` / `off` | Enables Adobe Target integration. Needed for A/B tests and AAM/Target segments. **Significant Lighthouse/perf cost** even with no active activity — leave `off` unless Target is actually needed. `postlcp` is the faster mode (Target controls only non-LCP / below-section-1 changes). |

Two ways to set them:

- **Page metadata block** — add the properties to the source page's metadata
  section (usually at the end). Affects only that page. **The block must be named
  exactly `metadata`.** Whole-page settings put in a **`section-metadata`** block
  are *not* recognized — `section-metadata` only configures the one section it
  sits in, so `personalization`/`target` there appear in the page source but MEP
  ignores them (the MEP pill will show personalization/Target **off** even though
  the values are visibly present). This is a common, easy-to-miss mistake.
- **Metadata spreadsheet** — each Milo site has one; applies settings across
  whole folders at once. Powerful, so it needs stakeholder approval.

For a **mixed** manifest (Target experiences + personalization tags): set
`target on` **and** list the manifest in `personalization` metadata — so users
still get a good experience if Target is unavailable.

> Legacy note: older docs reference a `martech off` property; the current
> control is the `target` property.

### Other enablement metadata keys (you'll see these in the wild)

`personalization` and `target` are the two you author most, but Milo reads a
wider set of enablement keys (source: `getMepEnablement` in `libs/utils/utils.js`).
Recognize them when auditing a page:

| metadata key | what it enables |
|---|---|
| `personalization` | the manifest path(s) — the normal case |
| `personalization-v2` | the newer **logged-out** personalization path (value `on`; the homepage uses this). Milo resolves the manifest set from the metadata spreadsheet / Target rather than an inline path list, so you'll see `on` here, not a `.json` path |
| `personalization-roc` | regional-customization (ROC) manifests |
| `manifestnames` (+ regional `apac_`/`emea_`/`americas_`/`jp_` variants) & `schedule` | promo attachment (merch promo spreadsheet) |
| `target` | Adobe Target integration (`on`/`postlcp`/`off`) |
| `xlg` | entitlement (XLG) resolution |
| `ajo` | Adobe Journey Optimizer integration |
| `mepgeolocation` | enables geo/`countryip` resolution |
| `mep-marketing-decrease` | marketing-decrease consent handling |

So a page whose pill shows personalization active with **no** inline `personalization`
path is usually driven by `personalization-v2` + the spreadsheet/Target, not a bug.

## Target integration performance modes

| setting | speed | behavior |
|---|---|---|
| `on` | slowest | Page can't begin building until the Target response returns; Target controls section-1 changes. |
| `postlcp` | faster | Target controls non-section-1 changes only. |
| `off` | fastest | Target disabled; MEP-native personalization still works. |

Use the MMM **MEP-Target Inactivity Report** to find pages with Target
needlessly `on`.

## The MEP button & `?mep` preview parameter

> For a full "what it does **and how it works**" explanation (panel anatomy,
> how the preview URL is built, how Highlight Changes works, the region/market
> spoofer, MMM integration, and the full URL-param cheat sheet), see
> `mep-button.md`. The summary below is enough for routine QA.

The MEP button is an on-page debug panel. It shows automatically on
localhost/preview/stage when Target or Personalization is enabled; force it
anywhere by appending **`?mep`** to the URL.

What it shows / does:
- Manifest count; whether Target/Personalization are active.
- Geo & locale details for the current view.
- Ordered manifest list: filenames, associated Target activities, available
  experiences; the experience loaded on init is the **pre-selected dropdown
  option** (shown as the bolded active variant).
- **Highlight Changes** toggle — visually flags every element MEP altered.
- **Experience selection** — force a specific experience per manifest from a
  dropdown.
- **Preview** — generates a URL that locks in your selected experiences.
- **Add manifest** — apply a manifest during dev even if metadata doesn't
  enable it.
- `mepButton=off` — hide the button in a preview link while keeping forced
  experiences.

Limitation: it can't show Target activities that are deliberately serving *no*
experience for the current audience.

## QA checklist (interpret / validate a manifest)

Run the **linter** first — it automates most of this checklist (no-op rows,
page-filter regex/backslash typos, `remove` intent inversions, undefined
placeholders, untrusted URLs, consent default). Published `.json`:
`node scripts/lint.mjs <file|URL>` or open `scripts/lint.html`; source `.xlsx`:
`python scripts/lint_manifest.py <file>` (see `references/linting.md`). Then
review the rest by hand:

- **Type & order**: is `manifest-type` right (Personalization vs Promo vs Test)?
  Does execution order match intent? On the page, is the manifest list in the
  intended priority order?
- **Experience priority**: are experience columns ordered most-specific/most-
  important first? Remember users get the **first** matching column only.
- **Selectors**: written against **plain** HTML? Appropriately "goldilocks"?
  Need `#_all` for multiple matches? Need `#_include-fragments` to reach nested
  content? `prepend`/`append` not used on a fragment selector?
- **Page filters**: do the globs actually match the target paths (US vs `**`
  localized, geo alternations)?
- **Actions/values**: `remove` cells set to `TRUE`? `updateAttribute` selectors
  include the attribute name? Fragment values point at a valid fragment **path**?
  (The URL's domain/host is normalized away — don't flag `hlx.page`/`aem.page`/
  `aem.live` or `dc` vs `da-dc` mismatches; see `selectors.md`.)
- **Naming/folders**: filename per `conventions.md` (page name / promo / test id
  / `roc-`)? Analytics name clean?
- **Target**: if any `target-` columns exist, is `target on` set on the page?

## Troubleshooting: "my experience isn't applying"

### Answer format

Follow the **Response style** in `SKILL.md`. Shape a troubleshooting answer as:

1. **Verdict** — one line: the single most likely root cause **and** the fix.
2. **The fix** — the corrected selector / row / value in a code block (so it can
   be copy-pasted).
3. **Why** — 2–3 tight sentences on the mechanism, tied to any "works when X,
   fails when Y" clue the user gave.
4. **Other things to check** — a short **ranked** list (most→least likely); each
   line: **cause** — how to tell / what to do. Include only plausible ones; stop
   there.
5. **Verify** — the concrete `?mep` + Highlight Changes step to confirm.

Keep it skimmable: bold the label on each point, one idea per line, no repeated
explanations. Don't dump the whole causes list below — pick the ones that fit
the symptom.

### Likely causes (the menu to diagnose from)

Work down this list:

1. **Not enabled** — is the manifest listed in `personalization` metadata (and
   `target on` if it uses `target-` columns)? If the values *are* in the page
   source but the MEP pill still says off, check the **block name**: whole-page
   settings must live in a block named exactly **`metadata`**, not
   **`section-metadata`** (the latter only configures its own section, so MEP
   never reads it).
2. **Manifest itself won't load (404 / wrong path)** — the JSON has to resolve at
   the requested URL. Two common traps: the **name isn't a rewrite-allowed
   pattern** (only `<pagename>.json` / `<pagename>-devicetype.json` resolve; other
   names 404 until Target serves them), or it's saved under **`/products/`**,
   which previews but doesn't publish to stage/prod. See `conventions.md`
   → *Placement gotchas* / *Manifest name must be a resolvable path*.
3. **Lost the priority race** — the user matched an earlier experience column,
   or an earlier manifest in the page's list took precedence.
4. **Page filter mismatch** — the current path doesn't match the row's
   `page filter` (common with US vs localized `**` patterns).
5. **Selector miss** — written against the decorated DOM instead of plain HTML,
   too specific, or matched only the first element (needs `#_all`) / didn't
   look inside a fragment (needs `#_include-fragments`).
6. **Audience mismatch** — tag not actually met (e.g. device detected
   differently); re-qualification needs a reload after spoofing.
7. **Missing localized fragment** — on a GEO page, the same-named local fragment
   doesn't exist, so default content shows (expected behavior).
8. **Target not serving** — Target activity is scoped to an audience the current
   user isn't in.
9. **Fragment origin not allowed** — fragment loads must be same-origin,
   configured in `allowedOrigins`, or pass Milo's trusted-URL check. Rejected
   fragment loads are logged. Scripts use the trusted-URL check. Check the URL
   host and the page's configured allowed origins.
10. **Consent gating** — `manifest-consent-type` determines behavior:
   `promo or no offer changes` bypasses gating; `non-personalized offer test`
   requires performance consent and otherwise assigns a persistent randomized
   variant; `personalized offer` requires both performance and advertising
   consent and otherwise forces Default. When absent, the key defaults to
   `personalized offer`, except promo-sourced manifests, which default to
   `promo or no offer changes`. Legacy `manifest-marketing-action` values are
   aliases; see `manifest-schema.md`.
11. **Geo restriction** — a `manifest-country-restriction` list that excludes
   the visitor's country forces the Default variant. For a single row, check
   `country filter` / `country filter optional` instead.

Reach for the `?mep` button's **Highlight Changes** and per-manifest experience
dropdown to confirm what's actually being applied.
