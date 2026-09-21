"""Optional integration tests: run after ./build.sh --all (no downloads here)."""
import json
import shutil
import subprocess
import tempfile
import unicodedata
import unittest
from pathlib import Path

import uharfbuzz as hb

from builder.merge import SYLLABLES, validate_font
from builder.sources import ROOT, resolve_file, sha256


def shape(path, text):
    font = hb.Font(hb.Face(path.read_bytes()))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    return [(info.codepoint, pos.x_advance, pos.y_advance, pos.x_offset, pos.y_offset) for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions)]


class BuiltFontTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("hb-view"), "hb-view is an optional rendering check")
    def test_original_ascii_hinted_pixels_at_preview_sizes(self):
        manifest = ROOT / "build/sarasa-mono-k/build.json"
        if not manifest.is_file():
            self.skipTest("Build Sarasa first")
        report = json.loads(manifest.read_text())
        sample = "".join(map(chr, range(32, 127)))
        with tempfile.TemporaryDirectory() as scratch:
            for output in report["outputs"]:
                original = resolve_file(report["agave_config"]["fonts"][output["weight"]], offline=True)
                for size in (12, 14, 16, 18):
                    rendered = []
                    for index, font in enumerate((original, manifest.parent / output["file"])):
                        png = Path(scratch) / f"{index}.png"
                        subprocess.run(["hb-view", str(font), f"--text={sample}", f"--font-size={size}", "--font-funcs=ft", "--ft-load-flags=0", f"--output-file={png}"], check=True, capture_output=True)
                        rendered.append(png.read_bytes())
                    with self.subTest(weight=output["weight"], size=size):
                        self.assertEqual(rendered[0], rendered[1], "Agave hinted ASCII rendering changed")

    def test_all_existing_builds(self):
        manifests = sorted((ROOT / "build").glob("*/build.json"))
        if not manifests:
            self.skipTest("Run ./build.sh --all for real-font integration checks")
        ascii_sample = "".join(map(chr, range(32, 127)))
        korean = "".join(map(chr, SYLLABLES))
        for manifest in manifests:
            report = json.loads(manifest.read_text())
            for output in report["outputs"]:
                with self.subTest(source=report["id"], weight=output["weight"]):
                    path = manifest.parent / output["file"]
                    base = resolve_file(report["agave_config"]["fonts"][output["weight"]], offline=True)
                    self.assertEqual(sha256(path), output["sha256"])
                    validate_font(path, base, report["family"], output["weight"])
                    self.assertEqual(shape(base, ascii_sample), shape(path, ascii_sample))
                    shaped = shape(path, korean)
                    self.assertEqual(len(shaped), 11172)
                    self.assertTrue(all(g[0] and g[1:] == (2048, 0, 0, 0) for g in shaped))
                    self.assertEqual(shape(path, unicodedata.normalize("NFD", korean)), shaped)


if __name__ == "__main__":
    unittest.main()
