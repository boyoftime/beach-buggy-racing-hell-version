"""Apply a broad LavaA-style visual theme to extracted map textures.

This edits only files under extracted/Expansion/VuTextureAsset. The original
PNGs are copied into mod_backups/ before they are replaced, so the mod can be
undone without re-extracting.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
TEXTURES = HERE / "extracted" / "Assets" / "VuTextureAsset"
BACKUP_ROOT = HERE / "mod_backups" / f"all_maps_lava_theme_{time.strftime('%Y%m%d_%H%M%S')}"


SOURCES = {
    "lava_rock": TEXTURES / "Natural" / "LavaRock.png",
    "lava_rock_n": TEXTURES / "Natural" / "LavaRock_n.png",
    "lava_rock_m": TEXTURES / "Natural" / "LavaRock_m.png",
    "lava_rock_dtl": TEXTURES / "Natural" / "LavaRock_dtl.png",
    "lava_tracks": TEXTURES / "Natural" / "LavaTracks.png",
    "lava_tracks_n": TEXTURES / "Natural" / "LavaTracks_n.png",
    "lava_fire": TEXTURES / "Natural" / "LavaFire.png",
    "lava_flow": TEXTURES / "Natural" / "LavaFlow.png",
    "lava_flow_m": TEXTURES / "Natural" / "LavaFlow_m.png",
    "volcano_sky": TEXTURES / "Skybox" / "VolcanoNight.png",
}


def backup(path: Path) -> None:
    rel = path.relative_to(HERE)
    dst = BACKUP_ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(path, dst)


def replace_png(target: Path, source: Path) -> None:
    backup(target)
    with Image.open(target) as target_img:
        size = target_img.size
        mode = target_img.mode
    with Image.open(source) as source_img:
        out = source_img.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    if mode != "RGBA":
        out = out.convert(mode)
    out.save(target)


def source_for_texture(path: Path) -> Path:
    name = path.stem.lower()
    folder = path.parent.name.lower()

    if folder == "skybox":
        return SOURCES["volcano_sky"]

    if folder == "water":
        if name.endswith("_m") or "fresnel" in name:
            return SOURCES["lava_flow_m"]
        return SOURCES["lava_flow"]

    if name.endswith("_n") or name.endswith("n"):
        if any(word in name for word in ("track", "road", "sand", "grass", "ground")):
            return SOURCES["lava_tracks_n"]
        return SOURCES["lava_rock_n"]

    if name.endswith("_m") or name.endswith("m"):
        if "flow" in name or "water" in name:
            return SOURCES["lava_flow_m"]
        return SOURCES["lava_rock_m"]

    if "dtl" in name or "detail" in name:
        return SOURCES["lava_rock_dtl"]

    if any(word in name for word in ("fire", "light", "window", "torch")):
        return SOURCES["lava_fire"]

    if any(word in name for word in ("track", "road", "sand", "grass", "ground", "sidewalk")):
        return SOURCES["lava_tracks"]

    if any(word in name for word in ("water", "wet", "wake", "flow")):
        return SOURCES["lava_flow"]

    return SOURCES["lava_rock"]


def main() -> None:
    missing = [label for label, source in SOURCES.items() if not source.exists()]
    if missing:
        print(f"Note: missing lava sources (skipping those): {missing}")

    folders = ["Natural", "Skybox", "Water", "Building", "Plant"]
    changed = []
    for folder in folders:
        for target in sorted((TEXTURES / folder).glob("*.png")):
            source = source_for_texture(target)
            if not source.exists():
                continue  # no lava source for this texture type on this platform
            if target.resolve() == source.resolve():
                continue
            replace_png(target, source)
            changed.append(target.relative_to(HERE))

    print(f"Backed up originals to: {BACKUP_ROOT}")
    print(f"Changed {len(changed)} texture PNGs.")
    for path in changed:
        print(f"  {path}")


if __name__ == "__main__":
    main()
