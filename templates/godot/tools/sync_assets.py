#!/usr/bin/env python3
"""Sync only requested AIProgramming packs into a Godot project.

Works with public releases without a token. For a private asset repository set
AIPROGRAMMING_ASSETS_TOKEN (or GH_TOKEN) in the environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile

DEFAULT_REPO = "muhamedtj/aiprogramming-assets"
DEFAULT_TAG = "assets-v0.2"


def request_json(url: str, token: str | None = None) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AIProgramming-Godot-Asset-Sync/0.2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def download_release_asset(asset: dict, dest: Path, token: str | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if token:
        url = asset["url"]
        headers = {
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "User-Agent": "AIProgramming-Godot-Asset-Sync/0.2",
        }
    else:
        url = asset["browser_download_url"]
        headers = {"User-Agent": "AIProgramming-Godot-Asset-Sync/0.2"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(zip_path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        root = target.resolve()
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            dest = (target / rel).resolve()
            if root not in dest.parents and dest != root:
                raise RuntimeError(f"Unsafe path in archive: {info.filename}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("assets.json"))
    ap.add_argument("--target", type=Path, default=Path("assets/aiprogramming"))
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--tag", default=DEFAULT_TAG)
    ap.add_argument("--cache", type=Path, default=Path(".aiprogramming-cache"))
    args = ap.parse_args()

    token = os.getenv("AIPROGRAMMING_ASSETS_TOKEN") or os.getenv("GH_TOKEN")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    requested = list(dict.fromkeys(manifest.get("packs", [])))
    if not requested:
        print("No AIProgramming packs requested in assets.json")
        return 0

    release = request_json(f"https://api.github.com/repos/{args.repo}/releases/tags/{args.tag}", token)
    release_assets = {a["name"]: a for a in release.get("assets", [])}
    if "release-index.json" not in release_assets:
        raise RuntimeError("Release does not contain release-index.json")

    args.cache.mkdir(parents=True, exist_ok=True)
    index_path = args.cache / "release-index.json"
    download_release_asset(release_assets["release-index.json"], index_path, token)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    pack_index = {p["pack_id"]: p for p in index.get("packs", [])}

    missing = [p for p in requested if p not in pack_index]
    if missing:
        raise RuntimeError(f"Unknown packs in assets.json: {', '.join(missing)}")

    # Replace the generated asset directory atomically enough for CI/local development.
    staging = args.target.parent / f".{args.target.name}-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    lock_packs = []
    combined_assets = []

    for pid in requested:
        meta = pack_index[pid]
        zip_name = meta["archive"]
        catalog_name = meta["catalog"]
        if zip_name not in release_assets or catalog_name not in release_assets:
            raise RuntimeError(f"Release is missing files for pack {pid}")

        zip_path = args.cache / zip_name
        if not zip_path.exists() or sha256(zip_path) != meta["sha256"]:
            print(f"Downloading {pid} ...")
            download_release_asset(release_assets[zip_name], zip_path, token)
        actual_sha = sha256(zip_path)
        if actual_sha != meta["sha256"]:
            raise RuntimeError(f"SHA256 mismatch for {pid}: expected {meta['sha256']}, got {actual_sha}")

        safe_extract(zip_path, staging)

        pack_catalog_path = args.cache / catalog_name
        download_release_asset(release_assets[catalog_name], pack_catalog_path, token)
        pack_catalog = json.loads(pack_catalog_path.read_text(encoding="utf-8"))
        combined_assets.extend(pack_catalog.get("assets", []))

        lock_packs.append({
            "pack_id": pid,
            "archive": zip_name,
            "sha256": actual_sha,
            "asset_count": meta["asset_count"],
        })

    if args.target.exists():
        shutil.rmtree(args.target)
    staging.rename(args.target)

    (args.target / "catalog.selected.json").write_text(json.dumps({
        "library_version": index.get("version"),
        "asset_count": len(combined_assets),
        "assets": combined_assets,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    Path("assets.lock.json").write_text(json.dumps({
        "repo": args.repo,
        "tag": args.tag,
        "library_version": index.get("version"),
        "packs": lock_packs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Synced {len(requested)} packs / {len(combined_assets)} assets into {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
