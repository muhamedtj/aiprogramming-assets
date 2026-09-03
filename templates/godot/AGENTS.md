# AIProgramming Student Project Rules

## Engine
- Godot 4.7.x.
- GDScript only. Do not use C#.
- Target platform is Web browser.
- Keep the Compatibility renderer enabled.
- Do not enable Web threads unless explicitly requested.

## Asset library
- Shared assets come from `muhamedtj/aiprogramming-assets` release `assets-v0.2`.
- `assets.json` is the source of truth for which packs this project uses.
- Generated files live under `res://assets/aiprogramming/` and must not be committed.
- Before creating placeholder geometry or drawing temporary art, search the AIProgramming asset library for an appropriate existing pack.
- Prefer assets that share the same visual style/theme.
- When adding a new pack, update `assets.json`, then run:
  `python tools/sync_assets.py`
- Read `assets/aiprogramming/catalog.selected.json` after syncing to locate exact asset paths.

## Project behavior
- Preserve existing working mechanics unless the task explicitly changes them.
- Keep scripts small and readable for children aged approximately 8–10.
- Prefer editable parameters near the top of scripts for speed, jump force, score targets, spawn intervals, etc.
- Use clear node and file names.

## Verification before committing
1. Sync requested assets.
2. Run Godot headless import and check for parse errors.
3. Ensure the Web export succeeds.
4. Never commit `.godot/`, `build/`, `.aiprogramming-cache/`, or generated asset binaries.
