import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from .merge import merge_font, validate_font
from .preview import generate_preview
from .sources import BUILD_ERRORS, ROOT, TRANSFORM_KEYS, WEIGHTS, apply_overrides, license_files, load_source, resolve_file, sha256
from .tune import generate_tuner, publish_source, serve


def available_sources():
    return [path.stem for path in sorted((ROOT / "sources").glob("*.json")) if path.stem != "agave"]


def build_source(source_id, offline=False, overrides=None):
    if source_id == "agave":
        raise ValueError("agave is the base, not a Korean source")
    config = load_source(source_id)
    if overrides:
        # Tuner values build without editing the preset; build.json records what was used.
        config["transform"] = apply_overrides(config["transform"], overrides)
        print(f"Transform override: {config['transform']}")
    agave = load_source("agave")
    # Resolve everything before touching the last successful build.
    sources = {weight: resolve_file(config["fonts"][weight], offline=offline) for weight in WEIGHTS}
    bases = {weight: resolve_file(agave["fonts"][weight], offline=offline) for weight in WEIGHTS}
    licenses = [("Agave", p) for p in license_files(agave, offline=offline)]
    licenses += [(source_id, p) for p in license_files(config, offline=offline)]
    texts = [p.read_text(encoding="utf-8") for _, p in licenses]
    redistributable = config["license"].get("id") == "OFL-1.1" and config["license"].get("redistribute", False)
    if not redistributable:
        texts.append("LOCAL EXPERIMENT ONLY. Donor rights are not verified. Do not distribute this font or preview. Local access does not grant modification or embedding rights.")
        print("Local experiment: donor rights unverified; do not distribute output or preview.")
    destination = ROOT / "build" / source_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{source_id}-", dir=destination.parent) as scratch:
        staging = Path(scratch)
        outputs = []
        for weight in WEIGHTS:
            print(f"Build: {source_id} {weight}", flush=True)
            output = staging / f"AgaveKorean-{weight.title()}.ttf"
            report = merge_font(bases[weight], sources[weight], output, config, weight, texts)
            report["validation"] = validate_font(output, bases[weight], config["family"], weight)
            outputs.append(report)
            print(f"  PASS: {report['agave_glyphs_preserved']} Agave glyphs preserved; {report['korean_characters']} Korean characters; width {report['ascii_width']}:{report['korean_width']}", flush=True)
            if report["overhang_count"]:
                print(f"  Warning: {report['overhang_count']} Korean outlines extend beyond their cell; reduce scale/x_offset if unintended.")
        license_dir = staging / "LICENSES"
        license_dir.mkdir()
        for i, (name, path) in enumerate(licenses):
            shutil.copyfile(path, license_dir / f"{name}-{i + 1}.txt")
        if not redistributable:
            (staging / "LOCAL-ONLY.txt").write_text(texts[-1] + "\n", encoding="utf-8")
        report = {"id": source_id, "name": config["name"], "family": config["family"], "version": config.get("version"), "transform": config["transform"], "redistribute": redistributable, "config": config, "agave_config": agave, "outputs": outputs}
        (staging / "build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        destination.mkdir(exist_ok=True)
        # Manifest is replaced last; preview verifies hashes and rejects mixed generations.
        for path in sorted(staging.iterdir(), key=lambda p: p.name == "build.json"):
            if path.is_dir():
                shutil.copytree(path, destination / path.name, dirs_exist_ok=True)
            else:
                path.replace(destination / path.name)
    return report


def validate_build(source_id, offline=False):
    directory = ROOT / "build" / source_id
    report = json.loads((directory / "build.json").read_text(encoding="utf-8"))
    if {item["weight"] for item in report["outputs"]} != set(WEIGHTS):
        raise ValueError("Build must contain Regular and Bold")
    for output in report["outputs"]:
        path = directory / output["file"]
        if sha256(path) != output["sha256"]:
            raise ValueError(f"Output hash differs from build manifest: {path}")
        base = resolve_file(report["agave_config"]["fonts"][output["weight"]], offline=offline)
        result = validate_font(path, base, report["family"], output["weight"])
        print(f"{source_id} {output['weight']}: {result}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build normal Agave + Korean; no FontForge required.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "validate", "tune"):
        sub = commands.add_parser(name)
        sub.add_argument("sources", nargs="*")
        sub.add_argument("--all", action="store_true", help="all configured Korean sources (missing local files are errors)")
        sub.add_argument("--offline", action="store_true", help="use cached/local files only")
        if name == "tune":
            sub.add_argument("--no-serve", action="store_true", help="only write preview/tuner.html; do not open it")
            sub.add_argument("--port", type=int, default=0, help="fixed port instead of a free one")
        if name == "build":
            sub.add_argument("--scale", type=float, help="uniform Korean scale, overriding the preset")
            sub.add_argument("--scale-x", type=float, help="horizontal Korean scale (defaults to --scale)")
            sub.add_argument("--scale-y", type=float, help="vertical Korean scale (defaults to --scale)")
            sub.add_argument("--x-offset", type=float, help="Korean x offset in output font units")
            sub.add_argument("--y-offset", type=float, help="Korean y offset in output font units")
    commands.add_parser("list")
    commands.add_parser("preview")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for source_id in available_sources():
                config = load_source(source_id)
                mode = "local" if any("local" in s for s in config["fonts"].values()) else "download"
                print(f"{source_id:22} {config['name']} ({mode})")
            return 0
        if args.command == "preview":
            generate_preview()
            return 0
        if args.all and args.sources:
            parser.error("choose source names OR --all")
        selected = available_sources() if args.all else args.sources or ["sarasa-mono-k"]
        overrides = {key: getattr(args, key) for key in TRANSFORM_KEYS if getattr(args, key, None) is not None}
        if overrides and len(selected) > 1:
            parser.error("transform overrides apply to a single source")
        errors = []
        for source_id in selected:
            try:
                # Validate before resolving any path, but isolate each source's errors.
                load_source(source_id)
                if args.command == "build":
                    build_source(source_id, args.offline, overrides)
                elif args.command == "tune":
                    publish_source(source_id, ROOT, args.offline)
                else:
                    validate_build(source_id, args.offline)
            except BUILD_ERRORS as error:
                errors.append(source_id)
                print(f"ERROR [{source_id}]: {error}", file=sys.stderr)
        if args.command == "build":
            generate_preview()
        if args.command == "tune" and len(errors) < len(selected):
            generate_tuner(ROOT, args.offline)
            if not args.no_serve:
                # The page saves to presets and builds through this process, so it holds the terminal.
                serve(ROOT, args.offline, lambda source_id: build_source(source_id, args.offline), args.port)
        return 1 if errors else 0
    except BUILD_ERRORS as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
