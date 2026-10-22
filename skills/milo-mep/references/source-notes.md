# Ground Truth from Source

Facts verified against the Milo source. Repo:
https://github.com/adobecom/milo/tree/main/libs/features/personalization

**Where to read the source:** prefer a **live local checkout** — it's fresher
than the snapshot. It's commonly at
`~/git/milo/libs/features/personalization/`; otherwise look for any
local `milo` checkout, and only then fall back to the bundled snapshot in
`assets/source/` (`personalization.js`, `promo-utils.js`, `preview.js`, …). The
snapshot exists so the skill works with no checkout, but it can drift from
`main` over time — when it matters, read the live repo.

When the public docs and the source disagree, **the source wins** — it's what
actually runs. The bundled snapshot is pinned in `assets/source/SOURCE_VERSION`;
grep its files (or the live checkout) to confirm edge cases.

## Audience column headers — exact matching logic

An experience column header can be any of these (matched in `hasMatch` /
`matchVariant`):

- **Built-in tags** (`PERSONALIZATION_TAGS`, matched case-insensitively):
  `all`, `chrome`, `firefox`, `safari`, `edge`, `android`, `ios`, `windows`,
  `mac`, `mobile-device`, `phone`, `tablet`, `desktop`, `loggedout`, `loggedin`.
  These are the **only** hardcoded tags. (There is **no** dark/light-mode tag in
  the code, despite older wiki notes.)
- **Entitlement tags** (e.g. `cc-all-apps`, `photoshop`): **not** hardcoded —
  loaded at runtime from the XLG tags sheet
  `https://www.adobe.com/federal/assets/data/mep-xlg-tags.json`. These are the
  "XLG segments." A header only resolves if it appears in that sheet (or in
  `config.consumerEntitlements`).
- **`param-<key>`** / **`param-<key>=<value>`** — URL query param (existence, or
  exact value; case-insensitive).
- **`previouspage-<glob>`** — matches the referrer path (`document.referrer`) via
  the same glob engine as page filters. This is the "came from email / previous
  page" capability.
- **`countryip(US,CA,...)`** — Akamai/edge-detected country (note `uk` is
  internally mapped to `gb`). Requires geolocation to be enabled.
  **Case-insensitive:** headers are lowercased at parse time
  (`normalizeKeys`→`toLowerAlpha`, which `.toLowerCase()`s before stripping) and
  the detected country is lowercased at resolution (`resolveDetectedMarketCountry`
  → `normCountryCode(x.toLowerCase())`), so `countryip(DE)` and `countryip(de)`
  match identically. `matchesCountryIP` then compares the two already-lowercased
  values with `countryList.includes(config.mep.countryIP)`.
- **`lob-<x>`** — line-of-business match from `config.mep.promises`.
- **`registered`** — matches when an event-registration promise is present.
- **`target-<name>`** — an Adobe Target / AJO activity; the name must match the
  Target experience exactly. Requires `target` on.

### Operators (built in `buildVariantInfo` / `matchVariant`)
- **OR** = comma — but a comma **inside parentheses is not a split point**
  (`split(/,(?![^(]*\))/)`), so `countryip(us,ca)` stays intact.
- **AND** = `&`.
- **NOT** = a leading `not ` on a condition.
- **Nickname** = `nickname: audience` — matching uses the part **after** the
  colon; the part before is the analytics label.
- `target-` headers are treated as a single opaque name (no `,`/`&` splitting).

### Priority
`variantNames.find(... matches)` → the **first** (leftmost) matching column wins.
Confirmed leftmost = highest priority.

## Manifest ordering on a page

Manifests are sorted by `executionOrder`, a string `"<execOrderIdx>-<typeIdx>"`:
- `manifest-execution-order`: `First`=0, `Normal`=1, `Last`=2 (primary sort key).
- `manifest-type`: `Personalization`=0, `Promo`=1, `Test`=2 (secondary).
- Missing info → default `"1-1"`.

Only `manifest-type: Personalization` is analytics-tracked
(`TRACKED_MANIFEST_TYPE`). `manifest-override-name`/filename analytics title is
truncated to **15 chars** (docs say "aim for 10").

**How non-Target manifests show up in analytics:** they don't get a dedicated AA
dimension (Target activities do). Instead Milo writes a generic **`daa-lh`** DOM
attribute carrying the manifest name(s) + the experience(s) served on a page hit,
**pipe-separated**, so they're queryable at the page-hit level. Long experience
names should use an **analytics nickname** to stay readable. (Reference: the
"Analytics in Milo" internal wiki.) Practical upshot for authoring: keep the
filename / `manifest-override-name` clean — and **don't change `override-name` on
a PZN manifest unless an analyst asks**; it's an analytics-only field.

## Actions — exact names

- **DOM commands** (`COMMANDS`): `remove`, `replace`, `updateattribute`,
  `analyticifseen`.
- **Insert commands** (`CREATE_CMDS`): `insertbefore` (beforebegin),
  `insertafter` (afterend), `prepend` (afterbegin), `append` (beforeend).
- **Global commands** (`GLOBAL_CMDS`): `insertscript`, `replacepage`,
  `updateframework`, `updatemetadata`, `useblockcode`.
- **`analyticifseen`** fires an analytics beacon when the element scrolls into
  view (IntersectionObserver) — no DOM change.
- **`updateframework`** swaps the Milo foundation stylesheet (value like `c1`,
  `c2`).
- **Legacy normalization** (line ~820): the action is lowercased and the
  substrings `content`, `fragment`, and `tosection` are stripped. So
  `replaceContent`→`replace`, `replaceFragment`→`replace`,
  `removeContent`→`remove`, `insertContentBefore`→`insertbefore`,
  `appendToSection`→`append`, etc.

## Selectors — exact behavior

- **Fragment selector** (starts with `/` or `http`): matched against `<a>` hrefs;
  automatically gets modifiers `#_all` + `#_include-fragments` (so a fragment
  swap hits **every** matching link, across fragments, by default).
- **Fragment URL domains are ignored** (`normalizePath`, lines ~145-161): for a
  known adobecom origin (`.hlx.`/`.aem.`/`.adobe.`/localhost/codeRoot) it returns
  just the pathname (localized unless en-US, `.json`, a locale-prefixed path, or
  `#_dnt`). This applies to fragment **selectors** (line 670) and fragment
  **values** alike (lines 850/870, `normalizeFragPaths` line 1289). Consequence:
  `hlx.page`/`aem.page`/`aem.live` and the repo host (`dc` vs `da-dc`) don't
  affect what serves — the path is fetched against the current page's origin, so
  a preview-looking URL in a published manifest serves the published fragment.
  **Never report mixed or preview fragment domains as an error/opportunity.**
- **Simplified selectors** (`modifySelectorTerm` / `specificSelectors`):
  `section`→`main > div`, `row`/`col`→`> div`, `primary-cta`→`strong a`,
  `secondary-cta`→`em a`, `action-area`→`*:has(> em a, > strong a)`,
  `any-marquee`→`[class*="marquee"]`,
  `any-marquee-section`→`main > div:has([class*="marquee"])`,
  `any-header`→`:is(h1,h2,h3,h4,h5,h6)`.
- A **numeric suffix** (`section3`, `text2`) → `:nth-child(n)` /
  `:nth-child(n of .class)`. `main > sectionN` collapses to `sectionN`. Unknown
  bare words are treated as **class names** (get a leading `.`). Raw HTML tag
  names pass through untouched.
- **`in-block:<blockname> <selector>`** — scopes an action to inside a specific
  block; also the mechanism for MAS (`mas.adobe.com`) fragment overrides.
- **`twp buttons`** — special selector type for free-trial buttons (auto-adds
  include-fragments/all/include-gnav; matches localized "free trial" copy).

### Flags / hash modifiers (parsed by splitting on `#_`, then `_`)
- `#_all` — act on all matches (default is first only, except fragment selectors).
- `#_include-fragments` — search inside fragments.
- `#_include-gnav` — search inside the global nav.
- `#_dnt` — do-not-translate: skip localized-fragment lookup (`normalizePath`).
- `#_inline` — insert fragment content inline (unwrapped).
- `#_href` (and `updateAttribute` `href_<param>`) — operate on a link's `href`:
  `href_#` appends to the href; `href_<param>` sets that query parameter (e.g.
  `href_osi` sets the `osi` param). Bare `#_href` replaces the href.
- Inline fragments normally insert their section contents. When the target has
  `data-mep-replace-type="row"` or `"cell"`, Milo instead extracts the
  corresponding row/cell content from the first fragment section and replaces
  that container. Inline fragment loading only supports one section; later
  sections are ignored.

## Fragment media reuse

When MEP replaces or removes content, it records valid `media_` image URLs from
the removed elements. A subsequently loaded fragment can reuse a recorded URL
when its relative `./media_...` asset has the same origin, media key, and query
string, avoiding a duplicate image fetch. Broken images and malformed or
multi-candidate media references are not reused. See `assets/source/fragment.js`
and `personalization.js`.

## Info sheet keys — full set (`getManifestConfig`)

Beyond `manifest-type` / `manifest-execution-order` / `manifest-override-name`:

- **`manifest-consent-type`** — canonical consent classification:
  - `promo or no offer changes` → bypasses consent gating.
  - `non-personalized offer test` → requires performance consent. Without it,
    Milo assigns a persistent randomized variant; a country-ineligible visitor
    still receives Default.
  - `personalized offer` → requires both performance and advertising consent;
    otherwise Default is forced.
  - Missing key defaults to `personalized offer`, except promo-sourced
    manifests, which default to `promo or no offer changes`.
- **Legacy `manifest-marketing-action` aliases:** `core services`,
  `core services/non-marketing`, and `non-marketing` map to
  `promo or no offer changes`; `marketing decrease` and `marketing increase`
  map to `non-personalized offer test`. They no longer mean independent
  performance-vs-advertising gates.
- **`manifest-country-restriction`** — comma-separated country codes for the
  whole manifest; a visitor outside the list gets Default. Legacy
  `manifest-geo-restriction` is still accepted. Country codes normalize to
  lowercase, `uk` maps to `gb`, and locale-like suffixes normalize to country.
- **Experience-row `country filter` / `country filter optional`** — a
  comma-separated country list can also scope one action row without restricting
  the whole manifest. Country codes use the same normalization.

## Enablement & security

- Enabled via metadata sources in `combineMepSources`: `pzn` (the
  `personalization` metadata), `pzn-roc` (regional/ROC personalization), `promo`,
  the `?mep` param, and `mktg-decrease`. Target/AJO manifests are added
  separately in `init()` (via `callMartech` / `handleMartechTargetInteraction`),
  not in `combineMepSources`.
- Entitlement resolution uses the Alloy event after sign-in. If the page has no
  Server-Timing sign-in hint (for example, on `aem.live`), current Milo `main`
  checks IMS sign-in state before awaiting that event; pages with the hint keep
  the existing path. This avoids leaving the entitlement promise pending on
  hosts that omit the header.
- **`target` metadata** resolves to `true` | `'postlcp'` | off — `postlcp` is the
  faster mode where Target controls only non-LCP (below section 1) changes.
- **Trusted URLs only:** scripts are checked by `isTrustedUrl`; fragment loads
  may also use configured `allowedOrigins`. Otherwise fragments must be
  same-origin or pass `isTrustedUrl` (`*.adobe.com` and supported Adobe
  preview/publish hosts). Rejected fragment loads are logged, not silently
  dropped.
- `href` values of `javascript:`/`data:` are rejected in `updateAttribute`.

## Page-filter glob (`matchGlob`)

`**` → `.*`, then anchored `^…(\.html)?$`, case-insensitive. Full regex syntax
works inside (alternation `(de|fr)`, negative lookahead `(?!de|fr)`). A plain
path matches exactly.

## Promos (`promo-utils.js`)

Promos are scheduled via metadata, not just a manifest reference:
- `manifestnames` (and `<region>_manifestnames`) lists which promos are attached.
- `schedule` (and `<region>_schedule`) holds pipe-delimited entries:
  `name|start|end|manifestPath|locales|cdtStart|cdtEnd` (GMT dates).
- Regions are `APAC`, `EMEA`, `AMERICAS`, `JP` (locale lists in the file).
- A promo is disabled outside its `start`/`end` window or its `locales`.
  `?instant=<date>` overrides "now" for testing.
