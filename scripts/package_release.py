#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("library", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    root = args.library
    out = args.output
    packs_dir = root / "packs"
    catalog_path = root / "catalog.generated.json"
    provenance_path = root / "PROVENANCE.json"

    if not packs_dir.is_dir() or not catalog_path.exists():
        raise SystemExit("Library is missing packs/ or catalog.generated.json")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else []
    provenance_by_pack = {p["pack_id"]: p for p in provenance}

    assets_by_pack: dict[str, list[dict]] = defaultdict(list)
    for asset in catalog.get("assets", []):
        assets_by_pack[asset["pack_id"]].append(asset)

    pack_records: list[dict] = []
    for pack_dir in sorted(p for p in packs_dir.iterdir() if p.is_dir()):
        pid = pack_dir.name
        pack_assets = assets_by_pack.get(pid, [])
        if not pack_assets:
            continue

        archive_base = out / pid
        archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=packs_dir, base_dir=pid))
        kinds = sorted({str(a.get("kind") or "unknown") for a in pack_assets})
        themes = sorted({str(a.get("theme") or "general") for a in pack_assets})
        styles = sorted({str(a.get("style") or "unknown") for a in pack_assets})
        formats = sorted({str(a.get("format") or "") for a in pack_assets if a.get("format")})
        tags = sorted({t for a in pack_assets for t in a.get("tags", [])})

        mini_catalog = {
            "pack_id": pid,
            "asset_count": len(pack_assets),
            "themes": themes,
            "kinds": kinds,
            "styles": styles,
            "formats": formats,
            "assets": pack_assets,
        }
        mini_name = f"{pid}.catalog.json"
        (out / mini_name).write_text(json.dumps(mini_catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        prov = provenance_by_pack.get(pid, {})
        pack_records.append({
            "pack_id": pid,
            "archive": archive_path.name,
            "catalog": mini_name,
            "asset_count": len(pack_assets),
            "size_bytes": archive_path.stat().st_size,
            "sha256": sha256(archive_path),
            "themes": themes,
            "kinds": kinds,
            "styles": styles,
            "formats": formats,
            "search_terms": tags[:250],
            "source_page": prov.get("source_page"),
            "license": prov.get("license"),
        })

    # Compact index: small enough for ChatGPT/Codex to inspect before deciding what to download.
    release_index = {
        "library": catalog.get("library", "AIProgramming Asset Library"),
        "version": catalog.get("version"),
        "pack_count": len(pack_records),
        "asset_count": sum(p["asset_count"] for p in pack_records),
        "packs": pack_records,
    }
    (out / "release-index.json").write_text(json.dumps(release_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # Full global catalog is useful for exact asset lookup and stays separate from runtime pack downloads.
    shutil.copy2(catalog_path, out / "catalog.generated.json")
    if provenance_path.exists():
        shutil.copy2(provenance_path, out / "PROVENANCE.json")

    print(f"Packaged {len(pack_records)} packs containing {release_index['asset_count']} assets")
    print(f"Release directory: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
