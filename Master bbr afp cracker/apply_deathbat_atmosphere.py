"""Make every level use Death Bat Alley's (LavaA) sky + fog atmosphere.

For each level TEMPLATE (VuTemplateAsset/Levels/*.bin.json):
  - SkyBox01 "Model Asset"            -> Skybox/Skybox_Volcano
  - cube SubstituteAsset "Subst Asset Name" -> HazyOrange_cube
  - GlobalGfxSettings01 fog block      -> LavaA orange-haze values

For each PROJECT (VuProjectAsset/<Level>_<Mode>.bin.json):
  - add the volcano skybox assets to the AssetData dependency lists so they load

Also restores the ORIGINAL skybox base textures (the volcano dome samples
Skybox/BlueSky), undoing the earlier flat-texture paint-over for the sky only.

Originals (the .bin.json files) are backed up under mod_backups/ first.
"""
from __future__ import annotations

import json
import glob
import os
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "extracted" / "Assets"
LEVELS = ASSETS / "VuTemplateAsset" / "Levels"
PROJECTS = ASSETS / "VuProjectAsset"
SKYBOX_TEX = HERE / "extracted" / "Assets" / "VuTextureAsset" / "Skybox"
BACKUP = HERE / "mod_backups" / f"deathbat_atmosphere_{time.strftime('%Y%m%d_%H%M%S')}"

# Most recent texture backup that still holds the ORIGINAL skybox PNGs.
TEX_BACKUP_GLOB = sorted((HERE / "mod_backups").glob(
    "all_maps_lava_theme_*/extracted/Assets/VuTextureAsset/Skybox"))

# ---- LavaA / Death Bat Alley target atmosphere ------------------------------
SKY_MODEL = "Skybox/Skybox_Volcano"
SKY_CUBE = "HazyOrange_cube"

FOG = {
    "Fog Color": {"R": 246, "G": 163, "B": 45, "A": 255},
    "Fog Start": 20,
    "Fog End": 400,
    "Depth Fog Color": {"R": 220, "G": 159, "B": 52, "A": 255},
    "Depth Fog Distance": 6,
    "Depth Fog Start": 200,
    "Camera Far Plane": 400,
    "Pfx Ambient Color": {"R": 192, "G": 138, "B": 100, "A": 255},
    "Pfx Diffuse Color": {"R": 206, "G": 164, "B": 112, "A": 255},
}

# Assets the volcano skybox needs present in each project's dependency table.
DEP_ADD = {
    "VuStaticModelAsset": ["Skybox/Skybox_Volcano"],
    "VuCubeTextureAsset": ["HazyOrange_cube"],
    "VuMaterialAsset": ["Skybox/BlueSky"],
    "VuTextureAsset": ["Skybox/BlueSky"],
}


def backup(path: Path) -> None:
    rel = path.relative_to(HERE)
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(path, dst)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.utime(path, None)


def index_named(root) -> dict:
    """Map every entity that has a 'name' + 'data' dict."""
    acc = {}

    def walk(o):
        if isinstance(o, dict):
            if "name" in o and isinstance(o.get("data"), dict):
                acc.setdefault(o["name"], o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(root)
    return acc


def set_color(props: dict, key: str, val) -> bool:
    cur = props.get(key)
    if isinstance(cur, dict) and isinstance(val, dict):
        changed = any(cur.get(k) != v for k, v in val.items())
        cur.update(val)
        return changed
    if props.get(key) != val:
        props[key] = dict(val) if isinstance(val, dict) else val
        return True
    return False


def edit_template(path: Path) -> list[str]:
    data = load(path)
    named = index_named(data)
    notes = []

    sky = named.get("SkyBox01")
    if sky is not None:
        props = sky["data"].setdefault("Properties", {})
        if props.get("Model Asset") != SKY_MODEL:
            props["Model Asset"] = SKY_MODEL
            notes.append("sky-model")

    # cube substitute: VuCubeTextureAsset proxy swap
    for ent in named.values():
        p = ent["data"].get("Properties", {})
        if p.get("Asset Type") == "VuCubeTextureAsset" and p.get("Asset Name") == "Proxy_cube":
            if p.get("Subst Asset Name") != SKY_CUBE:
                p["Subst Asset Name"] = SKY_CUBE
                notes.append("sky-cube")
            break

    gfx = named.get("GlobalGfxSettings01")
    if gfx is not None:
        props = gfx["data"].setdefault("Properties", {})
        if any(set_color(props, k, v) for k, v in FOG.items()):
            notes.append("fog")
    else:
        notes.append("NO-gfx")

    if notes and notes != ["NO-gfx"]:
        backup(path)
        save(path, data)
    return notes


def edit_project(path: Path) -> list[str]:
    data = load(path)
    ad = data.get("AssetData")
    if not isinstance(ad, list):
        return ["NO-assetdata"]

    rows = {row[0]: row for row in ad if isinstance(row, list) and row}
    added = []
    for atype, names in DEP_ADD.items():
        row = rows.get(atype)
        if row is None:
            row = [atype]
            ad.append(row)
            rows[atype] = row
        existing = set(row[1:])
        for n in names:
            if n not in existing:
                row.append(n)
                added.append(f"{atype}:{n}")

    if added:
        # keep each asset-type's name list sorted (matches engine's usual order)
        for row in ad:
            if isinstance(row, list) and len(row) > 2:
                head, tail = row[0], sorted(row[1:])
                row[:] = [head] + tail
        backup(path)
        save(path, data)
    return added


def restore_skybox_textures() -> int:
    if not TEX_BACKUP_GLOB:
        print("  (no skybox texture backup found - skipping restore)")
        return 0
    src_dir = TEX_BACKUP_GLOB[-1]
    n = 0
    for src in src_dir.glob("*.png"):
        dst = SKYBOX_TEX / src.name
        if dst.exists():
            shutil.copy2(src, dst)
            os.utime(dst, None)  # mark changed so repack re-encodes original
            n += 1
    print(f"  restored {n} original skybox PNG(s) from {src_dir}")
    return n


def main() -> None:
    print("== Restoring original skybox base textures ==")
    restore_skybox_textures()

    print("\n== Editing level templates ==")
    for path in sorted(LEVELS.glob("*.bin.json")):
        notes = edit_template(path)
        print(f"  {path.name:22} {notes}")

    print("\n== Patching project dependency tables ==")
    for path in sorted(PROJECTS.glob("*.bin.json")):
        added = edit_project(path)
        flag = "ok" if added else "already-ok"
        print(f"  {path.name:34} {flag} (+{len(added)})")

    print(f"\nBackups of edited JSON in: {BACKUP}")
    print("Done. Now repack: py 3_pack.py")


if __name__ == "__main__":
    main()
