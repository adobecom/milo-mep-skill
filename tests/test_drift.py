import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("drift", ROOT / "skills/milo-mep/scripts/check-source-drift.py")
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


class DriftTests(unittest.TestCase):
    def test_reference_cited_functions_are_tracked(self):
        for symbol in ("consolidateObjects", "getVariantInfo", "handleFragmentCommand", "normalizePath"):
            self.assertIn(symbol, drift.CITED)
        for generic in ("action", "content", "fragment"):
            self.assertNotIn(generic, drift.CITED)

    def test_personalization_files_and_cited_symbols_need_review(self):
        changed = [
            ("utils.js", "libs/utils/utils.js", []),
            ("preview.js", "libs/features/personalization/preview.js", []),
            ("fragment.js", "libs/blocks/fragment/fragment.js", ["normalizePath"]),
        ]
        review, incidental = drift.classify(changed)
        self.assertEqual([c[0] for c in review], ["preview.js", "fragment.js"])
        self.assertEqual([c[0] for c in incidental], ["utils.js"])


if __name__ == "__main__":
    unittest.main()
