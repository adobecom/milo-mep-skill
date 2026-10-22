# Replacing M@S Cards, CaaS, and Content in Nested Fragments

The single most common "MEP won't apply" case: swapping a **merch card (M@S)**
or **CaaS** content that sits **inside a nested experience fragment (XF)** — e.g.
a segment blade authored in DA that itself pulls in an XF that renders the card.
It works on a flat test page but fails when nested. Here's why and how to fix it.

## The core rule: CSS selectors don't search fragments; fragment-URL selectors do

- A **fragment-URL selector** (starts with `/` or `http`) is automatically given
  `#_all` + `#_include-fragments` by MEP (`getSelectedElements`), so it searches
  **inside** fragments by default. That's why most manifest rows that target a
  card by its DA fragment path "just work," even nested.
- A **CSS selector** (e.g. `a[href*="<guid>"]`, `.merch-card`, `any-marquee`)
  gets **no** such treatment. By default MEP scans only the **base page** and
  marks the command complete after that pass (`handleCommands`), so it never
  descends into a nested XF. → **Add `#_include-fragments`** (and `#_all` if
  several cards match). With the flag, the command stays active and re-runs as
  each fragment decorates, so it reaches the card.

**Rule of thumb:** targeting nested content with a **CSS** selector → always
append `#_include-fragments`. Targeting by **fragment path** → already covered.

**Caveat — M@S cards inside a *nested DA fragment* are the unreliable case.** Even
with `#_include-fragments`, replacing a `<merch-card>` that lives inside a DA
experience fragment can fail intermittently: the card is a web component hydrated
**after** MEP runs, and the nested-fragment load timing doesn't always line up
with MEP's include-fragments re-passes. It works on a flat page and is flaky when
nested. Prefer the **`in-block:` M@S override** (by fragment id) for these, and if
a plain replace still misfires, treat it as a timing/hydration limitation — not a
selector typo. Confirm with `?mep` + Highlight Changes (M@S highlight).

## M@S cards are web components — match the authored reference, not the render

A merch card is a `<merch-card>` web component containing
`<aem-fragment fragment="<guid>">`, hydrated **client-side after** MEP runs. So:

- On the **plain, pre-decoration HTML**, confirm what's actually there. If the
  card is authored as a link, you'll see `<a href="…<guid>…">` → a selector like
  `a[href*="<guid>"] #_include-fragments` works.
- If it's an `<aem-fragment fragment="<guid>">` element (no `href`), then
  `a[href*=…]` matches **nothing** — target `[fragment*="<guid>"] #_include-fragments`
  instead, or use the M@S override below.
- Match the **authored fragment reference**, not the rendered component — MEP
  runs before hydration.

## The M@S override path (`in-block:` + a mas.adobe.com fragment)

The source has a dedicated mechanism for overriding a M@S card by fragment id
(`registerInBlockActions`): use an **`in-block:<block>`** selector whose value is
a `https://mas.adobe.com/…#…fragment=<guid>…` URL. MEP extracts the fragment id,
registers it in `config.mep.inBlock[block].fragments`, and injects an
`<aem-fragment>` into a hidden `mas-overrides` container so M@S renders your
override. Prefer this when you're swapping one M@S fragment for another by id,
rather than doing raw DOM surgery on `a[href*=guid]`.

For a field-level override, the MAS Studio URL in the selector can include
`&field=<field-name>` after its fragment/query identifier. Milo keys that
override by both the source fragment and field; the replacement MAS URL still
provides the replacement fragment. This also supports lightweight inline MAS
field links without hydrating a full merch card.

## Replacing specific cards in a `merch-card-collection`

To swap individual cards inside a catalog/collection, target the collection block
and let the code match cards by name:

- Selector: **`in-block:merch-card-collection`**, one manifest row per card you're
  replacing.
- Each merch card has a **`_name_`** value — the **H6** in the source doc. Put the
  replacement **fragment URL** in the action's content column; the collection code
  reads the `_name_` from that fragment and maps it back to the matching card in
  the collection. (This name→card mapping lives in the M@S
  `merch-card-collection` component, not in `personalization.js`; per the MEP
  support channel it's the supported path but was undocumented.)
- **Caveat:** for updating a card **CTA `href`** that depends on `data-wcs-osi`,
  `in-block:merch-card-collection` is **not** the right tool — that attribute
  isn't reliably present at execution time.

## CaaS

CaaS collections render from `[data-caas-block]`. The `?mep` **CaaS highlight**
toggle adds an "Edit in CaaS Configurator" badge so you can find the config.
CaaS content is usually better changed in the CaaS config than via MEP DOM
surgery; if you do target it with MEP, the same nested-fragment rule applies
(use `#_include-fragments`).

**The reliable MEP recipe for CaaS is fragment-swap, not DOM surgery:** put the
current CaaS collection **inside a fragment**, load that fragment on the page,
then have MEP **`replace` that fragment** with a fragment containing your new
cards (e.g. blog cards). MEP changes *what the page loads* rather than editing
CaaS output directly. This performs fine when the collection sits low on the
page. You can also swap the CaaS collection's link/href for a new link generated
by the same tool that produced the original. Either beats trying to reach
individual CaaS cards with CSS.

## Fix checklist (for "my card replace isn't applying")

1. **Add `#_include-fragments`** to any **CSS** selector that targets nested
   content (fragment-URL selectors already have it).
2. **Verify the plain HTML** — is the card an `<a href*="guid">` or an
   `<aem-fragment fragment="guid">`? Pick the matching selector
   (`a[href*=…]` vs `[fragment*=…]`), or use the `in-block:` M@S override.
3. **Check the page filter** — exact `/path` misses localized pages; use
   `**/path` if the blade is on localized/LATAM pages.
4. **Confirm timing** — MEP matches the authored fragment reference before M@S
   hydration; `#_include-fragments` re-applies within fragments as they load.

## Verify

Open with `?mep` + **Highlight Changes** (and **M@S highlight** to see cards and
their edit links). If the card doesn't light up, the selector isn't matching →
it's the fragment-reach / plain-HTML issue above, not priority. Toggle
`#_include-fragments` to confirm.

Source: `getSelectedElements` (fragment auto-modifiers), `handleCommands`
(include-fragments re-run), `registerInBlockActions` (in-block / mas.adobe.com) —
all in `assets/source/personalization.js`.
