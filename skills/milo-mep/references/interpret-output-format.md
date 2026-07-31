# Interpreting a Manifest — Output Format

When explaining or interpreting a manifest, **lead with business framing, then
back it with rigor.** A reader should understand *who gets what and why* in the
first few lines, then be able to drill into the exact mechanics, and never miss
a real bug. Use the template below; drop sections that don't apply (e.g. no
`Errors` → say "None found"), but keep the order.

## Template

```
## <Page> — <one-line personalization strategy>

<TL;DR: 1–2 sentences, plain business language. What page, what kind of
manifest, and the gist of the strategy — e.g. "Tailors the Acrobat pricing page
to campaign intent, cart-abandoners, B2B buyers, and device.">

### At a glance
- **Type / order:** Personalization | Promo | Test; execution order; and whether
  it's analytics-tracked (only Personalization is).
- **Analytics name:** `manifest-override-name` or the filename truncated to 15.
- **Consent:** what `manifest-marketing-action` requires — and **flag the default**
  (`marketing increase` → advertising consent) when the key is absent.
- **Placeholders:** present/empty; flag any `{{token}}` used but undefined here.

### Audiences (priority order — first match wins)
| Priority | Column | Likely intent | Requires |
|---|---|---|---|
| 1 | `target-…` | <inferred meaning> | Target on |
| … | `param-<key>=…` | <inferred campaign> | ?<key>= param |
| … | `Desktop`/`Phone`/… | device | — |

State explicitly: columns are left-to-right priority and **a visitor qualifies
for only the first column they match** (so Target beats param beats device;
segments don't stack).

### What each segment sees
| Segment | Experience |
|---|---|
| Default (no match) | … |
| <segment> | <plain-language experience> |

### How it works (detail)
Grouped by audience or theme. Row-level: action, selector (+ flags like
`#_all` / `#_include-fragments`), geo page-filters, inline vs fragment content.
Preserve the full mechanics — this is where the rigor lives.

### Errors
Numbered; each with **evidence** (row, exact value) and **impact**. Only real,
verified defects (see the checks below). "None found" if clean.

### Opportunities to improve
Numbered; conventions, de-duplication/localization, analytics naming, etc.
```

## Inferring intent (the business layer)

Translate technical audience/offer names into plain intent so the reader
understands *why*, but **mark every inference as inference** ("likely", "reads
as") — these are naming conventions, not guarantees. Keep inferred intent
visually separate from verifiable mechanics.

Common Adobe/DC naming cues to decode:
- `puf` → "pay up front"; `winback` → lapsed/returning users; `genai` → GenAI/AI
  Assistant campaign; `abdn`/`twp` → cart-abandon / try-with-purchase;
  `roc-` → regional customization; `b2b`/`opm` → business / online-purchase.
- `param-<key>=<x>` → visitors arriving from a specific campaign/tracking link.
- Explain the *effect* of actions too ("removes the aside CTAs → funnels to a
  single conversion path"), not just the mechanic.

If a name is opaque, say so and say what would confirm it (the Target activity,
the campaign brief) rather than over-guessing.

## Don't-miss checks (fold these into Errors/Opportunities)

Always run these while interpreting — they're the defects human readers miss:
- **Consent default:** missing `manifest-marketing-action` → advertising consent
  required (whole manifest gated). Flag it.
- **No-op rows:** a row with a selector/page filter but **no experience value**
  does nothing — likely an unfinished row.
- **Page-filter regex typos:** filters are compiled as regex (`matchGlob`). A
  stray char (e.g. `be_nl\nl` instead of `be_nl|nl`) silently breaks matching
  for those locales. Check byte-for-byte when a locale "should" match.
- **Undefined placeholders:** `{{token}}` with an empty/absent placeholders entry
  renders literally (unless a global placeholder covers it).
- **remove intent inversion:** a `remove` cell meant to be `false` but mistyped
  (`flse`, `false ` with a space, `0`/`no`) deletes the element. See `actions.md`.
- **Do NOT flag fragment-URL domains** (`hlx.page`/`aem.page`/`aem.live`, repo
  host) — they're normalized to a path. See `selectors.md`.
```
