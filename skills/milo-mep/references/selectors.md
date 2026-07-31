# MEP Selectors

The `selector` column says *where* on the page an action applies. MEP accepts
standard CSS selectors, Milo **simplified selectors** (shorthand), fragment
URLs, and section IDs — and supports flags.

## The golden rules

1. **Selectors run against plain HTML, before Milo decorates the page.**
   Classes/attributes on the rendered page may differ. Inspect the *source*
   HTML (or view-source / the pre-decoration DOM), not the finished page.
2. **Goldilocks specificity**: be as vague as possible while still selecting
   only what you want. Prefer `any-marquee primary-cta` over a brittle chain
   like `.marquee .row2 .col1 .primary-cta`.
3. **First match by default.** MEP acts on the first matching element unless you
   add `#_all` — it runs `querySelector`, not `querySelectorAll`. If a selector
   legitimately matches several elements (e.g. every "Buy now" CTA in a
   riverflow) and you want them all, either add `#_all` or repeat the row once
   per target.

## Fragments

Select a fragment by pasting its document link into the `selector` column.
Fragment selectors work with `replace`, `insertBefore`, `insertAfter`, and also
`prepend`/`append` (the inserts are positioned relative to the fragment link's
**parent** element). The public docs say `prepend`/`append` don't apply to
fragments; the source does support them, but `insertBefore`/`insertAfter` are
more predictable there — see `actions.md`.

**The domain of a fragment URL doesn't matter** — for both selectors *and*
values, `normalizePath` strips any known adobecom origin (`.hlx.` / `.aem.` /
`.adobe.` / localhost / codeRoot) down to a **path** and resolves it against the
current page's origin. So `hlx.page` vs `aem.page` vs `aem.live`, and even the
repo host (`dc` vs `da-dc`), are all discarded: a "preview"-looking URL in a
published manifest still serves the *published* fragment at that path in
production. **Do not flag mixed/preview fragment domains as a bug** — it's a
no-op at runtime. (Only the path, and localization/`#_dnt`, affect what loads.)

## Section IDs and anchors

Target a section by its id with hash notation: `#my-section-id`. The `#_dnt`
anchor on a fragment opts it out of localized fragment lookup.

## Simplified selectors

Shorthand for common Milo structures. Most accept a numeric suffix
(`section3`, `text2`, `row1`, `col2`).

| simplified | meaning | CSS equivalent |
|---|---|---|
| `section` | direct child of `main` | `main > div` |
| `row` | direct child of a block | `> div` |
| `col` | direct child of a row | `> div` |
| `primary-cta` | link that becomes a solid button | `strong a` |
| `secondary-cta` | link that becomes a hollow button | `em a` |
| `action-area` | parent holding a button | `*:has(> em a, > strong a)` |
| `any-marquee` | any marquee variant | `[class*="marquee"]` |
| `any-marquee-section` | section containing a marquee | `main > div:has([class*="marquee"])` |
| `any-header` | any heading level | `:is(h1,h2,h3,h4,h5,h6)` |

Simplified and raw CSS mix freely: `section3 text2 p:nth-child(3)`.

**A bare block name selects that block.** Any Milo block can be targeted by its
name (the class Milo puts on it): `marquee` (or `.marquee`), `text`, `wayfinder`,
`media`, `aside`, etc. So `wayfinder` replaces the wayfinder block just like
`marquee` replaces the marquee. Use `media4 p` to reach a paragraph inside the
fourth media block. This is the least brittle way to grab a whole block; combine
with a variant/pseudo-id class (see below) when position or layout may change.

### updateAttribute selectors
Append the attribute name to the element selector. If the element is
`#learn-more-blade primary-cta` and you want the href, the selector becomes
`#learn-more-blade primary-cta href`. For a specific href param (OSI code):
`any-marquee primary-cta href_osi`.

## Cheat sheet

| goal | selector |
|---|---|
| any marquee variant | `any-marquee` |
| section containing a marquee | `any-marquee-section` |
| solid button in marquee | `any-marquee primary-cta` |
| hollow button in marquee | `any-marquee secondary-cta` |
| button container | `any-marquee action-area` |
| marquee solid button href | `any-marquee primary-cta href` |
| paragraph after marquee headline | `any-marquee h1 + p` |
| second media block | `media2` |
| last page section | `section:last-child` |

## Flags / modifiers

Append these to a selector (combine as needed; parsed by splitting on `#_`):

- **`#_all`** — act on *all* matches, not just the first.
  Example: `section3 secondary-cta #_all`.
- **`#_include-fragments`** — also search inside fragments, not just the base
  page. Example: `section5 text #_include-fragments`. Write the block token to
  match the block that actually *contains* the target (`text`, `aside`, …), e.g.
  `section5 secondary-cta #_include-fragments` for a hollow button in a fragment.
  **Modals count as fragments**: to change modal content with a CSS/simplified
  selector you must add `#_include-fragments` (behavior since the Nov 2024
  release). Same for nested cross-fragments (XF) and M@S content — a plain CSS
  selector only searches the base page and never reaches the nested fragment.
- **`#_include-gnav`** — also search inside the global nav (gnav), which MEP
  otherwise doesn't scan.
- **`#_dnt`** — (on fragments) do-not-translate: skip localized fragment lookup.
  (Unlike the others, this isn't a parsed selector modifier — it's a hash on the
  fragment URL handled by `normalizePath`.)
- **`#_inline`** — insert the fragment's content inline (unwrapped). Caveat:
  inlined content is spliced in **without re-running block decoration**, so it
  renders as **plain HTML, not a decorated Milo block** (unless it contains a
  nested `/fragments/` link, which re-triggers decoration). If you need the
  swapped-in content to be a fully decorated block, use a **plain (non-inline)
  fragment link** instead — that path wraps it in a `.fragment` div and runs
  `loadArea`/`loadBlock`.
- **`#_href`** — operate on a link's `href` rather than its content. In
  `updateAttribute`, `href_<param>` sets a query parameter (e.g. `href_osi` sets
  `osi`), and `href_#` appends to the href.
- **`#_mep-lingo`** — (on a `/fragments/` link) region-swap for Lingo: at runtime
  Milo prepends the visitor's detected region prefix to the base fragment path and
  loads the regional variant, falling back to the base fragment if none exists.
  Author the **base** path (no hardcoded `/fr/`); the token is stripped from the
  final href. Requires the page to be **Lingo-enabled** (`?langfirst=on` or
  `<meta name="langfirst" content="on">`) — otherwise the flag is ignored (a
  common "not loading" cause). Source: `libs/features/mep/lingo.js`.

Note: a **fragment-URL selector automatically behaves as if `#_all` +
`#_include-fragments` were set** — it swaps every matching link across fragments.

## Scoping to a block: `in-block:`

Prefix a selector with `in-block:<blockname>` to scope the action to inside a
specific block, e.g. `in-block:marquee primary-cta`. This is also the mechanism
for MAS (`mas.adobe.com`) fragment overrides.

**Global nav / LocalNav (`in-block:global`).** To personalize content in the
shared global nav or LocalNav for one country **without cloning the nav file**,
combine a `countryip(...)` experience column with an **`in-block:global`**
selector — `countryip(de)` scopes the row to the country, `in-block:global`
reaches inside the shared `global` (nav) block so the base file stays shared.

**Modifying the gnav promo strip.** The gnav and footer **source is derived from
metadata**, so an alternative to a selector is to use `updateMetadata` to point
the gnav at a **new source fragment** for the targeted audience. The promo strip
/ blade above the nav is reachable this way (added per page). Note: targeting the
**promo card inside the gnav flyout** has been unreliable — no dependable
selector/attribute for it, so treat that specific element as a known gap.

## Advanced CSS patterns

- **Attribute selectors**: `#my-section [class]` (has any class);
  `[href="https://www.adobe.com"]` (exact).
- **Partial attribute match**: `[href*="photoshop.html"]`, `[href*="<osi-code>"]`.
- **`:has()`** — put the *unique* item in the parens before the non-unique
  target: `div:has(#illustrator) [href*="plans.html"]`.
- **`:not()`** — exclude a variant: `.text:not(.xl-spacing)`.
- **`:nth-child()`** and combinators (`+`, `>`) work as in normal CSS.

Real-world examples seen in manifests: `.hero-marquee`, `any-marquee`,
`tabs div:nth-child(2) > div:nth-child(2) #_include-fragments`.

### Stable selectors for localized / promo-shifting pages

Because MEP runs before decoration, **only headers auto-get IDs** at that point
(e.g. the headline "Build strong brands." → `#build-strong-brands`). Two durable
patterns:

- **`:has()` on a header** to grab its section/block regardless of position:
  `main > div:has(#build-strong-brands)` (section) or
  `.aside:has(#build-strong-brands)` (block). Good when a promo bar can shift
  `section1`/`nth-child` numbering.
- **Pseudo-id variant class** for non-header blocks: author a variant name like
  `text (build-strong-brands)` (variant names are **not** localized), then select
  `section:has(.build-strong-brands)`. Caveat: authors must re-add the variant if
  the block is ever replaced.

For marquees (usually unique / you want the first), `section:has([class*="marquee"])`
is the most resilient section selector.
