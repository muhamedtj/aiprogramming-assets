#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "catalog" / "sources.json"
TEXT_KEEP = {"license.txt", "readme.txt", "instructions.txt"}
CATALOG_EXTS = {".glb", ".gltf", ".png", ".webp", ".jpg", ".jpeg", ".ogg", ".wav", ".ttf", ".otf", ".hdr", ".exr"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(value: str) -> str:
    value = value.lower().replace("\\", "/")
    value = re.sub(r"[^a-z0-9._/-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-./")


def asset_id(pack_id: str, rel: str) -> str:
    stem = safe_name(str(Path(rel).with_suffix(""))).replace("/", "_").replace("-", "_")
    stem = re.sub(r"_+", "_", stem).strip("_")
    return f"AP_{pack_id.upper().replace('-', '_')}_{stem.upper()}"


def tokenize(pack: dict, rel: str) -> list[str]:
    text = f"{pack['id']} {pack.get('name','')} {pack.get('theme','')} {' '.join(pack.get('tags', []))} {rel}"
    toks = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"format", "models", "model", "png", "glb", "gltf", "audio", "files", "file", "kenney"}
    return sorted({t for t in toks if len(t) > 1 and t not in stop})


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 AIProgramming-Asset-Builder/0.1",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def resolve_official_download(pack: dict) -> str:
    """Resolve the current ZIP from a Kenney asset page.

    Kenney changes hashed media URLs over time, so the registry stores the stable
    asset page rather than a brittle direct ZIP URL.
    """
    page = pack["source_page"]
    body = fetch_bytes(page, timeout=60).decode("utf-8", errors="replace")
    body = html.unescape(body)
    candidates = re.findall(r'''(?:href|data-url)=["']([^"']+\.zip(?:\?[^"']*)?)["']''', body, flags=re.I)
    if not candidates:
        candidates = re.findall(r'''(https?://[^"'<>\s]+\.zip(?:\?[^"'<>\s]*)?)''', body, flags=re.I)
    if not candidates:
        raise RuntimeError(f"Could not locate a ZIP download on {page}")
    preferred = [u for u in candidates if "kenney.nl/media/pages/assets/" in u]
    url = preferred[0] if preferred else candidates[0]
    return urllib.parse.urljoin(page, url)


def download_pack(pack: dict, dst: Path, retries: int = 3) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []
    try:
        urls.append(resolve_official_download(pack))
    except Exception as exc:
        print(f"    official URL resolution failed: {exc}")
    fallback = pack.get("fallback_url")
    if fallback:
        urls.append(fallback)
    if not urls:
        raise RuntimeError(f"No download source available for {pack['id']}")

    last_error: Exception | None = None
    for url in dict.fromkeys(urls):
        for attempt in range(1, retries + 1):
            try:
                print(f"    download: {url}")
                payload = fetch_bytes(url, timeout=180)
                dst.write_bytes(payload)
                if not zipfile.is_zipfile(dst):
                    raise RuntimeError(f"Downloaded file is not a ZIP ({len(payload)} bytes)")
                return url
            except Exception as exc:
                last_error = exc
                if dst.exists():
                    dst.unlink()
                if attempt < retries:
                    time.sleep(attempt * 2)
        print(f"    source failed, trying fallback if available: {last_error}")
    raise RuntimeError(f"Download failed for {pack['id']}: {last_error}")


def choose_extensions(z: zipfile.ZipFile, pack: dict) -> set[str]:
    names = [Path(i.filename).suffix.lower() for i in z.infolist() if not i.is_dir()]
    available = set(names)
    kind = pack.get("kind", "")
    if kind.startswith("3d"):
        if ".glb" in available:
            return {".glb"}
        if ".gltf" in available:
            return {".gltf", ".bin", ".png", ".jpg", ".jpeg"}
        raise RuntimeError(f"{pack['id']} has no GLB/glTF files; refusing source-only 3D formats")
    if kind == "audio":
        return {".ogg"} if ".ogg" in available else {".wav"}
    if kind == "2d_ui":
        return {".png", ".webp", ".jpg", ".jpeg", ".ttf", ".otf"}
    if kind in {"2d_vfx", "texture"}:
        return {".png", ".webp", ".jpg", ".jpeg", ".hdr", ".exr"}
    return {".png", ".webp", ".jpg", ".jpeg", ".ogg", ".wav", ".ttf", ".otf"}


def safe_extract_selected(z: zipfile.ZipFile, dest: Path, pack: dict) -> list[Path]:
    keep = choose_extensions(z, pack)
    out: list[Path] = []
    for info in z.infolist():
        if info.is_dir():
            continue
        raw = info.filename.replace("\\", "/")
        p = Path(raw)
        if p.is_absolute() or ".." in p.parts:
            continue
        lower_name = p.name.lower()
        ext = p.suffix.lower()
        if ext not in keep and lower_name not in TEXT_KEEP:
            continue
        if lower_name in {"desktop.ini", ".ds_store", "thumbs.db"}:
            continue
        rel = Path(*[(safe_name(part) or "item") for part in p.parts])
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        out.append(target)
    return out


def build(output: Path, cache: Path, selected: set[str] | None = None) -> None:
    cfg = json.loads(SOURCES.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "packs").mkdir(exist_ok=True)
    (output / "licenses").mkdir(exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    catalog: list[dict] = []
    provenance: list[dict] = []

    for pack in cfg["packs"]:
        pid = pack["id"]
        if selected and pid not in selected:
            continue
        print(f"\n==> {pid}: {pack['name']}")
        zip_path = cache / f"{pid}.zip"
        source_url = "cache"
        if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
            source_url = download_pack(pack, zip_path)
        zip_sha = sha256_file(zip_path)
        pack_dest = output / "packs" / pid
        if pack_dest.exists():
            shutil.rmtree(pack_dest)
        pack_dest.mkdir(parents=True)

        with zipfile.ZipFile(zip_path) as z:
            extracted = safe_extract_selected(z, pack_dest, pack)

        license_text = (
            f"AIProgramming pack: {pid}\n"
            f"Source: {pack['source']}\n"
            f"Source page: {pack['source_page']}\n"
            f"Downloaded from: {source_url}\n"
            f"Declared license: {pack['license']}\n"
            f"Archive SHA256: {zip_sha}\n"
        )
        (output / "licenses" / f"{pid}.txt").write_text(license_text, encoding="utf-8")

        file_count = 0
        for file in extracted:
            if file.name.lower() in TEXT_KEEP or file.suffix.lower() not in CATALOG_EXTS:
                continue
            rel_in_pack = str(file.relative_to(pack_dest))
            rel = file.relative_to(output).as_posix()
            ext = file.suffix.lower().lstrip(".")
            catalog.append({
                "asset_id": asset_id(pid, rel_in_pack),
                "pack_id": pid,
                "name": file.stem,
                "theme": pack.get("theme"),
                "style": pack.get("style"),
                "kind": pack.get("kind"),
                "path": rel,
                "format": ext,
                "size_bytes": file.stat().st_size,
                "sha256": sha256_file(file),
                "tags": tokenize(pack, rel_in_pack),
                "source": pack["source"],
                "source_page": pack["source_page"],
                "license": pack["license"],
                "web_ready": True,
            })
            file_count += 1

        provenance.append({
            "pack_id": pid,
            "archive_sha256": zip_sha,
            "source_page": pack["source_page"],
            "download_url": source_url,
            "license": pack["license"],
            "runtime_files": file_count,
        })
        print(f"    runtime files catalogued: {file_count}")

    generated = {
        "library": cfg["library"],
        "version": cfg["version"],
        "default_style": cfg.get("default_style"),
        "asset_count": len(catalog),
        "assets": catalog,
    }
    (output / "catalog.generated.json").write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "PROVENANCE.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "BUILD_INFO.json").write_text(json.dumps({
        "library": cfg["library"],
        "version": cfg["version"],
        "asset_count": len(catalog),
        "packs": len(provenance),
    }, indent=2), encoding="utf-8")
    print(f"\nBuilt {len(catalog)} runtime assets in {output}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / "dist" / "aiprogramming-assets-v0.1")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "downloads")
    ap.add_argument("--packs", default="", help="Comma-separated pack ids; empty = all")
    ap.add_argument("--zip", action="store_true", dest="make_zip")
    args = ap.parse_args()
    selected = {x.strip() for x in args.packs.split(",") if x.strip()} or None
    build(args.output, args.cache, selected)
    if args.make_zip:
        archive = shutil.make_archive(str(args.output), "zip", root_dir=args.output.parent, base_dir=args.output.name)
        print(f"ZIP: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
