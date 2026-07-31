# MEP Concepts (depth for explaining)

Background for answering "how does MEP work / what is X" questions precisely.

## Glossary

- **Milo** — Adobe's authoring system for adobe.com pages (Word/Google Docs and
  tables → EDS/Helix pages).
- **EDS / Helix / DA** — the document-authoring + edge delivery stack. Manifests
  authored in Excel publish to JSON via EDS. `.aem.page` = preview (auth
  required), `.aem.live` = published (public).
- **MEP** — Milo Experiments and Personalization: runtime page modification
  driven by a manifest, without editing the source page.
- **Manifest** — the Excel workbook (published to JSON) describing the changes.
- **Experience** — one column in the `experiences` sheet; an audience + the
  content they get.
- **Fragment** — a reusable content document swapped in by an action.
- **Adobe Target** — Adobe's testing/personalization engine; MEP integrates with
  it for A/B tests and audience (AAM/Target) segments.
- **Feds Object** — the front-end data object MEP/Target read for context.
- **MMM** — the **Mep Manifest Manager**: the reporting/QA side (the manifest
  list panel, plus inactivity and metadata-lookup reports).

## How MEP runs (lifecycle)

1. Author builds a Milo page (Word/Docs + blocks).
2. Author builds a **manifest** in Excel; EDS publishes it to JSON.
3. The manifest is attached to a page via `personalization` metadata (and
   `target on` if Target is used), or via promo/metadata spreadsheets.
4. At runtime Milo parses the manifest, determines which experience column the
   user qualifies for (priority order), and applies each row's action to the
   matching selector — content replace, fragment swap, element insert/remove,
   attribute/metadata update, etc.

## Why MEP exists (objectives)

- **Unify** testing and personalization, replacing legacy TOUT and DXF /
  Dynamic Experience Fragments (Dexter) approaches.
- **Keep advanced capabilities** — Target refinements, multi-activity support.
- **Integrate into Milo** for faster production rollout and better performance
  than the old CMS flows.

## MEP-native vs Target-dependent (the key mental model)

- **MEP-native, effectively free**: browser, OS, device, locale/geo, URL params,
  promo scheduling. Read from the request/UA at load with no external call —
  negligible perf impact.
- **MEP-native but render-blocking**: **login state (`loggedin`/`loggedout`) and
  entitlements**. No Target, but Milo must **load IMS and resolve the user's
  sign-in/entitlement state before it can render** the personalized region — so
  these *do* carry a real performance cost (added to LCP), unlike the group
  above. Don't describe a logged-in experience as "free."
- **Target-dependent** (requires `target on`, blocks page build): A/B tests and
  AAM/Target audience segments.

This split drives most performance and QA advice: don't turn Target `on` unless
a feature genuinely needs it — and remember login/entitlement gating isn't free
either.

### Logged-in element visibility (granularity)

You *can* gate a `remove` of a single element (e.g. one marquee CTA) to a
`loggedin` column — element-level removal works. But **changing** part of a
component for logged-in users is best done by swapping the **whole component as a
variant fragment** (author the full marquee with the one change, `replace` it for
`loggedin`), because that's how login-gated content is reliably delivered.
Either way, the IMS render-blocking cost above applies.

## Use cases

- **Personalization** — audience-tailored content (device, geo, login, etc.).
- **Promotions** — time-boxed offers; reused year to year. Scheduled via the
  merch team's **promo spreadsheet** (with start/end times), not per-page
  `personalization` metadata — follow Milo's create-promo → schedule-promo →
  validate-promo docs. A scheduled-promo manifest needs its experience/variation
  named **`all`**. If the launch/takedown automation fails, the fallback is to
  publish the manifest manually like a normal personalization.
- **A/B testing** — measured experiments, usually via Target.
- **Regional customization (ROC)** — geo-specific page tweaks (`roc-` manifests).
