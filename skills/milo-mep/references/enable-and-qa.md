# Enabling MEP & QA / Troubleshooting

## Enabling MEP on a page

MEP is turned on via **page metadata**. Two properties:

| metadata property | value | effect |
|---|---|---|
| `personalization` | manifest path(s), e.g. `/example/smart-tools.json` | Attaches manifest(s). Multiple allowed, comma- or line-break-separated. List order breaks ties only after execution order and type (see below). Low performance cost. |
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

## Priority: MEP vs Target

**Execution Order is checked first, then Type** — for both MEP-native and
Target-delivered manifests. Target is a delivery source, not a higher-priority
manifest type. Don't answer this case only with the order of paths in
`personalization` metadata, or claim that cross-system ordering is undefined:
Target-delivered manifests join MEP's shared manifest sort.

| Compare in this order | Setting in `helix-info` | Earlier / higher priority |
|---|---|---|
| 1. Execution Order | `manifest-execution-order` | `First` → `Normal` → `Last` |
| 2. Type (only if Execution Order ties) | `manifest-type` | `Personalization` → `Promo` → `Test` |
| 3. Both settings tie | Input order | Stable sort preserves incoming order; for metadata-listed manifests, first listed stays first |

For example, if both manifests have `Normal` execution order:

| Delivery source | `manifest-execution-order` | `manifest-type` | Result |
|---|---|---|---|
| MEP / page metadata | `Normal` | `Personalization` | Earlier / higher priority |
| Target | `Normal` | `Promo` | Later / lower priority |

Reverse the delivery sources and the `Personalization` manifest still comes
first. A `First` + `Promo` manifest also comes before a `Normal` +
`Personalization` manifest: execution order takes precedence over type.

**How to change the order:** edit the relevant manifest's **`helix-info`**
sheet (`info` in published JSON). For example, to move an existing Promo ahead
of a Normal Personalization while keeping its type:

```text
key                         value
manifest-execution-order    First
manifest-type               Promo
```

Confirm the other manifest's settings too; `First` does not outrank another
`First` without comparing types. Keep type aligned with the actual use case
(it affects analytics); prefer execution order when changing sequencing.
Reordering the drawer is not the authoring control, and rearranging metadata
paths cannot override different execution-order/type settings.

**Scope:** this is Milo's ordering of manifests, including those delivered by
Target — not a universal priority rule for arbitrary Target scripts or offers
outside the MEP manifest pipeline. Earlier processing is not a guarantee of
the final value for every action: later attribute updates can overwrite earlier
ones, while fragment replacements have first-selector-wins behavior. See
`source-notes.md` for the action-specific details. Within one manifest,
experience columns are a separate rule: leftmost matching column wins.

**Verify:** reload with `?mep` (or append `&mep` to an existing query), inspect
both manifests' settings and selected experiences, and enable **Highlight
Changes** on the conflicting element. The panel's numbered list alone does
not prove that Target has priority or which action ultimately wins.

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
  Compare execution order first, then type, across both MEP-native and
  Target-delivered manifests. Only then check metadata list order for ties.
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
5. **Verify** — the concrete `?mep` + Highlight Changes step and the expected
   observable result: which content, attribute, or experience should change
   on which page. Confirm a broad element selector is unique in authored HTML.

For localization fixes, `#_dnt` belongs on the **replacement fragment URL in
the experience cell**, not the selector identifying the original content:
`/example-shared/fragments/alternate-hero#_dnt`. Use it only for intentionally
unlocalized content. Creating a localized fragment is a proposed fix, not
permission to write or publish shared content.

Keep it skimmable: bold the label on each point, one idea per line, no repeated
explanations. Don't dump the whole causes list below — pick the ones that fit
the symptom.

### Likely causes (the menu to diagnose from)

Work down this list:

**Before diagnosing a production targeting leak:** compare a clean URL with
the reported preview URL. A carried `mep=<manifest>--<experience>` parameter
can explicitly attach/force that manifest on a different page; hiding the
button does not clear it. **Row page/country filters still apply.** The forced
URL alone neither proves nor rules out a production leak; compare normal
delivery before making that judgment. See `mep-button.md` → *A manifest appears on the wrong
page after previewing*. For repeated copy that varies by pathname, use the
page-scoped placeholder rows in `manifest-schema.md` rather than duplicating
fragments or inventing page-specific audience columns.

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
   or another manifest ran earlier by execution order, then type (including
   Target-delivered manifests). Metadata list order only breaks equal-setting
   ties. See *Priority: MEP vs Target* above and verify the conflicting action.
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
