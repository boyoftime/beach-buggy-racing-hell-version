"""Paint all visible character diffuse skins with a volcanic/lava look.

Only Character/*/*.png diffuse textures are modified.  Normal maps and .bin
texture metadata are left alone.  The effect keeps alpha, darkens the original
art, adds red-orange heat, and overlays procedural lava cracks so the characters
look scorched without needing hand-painted assets.
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


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v25_volcanic_character_skins_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        rel = path.relative_to(CHAR_DIR)
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    return backup_dir


def lava_cracks(size: tuple[int, int], seed: int) -> Image.Image:
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(20):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, 6.283185307179586)
        length = rng.randrange(width // 5, width // 2)
        points = [(x, y)]
        for _step in range(rng.randrange(6, 13)):
            angle += rng.uniform(-0.7, 0.7)
            step = length / rng.randrange(7, 13)
            x += int(math.cos(angle) * step)
            y += int(math.sin(angle) * step)
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(145, 230), width=rng.choice([1, 1, 2]), joint="curve")

        if rng.random() < 0.55 and len(points) > 3:
            bx, by = points[rng.randrange(1, len(points) - 1)]
            branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.75, 1.35)
            branch = [(bx, by)]
            for _step in range(rng.randrange(3, 6)):
                bx += int(math.cos(branch_angle) * rng.randrange(10, 24))
                by += int(math.sin(branch_angle) * rng.randrange(10, 24))
                branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
            draw.line(branch, fill=rng.randrange(115, 190), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.35))


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    src = image.load()

    cracks = lava_cracks((width, height), 9000 + index * 101)
    glow = cracks.filter(ImageFilter.GaussianBlur(4.0))
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
            heat = glow_pix[x, y] / 255.0
            crack = crack_pix[x, y] / 255.0

            # Scorched base keeps enough original detail for faces/clothes to read.
            nr = int(lum * 0.22 + r * 0.08 + 35 + heat * 120 + crack * 220)
            ng = int(lum * 0.12 + g * 0.05 + 12 + heat * 42 + crack * 112)
            nb = int(lum * 0.10 + b * 0.06 + 8 + heat * 8)

            # Make the cracks white-hot in their cores.
            if crack > 0.75:
                nr = int(nr * 0.45 + 255 * 0.55)
                ng = int(ng * 0.45 + 190 * 0.55)
                nb = int(nb * 0.45 + 55 * 0.55)

            dst[x, y] = (min(nr, 255), min(ng, 220), min(nb, 110), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=3))
    out.save(path)
    now = time.time()
    os.utime(path, (now, now))


def main() -> None:
    textures = sorted(path for path in CHAR_DIR.glob("*/*.png") if not path.stem.lower().endswith("_n"))
    if not textures:
        raise SystemExit(f"No character textures found in {CHAR_DIR}")

    backup_dir = backup(textures)
    for index, path in enumerate(textures):
        repaint(path, index)
        print(f"Volcanic skin: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backup: {backup_dir}")
    print(f"Repainted {len(textures)} character skins.")


if __name__ == "__main__":
    main()
