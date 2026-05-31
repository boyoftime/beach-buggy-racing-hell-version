# Beach Buggy Racing — Hell Version

A modding project for **Beach Buggy Racing 1** (Android, `com.vectorunit.purple.googleplay`).
It re-skins the game with a dark "hell / zombie / volcanic" theme and overhauls the
career AI into a brutal, fast, boss-grade challenge.

> This repo contains the **modding scripts and build history only**. Game assets, APKs,
> and signing keys are intentionally **not** published. Grab the playable build from the
> [Releases](../../releases) page.

## What the mod does

**Visuals**
- Zombie blood-wound character skins (vivid, readable, heavy gore)
- Edited UI: track / series / champ selection icons and in-race HUD art
- Lava / volcanic world theme, hell props

**Gameplay / AI**
- Career opponents driven at boss-grade speed and aggression
- Uniform "super-boost" so the whole grid stays floored (no rubber-band rabbit)
- Elite bosses: relentless powerup/ability use, perfect precision, much harder to beat

See [`VERSION_HISTORY.txt`](VERSION_HISTORY.txt) for the full v1 → v46 changelog.

## Build pipeline

The game packs all data into a single `assets/Assets.apf` archive. The flow
(scripts live in `Master bbr afp cracker/`):

1. `1_extract.py` — decode `Assets.apf` → `extracted/` (DBs become `.bin.json`)
2. edit data / textures (the `make_v*.py` scripts apply each version's changes)
3. `3_pack.py` — rebuild `output/Assets.apf` (picks up edits by mtime)
4. `4_build_apk.py <source.apk> --out <signed.apk>` — swap the APF in, zipalign, sign

Every build is signed with the same key so it installs as an in-place update
(`adb install -r`) with no save-data loss.

## Disclaimer

Educational / personal modding project. Beach Buggy Racing is © Vector Unit.
No game assets are redistributed here.
