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

    # change an EXISTING manifest in place (keeps unrelated rows, sheets,
    # readme, styles, and dropdowns); --out may be the input path
    python mep_xlsx.py edit existing.xlsx --out updated.xlsx --spec edit.json

edit.json shape (all keys optional; nothing is written if any step fails):
    {
      "info": { "manifest-type": "Personalization" },
      "experiences": {
        "add_columns": [{"name": "phone", "before": "all"}],
        "update": [{"match": {"action": "replace", "selector": "any-marquee"},
                    "set": {"phone": "/fragments/marquee-phone"}}],
        "delete": [{"match": {"selector": ".old-banner"}}],
        "append": [{"action": "remove", "selector": ".legal", "phone": "true"}]
      },
      "placeholders": { "update": [{"match": {"key": "cta"}, "set": {"value": "Buy"}}] }
    }
    Each update/delete "match" must select exactly one existing row.

Programmatic API: read_manifest(path) -> dict; write_manifest(out, ...);
edit_manifest(path, out, spec).
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
    return _swap_sheetdata(xml, _sheetdata(columns, rows, header_styles),
                           len(columns), len(rows))


def _swap_sheetdata(xml, new_sd, ncols, nrows):
    if "<sheetData/>" in xml:
        xml = xml.replace("<sheetData/>", new_sd, 1)
    else:
        xml = re.sub(r"<sheetData>.*?</sheetData>", lambda m: new_sd,
                     xml, count=1, flags=re.S)
    # keep <dimension> accurate so read_only consumers see all rows
    ref = f"A1:{_col_letter(max(ncols, 1))}{1 + nrows}"
    xml = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="{ref}"/>',
                 xml, count=1)
    return xml


def _patch_cell(xml, ref, value):
    """Replace an existing cell's value in place, preserving its style (`s`)."""
    m = re.search(rf'<c r="{ref}"([^>]*?)(?:/>|>.*?</c>)', xml, re.S)
    if not m:
        raise ValueError(f"Template is missing info value cell {ref}")
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


def _append_info_rows(xml, values, keyrow):
    root = ET.fromstring(xml)
    ns = "{%s}" % _WB_NS["m"]
    data = root.find(ns + "sheetData")
    last_row = max(int(row.get("r")) for row in data)
    style_row = keyrow.get("manifest-type") or next(iter(keyrow.values()), 0)
    styles = {cell.get("r"): cell.get("s") for cell in data.iter(ns + "c")}
    additions = []
    for row_number, (key, value) in enumerate(values.items(), start=last_row + 1):
        cells = (_cell(f"A{row_number}", key, styles.get(f"A{style_row}"))
                 + _cell(f"B{row_number}", value, styles.get(f"B{style_row}")))
        additions.append(f'<row r="{row_number}" spans="1:2">{cells}</row>')
    xml = xml.replace("</sheetData>", "".join(additions) + "</sheetData>", 1)
    dimension = root.find(ns + "dimension")
    if dimension is not None:
        ref = dimension.get("ref")
        end = ref.split(":")[-1]
        match = re.fullmatch(r"([A-Z]+)(\d+)", end)
        column = match.group(1)
        if column == "A":
            column = "B"
        end_row = max(int(match.group(2)), last_row + len(values))
        new_ref = f'{ref.split(":")[0]}:{column}{end_row}'
        xml = xml.replace(f'<dimension ref="{ref}"/>', f'<dimension ref="{new_ref}"/>', 1)
    return xml


_SUPPORTED_INFO = {
    "manifest-type", "manifest-execution-order", "manifest-override-name",
    "manifest-consent-type", "manifest-country-restriction",
    "manifest-marketing-action", "manifest-geo-restriction",
}


def write_manifest(out_path, template_path=_DEFAULT_TEMPLATE,
                   info=None, experiences=None, placeholders=None):
    """Build a manifest by copying the template and rewriting only what changes.

    Preserves the readme, styles, conditional formatting, and the dropdowns
    (x14 data validations). info: {key: value} patches helix-info value cells
    and appends supported keys missing from older templates;
    experiences/placeholders: {"columns": [...], "rows": [{header: val}]} (the
    experience column order is the priority order, leftmost highest).
    """
    keyrow = _info_key_rows(template_path) if info else {}
    unknown = set(info or {}) - set(keyrow) - _SUPPORTED_INFO
    if unknown:
        raise ValueError(f"Unknown info keys: {', '.join(sorted(unknown))}")
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
        for key, val in info.items():
            if key in keyrow:
                xml = _patch_cell(xml, f"B{keyrow[key]}", val)
        missing = {key: val for key, val in info.items() if key not in keyrow}
        if missing:
            xml = _append_info_rows(xml, missing, keyrow)
        mods[path] = xml

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = mods.get(item.filename)
            zout.writestr(item, data.encode("utf-8") if data is not None
                          else zin.read(item.filename))
    zin.close()
    return out_path


# ------------------------------- editing --------------------------------
# Same surgery as write_manifest, but on an existing workbook: only the
# <sheetData> of edited sheets is rebuilt (and helix-info values patched), and
# each surviving cell keeps its original style. Fully blank rows are dropped.

_TABLE_OPS = ("add_columns", "update", "delete", "append")


def _cell_styles(xml):
    """{row_number: {column_letter: style_id}} from raw worksheet XML."""
    ns = "{%s}" % _WB_NS["m"]
    styles = {}
    for row in ET.fromstring(xml).iter(ns + "row"):
        for cell in row.findall(ns + "c"):
            ref, style = cell.get("r"), cell.get("s")
            if ref and style is not None:
                col, num = re.fullmatch(r"([A-Z]+)(\d+)", ref).groups()
                styles.setdefault(int(num), {})[col] = style
    return styles


def _read_table(ws, xml, sheet):
    styles = _cell_styles(xml)
    grid = list(ws.iter_rows())
    header = ["" if c.value is None else str(c.value) for c in grid[0]] if grid else []
    while header and header[-1] == "":
        header.pop()
    if "" in header or len(set(header)) != len(header):
        raise ValueError(f"{sheet}: header row has blank or duplicate column names")
    letters = {name: _col_letter(i + 1) for i, name in enumerate(header)}
    header_styles = {name: styles.get(1, {}).get(letters[name]) for name in header}
    records = []
    for raw in grid[1:]:
        values = {name: ("" if i >= len(raw) or raw[i].value is None else str(raw[i].value))
                  for i, name in enumerate(header)}
        if any(values.values()):
            row_styles = styles.get(raw[0].row, {})
            records.append({"values": values,
                            "styles": {n: row_styles.get(letters[n]) for n in header}})
    return header, header_styles, records


def _apply_table_ops(sheet, header, header_styles, records, ops):
    unknown = set(ops) - set(_TABLE_OPS)
    if unknown:
        raise ValueError(f"{sheet}: unknown edit operations: {', '.join(sorted(unknown))}")
    header = list(header)
    style_from = {}
    for col in ops.get("add_columns", []):
        col = {"name": col} if isinstance(col, str) else col
        name = col.get("name")
        if not isinstance(name, str) or not name.strip() or name in header:
            raise ValueError(f"{sheet}: cannot add column {name!r}")
        anchor = col.get("before", col.get("after"))
        if anchor is not None and anchor not in header:
            raise ValueError(f"{sheet}: no column {anchor!r} to place {name!r} next to")
        pos = len(header) if anchor is None else header.index(anchor) + ("after" in col)
        style_from[name] = anchor if anchor is not None else header[-1]
        header.insert(pos, name)
        header_styles[name] = header_styles.get(style_from[name])

    def known(keys, what):
        missing = [k for k in keys if k not in header]
        if missing:
            raise ValueError(f"{sheet}: {what} names unknown columns: {', '.join(missing)}")

    def find(match):
        if not isinstance(match, dict) or not match:
            raise ValueError(f"{sheet}: each update/delete needs a non-empty match")
        known(match, "match")
        hits = [r for r in records
                if all(r["values"].get(k, "").strip() == str(v).strip() for k, v in match.items())]
        if len(hits) != 1:
            raise ValueError(f"{sheet}: match {match} selects {len(hits)} rows; it must select exactly 1")
        return hits[0]

    for item in ops.get("update", []):
        record = find(item.get("match"))
        changes = item.get("set") or {}
        known(changes, "set")
        record["values"].update({k: "" if v is None else str(v) for k, v in changes.items()})
    for item in ops.get("delete", []):
        records.remove(find(item.get("match")))
    for row in ops.get("append", []):
        known(row, "append")
        last = records[-1]["styles"] if records else {}
        records.append({"values": {k: "" if v is None else str(v) for k, v in row.items()},
                        "styles": dict(last)})
    for record in records:
        for name, source in style_from.items():
            record["styles"].setdefault(name, record["styles"].get(source))
    return header, header_styles, records


def _styled_sheetdata(header, header_styles, records):
    n = len(header)
    cells = "".join(_cell(f"{_col_letter(i + 1)}1", name, header_styles.get(name))
                    for i, name in enumerate(header))
    parts = [f'<row r="1" spans="1:{n}">{cells}</row>']
    for r, record in enumerate(records, start=2):
        cells = "".join(_cell(f"{_col_letter(i + 1)}{r}", record["values"].get(name, ""),
                              record["styles"].get(name))
                        for i, name in enumerate(header))
        parts.append(f'<row r="{r}" spans="1:{n}">{cells}</row>')
    return "<sheetData>" + "".join(parts) + "</sheetData>"


def _set_info_value(xml, row, value):
    """Set column B of an existing helix-info row, inserting the cell if absent."""
    ref = f"B{row}"
    if re.search(rf'<c r="{ref}"[\s/>]', xml):
        return _patch_cell(xml, ref, value)
    match = re.search(rf'<row r="{row}"[^>]*?(?:/>|>(.*?)</row>)', xml, re.S)
    if not match:
        raise ValueError(f"helix-info row {row} not found")
    body = match.group(1) or ""
    later = re.search(r'<c r="(?:[C-Z]|[A-Z]{2,})\d+"', body)
    insert_at = later.start() if later else len(body)
    body = body[:insert_at] + _cell(ref, value) + body[insert_at:]
    head = re.match(rf'<row r="{row}"[^>]*?(?=/?>)', match.group(0)).group(0)
    return xml[:match.start()] + f"{head}>{body}</row>" + xml[match.end():]


def edit_manifest(in_path, out_path, spec):
    """Apply an edit spec (see module docstring) to an existing manifest .xlsx.

    Rows not named by an operation, other sheets, the readme, styles, and the
    x14 dropdowns are preserved. Raises ValueError (writing nothing) when an
    operation is ambiguous or names an unknown column/key.
    """
    if not isinstance(spec, dict):
        raise ValueError("edit spec must be an object")
    unknown = set(spec) - {"info", "experiences", "placeholders"}
    if unknown:
        raise ValueError(f"Unknown edit sections: {', '.join(sorted(unknown))}")
    wb = load_workbook(in_path, read_only=False, data_only=True)
    with zipfile.ZipFile(in_path) as zin:
        items = [(item, zin.read(item.filename)) for item in zin.infolist()]
        name2path = dict(_sheet_paths(zin))
    data = {item.filename: raw for item, raw in items}
    mods = {}
    for section in ("experiences", "placeholders"):
        ops = spec.get(section)
        if ops is None:
            continue
        sheet = f"helix-{section}"
        if sheet not in name2path:
            raise ValueError(f"Workbook has no {sheet} sheet")
        path = name2path[sheet]
        xml = data[path].decode("utf-8")
        header, header_styles, records = _apply_table_ops(
            sheet, *_read_table(wb[sheet], xml, sheet), ops)
        mods[path] = _swap_sheetdata(xml, _styled_sheetdata(header, header_styles, records),
                                     len(header), len(records))
    info = spec.get("info")
    if info:
        if "helix-info" not in name2path:
            raise ValueError("Workbook has no helix-info sheet")
        keyrow = {str(r[0].value).strip(): r[0].row
                  for r in wb["helix-info"].iter_rows(min_row=1) if r and r[0].value is not None}
        unsupported = set(info) - set(keyrow) - _SUPPORTED_INFO
        if unsupported:
            raise ValueError(f"Unknown info keys: {', '.join(sorted(unsupported))}")
        path = name2path["helix-info"]
        xml = data[path].decode("utf-8")
        for key, value in info.items():
            if key in keyrow:
                xml = _set_info_value(xml, keyrow[key], value)
        missing = {k: v for k, v in info.items() if k not in keyrow}
        if missing:
            xml = _append_info_rows(xml, missing, keyrow)
        mods[path] = xml
    wb.close()
    out_path = os.path.abspath(out_path)
    temp = out_path + ".tmp"
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item, raw in items:
                new = mods.get(item.filename)
                zout.writestr(item, new.encode("utf-8") if new is not None else raw)
        os.replace(temp, out_path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)
    return out_path


# --------------------------------- CLI ----------------------------------

def _main(argv):
    if not argv or argv[0] not in ("read", "write", "edit"):
        print(__doc__)
        return 2
    if argv[0] == "read":
        print(json.dumps(read_manifest(argv[1]), indent=2, ensure_ascii=False))
        return 0
    import argparse
    if argv[0] == "edit":
        p = argparse.ArgumentParser(prog="mep_xlsx.py edit")
        p.add_argument("manifest", help="existing manifest .xlsx")
        p.add_argument("--out", required=True, help="output path (may equal the input)")
        p.add_argument("--spec", required=True, help="Path to edit spec JSON")
        args = p.parse_args(argv[1:])
        with open(args.spec) as f:
            spec = json.load(f)
        try:
            edit_manifest(args.manifest, args.out, spec)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print(f"Wrote {args.out}")
        return 0
    # write
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
