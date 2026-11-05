# Compact Synthetic Examples

These are illustrative, not live Adobe offers or publish-ready paths. Confirm
plain HTML, destination paths, consent classification, and stakeholders before
using them. Build workbooks from the official template with `mep_xlsx.py write`.

## 1. Native personalization: phone hero, desktop unchanged

**Goal:** swap the hero on `/example/smart-tools` for phone users. No Target
activity is involved; `target on` is not needed for this change.

`helix-info`:

| key | value |
|---|---|
| manifest-type | Personalization |
| manifest-execution-order | Normal |
| manifest-consent-type | promo or no offer changes |

This example assumes a layout-only change with no offer changes. Do not copy
that consent classification to a personalized offer without reviewing it.

`helix-experiences`:

| action | selector | page filter (optional) | phone |
|---|---|---|---|
| replace | any-marquee | /example/smart-tools | /example-shared/fragments/smart-tools/phone-hero |

There is deliberately no desktop or `all` column: nonmatching users keep the
original page. `phone` requires mobile-device detection **and** a screen width
or height below 550; narrowing a desktop browser viewport alone is not enough.
See `personalization-tags.md`. Confirm `any-marquee` matches exactly the
intended plain-HTML block. Add the resolvable manifest path to the page's
`personalization` metadata, **appending** it if the metadata already lists
other manifests; do not replace them.

**Verify:** on `/example/smart-tools?mep` from a phone (or a mobile-device
emulation below 550px), select the `phone` experience and enable Highlight
Changes. Expected: the hero shows the `phone-hero` fragment content (its
`data-path` is `/example-shared/fragments/smart-tools/phone-hero`). On desktop,
expected: the original hero, unchanged. If the page has other manifests,
confirm their changes still apply on both devices.

## 2. Target Promo versus native Personalization

**Goal:** understand two manifests replacing the same fragment selector.

| Delivery | Execution Order | Type | Selector | Replacement |
|---|---|---|---|---|
| Page metadata | Normal | Personalization | /example-shared/fragments/hero | /example-shared/fragments/member-hero |
| Target | Normal | Promo | /example-shared/fragments/hero | /example-shared/fragments/promo-hero |

Assume both manifests qualify and pass consent/country checks. The native
Personalization sorts earlier; Target delivery does not grant extra priority.
For these fragment replacements, the first selector replacement wins. To
sequence the Promo earlier, set its `helix-info` value:

```text
manifest-execution-order    First
```

Keep its type `Promo`. A `First` Promo sorts before a `Normal` Personalization.
Do not generalize this to every action: later `updateAttribute` rows can
overwrite earlier values. Metadata URL order only breaks equal-order/type
ties; drawer numbering is not the authoring control.

**Verify:** use `?mep` to inspect both manifests and selected experiences, then
Highlight Changes on the fragment. See `enable-and-qa.md` for full ordering.

## 3. US works, German page retains default content

**Symptom:** this row applies in the US but not on the German page, despite
both pages loading the same manifest and qualifying for the experience:

| action | selector | page filter (optional) | all |
|---|---|---|---|
| replace | any-marquee | **/example/smart-tools | /example-shared/fragments/smart-tools/hero |

**Likely cause:** the same-named German fragment is missing. Manifests are not
localized; the German page reuses the manifest and looks for:

```text
/de/example-shared/fragments/smart-tools/hero
```

If that fragment is missing, default **page content** remains; do not promise
automatic fallback to the US replacement fragment. Create the localized
fragment through the normal approved workflow. Only if the content should
intentionally stay unlocalized, use:

```text
/example-shared/fragments/smart-tools/hero#_dnt
```

Do not create a separate German manifest or change a fragment URL's host as a
fix. Confirm the page filter matches, then verify the localized path resolves.

**Verify:** reload `/de/example/smart-tools?mep`, select the experience, and
enable Highlight Changes. Confirm both US and German results.
