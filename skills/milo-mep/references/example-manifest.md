# Worked Example: a manifest

This walks through a representative manifest — a fictional `example/smart-tools`
page — so you can see the schema in practice. Raw JSON is in
`assets/example-manifest.json`. (Values are synthetic but the structure mirrors a
real personalization manifest.)

## `info` sheet

```
manifest-type              Personalization
manifest-override-name     (blank)
manifest-execution-order   Normal
manifest-marketing-action  non-marketing
```
→ A Personalization manifest (counts in analytics, runs first), normal ordering,
no analytics-name override, classified non-marketing.

## `experiences` sheet — columns

Priority order (from the JSON `columns` array), left to right:

1. `action`  2. `selector`  3. `page filter (optional)`
4. `target-example-promo` — a Target activity (highest-priority experience)
5. `param-view=tour`
6. `param-view=demo`
7. `param-view=trial`
8. `desktop`  9. `tablet`  10. `Phone`

So an eligible visitor to the Target activity `example-promo` gets that column;
otherwise a `?view=…` URL param picks a variant; otherwise device tags apply.

## Selected rows, read in plain language

- **Row 1** — `replace` `.hero-marquee` on `/example/smart-tools`.
  `tablet` and `Phone` columns point at a `marquee-mobile` fragment; desktop and
  the param/target columns are blank. → On the US page, tablet/phone users get a
  mobile marquee; everyone else keeps the default.
- **Rows 2–3** — same `replace .hero-marquee` mobile swap, but the
  `page filter` lists large geo alternations (`/(ca|au|...)/example/...` and
  `/(de|at|...)/example/...`) so the mobile marquee also applies across those
  locales.
- **Row 4** — `useBlockCode` with blank selector; the param and device columns
  all point to `libs/mep/example-brick-block/brick`. → Loads a custom "brick"
  block.
- **Row 5** — `replace .hero-marquee` on the US page where the `param-view=…`
  columns each point at a different marquee fragment (`tour-marquee`,
  `demo-marquee`, `trial-marquee`). → URL param chooses which hero to show.
- **Rows 6–8** — the same param-driven hero swap constrained to different geo
  groups, with some cells intentionally blank (that variant not offered there).
- **Row 9** — `replace any-marquee` with the `target-example-promo` column
  pointing at a test fragment. → Target activity swaps the marquee.
- **Row 10** — `replace` where the **selector is a fragment URL**
  (`.../promo-banners/example-promo`) and the Target column supplies a
  replacement sticky-banner fragment.
- **Row 11** — `replace` `tabs div:nth-child(2) > div:nth-child(2)
  #_include-fragments` with the Target column value `2`. → Inside a tabs block,
  reach into fragments (`#_include-fragments`) and replace with fragment index 2.

## What this example teaches

- Experience columns mix **Target**, **URL params**, and **device** tags in one
  manifest, ordered by priority.
- The **same visual change** (mobile marquee) is repeated across rows only to
  vary the **page filter** for different geo groups — manifests aren't
  localized, but page filters still scope geo behavior.
- Selectors range from simple (`.hero-marquee`), to simplified (`any-marquee`),
  to a full CSS chain with a flag (`... #_include-fragments`), to a **fragment
  URL as the selector**.
- Blank cells are normal and meaningful: "no change for this experience here."
