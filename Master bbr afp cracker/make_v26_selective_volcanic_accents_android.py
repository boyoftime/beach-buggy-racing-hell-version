"""Restore character colors and add selective volcanic accents.

v25 looked like a red filter over every character and put cracks across faces
and skin.  This version restores the original diffuse textures from the v25
backup, then keeps the original colors mostly intact.  Lava cracks are sparse
and masked away from skin-tone and bright face-detail pixels.
"""
from __future__ import annotations

import math
import os
import random
import shutil
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


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
    backup_dir = BACKUP_ROOT / f"v26_selective_volcanic_accents_{stamp}"
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


def lava_mask(size: tuple[int, int], seed: int) -> Image.Image:
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(9):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(4, 8)):
            angle += rng.uniform(-0.55, 0.55)
            x += int(math.cos(angle) * rng.randrange(18, 42))
            y += int(math.sin(angle) * rng.randrange(18, 42))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(145, 230), width=1, joint="curve")

        if rng.random() < 0.35 and len(points) > 3:
            bx, by = points[rng.randrange(1, len(points) - 1)]
            branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.8, 1.3)
            branch = [(bx, by)]
            for _step in range(rng.randrange(2, 4)):
                bx += int(math.cos(branch_angle) * rng.randrange(10, 24))
                by += int(math.sin(branch_angle) * rng.randrange(10, 24))
                branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
            draw.line(branch, fill=rng.randrange(100, 170), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.25))


def likely_skin_or_face(r: int, g: int, b: int) -> bool:
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    maxc = max(r, g, b)
    minc = min(r, g, b)
    skin_hue = (
        r > 65
        and g > 35
        and b > 18
        and r >= g * 1.03
        and r >= b * 1.25
        and (r - g) < 105
        and (maxc - minc) > 18
    )
    bright_detail = lum > 178 and maxc - minc < 95
    return skin_hue or bright_detail


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    src = image.load()

    cracks = lava_mask((width, height), 26000 + index * 113)
    glow = cracks.filter(ImageFilter.GaussianBlur(3.2))
    crack_pix = cracks.load()
    glow_pix = glow.load()

    out = Image.new("RGBA", image.size)
    dst = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            lum = 0.299 * r + 0.587 * g + 0.114 * b
            face_or_skin = likely_skin_or_face(r, g, b)
            crack = crack_pix[x, y] / 255.0
            heat = glow_pix[x, y] / 255.0

            if face_or_skin:
                # Keep faces and skin readable: only a tiny neutral soot pass.
                nr = int(r * 0.96 + 4)
                ng = int(g * 0.96 + 3)
                nb = int(b * 0.95 + 2)
                crack = 0.0
                heat = 0.0
            else:
                # Preserve original colors, with a subtle charred contrast.
                nr = int(r * 0.78 + lum * 0.10 + 8)
                ng = int(g * 0.76 + lum * 0.08 + 7)
                nb = int(b * 0.74 + lum * 0.07 + 7)

            # Only strong marks on non-skin pixels; glow remains local to cracks.
            if crack > 0.08:
                nr = int(nr * (1.0 - crack * 0.55) + 255 * crack * 0.55)
                ng = int(ng * (1.0 - crack * 0.42) + 118 * crack * 0.42)
                nb = int(nb * (1.0 - crack * 0.35) + 18 * crack * 0.35)
            elif heat > 0.10:
                nr = int(nr + heat * 22)
                ng = int(ng + heat * 8)

            dst[x, y] = (min(nr, 255), min(ng, 255), min(nb, 255), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=45, threshold=4))
    out.save(path)
    now = time.time()
    os.utime(path, (now, now))


def main() -> None:
    textures = sorted(path for path in CHAR_DIR.glob("*/*.png") if not path.stem.lower().endswith("_n"))
    if not textures:
        raise SystemExit(f"No character textures found in {CHAR_DIR}")

    current_backup = backup_current(textures)
    restored_from = restore_originals(textures)
    for index, path in enumerate(textures):
        repaint(path, index)
        print(f"Selective volcanic accents: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current v25 textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins with sparse non-skin lava accents.")


if __name__ == "__main__":
    main()
