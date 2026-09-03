#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REQUIRED_THEMES = {
    "nature",
    "city",
    "space",
    "fantasy",
    "racing",
    "platformer",
    "characters",
    "core",
}

REQUIRED_KIND_GROUPS = {
    "3d": {"3d", "3d_animated"},
    "2d": {"2d_vfx"},
    "ui": {"2d_ui"},
    "audio": {"audio"},
    "textures": {"texture"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("library_dir", type=Path)
    ap.add_argument("--min-assets", type=int, default=3000)
    ap.add_argument("--min-packs", type=int, default=30)
    ap.add_argument("--min-themes", type=int, default=8)
    ap.add_argument("--min-kind-groups", type=int, default=4)
    args = ap.parse_args()

    root = args.library_dir
    catalog_path = root / "catalog.generated.json"
    provenance_path = root / "PROVENANCE.json"

    if not catalog_path.exists() or not provenance_path.exists():
        print("ERROR: catalog/provenance missing")
        return 1

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assets = catalog.get("assets", [])

    themes = Counter((a.get("theme") or "unknown") for a in assets)
    kinds = Counter((a.get("kind") or "unknown") for a in assets)
    packs = Counter((a.get("pack_id") or "unknown") for a in assets)

    kind_groups_present = set()
    for group, members in REQUIRED_KIND_GROUPS.items():
        if any(kinds.get(k, 0) > 0 for k in members):
            kind_groups_present.add(group)

    required_theme_hits = REQUIRED_THEMES.intersection(themes)

    print(f"Assets: {len(assets)}")
    print(f"Packs with runtime assets: {len(packs)}")
    print(f"Themes: {len(themes)} -> {dict(themes.most_common())}")
    print(f"Kinds: {dict(kinds.most_common())}")
    print(f"Required themes present: {sorted(required_theme_hits)}")
    print(f"Kind groups present: {sorted(kind_groups_present)}")

    errors: list[str] = []
    if len(assets) < args.min_assets:
        errors.append(f"only {len(assets)} assets; need >= {args.min_assets}")
    if len(packs) < args.min_packs:
        errors.append(f"only {len(packs)} runtime packs; need >= {args.min_packs}")
    if len(themes) < args.min_themes:
        errors.append(f"only {len(themes)} themes; need >= {args.min_themes}")
    if len(kind_groups_present) < args.min_kind_groups:
        errors.append(
            f"only {len(kind_groups_present)} kind groups; need >= {args.min_kind_groups}"
        )

    # Strong content requirements for useful student game projects.
    if not {"nature", "city", "space", "fantasy"}.issubset(themes):
        errors.append("missing one or more core worlds: nature/city/space/fantasy")
    if "characters" not in themes:
        errors.append("missing character-focused assets")
    if "core" not in themes:
        errors.append("missing core UI/audio assets")
    if not any(kinds.get(k, 0) for k in ("3d", "3d_animated")):
        errors.append("missing 3D runtime assets")
    if kinds.get("2d_ui", 0) == 0:
        errors.append("missing UI assets")
    if kinds.get("audio", 0) == 0:
        errors.append("missing audio assets")

    if errors:
        print("ERROR: library is not rich enough:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("OK: library coverage is sufficiently broad for AIProgramming student projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
