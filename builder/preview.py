"""Generate a framework-free comparison page from verified build manifests."""

import json

from .sources import ROOT, sha256


def generate_preview(root=ROOT):
    entries = []
    faces = []
    for path in sorted((root / "build").glob("*/build.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        files = {item["weight"]: item for item in report["outputs"]}
        if set(files) != {"regular", "bold"}:
            continue
        if any(not (path.parent / item["file"]).is_file() or sha256(path.parent / item["file"]) != item["sha256"] for item in files.values()):
            print(f"Preview skips incomplete/modified build: {path.parent.name}")
            continue
        css_family = f"comparison-{len(entries)}"
        entry = {key: report[key] for key in ("id", "name", "family", "transform", "redistribute")}
        entry.update(css_family=css_family, outputs=report["outputs"])
        for weight, item in files.items():
            url = f"../build/{report['id']}/{item['file']}?v={item['sha256'][:12]}"
            entry[weight] = url
            faces.append(f'@font-face {{font-family: "{css_family}"; src: url("{url}") format("truetype"); font-weight: {700 if weight == "bold" else 400}; font-style: normal; font-display: block;}}')
        entries.append(entry)
    template = (root / "preview" / "template.html").read_text(encoding="utf-8")
    data = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c")
    page = template.replace("/* FONT_FACES */", "\n".join(faces)).replace("/* FONT_DATA */[]", data)
    target = root / "preview" / "index.html"
    target.write_text(page, encoding="utf-8")
    print(f"Preview: {target} ({len(entries)} sources)")
    return target
