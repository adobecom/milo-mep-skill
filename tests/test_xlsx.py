import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/milo-mep/scripts"
sys.path.insert(0, str(SCRIPTS))
from mep_xlsx import read_manifest, write_manifest, edit_manifest, load_workbook, _sheet_paths


class XlsxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "manifest.xlsx"
        self.template = ROOT / "skills/milo-mep/assets/mep-manifest-template.xlsx"
        self.columns = ["action", "selector", "page filter (optional)", "phone", "all"]
        self.rows = [
            {"action": "replace", "selector": "any-marquee", "phone": "/fragments/phone"},
            {"action": "", "selector": "any-marquee", "page filter (optional)": "/example", "all": "A & B <offer>"},
        ]

    def write(self):
        write_manifest(self.output,
                       info={"manifest-type": "Personalization", "manifest-execution-order": "First",
                             "manifest-consent-type": "promo or no offer changes",
                             "manifest-country-restriction": "us,de"},
                       experiences={"columns": self.columns, "rows": self.rows},
                       placeholders={"columns": ["key", "value"], "rows": [{"key": "offer", "value": "A & B"}]})

    def test_round_trip_preserves_blank_cell_positions_and_column_order(self):
        self.write()
        result = read_manifest(self.output)
        exp = result["helix-experiences"]
        self.assertEqual(exp["columns"], self.columns)
        self.assertEqual(exp["rows"], [{key: row.get(key, "") for key in self.columns} for row in self.rows])
        info = {r["key"]: r["value"] for r in result["helix-info"]["rows"]}
        self.assertEqual(info["manifest-type"], "Personalization")
        self.assertEqual(info["manifest-execution-order"], "First")
        self.assertEqual(info["manifest-consent-type"], "promo or no offer changes")
        self.assertEqual(info["manifest-country-restriction"], "us,de")
        self.assertEqual(result["helix-placeholders"]["rows"], [{"key": "offer", "value": "A & B"}])

    def test_template_parts_dropdowns_styles_and_readme_survive(self):
        self.write()
        with ZipFile(self.template) as original, ZipFile(self.output) as output:
            paths = dict(_sheet_paths(original))
            changed = {paths[n] for n in ("helix-info", "helix-experiences", "helix-placeholders")}
            self.assertEqual(original.namelist(), output.namelist())
            self.assertIn("readme", paths)
            dropdowns = 0
            for name in original.namelist():
                before, after = original.read(name), output.read(name)
                if name not in changed:
                    self.assertEqual(before, after, name)
                    continue
                before_xml, after_xml = ET.fromstring(before), ET.fromstring(after)
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                for tag in ("extLst", "conditionalFormatting", "cols"):
                    a, b = before_xml.findall(ns + tag), after_xml.findall(ns + tag)
                    self.assertEqual([ET.tostring(x) for x in a], [ET.tostring(x) for x in b], (name, tag))
                dropdowns += before.count(b"dataValidation")
                if name == paths["helix-info"]:
                    before_styles = {c.attrib["r"]: c.get("s") for c in before_xml.iter(ns + "c")}
                    after_styles = {c.attrib["r"]: c.get("s") for c in after_xml.iter(ns + "c")}
                    self.assertEqual(before_styles, {ref: after_styles[ref] for ref in before_styles})
                else:
                    def outside_data(xml):
                        xml = re.sub(rb"<sheetData>.*?</sheetData>|<sheetData/>", b"", xml, flags=re.S)
                        return re.sub(rb'<dimension ref="[^"]*"/>', b"", xml)
                    self.assertEqual(outside_data(before), outside_data(after), name)
            self.assertGreater(dropdowns, 0, "test must exercise real template dropdowns")
            exp_xml = ET.fromstring(output.read(paths["helix-experiences"]))
            styles = {c.get("r"): c.get("s") for c in exp_xml.iter(ns + "c")}
            self.assertEqual(styles["A1"], "1")
            self.assertEqual(styles["D1"], "6")
            self.assertEqual(styles["E1"], "6")

    def test_published_json_read_and_xlsx_cli_agree(self):
        self.rows[1] = {**self.rows[1], "action": "remvoe"}
        self.write()
        normalized = read_manifest(self.output)
        published = {
            name.removeprefix("helix-"): {"columns": sheet["columns"], "data": sheet["rows"]}
            for name, sheet in normalized.items() if name.startswith("helix-")
        }
        source = Path(self.temp.name) / "published.json"
        source.write_text(json.dumps(published))
        read = read_manifest(source)
        self.assertEqual(read["experiences"], normalized["helix-experiences"])
        direct = subprocess.run(["node", str(SCRIPTS / "lint.mjs"), "-"],
                                input=json.dumps(normalized), capture_output=True, text=True)
        wrapped = subprocess.run([sys.executable, str(SCRIPTS / "lint_manifest.py"), str(self.output)],
                                 capture_output=True, text=True)
        self.assertEqual(wrapped.returncode, 1, wrapped.stderr)
        self.assertEqual(wrapped.returncode, direct.returncode)
        self.assertEqual(wrapped.stdout, direct.stdout)

    def test_cli_writes_from_spec_and_preserves_readme(self):
        spec = Path(self.temp.name) / "spec.json"
        spec.write_text(json.dumps({"experiences": {"columns": self.columns, "rows": self.rows}}))
        result = subprocess.run([sys.executable, str(SCRIPTS / "mep_xlsx.py"), "write",
                                 "--out", str(self.output), "--spec", str(spec)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("readme", read_manifest(self.output))

    def test_vendored_reader_works_without_site_packages(self):
        self.write()
        result = subprocess.run([sys.executable, "-S", str(SCRIPTS / "mep_xlsx.py"),
                                 "read", str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), read_manifest(self.output))

    def test_unknown_info_key_fails_without_overwriting_output(self):
        self.output.write_bytes(b"existing workbook")
        with self.assertRaisesRegex(ValueError, "Unknown info keys: manifest-conset-type"):
            write_manifest(self.output, info={"manifest-conset-type": "personalized offer"})
        self.assertEqual(self.output.read_bytes(), b"existing workbook")

    def test_page_scoped_placeholders_round_trip_and_shared_linter_warning(self):
        rows = [
            {"key": "copy", "page filter": "/example/a", "value": "A"},
            {"key": "copy", "page filter": "/example/b", "value": "B"},
            {"key": "copy", "page filter": "", "value": "General"},
        ]
        for scoped_first in (True, False):
            ordered = rows if scoped_first else [rows[-1], *rows[:-1]]
            write_manifest(self.output,
                           experiences={"columns": ["action", "selector", "all"], "rows": [
                               {"action": "replace", "selector": "any-marquee", "all": "{{copy}}"},
                           ]},
                           placeholders={"columns": ["key", "page filter", "value"], "rows": ordered})
            self.assertEqual(read_manifest(self.output)["helix-placeholders"]["rows"], ordered)
            result = subprocess.run([sys.executable, str(SCRIPTS / "lint_manifest.py"), str(self.output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual("is shadowed by unscoped row 1" in result.stdout, not scoped_first)


class XlsxEditTests(unittest.TestCase):
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "page.xlsx"
        self.output = Path(self.temp.name) / "page-edited.xlsx"
        write_manifest(self.source,
                       info={"manifest-type": "Personalization"},
                       experiences={"columns": ["action", "selector", "page filter (optional)", "all"], "rows": [
                           {"action": "replace", "selector": "any-marquee", "all": "/example/fragments/marquee"},
                           {"action": "remove", "selector": ".legal", "all": "true"},
                       ]},
                       placeholders={"columns": ["key", "value"], "rows": [{"key": "cta", "value": "Buy"}]})

    def styles(self, path, sheet):
        with ZipFile(path) as z:
            xml = z.read(dict(_sheet_paths(z))[sheet])
        return {c.get("r"): c.get("s") for c in ET.fromstring(xml).iter(self.NS + "c")}

    def test_edit_preserves_unrelated_rows_parts_and_styles(self):
        edit_manifest(self.source, self.output, {
            "info": {"manifest-execution-order": "First"},
            "experiences": {
                "add_columns": [{"name": "phone", "before": "all"}],
                "update": [{"match": {"selector": "any-marquee"}, "set": {"phone": "/example/fragments/marquee-phone"}}],
                "append": [{"action": "insertAfter", "selector": "section2", "phone": "/example/fragments/app-banner"}],
            },
        })
        result = read_manifest(self.output)
        exp = result["helix-experiences"]
        self.assertEqual(exp["columns"], ["action", "selector", "page filter (optional)", "phone", "all"])
        self.assertEqual(exp["rows"], [
            {"action": "replace", "selector": "any-marquee", "page filter (optional)": "",
             "phone": "/example/fragments/marquee-phone", "all": "/example/fragments/marquee"},
            {"action": "remove", "selector": ".legal", "page filter (optional)": "", "phone": "", "all": "true"},
            {"action": "insertAfter", "selector": "section2", "page filter (optional)": "",
             "phone": "/example/fragments/app-banner", "all": ""},
        ])
        info = {r["key"]: r["value"] for r in result["helix-info"]["rows"]}
        self.assertEqual(info["manifest-type"], "Personalization")
        self.assertEqual(info["manifest-execution-order"], "First")
        self.assertEqual(result["helix-placeholders"]["rows"], [{"key": "cta", "value": "Buy"}])
        self.assertIn("readme", result)
        with ZipFile(self.source) as before, ZipFile(self.output) as after:
            paths = dict(_sheet_paths(before))
            edited = {paths["helix-experiences"], paths["helix-info"]}
            self.assertEqual(before.namelist(), after.namelist())
            for name in before.namelist():
                if name not in edited:
                    self.assertEqual(before.read(name), after.read(name), name)
        before_styles, after_styles = (self.styles(p, "helix-experiences") for p in (self.source, self.output))
        self.assertEqual(after_styles["D1"], before_styles["D1"])
        self.assertEqual(after_styles["E1"], before_styles["D1"])
        self.assertEqual(after_styles["A3"], before_styles["A3"])
        self.assertEqual(after_styles["E3"], before_styles["D3"])
        lint = subprocess.run([sys.executable, str(SCRIPTS / "lint_manifest.py"), str(self.output)],
                              capture_output=True, text=True)
        self.assertEqual(lint.returncode, 0, lint.stdout)

    def test_delete_and_placeholder_update(self):
        edit_manifest(self.source, self.output, {
            "experiences": {"delete": [{"match": {"selector": ".legal"}}]},
            "placeholders": {"update": [{"match": {"key": "cta"}, "set": {"value": "Buy now"}}],
                             "append": [{"key": "promo", "value": "Save 20%"}]},
        })
        result = read_manifest(self.output)
        self.assertEqual([r["selector"] for r in result["helix-experiences"]["rows"]], ["any-marquee"])
        self.assertEqual(result["helix-placeholders"]["rows"],
                         [{"key": "cta", "value": "Buy now"}, {"key": "promo", "value": "Save 20%"}])

    def test_ambiguous_or_missing_match_writes_nothing(self):
        original = self.source.read_bytes()
        bad_specs = [
            {"experiences": {"update": [{"match": {"selector": "nope"}, "set": {"all": "x"}}]}},
            {"experiences": {"update": [{"match": {"page filter (optional)": ""}, "set": {"all": "x"}}]}},
            {"experiences": {"update": [{"match": {"colour": "x"}, "set": {"all": "x"}}]}},
            {"experiences": {"rename": []}},
            {"experiences": {"add_columns": [{"name": "all"}]}},
            {"info": {"manifest-typo": "x"}},
            {"helix-experiences": {}},
        ]
        for spec in bad_specs:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                edit_manifest(self.source, self.output, spec)
            self.assertFalse(self.output.exists())
            with self.subTest(spec=spec, in_place=True), self.assertRaises(ValueError):
                edit_manifest(self.source, self.source, spec)
            self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.source])

    def test_cli_edits_in_place(self):
        spec = Path(self.temp.name) / "edit.json"
        spec.write_text(json.dumps({"experiences": {
            "update": [{"match": {"selector": ".legal"}, "set": {"page filter (optional)": "**/example/sale"}}]}}))
        result = subprocess.run([sys.executable, str(SCRIPTS / "mep_xlsx.py"), "edit", str(self.source),
                                 "--out", str(self.source), "--spec", str(spec)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = read_manifest(self.source)["helix-experiences"]["rows"]
        self.assertEqual(rows[1]["page filter (optional)"], "**/example/sale")
        spec.write_text(json.dumps({"experiences": {"delete": [{"match": {"action": "nope"}}]}}))
        result = subprocess.run([sys.executable, str(SCRIPTS / "mep_xlsx.py"), "edit", str(self.source),
                                 "--out", str(self.source), "--spec", str(spec)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("selects 0 rows", result.stderr)

    def test_info_value_cell_is_inserted_when_absent(self):
        with ZipFile(self.source) as z:
            items = [(i, z.read(i.filename)) for i in z.infolist()]
            info_path = dict(_sheet_paths(z))["helix-info"]
            keyrow = next(r[0].row for r in load_workbook(self.source)["helix-info"].iter_rows()
                          if r[0].value == "manifest-override-name")
        stripped = Path(self.temp.name) / "stripped.xlsx"
        with ZipFile(stripped, "w") as out:
            for item, raw in items:
                if item.filename == info_path:
                    raw = re.sub(rb'<c r="B%d"[^>]*?(?:/>|>.*?</c>)' % keyrow, b"", raw, flags=re.S)
                    self.assertNotIn(b'r="B%d"' % keyrow, raw)
                out.writestr(item, raw)
        edit_manifest(stripped, self.output, {"info": {"manifest-override-name": "page-override"}})
        info = {r["key"]: r["value"] for r in read_manifest(self.output)["helix-info"]["rows"]}
        self.assertEqual(info["manifest-override-name"], "page-override")
        self.assertEqual(info["manifest-type"], "Personalization")


if __name__ == "__main__":
    unittest.main()
