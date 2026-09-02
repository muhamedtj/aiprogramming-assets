# AIProgramming Asset Library

Central shared asset registry and build system for AIProgramming Godot/Web student projects.

The Git repository intentionally stays small. Heavy third-party binaries are downloaded during a GitHub Actions build and packaged into a versioned ZIP artifact/release.

## v0.1 contents

The starter registry contains 12 CC0 Kenney packs covering:

- nature and terrain props;
- city roads, commercial and industrial buildings;
- cars and vehicles;
- animated mini characters;
- modular space and space-station environments;
- UI;
- interface audio;
- skyboxes;
- light/VFX masks.

The source pages currently declare Creative Commons CC0. Build provenance records the exact source URL and SHA-256 used for each archive.

## Build the real library in GitHub

1. Open **Actions**.
2. Choose **Build AIProgramming Asset Library**.
3. Click **Run workflow**.
4. Wait for the build to finish.
5. Download artifact **aiprogramming-assets-v0.1**.

The workflow refuses to pass if the generated library has fewer than 500 catalogued runtime assets or the ZIP is suspiciously small.

## How it works

```text
catalog/sources.json
        ↓
resolve current official Kenney ZIP URLs
        ↓
download source packs
        ↓
keep Web/Godot-friendly runtime formats
(GLB, PNG/WebP/JPG, OGG/WAV, fonts)
        ↓
generate catalog.generated.json + provenance
        ↓
aiprogramming-assets-v0.1.zip
```

For 3D packs the builder prefers GLB and intentionally does not duplicate FBX/OBJ/DAE/STL source formats.

## Student project manifest

A student project should not contain the whole library. It declares only the packs it needs:

```json
{
  "library_version": "0.1",
  "packs": ["nature", "characters", "ui"]
}
```

The sync/build process downloads only those approved packs into the temporary project workspace before the Godot Web export.

## Repository layout

```text
catalog/                 approved source registry and schemas
scripts/                 build, verification and project-sync tools
examples/                example student manifest
licenses/                policy and source audit
.github/workflows/       GitHub Actions build/release workflows
```

See `AGENTS.md` for Codex/agent rules and `LICENSE_POLICY.md` for the redistribution policy.
