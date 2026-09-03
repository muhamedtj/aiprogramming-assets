#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_library as base

AUTO = ROOT / "catalog" / "autodiscovery.json"
SOURCES = ROOT / "catalog" / "sources.json"


def textify(body: str) -> str:
    body = re.sub(r"<script\b[^>]*>.*?</script>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<style\b[^>]*>.*?</style>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(body)).strip()


def kind_for(category: str, slug: str) -> str:
    c = category.lower()
    s = slug.lower()
    if "3d" in c:
        return "3d"
    if "audio" in c or any(x in s for x in ("sounds", "music", "audio", "voiceover")):
        return "audio"
    if "texture" in c or any(x in s for x in ("texture", "skybox", "pattern")):
        return "texture"
    if "ui" in c or any(x in s for x in ("ui-", "interface", "input-prompts", "mobile-controls", "icons")):
        return "2d_ui"
    return "2d_vfx"


def bucket_for(kind: str) -> str:
    if kind.startswith("3d"):
        return "3d"
    if kind == "audio":
        return "audio"
    if kind == "texture":
        return "textures"
    if kind == "2d_ui":
        return "ui"
    return "2d"


def theme_for(slug: str) -> str:
    s = slug.lower()
    checks = [
        ("space", ("space", "sci-fi", "alien", "ufo")),
        ("fantasy", ("fantasy", "medieval", "castle", "dungeon", "graveyard", "magic")),
        ("city", ("city", "urban", "road", "building", "factory", "industrial", "suburban")),
        ("nature", ("nature", "forest", "farm", "survival", "island", "cave", "terrain")),
        ("racing", ("racing", "car", "vehicle", "train", "transport", "coaster")),
        ("platformer", ("platformer", "runner")),
        ("pirate", ("pirate", "boat", "ship")),
        ("characters", ("character", "people", "survivor", "protagonist", "pet", "animal")),
        ("core", ("ui", "interface", "icon", "input", "font", "sound")),
    ]
    for theme, words in checks:
        if any(w in s for w in words):
            return theme
    return "general"


def discover_from_slug(slug: str, allowed: set[str]) -> dict | None:
    page = f"https://kenney.nl/assets/{slug}"
    try:
        body = base.fetch_bytes(page, timeout=60).decode("utf-8", errors="replace")
        text = textify(body)
        if "Creative Commons CC0" not in text:
            print(f"skip non-CC0/unconfirmed: {slug}")
            return None
        cat = re.search(r"Category\s+(.+?)\s+(?:Features|Files|License)\s+", text, flags=re.I)
        category = cat.group(1).strip() if cat else ""
        kind = kind_for(category, slug)
        if bucket_for(kind) not in allowed:
            return None
        download_url = base.resolve_official_download({"source_page": page})
        return {
            "id": f"kenney-{slug}",
            "name": slug.replace("-", " ").title(),
            "theme": theme_for(slug),
            "kind": kind,
            "style": "kenney_stylized",
            "source": "Kenney",
            "source_page": page,
            "fallback_url": download_url,
            "license": "CC0-1.0",
            "expected_items": 0,
            "tags": [x for x in slug.split("-") if x],
        }
    except Exception as exc:
        print(f"skip unavailable pack {slug}: {exc}")
        return None


def validate_runtime_pack(pack: dict, cache: Path) -> bool:
    """Download once, cache it, and reject packs that cannot produce web runtime files."""
    pid = pack["id"]
    zip_path = cache / f"{pid}.zip"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
            base.download_pack(pack, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            keep = base.choose_extensions(z, pack)
            runtime_count = 0
            runtime_bytes = 0
            for info in z.infolist():
                if info.is_dir():
                    continue
                ext = Path(info.filename).suffix.lower()
                if ext in keep:
                    runtime_count += 1
                    runtime_bytes += info.file_size
            if runtime_count == 0:
                raise RuntimeError("no usable runtime files")
        print(
            f"validated {pid}: {runtime_count} runtime files, "
            f"{runtime_bytes / 1024 / 1024:.1f} MiB uncompressed"
        )
        return True
    except Exception as exc:
        print(f"skip incompatible pack {pid}: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "downloads")
    ap.add_argument("--zip", action="store_true", dest="make_zip")
    args = ap.parse_args()

    cfg = json.loads(SOURCES.read_text(encoding="utf-8"))
    auto = json.loads(AUTO.read_text(encoding="utf-8"))
    allowed = {x.lower() for x in auto.get("categories", [])}
    existing_slugs = {p["source_page"].rstrip("/").split("/")[-1] for p in cfg["packs"]}
    existing_ids = {p["id"] for p in cfg["packs"]}

    discovered: list[dict] = []
    for slug in auto.get("seed_slugs", []):
        if slug in existing_slugs or f"kenney-{slug}" in existing_ids:
            continue
        pack = discover_from_slug(slug, allowed)
        if pack:
            discovered.append(pack)

    print(f"\nDiscovered {len(discovered)} additional confirmed CC0 packs")

    compatible: list[dict] = []
    for pack in discovered:
        if validate_runtime_pack(pack, args.cache):
            compatible.append(pack)

    print(f"\nAccepted {len(compatible)} additional web-runtime-compatible CC0 packs")
    expanded = dict(cfg)
    expanded["version"] = "0.2"
    expanded["packs"] = cfg["packs"] + compatible
    temp = ROOT / ".cache" / "sources-expanded.json"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(expanded, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.output.exists():
        shutil.rmtree(args.output)

    old_sources = base.SOURCES
    try:
        base.SOURCES = temp
        base.build(args.output, args.cache, selected=None)
    finally:
        base.SOURCES = old_sources

    if args.make_zip:
        archive = shutil.make_archive(
            str(args.output), "zip", root_dir=args.output.parent, base_dir=args.output.name
        )
        print(f"ZIP: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
