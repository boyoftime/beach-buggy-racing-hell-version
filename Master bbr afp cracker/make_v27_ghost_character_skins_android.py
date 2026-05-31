"""Make characters look ghostly without destroying faces.

This restores the original diffuse skins from the v25 pre-edit backup, then
applies a spectral pass:
- skin-like pixels become pale blue/gray but keep shading
- dark details near skin become deeper eye/mouth shadows
- bright eye-like details near skin get a cold cyan glow
- clothes/armor are only cooled and desaturated, not painted solid red
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parent
CHAR_DIR = ROOT / "extracted" / "Assets" / "VuTextureAsset" / "Character"
BACKUP_ROOT = ROOT / "mod_backups"


def newest_backup(pattern: str) -> Path:
    matches = sorted(
        [path for path in BACKUP_ROOT.glob(pattern) if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise SystemExit(f"No backup found for {pattern}")
    return matches[0]


def backup_current(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v27_ghost_character_skins_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        rel = path.relative_to(CHAR_DIR)
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    return backup_dir


def restore_originals(textures: list[Path]) -> Path:
    source_root = newest_backup("v25_volcanic_character_skins_*")
    for path in textures:
        rel = path.relative_to(CHAR_DIR)
        source = source_root / rel
        if not source.exists():
            raise SystemExit(f"Missing original backup texture: {source}")
        shutil.copyfile(source, path)
    return source_root


def luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def saturation(r: int, g: int, b: int) -> int:
    return max(r, g, b) - min(r, g, b)


def likely_skin(r: int, g: int, b: int) -> bool:
    maxc = max(r, g, b)
    minc = min(r, g, b)
    return (
        r > 62
        and g > 35
        and b > 18
        and r >= g * 1.02
        and r >= b * 1.18
        and (r - g) < 115
        and (maxc - minc) > 16
    )


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def repaint(path: Path) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    src = image.load()

    skin_mask = Image.new("L", image.size, 0)
    skin_pix = skin_mask.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a and likely_skin(r, g, b):
                skin_pix[x, y] = 255

    face_zone = skin_mask.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.GaussianBlur(1.2))
    face_pix = face_zone.load()

    out = Image.new("RGBA", image.size)
    dst = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            lum = luminance(r, g, b)
            sat = saturation(r, g, b)
            face = face_pix[x, y] / 255.0
            is_skin = skin_pix[x, y] > 0

            if is_skin:
                # Pale spectral skin, still shaped by original shading.
                nr = lum * 0.62 + 92
                ng = lum * 0.67 + 112
                nb = lum * 0.78 + 138
                if lum < 80:
                    nr *= 0.82
                    ng *= 0.82
                    nb *= 0.9
            elif face > 0.1 and lum < 72:
                # Hollow eye/mouth/crease details around face areas.
                nr = r * 0.22 + 6
                ng = g * 0.18 + 9
                nb = b * 0.35 + 28
            elif face > 0.2 and lum > 150 and sat < 85:
                # Cold glowing eye-like highlights.
                nr = r * 0.45 + 75
                ng = g * 0.55 + 125
                nb = b * 0.65 + 150
            else:
                # Clothes/armor: cool, slightly haunted, but original colors remain.
                gray = lum
                nr = r * 0.58 + gray * 0.22 + 12
                ng = g * 0.58 + gray * 0.26 + 22
                nb = b * 0.64 + gray * 0.32 + 42

            # A tiny moonlit lift on midtones helps the 3D model read in-game.
            if 55 < lum < 165:
                nr += 5
                ng += 8
                nb += 14

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.7, percent=55, threshold=4))
    out.save(path)
    now = time.time()
    os.utime(path, (now, now))


def main() -> None:
    textures = sorted(path for path in CHAR_DIR.glob("*/*.png") if not path.stem.lower().endswith("_n"))
    if not textures:
        raise SystemExit(f"No character textures found in {CHAR_DIR}")

    current_backup = backup_current(textures)
    restored_from = restore_originals(textures)
    for path in textures:
        repaint(path)
        print(f"Ghost skin: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins as ghost characters.")


if __name__ == "__main__":
    main()
