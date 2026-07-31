# Reading & Writing Manifest .xlsx Files

Use the bundled script **`scripts/mep_xlsx.py`** for any manifest `.xlsx` I/O —
don't hand-roll xlsx parsing. **Reading** uses **openpyxl** (vendored in
`scripts/vendor/`, so no install is needed; a system openpyxl is preferred if
present). **Writing** is byte-preserving surgery on the template zip (it only
rewrites the `<sheetData>` of the sheets it changes), so the template's
`readme`, styles, conditional formatting, and **dropdowns** all survive.

## Read

```bash
python scripts/mep_xlsx.py read <manifest.xlsx|manifest.json>
```

Returns `{ sheet_name: { "columns": [...], "rows": [ {col: value} ] } }`, with
each cell keyed by its column header. Also accepts a published `.json`
(normalizes it to the same shape). **Why use this, not a quick parser:** empty
cells are omitted from the raw XML, so positional parsing silently *shifts
columns* when a leading/middle cell (e.g. an empty `page filter`) is blank —
that produced false findings earlier. openpyxl reads by cell reference, so
columns always line up.

## Write (from the template)

Always build a new manifest from `assets/mep-manifest-template.xlsx` so the
`readme` tab, styles, and colors carry over:

```bash
python scripts/mep_xlsx.py write --out new-manifest.xlsx --spec spec.json
# optional: --template <other-template.xlsx>  (defaults to the bundled one)
```

`spec.json` (all keys optional):

```json
{
  "info": { "manifest-type": "Test", "manifest-execution-order": "Normal",
            "manifest-override-name": "" },
  "experiences": {
    "columns": ["action","selector","page filter (optional)","Loggedin & CC-All-Apps"],
    "rows": [
      {"action":"replace","selector":"any-marquee","page filter (optional)":"/products/photoshop",
       "Loggedin & CC-All-Apps":"https://…/fragments/…/marquee"}
    ]
  },
  "placeholders": { "columns": ["key","value"], "rows": [{"key":"promo","value":"Save 20%"}] }
}
```

- **`info`** sets the value column for matching keys in `helix-info`; the
  STEP-instruction column is preserved.
- **`experiences.columns`** is the ordered header row — **order = experience
  priority** (leftmost highest). Rename the default `all` column or add
  experience columns here (e.g. `target-…`, `param-view=…`, device tags).
- Existing data rows in the template are cleared before your rows are written.

Programmatic API (same file): `read_manifest(path)` and
`write_manifest(out, template_path=..., info=..., experiences=..., placeholders=...)`.

## Dropdowns / styles are preserved

The template's dropdowns are **x14 data-validation extensions** (in each sheet's
`<extLst>`, outside `<sheetData>`). openpyxl can't round-trip those, so the
writer **doesn't rebuild the workbook** — it copies the template byte-for-byte
and rewrites only the `<sheetData>` of the sheets it changes (and patches the
`helix-info` value cells in place). The dropdowns, cell styles/colors,
conditional formatting, drawings, and `readme` are therefore all preserved in
the generated file. (openpyxl is still used for *reading*, where it correctly
resolves cells by reference.)
