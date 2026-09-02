#!/usr/bin/env python3
"""Download only approved packs requested by a Godot project's assets.json."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_library import build  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "downloads")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    packs = set(manifest.get("packs", []))
    if not packs:
        print("No packs requested")
        return 0

    temp = args.target.parent / ".aiprogramming-sync-temp"
    if temp.exists():
        shutil.rmtree(temp)
    build(temp, args.cache, packs)

    args.target.mkdir(parents=True, exist_ok=True)
    for pid in packs:
        src = temp / "packs" / pid
        if not src.exists():
            raise RuntimeError(f"Unknown or unavailable pack: {pid}")
        dst = args.target / "packs" / pid
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)

    shutil.copy2(temp / "catalog.generated.json", args.target / "catalog.generated.json")
    shutil.copy2(temp / "PROVENANCE.json", args.target / "PROVENANCE.json")
    shutil.rmtree(temp)
    print(f"Synced {len(packs)} packs to {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
