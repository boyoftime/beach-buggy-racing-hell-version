"""Repaint every character as a stone (mid-gray granite) body with bright molten LavaA veins.

v31 "lava golem" pass:
- restores the original diffuse textures from the v25 backup first (clean base),
- converts the WHOLE opaque atlas (face included - full stone golem look) to a
  mid-gray granite rock base that keeps the original shading/form,
- adds procedural granite mottle so the rock reads as carved stone,
- carves a branching fissure network filled with BRIGHT molten lava (yellow-white
  cores, orange seams) plus an inner heat glow and a hot molten rim on UV-island
  edges - matching the LavaA theme.

Only Character/*/*.png diffuse textures are edited.  Normal maps (_n) stay stock.
Mirrors the proven v29/v30 restore->backup->repaint->retouch-mtime pipeline.
"""
from __future__ import annotations

import math
import os
import random
import shutil
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


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
    backup_dir = BACKUP_ROOT / f"v31_stone_lava_golem_skins_{stamp}"
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


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def granite_mottle(size: tuple[int, int], seed: int) -> Image.Image:
    """Two-octave grayscale noise so the stone base reads as carved granite grain."""
    width, height = size
    rng = random.Random(seed)
    noise = Image.new("L", size)
    noise.putdata([rng.randrange(0, 256) for _ in range(width * height)])
    fine = noise.filter(ImageFilter.GaussianBlur(0.7))
    coarse = noise.filter(ImageFilter.GaussianBlur(3.2))
    return ImageChops.blend(fine, coarse, 0.5)


def lava_veins(size: tuple[int, int], seed: int) -> Image.Image:
    """Branching fissure network used as the molten-lava crack mask."""
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(34):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(6, 11)):
            angle += rng.uniform(-0.8, 0.8)
            x += int(math.cos(angle) * rng.randrange(12, 34))
            y += int(math.sin(angle) * rng.randrange(12, 34))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(180, 250), width=rng.choice([1, 1, 2]), joint="curve")

        # spawn 1-2 branches per main vein for a cracked-stone web
        for _branch in range(rng.randrange(1, 3)):
            if len(points) <= 3:
                break
            bx, by = points[rng.randrange(1, len(points) - 1)]
            branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.7, 1.5)
            branch = [(bx, by)]
            for _step in range(rng.randrange(2, 6)):
                branch_angle += rng.uniform(-0.4, 0.4)
                bx += int(math.cos(branch_angle) * rng.randrange(8, 22))
                by += int(math.sin(branch_angle) * rng.randrange(8, 22))
                branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
            draw.line(branch, fill=rng.randrange(140, 215), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.22))


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    mottle = granite_mottle((width, height), 91000 + index * 211).load()

    cracks = lava_veins((width, height), 63000 + index * 173)
    cracks = ImageChops.multiply(cracks, alpha)  # keep lava on opaque texels only

    # inner heat glow around veins + a hot molten rim on UV-island edges
    eroded = alpha.filter(ImageFilter.MinFilter(9))
    inner_edge = ImageChops.subtract(alpha, eroded).filter(ImageFilter.GaussianBlur(1.0))
    glow = ImageChops.lighter(
        cracks.filter(ImageFilter.GaussianBlur(4.5)),
        inner_edge.filter(ImageFilter.GaussianBlur(2.7)),
    )

    crack_pix = cracks.load()
    edge_pix = inner_edge.load()
    glow_pix = glow.load()

    out = Image.new("RGBA", image.size)
    dst = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            lum = luminance(r, g, b)
            crack = crack_pix[x, y] / 255.0
            edge = edge_pix[x, y] / 255.0
            heat = glow_pix[x, y] / 255.0
            grain = (mottle[x, y] - 128) * 0.26

            # Mid-gray granite base: preserve original shading via luminance,
            # flatten toward neutral gray, add stone grain.  Slightly warm-neutral.
            stone = 86 + lum * 0.46 + grain
            nr = stone * 1.03 + 4
            ng = stone * 1.00
            nb = stone * 0.96 + 2

            # Inner heat warms nearby stone (gives veins depth before the core).
            nr += heat * 92 + edge * 60
            ng += heat * 38 + edge * 22
            nb += heat * 7

            # Molten lava in the fissures: orange seam.
            if crack > 0.10:
                nr = nr * (1.0 - crack * 0.50) + 255 * crack * 0.85
                ng = ng * (1.0 - crack * 0.45) + 144 * crack * 0.78
                nb = nb * (1.0 - crack * 0.32) + 26 * crack * 0.50

            # Hottest vein cores blow out to yellow-white.
            if crack > 0.60:
                nr = nr * 0.45 + 255 * 0.55
                ng = ng * 0.48 + 232 * 0.52
                nb = nb * 0.58 + 78 * 0.42

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=72, threshold=3))
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
        print(f"Stone lava golem: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins as granite stone bodies with molten lava veins.")


if __name__ == "__main__":
    main()
