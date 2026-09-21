"""JSON presets and cached, pinned official downloads."""

import hashlib
import json
import math
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import py7zr

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ("regular", "bold")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path must stay inside {root}: {value}")
    return path


def load_source(source_id, root=ROOT):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id):
        raise ValueError(f"Invalid source id: {source_id}")
    path = root / "sources" / f"{source_id}.json"
    if not path.is_file():
        raise ValueError(f"Unknown source {source_id}; run: python -m builder list")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("id") != source_id:
        raise ValueError(f"{path}: id must match filename")
    if set(config["fonts"]) != set(WEIGHTS):
        raise ValueError(f"{path}: exactly regular and bold are required")
    if not re.fullmatch(r"[A-Za-z0-9 ]{1,45}", config["family"]) or not config["family"].strip():
        raise ValueError("family must be 1–45 ASCII letters, numbers or spaces")
    transform = config.get("transform", {})
    if set(transform) - {"scale", "x_offset", "y_offset"}:
        raise ValueError("Unknown transform option")
    for key, default in (("scale", 1.0), ("x_offset", 0), ("y_offset", 0)):
        value = transform.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"transform.{key} must be finite")
        if key == "scale" and value <= 0:
            raise ValueError("transform.scale must be positive")
        transform[key] = value
    config["transform"] = transform
    license_info = config["license"]
    if not isinstance(license_info.get("redistribute", False), bool):
        raise ValueError("license.redistribute must be true or false")
    if license_info.get("redistribute") and license_info.get("id") != "OFL-1.1":
        raise ValueError("Only reviewed OFL-1.1 presets may set redistribute=true")
    for spec in config["fonts"].values():
        if len({"local", "url", "github"} & spec.keys()) != 1:
            raise ValueError("Each font needs exactly one of local, url, github")
    for reserved in license_info.get("reserved_names", []):
        if reserved.lower() in config["family"].lower():
            raise ValueError(f"family uses Reserved Font Name: {reserved}")
    if license_info.get("id") != "OFL-1.1" or not license_info.get("redistribute", False):
        if any("local" not in spec for spec in config["fonts"].values()):
            raise ValueError("Unreviewed/restricted fonts must use local files")
    return config


def download(spec, root=ROOT, offline=False):
    """Release assets use stable tag URLs; no GitHub API token is needed."""
    if "github" in spec:
        gh = spec["github"]
        url = f"https://github.com/{gh['repo']}/releases/download/{gh['tag']}/{gh['asset']}"
    else:
        url = spec["url"]
    if not url.startswith("https://"):
        raise ValueError("Downloads require HTTPS")
    digest = spec.get("sha256")
    if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("sha256 must be a lowercase SHA-256 hex digest")
    key = hashlib.sha256(url.encode()).hexdigest()
    path = root / ".cache" / "downloads" / key
    if path.is_file():
        if digest and sha256(path) != digest:
            raise ValueError(f"Cached SHA-256 mismatch: {path}; remove that file and retry")
        return path
    if offline:
        raise ValueError(f"Not cached (offline): {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Download: {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "agave-korean-builder/0.1"})
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                shutil.copyfileobj(response, stream)
            stream.close()
            if digest and sha256(temporary) != digest:
                raise ValueError(f"Downloaded SHA-256 mismatch: {url}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def resolve_file(spec, root=ROOT, offline=False):
    if "local" in spec:
        path = relative_path(root / "fonts" / "local", spec["local"])
        if not path.is_file():
            raise ValueError(f"Missing local file: {path}. See README / source config.")
        return path
    archive = download(spec, root, offline)
    if "member" not in spec:
        return archive
    member = spec["member"]
    parts = PurePosixPath(member)
    if parts.is_absolute() or ".." in parts.parts or "\\" in member:
        raise ValueError(f"Unsafe archive member: {member}")
    # Fingerprint the archive, so replacing it cannot leave stale extracted data.
    directory = root / ".cache" / "extracted" / sha256(archive)
    target = relative_path(directory, member)
    if target.is_file():
        return target
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as scratch:
        if spec.get("archive") == "7z":
            with py7zr.SevenZipFile(archive) as package:
                if member not in package.getnames():
                    raise ValueError(f"Archive has no member: {member}")
                entry = next(x for x in package.list() if x.filename == member)
                if entry.is_directory or entry.is_symlink:
                    raise ValueError(f"Not a regular archive file: {member}")
                package.extract(path=scratch, targets=[member])
        elif spec.get("archive") == "zip":
            with zipfile.ZipFile(archive) as package:
                info = package.getinfo(member)
                if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"Not a regular archive file: {member}")
                package.extract(member, scratch)
        else:
            raise ValueError("archive must be zip or 7z")
        extracted = relative_path(Path(scratch), member)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(extracted, target)
    return target


def license_files(config, root=ROOT, offline=False):
    info = config["license"]
    specs = info.get("files", [])
    if info.get("redistribute") and not specs:
        raise ValueError("Redistributable presets require complete license files")
    return [resolve_file(spec, root, offline) for spec in specs]
