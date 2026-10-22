# The MEP Button (Preview Panel)

The MEP button is MEP's on-page debug/preview tool. The current MEP Next panel
is the default; source is `assets/source/mep-next.js`, with URL assembly in
`mep-overlay-logic.js` and country/IP spoofing in `spoof-country-ip.js`.
`preview.js` (+ `preview.css`) remains the legacy panel selected by
`?mepnext=off`. The detailed legacy implementation notes below remain useful
because the controls and URL behavior overlap; use the current source when
confirming UI differences.

## When it appears

Preview mode is `config.mep.preview`, true when **`mepButton !== 'off'`** AND any
of:
- the environment is **not prod** (localhost/preview/stage), or
- the URL has a **`?mep`** param (even empty `?mep`), or
- `mepButton` is explicitly set.

So: it shows automatically off-prod when Target or Personalization is enabled,
and you force it on **any** environment (incl. prod) by appending **`?mep`**.
Hide it with **`mepButton=off`** (preview overrides still apply).

## Anatomy

The current MEP Next UI is a floating button (`.mep-fab`) that opens the
`#mep-drawer`, with **Actions** and **Summary** tabs. Actions include highlight
toggles, preview-link/manifest-parameter/manifest-manager controls, country
spoofing, and loading a manifest. Its Summary shows page consent, Lingo, M@S,
and CaaS information. Most action controls require authentication.

The legacy panel renders as a **popover pill** — "`N Manifest(s) found`" —
pinned bottom-left. Clicking it toggles `.mep-preview-overlay`. The legacy
panel is built from `parseMepConfig()`, which reads `config.mep` and the page:

**Legacy page-level info** (`parseMepConfig().page`):
- `target` — value of the `target` metadata (`on`/`postlcp`/`off`).
- `personalization` — `on` if `personalization` metadata is present, else `off`.
- `geo` (locale prefix, blank for `en-us`), `locale` (ietf), `region`.
- `highlight` — whether highlight mode is active.

**Legacy per-manifest list** (`getManifestListDomAndParameter()`), each row shows:
- Ordinal + filename, linked to the manifest to **open/edit** it.
- Target activity name (if any).
- **Selected experience** — the variant chosen on load, shown as the pre-selected
  dropdown option (bolded active variant), or "default (control)" if none matched.
- `source` (pzn / pzn-roc / promo / target / mep param), `Consent req`
  (`consentType`), and `Allowed User Countries` (`countryRestriction`) when set.
- For promos: `Active?` (active/inactive) and the `On`/`Off` event window, with an
  **`?instant=<iso>`** link to simulate that moment in time.
- `Last Seen` (from the MMM data API) when available.
- An **experience `<select>` dropdown**: `None (Don't add manifest)` /
  `Default (control)` / each variant name.

## Region / locale preview

Region/market spoofing is **delivery-side, not a DA feature** — so it's not a DA
product request. The MEP Next region/market control writes
**`?akamaiLocale=<cc>`** for Milo's geo resolution and, for supported countries,
**`mboxOverride.browserIp=<ip>`** so Adobe Target's IP-based geo-fencing uses
the same country. This drives `countryip(...)` audiences and market-priced
commerce; you can change the control and preview the effect. Delivery code can
tell it's running inside **DA's live preview** by checking for the
**`?dapreview=on`** query parameter. Note: making DA itself switch the editor to
a different locale was discouraged — it breaks the live-preview model (the
editor is still editing the underlying page, not the spoofed locale). To simply
jump to a page's counterpart in another locale, the existing **`Locales` plugin**
already does that.

## How the Preview URL is built (current MEP Next)

The current `mep-overlay-logic.js` rebuilds the href on the drawer's **Preview**
button (`.mep-footer a.con-button`) when controls change:

1. Collects every selected `<option>` and text input. For each manifest it
   serializes `"<manifestPath>--<variant>"`; a newly typed manifest path is added
   as just its path.
2. Joins them with `---` and sets **`?mep=<manifestPath>--<variant>---<path2>--<variant2>…`**
   on a copy of the page URL.
3. Folds the toggles into query params (and mirrors highlight flags onto
   `document.body` datasets so the current page updates live). The **Manifest
   Parameters** toggle removes the forced manifest list but keeps a bare `?mep`
   in the preview URL, so the MEP button remains available without applying
   manifest parameters. Its choice persists in `sessionStorage` until the tab
   closes.

| Checkbox | URL param | body dataset |
|---|---|---|
| Highlight changes | `mepHighlight=true` | `data-mep-highlight` |
| Highlight fragments | `mepFragments=true` | `data-mep-fragments` |
| CaaS highlight | `mepCaasHighlight=true` | `data-mep-caas-highlight` |
| MAS highlight | `mepMasHighlight=true` | `data-mep-mas-highlight` |
| Turn off preview button | `mepButton=off` | — |
| Manifest Parameters | bare `mep` (no manifest values) | — |
| Region/market spoofer | `akamaiLocale=<code>` and, for supported countries, `mboxOverride.browserIp=<ip>` (+ `mepMasMarket=true`) | — |

Clicking **Preview** navigates to that URL, so the chosen experiences and
toggles are locked in (and shareable). `?mep=off` turns off the `?mep`
experience overrides (in the bundled source it skips injecting mep-param
manifests; a broader "disable MEP for QA" gate, if any, is applied upstream of
this module).

The reverse direction is `parseMepParam()` in `personalization.js`: it splits
`?mep` on `---` then `--` into `{ manifestPath: variant }` and stores it as
`config.mep.variantOverride`, which `getPersonalizationVariant` honors before any
audience matching — that's how a forced experience wins.

## How "Highlight Changes" works

MEP tags every element it changes as it applies commands. `addIds` (in
`personalization.js`) sets the data attributes — `data-manifest-id` /
`data-manifest-display` (`"<manifestId>: <path>"`) and, for Target,
`data-adobe-target-testid` — while the command handlers add the CSS classes
(`createFrag`/`createContent`): a `replace` adds **both** `p13n-replaced` and
`p13n-deleted`, a `remove` adds `p13n-deleted`. **These tags are only written in
preview mode**
(`if (!config.mep?.preview) manifestId = false`), so a plain prod page has
nothing to highlight. Turning on highlight sets `body[data-mep-highlight='true']`,
and `preview.css` scopes all its rules under that flag — so one attribute lights
up (or clears) every tagged element at once, with **no re-render**, which is why
it's instant.

### Color coding & badges (from `preview.css`)

Each change type gets a distinct dashed outline color and a `::before` badge:

| Attribute on the element | Outline color | Badge label | Meaning |
|---|---|---|---|
| `data-manifest-id` | teal `#17a2b8` | `data-manifest-display` (e.g. `1: /path`), prefixed `🔗 ` if it's a fragment | content changed/inserted/replaced by a manifest |
| `data-code-manifest-id` | purple `#6626ef` | `code: <id>` | change applied by block code (`useBlockCode`) |
| `data-removed-manifest-id` | red `#ef3726` | `removed: <id>` | content a manifest removed |
| `data-mep-lingo-roc` | green `#28a745` | `🔗 mep-lingo: <val>` | localized (ROC) result |
| `data-mep-lingo-fallback` | amber `#ffc107` | `🔗 fallback: <val>` | localization fell back to default |
| `data-fragment-default` (via the separate `mepFragments` toggle) | gray `#6c757d` | `🔗 fragment: <display>` | default fragment location |
| `main[data-manifest-id]` | teal | `page: <id>` | whole-page `replacePage` |

Notable behavior: **removed content is hidden normally but revealed while
highlight is on** (`body:not([data-mep-highlight='true']) [data-removed-manifest-id]
{ display: none }`), so you can see what a manifest took away, outlined in red.

### The sibling highlighters

Several toggles reuse the same body-flag + CSS pattern, each with its own flag:
`Highlight fragments` (`data-mep-fragments`), `CaaS highlight`
(`data-mep-caas-highlight`), and `M@S highlight` (`data-mep-mas-highlight`). The
CaaS and M@S ones additionally inject clickable **badges** via MutationObservers:
- **CaaS** (`data-caas-block`) → "Edit in CaaS Configurator"; per-card a
  `🔗 caas-market:` (green) or `🔗 caas-lang:` (amber) badge.
- **MAS / merch** (`data-mas-block`, `<merch-card>`, `[data-wcs-osi]`) → "Edit
  Collection in M@S Studio" (collection badge) / "Edit Card" (card action),
  "View in OST", and "Copy Fragment ID", plus a market chip flagging
  card-vs-page market **mismatches**.

## Region / market spoofer

Dropdowns write **`?akamaiLocale=<code>`** to simulate Milo's detected country
(for `countryip(...)` audiences and market-priced commerce). For supported
countries, the preview also writes **`mboxOverride.browserIp=<ip>`** so Target
uses the same country for IP-based geo-fencing. A Lingo region select simulates
localization region. M@S market spoofing adds `mepMasMarket=true` to persist
across reloads.

## Shared with the MMM report

`preview.js` also powers the **MMM** report (a table of pages and the manifests
seen on them). It calls a data API (`API_URLS`: `get-pages`, `get-page`,
`save-mep-call`, `get-report`); `saveToMmm()` records each preview visit, which
is where the panel's **Last Seen** values and the MEP-Target inactivity data come
from.

## URL parameter cheat sheet

| param | effect |
|---|---|
| `?mep` | force the button/preview mode on; with no value, no manifest overrides are forced |
| `?mep=off` | turn off the `?mep` experience overrides |
| `?mep=<path>--<variant>---…` | force specific experiences per manifest |
| `mepButton=off` | hide the button (overrides still apply) |
| `mepHighlight=true` | outline changed elements |
| `mepFragments=true` | highlight default fragment locations |
| `mepCaasHighlight=true` | show CaaS edit badges |
| `mepMasHighlight=true` | show M@S/commerce edit badges + market chips |
| `akamaiLocale=<code>` | spoof Milo's detected country/market |
| `mboxOverride.browserIp=<ip>` | align Target's IP-based geo-fencing with the spoofed country |
| `mepMasMarket=true` | persist the M@S market spoof across reloads |
| `?instant=<iso-date>` | simulate "now" (for promo scheduling windows) |

## Limitations

The panel lists manifests/Target activities actually being **served**; it cannot
show a Target activity that is deliberately serving **no** experience to the
current audience.
