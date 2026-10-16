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
| `manifest-type` | `Personalization` \| `Promo` \| `Test` | Controls analytics inclusion, and is the **tie-breaker** in ordering. Only `Personalization` is analytics-tracked (`Promo`/`Test` are excluded). When execution-order is equal (the common case), manifests run `Personalization` → `Promo` → `Test`. |
| `manifest-execution-order` | `First` \| `Normal` \| `Last` | The **primary** sort key across all manifests on the page: `First` runs before everything and `Last` after everything **regardless of type**; `Normal` sits in between, after which `manifest-type` breaks ties. (Source sorts on `"<execOrderIdx>-<typeIdx>"` — see `source-notes.md`.) |
| `manifest-override-name` | short string | Overrides the filename as the analytics name. Aim for ≤10 chars (runtime truncates to 15). Personalization manifests only. **Don't set/change it unless an analyst asks** — it's analytics-only, not arbitrary. |
| `manifest-consent-type` | `promo or no offer changes` \| `non-personalized offer test` \| `personalized offer` | Canonical consent behavior. Promo/no-offer-change manifests bypass consent; non-personalized offer tests need performance consent; personalized offers need both performance and advertising consent. See `source-notes.md`. |
| `manifest-country-restriction` | comma-separated country codes | Restricts the whole manifest; a visitor outside the list receives the **Default** variant. |

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

- Nested placeholders are supported.
- Manifest-specific placeholders override global placeholders **only** for users
  who qualify for the manifest's experiences.
- Analytics resolution priority for a placeholder column: `en-us` > `us` > `en`
  > `key`.

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
