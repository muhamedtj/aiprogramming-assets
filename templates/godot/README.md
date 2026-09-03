# AIProgramming Godot Student Template

This folder is intended to become the root of each student project repository.

## What is already configured
- Godot 4.7.x project.
- Compatibility renderer for WebGL/Web export.
- Web export preset with thread support disabled.
- `assets.json` manifest for the shared AIProgramming asset library.
- `tools/sync_assets.py` downloads only requested packs from the shared release.
- GitHub Actions builds the Godot Web export and deploys it to GitHub Pages.
- `AGENTS.md` tells Codex how to work with the project safely.

## Asset workflow
1. Add approved pack IDs to `assets.json`.
2. Run `python tools/sync_assets.py`.
3. Generated assets appear in `assets/aiprogramming/`.
4. `assets.lock.json` records the exact archive SHA256 used.
5. Generated binaries are ignored by Git; CI downloads them again before building.

## Private asset repository
If `muhamedtj/aiprogramming-assets` remains private, each student repository needs the Actions secret:

`AIPROGRAMMING_ASSETS_TOKEN`

The token needs read access to the asset repository only. If the asset library is later made public, this secret is no longer required.

## GitHub Pages
In the student repository open:

Settings -> Pages -> Build and deployment -> Source -> GitHub Actions

Then push to `main` or run the workflow manually.

## Project rule
The student interacts with ChatGPT. GitHub, asset synchronization, Godot export and deployment remain implementation details managed by the AIProgramming system/teacher.
