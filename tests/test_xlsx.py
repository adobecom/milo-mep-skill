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
from mep_xlsx import read_manifest, write_manifest, _sheet_paths


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


if __name__ == "__main__":
    unittest.main()
