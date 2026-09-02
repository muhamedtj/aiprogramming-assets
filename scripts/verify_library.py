#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("library_dir", type=Path)
    ap.add_argument("--min-assets", type=int, default=500)
    ap.add_argument("--min-size-mib", type=float, default=0)
    args = ap.parse_args()

    root = args.library_dir
    catalog_path = root / "catalog.generated.json"
    if not catalog_path.exists():
        print("ERROR: catalog.generated.json missing")
        return 1

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    missing: list[str] = []
    duplicate: list[str] = []
    empty: list[str] = []

    for asset in data.get("assets", []):
        aid = asset["asset_id"]
        if aid in ids:
            duplicate.append(aid)
        ids.add(aid)
        path = root / asset["path"]
        if not path.exists():
            missing.append(asset["path"])
        elif path.stat().st_size == 0:
            empty.append(asset["path"])

    if len(ids) < args.min_assets:
        print(f"ERROR: only {len(ids)} assets; expected at least {args.min_assets}")
        return 1
    if duplicate or missing or empty:
        print("ERROR: library integrity check failed")
        if duplicate:
            print("duplicate ids:", duplicate[:20])
        if missing:
            print("missing files:", missing[:20])
        if empty:
            print("empty files:", empty[:20])
        return 1

    total_bytes = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    total_mib = total_bytes / 1024 / 1024
    if total_mib < args.min_size_mib:
        print(f"ERROR: library is only {total_mib:.1f} MiB; expected at least {args.min_size_mib:.1f} MiB")
        return 1

    print(f"OK: {len(ids)} catalogued assets; {total_mib:.1f} MiB extracted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
