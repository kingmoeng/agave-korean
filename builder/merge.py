"""Append Korean outlines to Agave without renumbering or redrawing Agave."""

import hashlib
import json

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.varLib.instancer import instantiateVariableFont

from .sources import sha256

# Deliberately omit conjoining/archaic Jamo: those require donor layout tables.
SYLLABLES = range(0xAC00, 0xD7A4)
COMPATIBILITY_JAMO = range(0x3131, 0x318F)
KOREAN = frozenset(SYLLABLES) | frozenset(COMPATIBILITY_JAMO)
REQUIRED_KOREAN = frozenset(SYLLABLES) | frozenset(range(0x3131, 0x3164))
UNCHANGED_TABLES = ("fpgm", "prep", "cvt ", "gasp", "GDEF", "GSUB", "GPOS", "kern", "TTFA", "FFTM")


def raw_glyphs(font):
    data = font.reader["glyf"]
    offsets = font["loca"].locations
    return {name: data[offsets[i]:offsets[i + 1]] for i, name in enumerate(font.getGlyphOrder())}


def open_donor(path, spec, weight):
    font = TTFont(path, fontNumber=spec.get("font_number", -1), recalcTimestamp=False)
    if "fvar" in font:
        values = dict(spec.get("axes", {}))
        axes = {axis.axisTag: axis for axis in font["fvar"].axes}
        if set(values) - set(axes):
            raise ValueError("Unknown variable font axis")
        for tag, axis in axes.items():
            value = values.setdefault(tag, 700 if weight == "bold" and tag == "wght" else 400 if tag == "wght" else axis.defaultValue)
            if not axis.minValue <= value <= axis.maxValue:
                raise ValueError(f"Axis {tag} out of range: {value}")
        font = instantiateVariableFont(font, values, inplace=True)
    elif spec.get("axes"):
        raise ValueError("axes provided for a static font")
    if not any(tag in font for tag in ("glyf", "CFF ", "CFF2")):
        raise ValueError("Only outline TrueType/OpenType fonts are supported")
    return font


def set_names(font, donor, config, weight, license_texts, fingerprint):
    original = font["name"]
    copyright_text = "\n".join(filter(None, [original.getDebugName(0), donor["name"].getDebugName(0)]))
    family = config["family"]
    style = weight.title()
    postscript = family.replace(" ", "") + "-" + style
    font["name"] = newTable("name")
    font["name"].names = []
    values = {
        0: copyright_text,
        1: family, 2: style, 3: f"AgaveKorean:0.1:{fingerprint[:16]}:{style}",
        4: f"{family} {style}", 5: "Version 0.100; Agave Korean builder", 6: postscript,
        9: "; ".join(filter(None, [original.getDebugName(9), donor["name"].getDebugName(9)])),
        10: f"Derived from normal Agave and {config['name']}. Korean outlines transformed; Agave glyphs preserved.",
        13: "\n\n".join(license_texts),
        14: "https://openfontlicense.org/" if config["license"].get("redistribute") else "See accompanying LICENSES and build report",
        16: family, 17: style, 21: family, 22: style,
    }
    for name_id, value in values.items():
        font["name"].setName(value, name_id, 3, 1, 0x409)
        if name_id in (1, 2, 3, 4, 5, 6):
            font["name"].setName(value, name_id, 1, 0, 0)


def merge_font(agave_path, donor_path, output, config, weight, license_texts):
    font = TTFont(agave_path, recalcBBoxes=False, recalcTimestamp=False)
    donor = open_donor(donor_path, config["fonts"][weight], weight)
    try:
        if "glyf" not in font or "fvar" in font:
            raise ValueError("Agave base must be a static TrueType font")
        old_order = font.getGlyphOrder()[:]
        original_bytes = raw_glyphs(font)
        cmap = font.getBestCmap()
        widths = {font["hmtx"][cmap[cp]][0] for cp in range(32, 127)}
        if len(widths) != 1:
            raise ValueError("Agave ASCII must be monospaced")
        cell = widths.pop()
        full_width = 2 * cell
        donor_cmap = donor.getBestCmap()
        missing = REQUIRED_KOREAN - donor_cmap.keys()
        if missing:
            raise ValueError(f"Donor lacks {len(missing)} required Korean characters (first U+{min(missing):04X})")
        if KOREAN & cmap.keys():
            raise ValueError("Agave already contains Korean; refusing to replace existing glyphs")
        glyph_set = donor.getGlyphSet()
        transform = config["transform"]
        unit = font["head"].unitsPerEm / donor["head"].unitsPerEm
        factor_x, factor_y = unit * transform["scale_x"], unit * transform["scale_y"]
        imported = {}
        overhangs = []
        for cp in sorted(KOREAN & donor_cmap.keys()):
            name = f"kr{cp:04X}"
            if name in font["glyf"]:
                raise ValueError(f"Glyph name collision: {name}")
            source_glyph = glyph_set[donor_cmap[cp]]
            # Center the donor's advance box, preserving its optical sidebearings.
            dx = (full_width - source_glyph.width * factor_x) / 2 + transform["x_offset"]
            dy = transform["y_offset"]
            recording = DecomposingRecordingPen(glyph_set, skipMissingComponents=False, reverseFlipped=True)
            source_glyph.draw(recording)
            pen = TTGlyphPen(None)
            quadratic = Cu2QuPen(pen, max_err=0.5, reverse_direction="glyf" not in donor)
            recording.replay(TransformPen(quadratic, (factor_x, 0, 0, factor_y, dx, dy)))
            glyph = pen.glyph()
            glyph.recalcBounds(font["glyf"])
            if glyph.numberOfContours:
                bounds = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
                if min(bounds) < -32768 or max(bounds) > 32767:
                    raise ValueError("Transform exceeds TrueType coordinate limits")
                # Decomposition may introduce overlaps; advertise that to rasterizers.
                glyph.flags[0] |= 0x40
                if glyph.xMin < 0 or glyph.xMax > full_width:
                    overhangs.append(cp)
            font["glyf"][name] = glyph
            font["hmtx"][name] = (full_width, getattr(glyph, "xMin", 0))
            if "vmtx" in font:
                font["vmtx"][name] = (font["head"].unitsPerEm, font["vhea"].ascent - getattr(glyph, "yMax", 0))
            imported[cp] = name
        font.setGlyphOrder(old_order + list(imported.values()))
        for table in font["cmap"].tables:
            if table.isUnicode() and table.format in (4, 12):
                table.cmap.update(imported)
        # Recompute structural maxima, not the Agave line spacing or glyph metrics.
        font["maxp"].recalc(font)
        font["hhea"].recalc(font)
        if "vhea" in font:
            font["vhea"].recalc(font)
        os2 = font["OS/2"]
        if not config["license"].get("redistribute") and "OS/2" in donor:
            # The pinned Agave base permits embedding. Copy the donor's mode;
            # fsType permission modes must not be combined with bitwise OR.
            os2.fsType = donor["OS/2"].fsType
        os2.usWinAscent = max(os2.usWinAscent, font["head"].yMax)
        os2.usWinDescent = max(os2.usWinDescent, -font["head"].yMin)
        os2.recalcUnicodeRanges(font)
        os2.recalcCodePageRanges(font)
        os2.usFirstCharIndex = min(font.getBestCmap())
        os2.usLastCharIndex = min(0xFFFF, max(font.getBestCmap()))
        os2.usWeightClass = 700 if weight == "bold" else 400
        os2.fsSelection = (os2.fsSelection & ~0x61) | (0x20 if weight == "bold" else 0x40)
        font["head"].macStyle = (font["head"].macStyle & ~3) | (1 if weight == "bold" else 0)
        if "DSIG" in font:
            del font["DSIG"]  # A signature cannot survive modification.
        fingerprint = hashlib.sha256((sha256(agave_path) + sha256(donor_path) + json.dumps(config, sort_keys=True)).encode()).hexdigest()
        set_names(font, donor, config, weight, license_texts, fingerprint)
        # Restore compact original byte blocks AFTER aggregate metric calculations.
        # With recalcBBoxes=False fontTools writes these blocks without re-encoding.
        for name, data in original_bytes.items():
            font["glyf"].glyphs[name] = Glyph(data)
        font.save(output)
        return {
            "weight": weight, "file": output.name, "ascii_width": cell,
            "korean_width": full_width, "korean_characters": len(imported),
            "agave_glyphs_preserved": len(old_order), "upem": font["head"].unitsPerEm,
            "outline_factor": [factor_x, factor_y], "overhang_count": len(overhangs),
            "vertical_bounds": [font["head"].yMin, font["head"].yMax],
            "line_metrics": [font["hhea"].ascent, font["hhea"].descent, font["hhea"].lineGap],
            "agave_sha256": sha256(agave_path), "donor_sha256": sha256(donor_path),
            "sha256": sha256(output),
        }
    finally:
        font.close()
        donor.close()


def validate_font(output, agave_path, family, weight):
    """Validate the SAVED artifact, including every original Agave glyph block."""
    with TTFont(output, checkChecksums=2) as font, TTFont(agave_path) as original:
        # Force all tables to decompile, including layout and optional vertical metrics.
        for tag in font.keys():
            font[tag]
        def require(condition, message):
            if not condition:
                raise ValueError(f"{output}: {message}")
        cmap = font.getBestCmap()
        require(set(range(32, 127)) <= cmap.keys(), "missing ASCII")
        require(REQUIRED_KOREAN <= cmap.keys(), "missing Korean")
        korean = KOREAN & cmap.keys()
        widths = {font["hmtx"][cmap[cp]][0] for cp in range(32, 127)}
        require(len(widths) == 1, "ASCII widths differ")
        cell = next(iter(widths))
        require({font["hmtx"][cmap[cp]][0] for cp in korean} == {2 * cell}, "Korean is not exactly two cells")
        old_order = original.getGlyphOrder()
        require(font.getGlyphOrder()[:len(old_order)] == old_order, "Agave glyph IDs changed")
        before, after = raw_glyphs(original), raw_glyphs(font)
        for name in old_order:
            require(before[name] == after[name], f"Agave glyph bytes changed: {name}")
            require(original["hmtx"][name] == font["hmtx"][name], f"Agave metrics changed: {name}")
            if "vmtx" in original:
                require(original["vmtx"][name] == font["vmtx"][name], f"Agave vertical metrics changed: {name}")
        require(all(cmap.get(cp) == name for cp, name in original.getBestCmap().items()), "Agave cmap changed")
        for tag in UNCHANGED_TABLES:
            if tag in original:
                require(font.reader[tag] == original.reader[tag], f"Agave {tag} changed")
        for tag, fields in (("head", ["unitsPerEm"]), ("hhea", ["ascent", "descent", "lineGap"]), ("OS/2", ["sTypoAscender", "sTypoDescender", "sTypoLineGap", "sxHeight", "sCapHeight", "xAvgCharWidth"])):
            for field in fields:
                require(getattr(font[tag], field) == getattr(original[tag], field), f"Agave {tag}.{field} changed")
        for cp in korean:
            glyph = font["glyf"][cmap[cp]]
            require(not glyph.isComposite(), "unresolved Korean composite")
            require(not getattr(glyph, "program", None) or not glyph.program.getBytecode(), "donor hint instructions imported")
        for name_id in (1, 16, 21):
            require(font["name"].getDebugName(name_id) == family, "incorrect family name")
        for name_id in (2, 17, 22):
            require(font["name"].getDebugName(name_id) == weight.title(), "incorrect subfamily")
        require(font["OS/2"].usWeightClass == (700 if weight == "bold" else 400), "incorrect weight")
        require(bool(font["head"].macStyle & 1) == (weight == "bold"), "incorrect bold flag")
        require(not font["head"].macStyle & 2, "unexpected italic flag")
        require(font["OS/2"].usWinAscent >= font["head"].yMax and font["OS/2"].usWinDescent >= -font["head"].yMin, "clipping bounds too small")
        return {"status": "passed", "original_glyphs": len(old_order), "korean_characters": len(korean), "ascii_width": cell, "korean_width": 2 * cell}
