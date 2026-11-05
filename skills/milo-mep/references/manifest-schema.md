# MEP Manifest Schema

An MEP manifest is a multi-sheet Excel workbook stored in SharePoint/DA and
published to JSON by EDS. This file documents the exact sheets, columns,
accepted values, and the published JSON shape.

## Contents
- [Sheets overview](#sheets-overview)
- [`info` sheet](#info-sheet)
- [`experiences` sheet](#experiences-sheet)
- [`placeholders` sheet](#placeholders-sheet)
- [Published JSON shape](#published-json-shape)

## Sheets overview

Excel tab names carry a `helix-` prefix; the published JSON drops it.

| Excel tab | Published JSON key | Purpose | Published? |
|---|---|---|---|
| `helix-info` | `info` | Manifest-level settings | Yes |
| `helix-experiences` | `experiences` | The changes (one per row) | Yes |
| `helix-placeholders` | `placeholders` | Key/value substitutions | Yes |
| `readme` | — | Color-coding & notes | No (informational) |

## `info` sheet

Two columns, `key` and `value`. Supported keys:

| key | values | meaning |
|---|---|---|
| `manifest-type` | `Personalization` \| `Promo` \| `Test` (exact case for ordering; an unrecognized value such as `personalization` sorts as `Promo`) | Controls analytics inclusion, and is the **tie-breaker** in ordering. Only `Personalization` is analytics-tracked (`Promo`/`Test` are excluded). When execution-order is equal (the common case), manifests run `Personalization` → `Promo` → `Test`. |
| `manifest-execution-order` | `First` \| `Normal` \| `Last` (exact case) | The **primary** sort key across all manifests on the page: `First` runs before everything and `Last` after everything **regardless of type**; `Normal` sits in between, after which `manifest-type` breaks ties. (Source sorts on `"<execOrderIdx>-<typeIdx>"` — see `source-notes.md`.) |
| `manifest-override-name` | short string | Overrides the filename as the analytics name. Aim for ≤10 chars (runtime truncates to 15). Personalization manifests only. **Don't set/change it unless an analyst asks** — it's analytics-only, not arbitrary. |
| `manifest-consent-type` | `promo or no offer changes` \| `non-personalized offer test` \| `personalized offer` | Canonical consent behavior. Promo/no-offer-change manifests bypass consent; non-personalized offer tests need performance consent; personalized offers need both performance and advertising consent. See `source-notes.md`. |
| `manifest-country-restriction` | comma-separated country codes | Restricts the whole manifest; a visitor outside the list receives the **Default** variant. |

**MEP vs Target:** these same ordering keys apply to Target-delivered manifests;
delivery source does not confer priority. Set them in `helix-info`. When both
keys tie, the stable sort keeps input order (metadata URL order for manifests
listed there). See `enable-and-qa.md` → *Priority: MEP vs Target* for examples.

Legacy aliases are still accepted: `manifest-marketing-action` maps `core
services`, `core services/non-marketing`, and `non-marketing` to
`promo or no offer changes`; `marketing decrease` and `marketing increase`
map to `non-personalized offer test`. If neither consent key is set, the
default is `personalized offer`, except promo-sourced manifests default to
`promo or no offer changes`. `manifest-geo-restriction` remains an alias for
`manifest-country-restriction`.

## `experiences` sheet

The core sheet. Each **row** is one action applied to the page. Columns fall
into two groups.

### Informational columns (always present, leftmost)

| column | required | meaning |
|---|---|---|
| `action` | yes | What to do — see `actions.md`. Chosen from a dropdown in the template. |
| `selector` | depends on action | Where on the page — a CSS selector, a simplified selector, a fragment URL, or empty. See `selectors.md`. For `updateAttribute` the attribute name is appended to the selector. |
| `page filter (optional)` | no | Restricts the row to matching page paths. Blank = applies everywhere the manifest runs. See page-filter syntax in `personalization-tags.md`. |
| `country filter` or `country filter optional` | no | Restricts the row to the listed comma-separated visitor country codes. Blank = no country restriction. |

The published JSON keys are literally `page filter (optional)` and
`country filter` / `country filter optional`.

### Experience columns (one per experience, ordered by priority)

Every column **after** the informational columns is an **experience**. Its
**header** is a personalization tag, a combination of tags, or a Target
activity name. The **cell** in each row holds the value for that action under
that experience (e.g. a fragment URL to replace with, `TRUE` for a remove, a
new attribute value, or blank = no change for this experience).

- Columns are ordered **highest priority (leftmost) to lowest**. A user
  qualifies for the **first** column whose header they match; other columns are
  ignored for that user.
- A blank cell means "this experience makes no change for this row."
  It does **not** inherit the cell from `all` or any later experience.
  Selection is once per manifest, not once per row. Adding a Firefox column
  before `all` and blanking unrelated rows therefore drops those `all` actions
  for Firefox visitors. Preserve applicable existing row values when extending
  a manifest. Do not copy `all` blindly if more-specific audiences also apply:
  inspect their combinations, or put the new isolated change in a separate
  manifest and preserve the existing metadata list. For that separate manifest,
  explicitly check other loaded manifests for overlapping selectors/actions
  and page/country filters; execution/type ordering can affect conflicts.
  State this check in the proposed fix, then verify both the new change and
  previously applicable unrelated changes for the affected audience.
  Do not append "or add this row to an existing manifest" unless you have
  inspected and explained its audience order and preserved row values.
- Headers can combine tags with operators (`,` = OR, `&` = AND, `not`), carry a
  `param-` or `target-` prefix, or use an analytics nickname (`nickname: tag`).
  Full tag/operator reference in `personalization-tags.md`.

Example header set, left to right by priority:
`target-example-promo`, `param-view=tour`, `param-view=demo`,
`param-view=trial`, `desktop`, `tablet`, `Phone`.

## `placeholders` sheet

Key/value pairs used for copy substitution and localization. Any text on the
page (or in a fragment) wrapped in double curly braces `{{key}}` is replaced by
the matching value.

| column | required | meaning |
|---|---|---|
| `key` | yes | The placeholder name used as `{{key}}`. |
| `value` | yes (default column) | Default replacement text. A column named `other` is also recognized as a fallback. |
| *(additional columns)* | no | Locale-/experience-specific overrides. Column headers may be experience names (matching `experiences` headers), geo folder codes (`fr`, `de`), page locale (`en-CA`, `fr-CA`), page language (`en`, `fr`), page country (`US`, `CA`), or `countryip(<code>)`. |
| `page filter` or `page filter (optional)` | no | Restricts a placeholder row to a page pathname, using the same `matchGlob` syntax as experience page filters. Blank matches every page using the manifest. |

- Nested placeholders are supported.
- Manifest-specific placeholders override global placeholders **only** for users
  who qualify for the manifest's experiences.
- Analytics resolution priority for a placeholder column: `en-us` > `us` > `en`
  > `key`.

### Page-scoped placeholder values

**One shared fragment can have different copy on different pages.** Add a
`page filter` column to `helix-placeholders`, repeat the placeholder key with
page-specific values, and place a blank-filter fallback **last**:

| key | page filter | value |
|---|---|---|
| hero-copy | /example/tool-a | Copy for tool A |
| hero-copy | /example/tool-b | Copy for tool B |
| hero-copy | | General tool copy |

Use `{{hero-copy}}` in the shared content. An exact filter matches that path
(and its `.html` form); use `**/example/tool-a` only if all locale prefixes
should share the same copy. No new fragment or experience column is needed
for each page. The manifest must still be loaded and a non-default experience
selected; a `default` experience does not apply its placeholder overrides.

`parsePlaceholders` keeps the **first matching row per key**. A nonmatching
row does not consume the key, but a matching blank value does: it does not
fall through to a later row. Put scoped rows before unscoped fallbacks.
The value column is also chosen in **sheet column order**: the first header
matching the selected experience, locale/country, `value`, or `other` is used.
The same column is read for all matching rows; blank cells do not trigger a
per-cell fallback to a later value column.

**The `valueNames` lookup list is not a precedence order.** There is no
automatic "experience, then locale/country, then value, then other" ranking.
For selected experience `phone`, these two sheet layouts give different results:

| sheet column order | row values in that order | selected text |
|---|---|---|
| `key, value, phone` | `hero-copy, General, Phone copy` | `General` |
| `key, phone, value` | `hero-copy, Phone copy, General` | `Phone copy` |

If `phone` is first and its cell is empty, the **stored placeholder value**
is empty, not `General`. That is not a guarantee of empty rendered text:
MEP's `replacePlaceholders` substitutes only truthy values, so it leaves
`{{hero-copy}}` unchanged for an empty stored value. This is the inspected
MEP replacement path, not a claim about every later page placeholder pipeline.
In an answer, label these as **stored value**, **MEP substitution**, and
**final page rendering**; the last requires checking the deployed pipeline.
Do not use a blank placeholder as a reliable way to remove copy; supply the
intended value or propose an appropriate content/removal action.
Row matching is independently **per key**, not one winning row for the sheet.
Verify both page-specific paths and a third fallback path with the intended
non-default experience; check the rendered `{{hero-copy}}` text, not just
whether the manifest appears in the panel.
For a prediction-only question, still finish with this QA step: on the
question's page, select its intended experience and check each predicted key
for each column layout. If a value is empty, compare MEP substitution with the
final decorated page rather than promising that either blank copy or a literal
token must be the final result.

Older advice that placeholders cannot vary by page URL predates this behavior.
Confirm the deployed Milo version if a site does not support these columns.
Source: `parsePlaceholders` and `matchGlob` in `assets/source/personalization.js`.

## Published JSON shape

A published manifest is a multi-sheet JSON. Top-level keys are the sheet names
plus metadata:

```json
{
  "info":        { "total": N, "offset": 0, "limit": N, "data": [ ... ], "columns": ["key","value"] },
  "placeholders":{ "total": N, "offset": 0, "limit": N, "data": [ ... ], "columns": ["key","value"] },
  "experiences": { "total": N, "offset": 0, "limit": N, "data": [ ... ], "columns": [ ... ] },
  ":version": 3,
  ":names": ["info","placeholders","experiences"],
  ":type": "multi-sheet"
}
```

- Each sheet is an object with `total`/`offset`/`limit`, a `columns` array (the
  ordered header names), and a `data` array of row objects keyed by column name.
- Empty cells serialize as `""`.
- The `columns` array for `experiences` preserves **priority order** of the
  experience columns — read it to recover priority from JSON.

See `example-manifest.md` for a full real manifest walked through end to end.
