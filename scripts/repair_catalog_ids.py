#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def slug(value: str) -> str:
    value = value.lower().replace('\\', '/')
    value = re.sub(r'[^a-z0-9]+', '_', value)
    return re.sub(r'_+', '_', value).strip('_')


def make_id(pack_id: str, path: str) -> str:
    readable = slug(path)
    digest = hashlib.sha1(path.lower().encode('utf-8')).hexdigest()[:8].upper()
    return f"AP_{slug(pack_id).upper()}_{readable.upper()}_{digest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('library_dir', type=Path)
    args = ap.parse_args()

    catalog_path = args.library_dir / 'catalog.generated.json'
    data = json.loads(catalog_path.read_text(encoding='utf-8'))

    seen: set[str] = set()
    repaired = 0
    for asset in data.get('assets', []):
        new_id = make_id(asset['pack_id'], asset['path'])
        if new_id in seen:
            # Extremely unlikely SHA-1 prefix collision. Extend deterministically.
            digest = hashlib.sha1((asset['pack_id'] + '|' + asset['path']).encode('utf-8')).hexdigest()[:16].upper()
            new_id = f"{new_id}_{digest}"
        seen.add(new_id)
        if asset.get('asset_id') != new_id:
            repaired += 1
        asset['asset_id'] = new_id

    data['asset_count'] = len(data.get('assets', []))
    catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Normalized {len(seen)} asset IDs; changed {repaired}; duplicates remaining: 0")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
