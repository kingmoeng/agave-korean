import contextlib
import copy
import hashlib
import io
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, TTCollection
from fontTools.ttLib.tables.ttProgram import Program

from builder import merge
from builder import tune
from builder import __main__ as cli
from builder.sources import ROOT, apply_overrides, download, load_source, normalize_transform, resolve_file


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
        self.config = {"name": "Fixture Korean", "family": "Agave Korean Test", "fonts": {"regular": {}, "bold": {}}, "transform": normalize_transform({"scale": .8, "x_offset": 20, "y_offset": -30}), "license": {"redistribute": True}}
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
        self.config["transform"] = normalize_transform({"scale": .5})
        self.build("bold")
        merge.validate_font(self.output, self.base, self.config["family"], "bold")
        with TTFont(self.output) as f:
            g = f["glyf"][f.getBestCmap()[0xAC00]]
            self.assertEqual((g.xMin, g.xMax, g.yMax), (300, 700, 350))
            self.assertEqual(f["hmtx"][f.getBestCmap()[0xAC00]][0], 1000)

    def test_split_axes_scale_each_direction_independently(self):
        self.config["transform"] = normalize_transform({"scale": .5, "scale_x": 1.0})
        self.build()
        merge.validate_font(self.output, self.base, self.config["family"], "regular")
        with TTFont(self.output) as f:
            glyph = f["glyf"][f.getBestCmap()[0xAC00]]
            # Donor box 200..1800 of 2000 upem, centred in a 1000-unit cell: x fills it, y halves.
            self.assertEqual((glyph.xMin, glyph.xMax), (100, 900))
            self.assertEqual((glyph.yMin, glyph.yMax), (0, 350))
            self.assertEqual(f["hmtx"][f.getBestCmap()[0xAC00]][0], 1000)

    def test_tuner_geometry_matches_the_merged_outline(self):
        """`geometry()` in preview/tuner-template.html predicts the built glyph from the
        donor's ink box. If the two drift apart the tuner's readout steers the wrong scale."""
        with TTFont(self.donor) as donor:
            glyph_set = donor.getGlyphSet()
            source_glyph = glyph_set[donor.getBestCmap()[0xAC00]]
            pen = BoundsPen(glyph_set)
            source_glyph.draw(pen)
            em = donor["head"].unitsPerEm
            advance, (left, bottom, right, top) = source_glyph.width / em, [value / em for value in pen.bounds]
        unit, box = 1000, 1000  # Agave fixture upem, and two 500-unit cells
        for values in ({"scale": .8, "x_offset": 20, "y_offset": -30}, {"scale": .5},
                       {"scale": .9, "scale_x": 1.1}, {"scale": 1.0, "scale_y": .75, "y_offset": 40}):
            transform = normalize_transform(values)
            self.config["transform"] = transform
            self.build()
            with TTFont(self.output) as font:
                built = font["glyf"][font.getBestCmap()[0xAC00]]
                built.recalcBounds(font["glyf"])
            dx = (box - advance * unit * transform["scale_x"]) / 2 + transform["x_offset"]
            expected = (dx + left * unit * transform["scale_x"], dx + right * unit * transform["scale_x"],
                        bottom * unit * transform["scale_y"] + transform["y_offset"],
                        top * unit * transform["scale_y"] + transform["y_offset"])
            with self.subTest(transform=values):
                # One unit of slack for the quadratic conversion and integer coordinates.
                for predicted, actual in zip(expected, (built.xMin, built.xMax, built.yMin, built.yMax)):
                    self.assertAlmostEqual(predicted, actual, delta=1)

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


class TuneTests(unittest.TestCase):
    """The tuner pipeline end to end on synthetic fonts: no downloads, no built TTF."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        local = self.root / "fonts" / "local" / "fixture"
        local.mkdir(parents=True)
        fixture(local / "base.ttf")
        fixture(local / "donor.ttf", donor=True)
        (self.root / "sources").mkdir()
        for source_id, name in (("agave", "base.ttf"), ("fixture", "donor.ttf")):
            (self.root / "sources" / f"{source_id}.json").write_text(json.dumps({
                "id": source_id, "name": source_id, "family": "Agave Korean Test",
                "transform": {"scale": .8, "y_offset": -30},
                "fonts": {weight: {"local": f"fixture/{name}"} for weight in ("regular", "bold")},
                "license": {"id": "OFL-1.1", "redistribute": False},
            }))
        (self.root / "preview").mkdir()
        shutil.copyfile(ROOT / "preview" / "tuner-template.html", self.root / "preview" / "tuner-template.html")
        context = patch.object(tune, "SUBSET", frozenset([0xAC00, 0x3131]))
        context.start()
        self.addCleanup(context.stop)

    def test_publishes_korean_only_faces_and_a_page_that_carries_the_preset(self):
        tune.publish_source("fixture", self.root, offline=True)
        page = tune.generate_tuner(self.root, offline=True)
        with TTFont(self.root / "preview" / "donors" / "fixture-regular.ttf") as font:
            # ASCII always comes from Agave, so a stray Latin glyph here would be a real face mix-up.
            self.assertEqual(set(font.getBestCmap()), {0xAC00, 0x3131})
        text = page.read_text(encoding="utf-8")
        self.assertNotIn("/* TUNER_DATA */null", text)
        self.assertIn('font-family: "tune-fixture-regular"', text)
        data = json.loads((self.root / "preview" / "donors" / "manifest.json").read_text())
        self.assertEqual(data["sources"]["fixture"]["transform"]["scale_x"], .8)
        self.assertEqual(data["sources"]["fixture"]["transform"]["y_offset"], -30)

    def test_second_run_reuses_faces_but_follows_an_edited_preset(self):
        tune.publish_source("fixture", self.root, offline=True)
        face = self.root / "preview" / "donors" / "fixture-regular.ttf"
        stamp = face.stat().st_mtime_ns
        preset = self.root / "sources" / "fixture.json"
        config = json.loads(preset.read_text())
        config["transform"] = {"scale": .9, "scale_x": 1.1}
        preset.write_text(json.dumps(config))
        tune.publish_source("fixture", self.root, offline=True)
        tune.generate_tuner(self.root, offline=True)
        self.assertEqual(face.stat().st_mtime_ns, stamp, "unchanged donor was subset again")
        data = json.loads((self.root / "preview" / "donors" / "manifest.json").read_text())
        self.assertEqual(data["sources"]["fixture"]["transform"]["scale_x"], 1.1)

    def test_page_drops_a_source_whose_face_disappeared(self):
        tune.publish_source("fixture", self.root, offline=True)
        (self.root / "preview" / "donors" / "fixture-regular.ttf").unlink()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            tune.generate_tuner(self.root, offline=True)
        self.assertIn("fixture", output.getvalue())
        self.assertEqual(json.loads((self.root / "preview" / "donors" / "manifest.json").read_text())["sources"], {})


class TunerServerTests(unittest.TestCase):
    """The page's three actions, over a real loopback socket."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "sources").mkdir()
        self.preset = self.root / "sources" / "fixture.json"
        self.preset.write_text(json.dumps({
            "id": "fixture", "name": "fixture", "family": "Agave Korean Test",
            "transform": {"scale": .8, "x_offset": 0, "y_offset": -60},
            "fonts": {weight: {"local": "fixture/donor.ttf"} for weight in ("regular", "bold")},
            "license": {"id": "OFL-1.1", "redistribute": False},
        }, indent=2) + "\n")
        local = self.root / "fonts" / "local" / "fixture"
        local.mkdir(parents=True)
        fixture(local / "donor.ttf", donor=True)
        # Regenerating the page and the preview needs published faces and builds; not these tests' subject.
        for name in ("generate_tuner", "generate_preview"):
            context = patch.object(tune, name)
            context.start()
            self.addCleanup(context.stop)
        self.built = []
        handlers = tune.actions(self.root, True, self.build)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), tune.make_handler(self.root, "secret", handlers))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def build(self, source_id):
        self.built.append(source_id)
        return {"transform": load_source(source_id, self.root)["transform"],
                "outputs": [{"weight": "regular", "overhang_count": 0, "korean_characters": 2, "vertical_bounds": [-1, 2]}]}

    def post(self, action, payload):
        url = f"http://127.0.0.1:{self.server.server_port}{action}"
        request = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_apply_writes_the_preset_and_reports_the_previous_value(self):
        status, result = self.post("/apply", {"token": "secret", "id": "fixture", "transform": {"scale": 0.923, "x_offset": 0, "y_offset": -30}})
        self.assertEqual((status, result["ok"]), (200, True))
        self.assertEqual(result["previous"], {"scale": .8, "x_offset": 0, "y_offset": -60})
        self.assertEqual(result["transform"]["scale_x"], 0.923)
        written = json.loads(self.preset.read_text())
        self.assertEqual(written["transform"], {"scale": 0.923, "x_offset": 0, "y_offset": -30})
        self.assertEqual(written["family"], "Agave Korean Test", "the rest of the preset is untouched")

    def test_apply_keeps_split_axes_and_rejects_impossible_values(self):
        self.post("/apply", {"token": "secret", "id": "fixture", "transform": {"scale_x": 1.1, "scale_y": .9, "x_offset": 0, "y_offset": 0}})
        self.assertEqual(json.loads(self.preset.read_text())["transform"]["scale_x"], 1.1)
        for bad in ({"scale": 0, "x_offset": 0, "y_offset": 0}, {"skew": 1}):
            status, result = self.post("/apply", {"token": "secret", "id": "fixture", "transform": bad})
            self.assertEqual((status, result["ok"]), (400, False))
        self.assertEqual(json.loads(self.preset.read_text())["transform"]["scale_x"], 1.1, "a rejected value never lands")

    def test_a_stale_or_unknown_page_cannot_write_or_build(self):
        for payload in ({"token": "wrong", "id": "fixture", "transform": {"scale": 1.0}}, {"id": "fixture", "transform": {"scale": 1.0}}):
            status, result = self.post("/apply", payload)
            self.assertEqual(status, 400)
            self.assertIn("Stale page", result["error"])
        self.assertEqual(json.loads(self.preset.read_text())["transform"]["scale"], .8)
        self.assertEqual(self.post("/nope", {"token": "secret"})[0], 400)
        status, result = self.post("/apply", {"token": "secret", "id": "../escape", "transform": {"scale": 1.0}})
        self.assertEqual((status, result["ok"]), (400, False))

    def test_build_runs_only_on_request_and_returns_a_summary(self):
        self.assertEqual(self.built, [])
        status, result = self.post("/build", {"token": "secret", "id": "fixture"})
        self.assertEqual((status, self.built), (200, ["fixture"]))
        self.assertEqual(result["outputs"][0]["overhang_count"], 0)
        self.assertEqual(result["transform"]["scale_y"], .8)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_presets_are_valid_and_families_unique(self):
        configs = [load_source(p.stem) for p in (ROOT / "sources").glob("*.json") if p.stem != "agave"]
        self.assertEqual(len(configs), len({c["family"] for c in configs}))

    def test_transform_axes_default_to_scale_and_reject_bad_values(self):
        self.assertEqual(normalize_transform({"scale": .9}),
                         {"scale": .9, "scale_x": .9, "scale_y": .9, "x_offset": 0, "y_offset": 0})
        self.assertEqual(normalize_transform({"scale": .9, "scale_x": 1.1})["scale_y"], .9)
        for bad in ({"scale_x": 0}, {"scale_y": -1}, {"scale_x": True}, {"skew": 1}):
            with self.assertRaises(ValueError):
                normalize_transform(bad)

    def test_uniform_scale_override_resets_both_axes(self):
        preset = normalize_transform({"scale": .85, "scale_x": 1.1, "y_offset": -60})
        self.assertEqual(apply_overrides(preset, {"scale": 1.0}),
                         {"scale": 1.0, "scale_x": 1.0, "scale_y": 1.0, "x_offset": 0, "y_offset": -60})
        self.assertEqual(apply_overrides(preset, {"scale": 1.0, "scale_y": .9})["scale_y"], .9)
        self.assertEqual(apply_overrides(preset, {"y_offset": -120})["scale_x"], 1.1)

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
        build.assert_called_once_with("good", True, {})
        preview.assert_called_once()


if __name__ == "__main__":
    unittest.main()
