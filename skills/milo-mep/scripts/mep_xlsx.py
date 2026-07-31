#!/usr/bin/env python3
"""
Read and write MEP manifest .xlsx files (and read the published .json).

Uses openpyxl so the template's readme tab, cell styles/colors, and dropdowns
(data validations) survive a write. openpyxl is vendored in ./vendor so this
works with no install; a system openpyxl is preferred if present.

CLI
    # read an xlsx (or published .json) and print normalized JSON
    python mep_xlsx.py read <manifest.xlsx|manifest.json>

    # build a manifest from the bundled template + a spec, write a new xlsx
    python mep_xlsx.py write --out new-manifest.xlsx --spec spec.json
        # optional: --template path/to/other-template.xlsx

spec.json shape (all keys optional):
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
      "placeholders": { "columns": ["key","value"],
                        "rows": [{"key":"promo","value":"Save 20%"}] }
    }

Programmatic API: read_manifest(path) -> dict; write_manifest(out, ...).
"""
import json
import os
import re
import sys
import warnings
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# The write path preserves the template's x14 data-validation dropdowns (they
# live in <extLst>, which we never touch), so openpyxl's "extension will be
# removed" warning during our read-only lookups is misleading here — silence it.
warnings.filterwarnings("ignore", message="Data Validation extension is not supported.*")

_WB_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _sheet_paths(z):
    """Map each sheet name -> its worksheet XML path inside the zip."""
    M = "{%s}" % _WB_NS["m"]
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid2t = {rel.get("Id"): rel.get("Target") for rel in rels}
    out = []
    for s in wb.find(M + "sheets").findall(M + "sheet"):
        tgt = rid2t[s.get("{%s}id" % _WB_NS["r"])]
        out.append((s.get("name"), ("xl/" + tgt) if not tgt.startswith("/") else tgt[1:]))
    return out

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(_HERE, "vendor")
_DEFAULT_TEMPLATE = os.path.normpath(
    os.path.join(_HERE, "..", "assets", "mep-manifest-template.xlsx")
)

try:  # prefer a system openpyxl, fall back to the vendored copy
    import openpyxl  # noqa: F401
except ModuleNotFoundError:
    if _VENDOR not in sys.path:
        sys.path.insert(0, _VENDOR)
    import openpyxl  # noqa: F401

from openpyxl import load_workbook


# ------------------------------- reading --------------------------------

def _read_json(path):
    """Normalize a published multi-sheet manifest .json to the same shape."""
    with open(path) as f:
        data = json.load(f)
    out = {}
    names = data.get(":names") or [k for k in data if not k.startswith(":")]
    for name in names:
        sheet = data.get(name) or {}
        cols = sheet.get("columns", [])
        rows = sheet.get("data", [])
        out[name] = {"columns": list(cols), "rows": [dict(r) for r in rows]}
    return out


def read_manifest(path):
    """Return {sheet_name: {"columns": [...], "rows": [ {col: value} ]}}.

    Works on a manifest .xlsx or a published .json. Cells are keyed by their
    column header (row 1); missing cells are "" — so an empty leading/middle
    cell never shifts the columns (the bug hand-rolled parsers hit).
    """
    if str(path).lower().endswith(".json"):
        return _read_json(path)

    # read_only=False so we read the actual cells present, not a (possibly
    # stale) declared <dimension> — real manifests often have a stale dimension.
    wb = load_workbook(path, read_only=False, data_only=True)
    out = {}
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        if not grid:
            out[ws.title] = {"columns": [], "rows": []}
            continue
        header = ["" if c is None else str(c) for c in grid[0]]
        # trim fully-empty trailing header columns
        while header and header[-1] == "":
            header.pop()
        width = len(header)
        rows = []
        for raw in grid[1:]:
            cells = ["" if v is None else str(v) for v in list(raw)[:width]]
            cells += [""] * (width - len(cells))
            row = {}
            for i in range(width):
                key = header[i] if header[i] else _col_letter(i + 1)
                row[key] = cells[i]
            if any(v != "" for v in row.values()):
                rows.append(row)
        out[ws.title] = {"columns": header, "rows": rows}
    wb.close()
    return out


def _col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ------------------------------- writing --------------------------------
# Writing is byte-preserving surgery on the template zip: only the <sheetData>
# of the sheets we change is rewritten (helix-info values are patched in place).
# Everything else is copied verbatim — styles, conditional formatting, drawings,
# customXml, and crucially the x14 data-validation DROPDOWNS, which live in each
# sheet's <extLst> (outside <sheetData>). openpyxl would strip those on save;
# this doesn't touch them.

def _cell(ref, value, style=None):
    s = f' s="{style}"' if style is not None else ""
    if value is None or value == "":
        return f'<c r="{ref}"{s}/>'
    return (f'<c r="{ref}"{s} t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def _sheetdata(columns, rows, header_styles=None):
    hs = header_styles or {}
    n = len(columns)
    parts = ["".join(_cell(f"{_col_letter(i)}1", columns[i - 1], hs.get(i))
                     for i in range(1, n + 1))]
    parts[0] = f'<row r="1" spans="1:{n}">{parts[0]}</row>'
    for r, row in enumerate(rows, start=2):
        cells = "".join(_cell(f"{_col_letter(i)}{r}", row.get(columns[i - 1], ""))
                        for i in range(1, n + 1))
        parts.append(f'<row r="{r}" spans="1:{n}">{cells}</row>')
    return "<sheetData>" + "".join(parts) + "</sheetData>"


def _replace_sheetdata(xml, columns, rows, header_styles=None):
    new_sd = _sheetdata(columns, rows, header_styles)
    if "<sheetData/>" in xml:
        xml = xml.replace("<sheetData/>", new_sd, 1)
    else:
        xml = re.sub(r"<sheetData>.*?</sheetData>", lambda m: new_sd,
                     xml, count=1, flags=re.S)
    # keep <dimension> accurate so read_only consumers see all rows
    ref = f"A1:{_col_letter(len(columns))}{1 + len(rows)}"
    xml = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="{ref}"/>',
                 xml, count=1)
    return xml


def _patch_cell(xml, ref, value):
    """Replace an existing cell's value in place, preserving its style (`s`)."""
    m = re.search(rf'<c r="{ref}"([^>]*?)(?:/>|>.*?</c>)', xml, re.S)
    if not m:
        return xml  # template's info value cells all exist, so this is fine
    sm = re.search(r'\bs="(\d+)"', m.group(1))
    return xml[:m.start()] + _cell(ref, value, sm.group(1) if sm else None) + xml[m.end():]


def _info_key_rows(template_path):
    wb = load_workbook(template_path, read_only=True, data_only=True)
    ws = wb["helix-info"]
    rows = {}
    for row in ws.iter_rows(min_row=1):
        if row and row[0].value is not None:
            rows[str(row[0].value)] = row[0].row
    wb.close()
    return rows


def write_manifest(out_path, template_path=_DEFAULT_TEMPLATE,
                   info=None, experiences=None, placeholders=None):
    """Build a manifest by copying the template and rewriting only what changes.

    Preserves the readme, styles, conditional formatting, and the dropdowns
    (x14 data validations). info: {key: value} patches helix-info value cells;
    experiences/placeholders: {"columns": [...], "rows": [{header: val}]} (the
    experience column order is the priority order, leftmost highest).
    """
    zin = zipfile.ZipFile(template_path)
    name2path = dict(_sheet_paths(zin))
    defaults = None
    mods = {}

    def default_cols(sheet):
        nonlocal defaults
        if defaults is None:
            defaults = read_manifest(template_path)
        return defaults[sheet]["columns"]

    if experiences is not None:
        path = name2path["helix-experiences"]
        cols = experiences.get("columns") or default_cols("helix-experiences")
        hs = {1: "1"}                                  # col A green (like A1)
        for i in range(4, len(cols) + 1):
            hs[i] = "6"                                 # experience cols blue (like D1)
        mods[path] = _replace_sheetdata(
            zin.read(path).decode("utf-8"), cols, experiences.get("rows", []), hs)

    if placeholders is not None:
        path = name2path["helix-placeholders"]
        cols = placeholders.get("columns") or default_cols("helix-placeholders")
        mods[path] = _replace_sheetdata(
            zin.read(path).decode("utf-8"), cols, placeholders.get("rows", []),
            {1: "1", 2: "1"})

    if info:
        path = name2path["helix-info"]
        xml = mods.get(path, zin.read(path).decode("utf-8"))
        keyrow = _info_key_rows(template_path)
        for key, val in info.items():
            if key in keyrow:
                xml = _patch_cell(xml, f"B{keyrow[key]}", val)
        mods[path] = xml

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = mods.get(item.filename)
            zout.writestr(item, data.encode("utf-8") if data is not None
                          else zin.read(item.filename))
    zin.close()
    return out_path


# --------------------------------- CLI ----------------------------------

def _main(argv):
    if not argv or argv[0] not in ("read", "write"):
        print(__doc__)
        return 2
    if argv[0] == "read":
        print(json.dumps(read_manifest(argv[1]), indent=2, ensure_ascii=False))
        return 0
    # write
    import argparse
    p = argparse.ArgumentParser(prog="mep_xlsx.py write")
    p.add_argument("--out", required=True)
    p.add_argument("--template", default=_DEFAULT_TEMPLATE)
    p.add_argument("--spec", required=True, help="Path to spec JSON")
    args = p.parse_args(argv[1:])
    with open(args.spec) as f:
        spec = json.load(f)
    write_manifest(args.out, template_path=args.template,
                   info=spec.get("info"), experiences=spec.get("experiences"),
                   placeholders=spec.get("placeholders"))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
