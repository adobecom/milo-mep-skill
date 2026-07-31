# Personalization Tags, Operators & Page Filters

Each **experience column header** in the `experiences` sheet is built from
personalization tags (or a Target activity name). This file lists the tags, how
to combine them, the `param-`/`target-` prefixes, and the `page filter` syntax.

## Built-in tags

These are the **only** hardcoded tags (`PERSONALIZATION_TAGS` in the source),
matched case-insensitively:

**Browsers**: `Chrome`, `Firefox`, `Safari`, `Edge`

**Operating systems**: `Android`, `iOS`, `Windows`, `Mac`

**Device types**: `Mobile-Device`, `Phone`, `Tablet`, `Desktop`

**Login status**: `Loggedout`, `Loggedin`

**Misc**: `All` (everyone)

**Exact device definitions** (source: `PERSONALIZATION_TAGS` + `PHONE_SIZE`):
`PHONE_SIZE = window.screen.width < 550 || window.screen.height < 550` — note it
reads **`window.screen`** (the physical screen), **not** `window.innerWidth`. So:
`phone` = mobile-device UA **and** `PHONE_SIZE`; `tablet` = mobile-device **and
not** `PHONE_SIZE`; `desktop` = **not** mobile-device. Consequences worth knowing:
a true desktop can never be `phone` (mobile-device is false), and because it's
evaluated **once at page load** off physical screen size, **resizing or zooming
the browser after load does not re-trigger** device matching (need a reload).
Don't claim page-zoom shrinks `screen.width` — it's physical.

Tags are matched at page load. Spoofing the browser/device requires a reload to
re-qualify. (There is **no** dark/light-mode tag in the code, despite older wiki
notes — don't promise it.)

## Entitlement tags (XLG segments)

Entitlements like `CC-All-Apps`, `Photoshop`, `Illustrator` are **not**
hardcoded — they're loaded at runtime from the XLG tags sheet
(`mep-xlg-tags.json`). A header only resolves if it exists in that sheet (or in
`config.consumerEntitlements`). Treat the exact set as data-driven, not fixed.

### Requesting a new tag / segment (intake process)

Getting a new entitlement/segment tag is a **two-step** process, and step 1 is
the real work:

1. **Request the segment** so the source team starts *sending* it to MEP — not
   every possible segment is piped in, only ones that have been requested. File
   a Jira intake request with the team that pipes segments to MEP, **one ticket
   per segment**.
2. **Add it to the tag list** (trivial). The list currently lives in a JS file
   that needs a PR to update (there's a plan to move it to a spreadsheet, which
   only eases step 2 — step 1 is still required).

So a manifest header referencing a not-yet-piped segment won't resolve until the
request lands. Route questions through your team's MEP support channel.

## Prefixed / special experience headers

- **`param-`** — URL query parameter. `param-<key>` matches when the key is
  present; `param-<key>=<value>` matches an exact value. Examples:
  `param-remove`, `param-remove=true`, `param-promocode=back2school`,
  `param-view=demo`.
- **`previouspage-<glob>`** — matches the **referrer** path (where the visitor
  came from) using the same glob engine as page filters. Powers "came from
  email / previous page" targeting.
- **`countryip(US,CA,...)`** — Akamai/edge-detected country (note `uk` maps to
  `gb` internally). Requires geolocation enabled.
- **`lob-<x>`** — line-of-business match; **`registered`** — matches when an
  event-registration is present.
- **`target-`** — an Adobe Target/AJO activity/experience. The header must
  **exactly match** the Target experience name. Requires `target` on. Example:
  `target-example-promo`. (Not split on `,`/`&` — treated as one opaque name.)

For the exact matching logic see `source-notes.md`.

## Operators (combine tags in one header)

- **`,`** (OR) — any listed condition qualifies. `Chrome, Firefox`. A comma
  **inside parentheses does not split** (so `countryip(us,ca)` stays intact).
- **`&`** (AND) — all conditions must hold. `Loggedin & Photoshop`.
- **`not`** — exclude (leading `not ` on a condition). `not Safari`.

## Analytics nickname

Give an experience a clean analytics label with `nickname: tag-name`
(the part before the colon is the analytics name).

## Priority & qualification

- Columns are ordered **highest priority (leftmost) → lowest**.
- A user qualifies for the **first** column whose header they match; the rest
  are ignored for that user.
- Control/holdout columns are unnecessary if an experience makes no changes —
  just leave it out.

## Page filter syntax

The `page filter (optional)` column restricts a row to matching page paths.
Blank = every page the manifest runs on. Glob/regex-ish patterns:

| pattern | matches |
|---|---|
| `/products/photoshop` | exactly that path (US) |
| `**/products/photoshop` | that page in **all** locales |
| `/**/**/products/photoshop` | localized versions but **not** the US exact path |
| `/fr/**` | all French pages |
| `**/products/**/pricing` | pricing pages across products & geos |
| `/(de\|fr\|uk)/products/photoshop` | only those geos |
| `/(?!de\|fr\|uk)**/products/photoshop` | all geos **except** those |

Example combining many geos:
`/(ca|au|hk_en|id_en|in|my_en|nz|ph_en|sg|th_en|vn_en|...)/example/smart-tools`

## MEP-native vs Target-dependent

No Target required, effectively free: browser, OS, device, locale/geo, URL
params, promo scheduling.

No Target required but **render-blocking**: **login state
(`loggedin`/`loggedout`) and entitlements** — Milo must load IMS and resolve
sign-in/entitlement before rendering, so these add to LCP even though no Target
is involved. Don't call a logged-in experience "free."

Target required (`target on`, slower — blocks page build): A/B tests and
AAM/Target audience segments.
