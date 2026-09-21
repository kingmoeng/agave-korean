"""Rehearse a Korean transform in the browser before committing it to a build.

The page loads no built font. It loads unmodified Agave for ASCII and the raw donor
for Korean, then reproduces `merge_font` in CSS: a Korean cell is a two-cell box, the
donor renders at `scale * font-size` so its outline matches the imported one exactly,
and the advance box is centred just as `dx` centres it. Rendering the donor at another
size — rather than scaling rasterised text — keeps the 12-16px sizes that decide the
question sharp.
"""

import json
import secrets
import shutil
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from fontTools import subset
from fontTools.ttLib import TTFont

from .merge import KOREAN, open_donor
from .preview import generate_preview
from .sources import BUILD_ERRORS, ROOT, WEIGHTS, load_source, normalize_transform, resolve_file, sha256

DONORS = "donors"
# Korean is all the donor is allowed to draw here; ASCII always comes from Agave.
SUBSET = frozenset(KOREAN)


def face(path, name):
    with path.open("rb") as stream:
        opentype = stream.read(4) == b"OTTO"
    return {"file": f"{DONORS}/{path.name}", "name": name, "sha256": sha256(path),
            "format": "opentype" if opentype else "truetype"}


def publish_agave(root, offline):
    """Copy the pinned Agave faces and export the metrics the page measures against."""
    config = load_source("agave", root)
    weights = {}
    for weight in WEIGHTS:
        source = resolve_file(config["fonts"][weight], root, offline=offline)
        target = root / "preview" / DONORS / f"agave-{weight}.ttf"
        shutil.copyfile(source, target)
        with TTFont(target) as font:
            cmap = font.getBestCmap()
            widths = {font["hmtx"][cmap[cp]][0] for cp in range(32, 127)}
            if len(widths) != 1:
                raise ValueError("Agave ASCII must be monospaced")
            weights[weight] = face(target, f"tune-agave-{weight}") | {
                "cell": widths.pop(), "upem": font["head"].unitsPerEm,
                "ascent": font["hhea"].ascent, "descent": font["hhea"].descent,
                "line_gap": font["hhea"].lineGap,
                "cap_height": font["OS/2"].sCapHeight, "x_height": font["OS/2"].sxHeight,
            }
    return {"weights": weights}


def publish_donor(source_id, config, weight, root, offline):
    """Save the exact face `merge_font` would import: instanced, unhinted, Korean only."""
    spec = config["fonts"][weight]
    resolved = resolve_file(spec, root, offline=offline)
    font = open_donor(resolved, spec, weight)
    try:
        options = subset.Options()
        options.hinting = False                                  # the build imports outlines only
        options.layout_features = []                             # and carries no Korean layout rules
        options.drop_tables = list(options.drop_tables) + ["DSIG"]
        options.notdef_outline = True
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=SUBSET & font.getBestCmap().keys())
        subsetter.subset(font)
        suffix = ".otf" if "CFF " in font or "CFF2" in font else ".ttf"
        target = root / "preview" / DONORS / f"{source_id}-{weight}{suffix}"
        target.unlink(missing_ok=True)
        font.save(target)
        upem = font["head"].unitsPerEm
    finally:
        font.close()
    return face(target, f"tune-{source_id}-{weight}") | {"upem": upem, "spec": spec}


def preset_fields(source_id, root):
    config = load_source(source_id, root)
    license_info = config["license"]
    return config, {"id": source_id, "name": config["name"], "family": config["family"],
                    "version": config.get("version"), "transform": config["transform"],
                    "redistribute": license_info.get("id") == "OFL-1.1" and license_info.get("redistribute", False)}


def source_entry(source_id, root, offline, previous=None):
    config, entry = preset_fields(source_id, root)
    entry["weights"] = {}
    for weight in WEIGHTS:
        cached = (previous or {}).get("weights", {}).get(weight)
        if cached and cached.get("spec") == config["fonts"][weight] and (root / "preview" / cached["file"]).is_file():
            # Subsetting 11k outlines is the slow part, and the pinned spec identifies the face.
            entry["weights"][weight] = cached
            continue
        print(f"Tune: {source_id} {weight}", flush=True)
        entry["weights"][weight] = publish_donor(source_id, config, weight, root, offline)
    return entry


def read_manifest(root):
    path = root / "preview" / DONORS / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}


def publish_source(source_id, root=ROOT, offline=False):
    """Publish one donor; the page is written separately so one failure keeps the rest."""
    (root / "preview" / DONORS).mkdir(parents=True, exist_ok=True)
    published = read_manifest(root)
    published[source_id] = source_entry(source_id, root, offline, published.get(source_id))
    path = root / "preview" / DONORS / "manifest.json"
    path.write_text(json.dumps({"sources": published}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_tuner(root=ROOT, offline=False):
    (root / "preview" / DONORS).mkdir(parents=True, exist_ok=True)
    # Earlier runs stay comparable, but only while preset and published faces both survive.
    entries = []
    for source_id, entry in sorted(read_manifest(root).items()):
        if not (root / "sources" / f"{source_id}.json").is_file():
            print(f"Tuner drops {source_id}: the preset is gone.")
        elif any(not (root / "preview" / item["file"]).is_file() for item in entry["weights"].values()):
            print(f"Tuner drops {source_id}: a published face is missing; run tune for it again.")
        else:
            # A preset edited since publishing still shows its current transform as the A side.
            entries.append(preset_fields(source_id, root)[1] | {"weights": entry["weights"]})
    published = {entry["id"] for entry in entries}
    presets = [{"id": path.stem, "name": load_source(path.stem, root)["name"], "published": path.stem in published}
               for path in sorted((root / "sources").glob("*.json")) if path.stem != "agave"]
    data = {"agave": publish_agave(root, offline), "sources": entries, "presets": presets}
    manifest = root / "preview" / DONORS / "manifest.json"
    manifest.write_text(json.dumps({"sources": {entry["id"]: entry for entry in entries}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    faces = []
    for item in [face for entry in [data["agave"], *entries] for face in entry["weights"].values()]:
        url = f"{item['file']}?v={item['sha256'][:12]}"
        faces.append(f'@font-face {{font-family: "{item["name"]}"; src: url("{url}") format("{item["format"]}"); font-weight: normal; font-style: normal; font-display: block;}}')
    template = (root / "preview" / "tuner-template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    page = template.replace("/* FONT_FACES */", "\n".join(faces)).replace("/* TUNER_DATA */null", payload)
    target = root / "preview" / "tuner.html"
    target.write_text(page, encoding="utf-8")
    print(f"Tuner: {target} ({len(entries)} sources)")
    return target


def write_transform(root, source_id, transform):
    """Write a tuned transform back into its preset, leaving the rest of the file alone."""
    load_source(source_id, root)            # rejects unknown ids and presets that no longer load
    normalize_transform(transform)          # rejects bad values before the file is touched
    path = root / "sources" / f"{source_id}.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    previous = config.get("transform", {})
    config["transform"] = {key: int(value) if isinstance(value, float) and value.is_integer() else value
                           for key, value in transform.items()}
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return previous


def actions(root, offline, build):
    """The three things the page may do to the project, each on an explicit click."""
    def apply(payload):
        previous = write_transform(root, payload["id"], payload["transform"])
        generate_tuner(root, offline)       # the page reloads into the saved value
        return {"transform": normalize_transform(payload["transform"]), "previous": previous}

    def run_build(payload):
        report = build(payload["id"])
        generate_preview(root)
        return {"transform": report["transform"], "outputs": [
            {key: output[key] for key in ("weight", "overhang_count", "korean_characters", "vertical_bounds")}
            for output in report["outputs"]]}

    def publish(payload):
        publish_source(payload["id"], root, offline)
        generate_tuner(root, offline)
        return {"id": payload["id"]}

    return {"/apply": apply, "/build": run_build, "/publish": publish}


def make_handler(root, token, handlers):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):
            pass                            # the terminal belongs to build output

        def reply(self, status, body):
            encoded = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            handler = handlers.get(self.path)
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or "{}")
                # A local page still has to prove it is this run's page, and only a browser
                # pointed at the loopback address gets to act at all.
                if not handler or not self.headers.get("Host", "").startswith("127.0.0.1"):
                    raise ValueError("Unknown action")
                if not secrets.compare_digest(str(payload.get("token", "")), token):
                    raise ValueError("Stale page: restart the tuner and reload")
                self.reply(200, handler(payload) | {"ok": True})
            except BUILD_ERRORS as error:
                print(f"ERROR [{self.path}]: {error}", flush=True)
                self.reply(400, {"ok": False, "error": str(error)})

    return Handler


def serve(root=ROOT, offline=False, build=None, port=0, open_browser=True):
    token = secrets.token_urlsafe(16)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root, token, actions(root, offline, build)))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/preview/tuner.html?token={token}"
    print(f"Tuner: {url}\nSave and build from the page. Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTuner stopped.")
    finally:
        server.server_close()
    return server
