import copy
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, TTCollection
from fontTools.ttLib.tables.ttProgram import Program

from builder import merge
from builder import __main__ as cli
from builder.sources import ROOT, download, load_source, resolve_file


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((200, 0))
    pen.lineTo((1800, 0))
    pen.lineTo((1800, 1400))
    pen.lineTo((200, 1400))
    pen.closePath()
    return pen.glyph()


def fixture(path, donor=False, missing=False):
    fb = FontBuilder(2000 if donor else 1000, isTTF=True)
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "box": rectangle()}
    pen = TTGlyphPen(glyphs)
    pen.addComponent("box", (1, 0, 0, 1, 0, 0))
    glyphs["composite"] = pen.glyph()
    glyphs["box"].program = Program()
    glyphs["box"].program.fromBytecode([0])
    fb.setupGlyphOrder(list(glyphs))
    cmap = {0xAC00: "composite", 0x3131: "box"} if donor else {cp: "box" for cp in range(32, 127)}
    if missing:
        del cmap[0xAC00]
    if not donor:
        cmap[65] = "composite"
        cmap[0x10000] = "box"
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({name: (2000 if donor else 500, getattr(g, "xMin", 0)) for name, g in glyphs.items()})
    fb.setupHorizontalHeader(ascent=1600 if donor else 800, descent=-400 if donor else -200)
    fb.setupNameTable({"familyName": "Fixture", "styleName": "Regular", "uniqueFontIdentifier": "fixture", "fullName": "Fixture Regular", "psName": "Fixture-Regular", "version": "Version 1.0"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=1600, usWinDescent=400, sxHeight=500, sCapHeight=700)
    fb.setupPost()
    fb.save(path)


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "base.ttf"
        self.donor = self.root / "donor.ttf"
        self.output = self.root / "out.ttf"
        fixture(self.base)
        fixture(self.donor, donor=True)
        self.config = {"name": "Fixture Korean", "family": "Agave Korean Test", "fonts": {"regular": {}, "bold": {}}, "transform": {"scale": .8, "x_offset": 20, "y_offset": -30}, "license": {"redistribute": True}}
        for key in ("KOREAN", "REQUIRED_KOREAN"):
            context = patch.object(merge, key, frozenset([0xAC00, 0x3131]))
            context.start()
            self.addCleanup(context.stop)

    def build(self, weight="regular"):
        return merge.merge_font(self.base, self.donor, self.output, self.config, weight, ["Fixture license"])

    def test_composite_hinting_offsets_and_two_cell_width(self):
        self.build()
        result = merge.validate_font(self.output, self.base, self.config["family"], "regular")
        self.assertEqual(result["korean_width"], 1000)
        with TTFont(self.output) as f:
            g = f["glyf"][f.getBestCmap()[0xAC00]]
            self.assertFalse(g.isComposite())
            self.assertEqual((g.xMin, g.yMin, g.xMax, g.yMax), (200, -30, 840, 530))
            self.assertEqual(f["hmtx"][f.getBestCmap()[0xAC00]], (1000, 200))
            self.assertFalse(g.program.getBytecode())
            self.assertEqual(f.getBestCmap()[0x10000], "box")

    def test_scale_changes_outline_but_not_advance_or_agave(self):
        self.config["transform"] = {"scale": .5, "x_offset": 0, "y_offset": 0}
        self.build("bold")
        merge.validate_font(self.output, self.base, self.config["family"], "bold")
        with TTFont(self.output) as f:
            g = f["glyf"][f.getBestCmap()[0xAC00]]
            self.assertEqual((g.xMin, g.xMax, g.yMax), (300, 700, 350))
            self.assertEqual(f["hmtx"][f.getBestCmap()[0xAC00]][0], 1000)

    def test_missing_modern_korean_fails(self):
        fixture(self.donor, donor=True, missing=True)
        with self.assertRaisesRegex(ValueError, "lacks"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_tampered_ascii_metrics_are_detected(self):
        self.build()
        with TTFont(self.output) as f:
            width, lsb = f["hmtx"]["box"]
            f["hmtx"]["box"] = (width, lsb + 1)
            f.save(self.output)
        with self.assertRaisesRegex(ValueError, "Agave metrics changed"):
            merge.validate_font(self.output, self.base, self.config["family"], "regular")

    def test_transform_overflow_fails(self):
        self.config["transform"]["y_offset"] = 40000
        with self.assertRaisesRegex(ValueError, "coordinate limits"):
            self.build()

    def test_local_collection_face_selection(self):
        directory = self.root / "fonts/local/custom"
        directory.mkdir(parents=True)
        collection = TTCollection()
        collection.fonts = [TTFont(self.base), TTFont(self.donor)]
        collection.save(directory / "Korean.ttc")
        for font in collection.fonts:
            font.close()
        spec = {"local": "custom/Korean.ttc", "font_number": 1}
        resolved = resolve_file(spec, self.root, offline=True)
        with merge.open_donor(resolved, spec, "regular") as donor:
            self.assertEqual(donor["head"].unitsPerEm, 2000)
            self.assertIn(0xAC00, donor.getBestCmap())

    def test_local_embedding_flags_are_not_relaxed(self):
        with TTFont(self.donor) as donor:
            donor["OS/2"].fsType = 2
            donor.save(self.donor)
        self.config["license"]["redistribute"] = False
        self.build()
        with TTFont(self.output) as font:
            self.assertEqual(font["OS/2"].fsType, 2)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_presets_are_valid_and_families_unique(self):
        configs = [load_source(p.stem) for p in (ROOT / "sources").glob("*.json") if p.stem != "agave"]
        self.assertEqual(len(configs), len({c["family"] for c in configs}))

    def test_missing_and_escaping_local_file(self):
        with self.assertRaisesRegex(ValueError, "Missing local file"):
            resolve_file({"local": "custom/Regular.ttf"}, self.root)
        with self.assertRaisesRegex(ValueError, "inside"):
            resolve_file({"local": "../../outside.ttf"}, self.root)

    def test_cached_checksum_and_offline(self):
        url = "https://example.invalid/font.ttf"
        key = hashlib.sha256(url.encode()).hexdigest()
        cache = self.root / ".cache" / "downloads" / key
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"fixture")
        spec = {"url": url, "sha256": hashlib.sha256(b"fixture").hexdigest()}
        self.assertEqual(download(spec, self.root, offline=True), cache)
        cache.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            download(spec, self.root, offline=True)
        with self.assertRaisesRegex(ValueError, "offline"):
            download({"url": url + "new"}, self.root, offline=True)

    def test_zip_exact_member_and_traversal_rejection(self):
        url = "https://example.invalid/font.zip"
        key = hashlib.sha256(url.encode()).hexdigest()
        cache = self.root / ".cache" / "downloads" / key
        cache.parent.mkdir(parents=True)
        with zipfile.ZipFile(cache, "w") as z:
            z.writestr("fonts/Regular.ttf", b"font")
            z.writestr("../escape", b"bad")
        spec = {"url": url, "archive": "zip", "member": "fonts/Regular.ttf"}
        self.assertEqual(resolve_file(spec, self.root, offline=True).read_bytes(), b"font")
        with self.assertRaisesRegex(ValueError, "Unsafe archive member"):
            resolve_file(dict(spec, member="../escape"), self.root, offline=True)
        self.assertFalse((self.root / "escape").exists())

    def test_restricted_source_cannot_download(self):
        config = copy.deepcopy(load_source("sarasa-mono-k"))
        config["license"]["redistribute"] = False
        (self.root / "sources").mkdir()
        (self.root / "sources" / "sarasa-mono-k.json").write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "must use local"):
            load_source("sarasa-mono-k", self.root)

    def test_batch_keeps_building_after_invalid_source(self):
        def load(source_id):
            if source_id == "bad":
                raise ValueError("invalid preset")
            return {}
        with patch.object(cli, "load_source", side_effect=load), patch.object(cli, "build_source") as build, patch.object(cli, "generate_preview") as preview, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["build", "bad", "good", "--offline"]), 1)
        build.assert_called_once_with("good", True)
        preview.assert_called_once()


if __name__ == "__main__":
    unittest.main()
