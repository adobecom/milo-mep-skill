# MEP Actions

The `action` column of the `experiences` sheet says *what* to do. The value in
an experience column is the *payload* for that action (a fragment URL, `TRUE`,
a new attribute value, a folder path, etc.). This is the full action set.

## Action reference

| action | selector | experience-cell value | notes |
|---|---|---|---|
| `replace` | required (element or fragment) | preview URL (fragment) or HTML/content | Replaces the matched element(s) or fragment with the given content. Most common action. |
| `remove` | required | `TRUE` (to remove) or `FALSE`/blank | Removes the matched element(s). |
| `insertBefore` | required | preview URL / content | Inserts content immediately before the match. |
| `insertAfter` | required | preview URL / content | Inserts content immediately after the match. |
| `prepend` | required | preview URL / content | Inserts as first child of the match (for a fragment-URL selector, of the fragment link's parent element). |
| `append` | required | preview URL / content | Inserts as last child of the match (for a fragment-URL selector, of the fragment link's parent element). |
| `updateAttribute` | required **+ attribute name appended** | new attribute value | Selector ends with the attribute to change, e.g. `#learn-more-blade primary-cta href`. |
| `replacePage` | n/a | preview URL of replacement fragment | Swaps the entire page content for a fragment. |
| `useBlockCode` | n/a | folder path (relative, e.g. `libs/mep/dc-brick-block/brick`) | Loads custom block code from the given path. |
| `insertScript` | n/a | trusted script URL | Injects a script (must be a trusted domain). |
| `updateMetadata` | metadata field name (in selector) | new metadata value | Changes a page metadata value at runtime. |
| `analyticIfSeen` | required | analytics label | No DOM change — fires an analytics beacon when the element scrolls into view (IntersectionObserver). |
| `updateFramework` | n/a | foundation code (`c1`, `c2`, …) | Swaps the Milo foundation stylesheet. |

Exact source names: `remove`, `replace`, `updateattribute`, `analyticifseen`,
`insertbefore`, `insertafter`, `prepend`, `append`, `insertscript`,
`replacepage`, `updateframework`, `updatemetadata`, `useblockcode`
(case-insensitive).

## Legacy action names

The runtime lowercases the action and strips the substrings `content`,
`fragment`, and `tosection`, so legacy names normalize automatically:

| legacy | current |
|---|---|
| `replaceContent` | `replace` |
| `replaceFragment` | `replace` (with a fragment URL selector) |
| `removeContent` | `remove` |
| `insertContentBefore` | `insertBefore` |
| `insertContentAfter` | `insertAfter` |
| `appendToSection` | `append` |

Write the current names; this table is just for reading old manifests.

## Choosing an action

- Swapping a whole block/section or a fragment → `replace`.
- Hiding something → `remove` with `TRUE`.
- Adding new content near an existing element → `insertBefore` / `insertAfter`
  (siblings) or `prepend` / `append` (children).

> All four insert actions (`insertBefore`/`insertAfter`/`prepend`/`append`) work
> with **fragment-URL selectors** too — `handleCommands` positions them relative
> to the fragment link's **parent** element (source: `CREATE_CMDS` branch, lines
> ~791-799). The public docs say `prepend`/`append` don't work on fragments; the
> source does support them, but because they act on the parent, `insertBefore`/
> `insertAfter` (or an element selector) are more predictable for fragments.
- Changing a link target, image src, or other attribute → `updateAttribute`
  (append the attribute name to the selector).
- Setting/changing an **`aria-label`** or other a11y attribute → on an **existing**
  element use `updateAttribute` (e.g. `any-marquee primary-cta aria-label`); when
  you're **replacing** a CTA/element, author the `aria-label` **into the
  replacement content itself** (the fragment or inline HTML being swapped in) —
  `replace` only carries a payload, it has no separate attribute field.
- Whole-page variant → `replacePage`.
- Editing an SEO/meta value → `updateMetadata`.

## Value conventions

- **Fragment/content values** are typically **preview URLs** to a fragment
  (e.g. `https://main--<repo>--<org>.aem.page/.../fragments/.../marquee-mobile`).
  A bare integer (e.g. `2`) can be used to reference a fragment index in some
  block contexts.
- A **blank** experience cell = no change for that experience on that row.
- For `remove`, the removal is **skipped only** when the cell is blank or the
  value is exactly `false` (case-insensitive: parse-time check
  `line[vn].toLowerCase() === 'false'`, line 835; **not trimmed**). **Any other
  non-blank value deletes** the element (command-time `content !== 'false'`,
  line 306).
  - `TRUE`, `true`, and `1` all mean "remove" and are equally valid — **do not
    flag `1` vs `TRUE`.**
  - But because *only* the exact word `false` skips, a value that was **meant**
    to be `false` will silently **remove** instead: a typo (`flse`, `fasle`),
    `false` with a stray leading/trailing space (not trimmed!), or `0`/`no`/`off`
    all evaluate as truthy and delete the element. **Flag these** — they invert
    the author's intent.
