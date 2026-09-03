#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_library as base
import build_library_large as discover

CONFIG = ROOT / "catalog" / "gamemaker.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "gamemaker-downloads")
    ap.add_argument("--zip", action="store_true", dest="make_zip")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    allowed = {x.lower() for x in cfg.get("categories", ["2d", "ui", "audio", "textures"])}

    packs: list[dict] = []
    seen: set[str] = set()

    for slug in cfg.get("seed_slugs", []):
        pack = discover.discover_from_slug(slug, allowed)
        if not pack:
            continue
        if pack.get("kind", "").startswith("3d"):
            continue
        if pack["id"] in seen:
            continue
        seen.add(pack["id"])
        packs.append(pack)

    if not packs:
        raise SystemExit("No GameMaker-compatible CC0 packs were discovered")

    print(f"Accepted {len(packs)} GameMaker-compatible CC0 packs")

    runtime_cfg = {
        "schema_version": 1,
        "library": cfg.get("library", "AIProgramming GameMaker Assets"),
        "version": cfg.get("version", "0.1"),
        "default_style": "kenney_2d",
        "packs": packs,
    }

    temp = ROOT / ".cache" / "gamemaker-sources-expanded.json"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(runtime_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    old_sources = base.SOURCES
    try:
        base.SOURCES = temp
        base.build(args.output, args.cache, selected=None)
    finally:
        base.SOURCES = old_sources

    # Add a GameMaker-specific manifest that a future importer/Codex workflow can read.
    catalog_path = args.output / "catalog.generated.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    gm_manifest = {
        "library": runtime_cfg["library"],
        "version": runtime_cfg["version"],
        "engine": "GameMaker",
        "preferred_sprite_formats": ["png", "webp", "jpg", "jpeg", "gif"],
        "preferred_audio_formats": ["ogg", "wav", "mp3"],
        "asset_count": catalog.get("asset_count", 0),
        "packs": [
            {
                "pack_id": p["id"],
                "name": p["name"],
                "theme": p.get("theme"),
                "kind": p.get("kind"),
                "source_page": p["source_page"],
                "license": p["license"],
            }
            for p in packs
        ],
    }
    (args.output / "GAMEMAKER_MANIFEST.json").write_text(
        json.dumps(gm_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.make_zip:
        archive = shutil.make_archive(
            str(args.output), "zip", root_dir=args.output.parent, base_dir=args.output.name
        )
        print(f"ZIP: {archive}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
