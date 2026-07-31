# Adobe MEP Conventions (naming, folders, localization)

These are Adobe-internal conventions for the adobe.com web platform — not in
the public Milo docs. Follow them when **authoring** so manifests are analytics-
clean, discoverable, and localize correctly.

## Universal rules

- **All folders and files lowercase.**
- URLs/filenames use only **lowercase letters, numbers, and dashes**. Avoid
  underscores, capitals, periods, commas, and other special characters.
- The **manifest filename is passed to Analytics** — keep it clean; no dates,
  promo codes, or extra descriptors.

## File naming

| use case | manifest name | example |
|---|---|---|
| Personalization | the **page name** | `photoshop.xlsx`, `creativecloud.xlsx`, `free-trial-download.xlsx` |
| Promo | the **promo name** | `black-friday.xlsx`, `cyber-monday.xlsx`, `cci-allapps.xlsx` |
| Test | the **test id** | `ace0123.xlsx`, `dc0994.xlsx`, `gnav0001.xlsx` |
| Regional customization (ROC) | `roc-` + page name | `roc-photoshop.xlsx`, `roc-acrobat.xlsx` |

Fragment naming:

| use case | fragment name pattern | example |
|---|---|---|
| Personalization | block + segment descriptor | `marquee-edu.docx`, `riverflow-returnvisitor.docx` |
| Test | pagename + block + descriptor | `photoshop-marquee-newcopy`, `illustrator-riverflow-newimages` |
| ROC | section + `-dotcom-` + Jira id | `sectionname-dotcom-<jira-id>.doc` |

(Personalization/ROC fragments don't repeat the page name — the folder already
scopes them.)

### Manifest name must be a resolvable path (or it 404s in preview)

The `?mep` / metadata loader only resolves manifest names that the site's
path-mapping rewrites allow — in practice **`<pagename>.json`** and
**`<pagename>-devicetype.json`**. An arbitrary name like
`photoshop-target-pzn.json` **404s** when loaded directly (e.g. pasted into the
MEP button in incognito) until an experience actually qualifies and Target
delivers the JSON. This is a platform/ops-owned data-governance guardrail, not a
bug — a genuinely new name pattern requires a rewrite request. When authoring,
stick to `<pagename>.json` / `<pagename>-devicetype.json` unless you've confirmed
a rewrite exists.

## Folder organization

**A/B tests** — manifest + fragments together under the shared `tests` folder,
split by year then quarter:
```
/cc/www/cc-shared/fragments/tests/   (CC)
/dc/dc-shared/fragments/tests/       (DC)
/bacom/fragments/tests/              (BACOM)
/homepage/homepage/fragments/loggedout/tests/
    tests/2024/q1/<test-id>.xlsx + fragments
```

**Promos** — each promo gets its own folder holding its manifest + a `fragments`
folder:
```
/cc/www/promos/[geo]/[name-of-promo]/
/dc/dc-shared/fragments/promos/
    promos/[geo]/black-friday/black-friday.xlsx + fragments/
```
Promo manifests are **reused year to year** — old ones aren't archived.

**Test / demo promos — keep them out of the production promo sheet.** The prod
schedule lives in `promotions[-<region>].xlsx`; experimental rows belong in a
**separate test `promotions.xlsx` under `/www/drafts/promos`** (created for
experiments, works like the real one). **Do not publish that test sheet** —
publishing it can accidentally affect the real production page. For a **demo**,
keep the manifest in **`/drafts/promos/`**, stay on the **`.page`** (preview)
environment, and **preview only**. The "for real" production activation manifests
live in **`/cc-shared/fragments/promos`** (split per region). Before editing the
shared prod sheet, check its version history and ping prior editors.

**Single-page personalization** — the manifest lives **in the page's folder**,
named after the page (`photoshop.xlsx`). Personalization fragments live where
that page's default fragments live.

**Regional customization (ROC)** — under
`<geo>/cc-shared/fragments/roc/mep/<pagename>/`, mirroring the live URL
hierarchy; manifest named `roc-<pagename>.xlsx`, fragments in the same folder.
e.g. AU Photoshop → `au/cc-shared/fragments/roc/mep/photoshop/roc-photoshop.xlsx`.

### Placement gotchas (where a manifest will/won't publish)

The **manifest's folder doesn't affect whether it applies** — a page loads
whatever path its metadata lists, wherever it lives (same-folder-as-the-page is a
tidiness suggestion, not a requirement). `/fragments` and `cc-shared` subfolders
are always safe. But two placements bite:

- **`/products/` has no directory-level rewrite.** A manifest saved under
  `/products/` **previews fine but can't publish to stage/prod** (you'll see it
  work on the `aem.page` URL but not on `stage.adobe.com`). Workaround: keep it in
  a **`cc-shared`** subfolder while testing, then move it to `/products/` only
  when a per-file rewrite is in place. (Same applies to geo-specific manifests
  like `/in/products/in-premiere.json` — they must sit at a production-mapped
  path to work live.)
- **Don't put manifests at the repo root.** Root-level placement has broken stage
  setups; keep them under a real folder.
- **Fragments** (not manifests) **must not live in `drafts/`** if they're needed
  in production.
- **The manifest `.json` must actually resolve at the environment you're
  testing.** MEP fetches the published JSON, so a manifest that only exists on
  `aem.page` (preview) or isn't mapped to a stage path **404s on stage/prod** and
  simply doesn't apply — a frequent "works in preview, nothing on stage" cause.
  For geo QA without a real IP, spoof with the MEP button's region/market
  selector (`?akamaiLocale=<cc>`), but note the manifest itself still has to be
  reachable at that environment.

## Localization

- Manifests are **not localized.** A localized GEO page reuses the **US
  manifest**. Milo automatically looks for a **local fragment of the same name**
  as the US fragment.
- If the local fragment **doesn't exist**, the page shows the **default**
  (unpersonalized) content — nothing breaks.
- To deliberately **skip** localized lookup (one fragment shared across geos),
  use placeholders or the `#_dnt` anchor.

## Manifest priority on a page

When a page lists **multiple** manifests in its `personalization` metadata,
priority follows the **order the URLs are listed — top = highest**.

## Team & support

MEP is owned by the adobe.com web-platform / MarTech team. Route questions, bugs,
and enhancement ideas to your team's MEP support channel — the
support-and-troubleshooting channel for manifests, selectors, geo/device scoping,
Target coordination, and preview/stage/live validation.
