"""v32 - Volcanic fire-body golem character skins.

Follow-up to v31: the mid-gray granite read as plain stone.  This pass keeps the
full-body golem structure but swaps the base from neutral grey to ACTIVE VOLCANIC
ROCK - a dark charred black/red basalt crust with:
- a soft low-frequency "magma underglow" so molten patches seem to glow beneath
  the crust (warm volcanic variation, not flat grey),
- a denser, brighter fire-crack network (orange seams + yellow-white hot cores),
- stronger inner heat glow around the cracks and a hot molten rim on UV-island
  edges.

Whole opaque atlas is treated (face included - full golem look), original shading
preserved via luminance.  Only Character/*/*.png diffuse atlases edited; normal
maps (_n) stay stock.  Restore->backup->repaint->retouch-mtime pipeline as v31.
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
    backup_dir = BACKUP_ROOT / f"v32_volcanic_fire_body_golem_skins_{stamp}"
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


def rock_mottle(size: tuple[int, int], seed: int) -> Image.Image:
    """Two-octave grayscale noise for charred basalt grain."""
    width, height = size
    rng = random.Random(seed)
    noise = Image.new("L", size)
    noise.putdata([rng.randrange(0, 256) for _ in range(width * height)])
    fine = noise.filter(ImageFilter.GaussianBlur(0.7))
    coarse = noise.filter(ImageFilter.GaussianBlur(3.4))
    return ImageChops.blend(fine, coarse, 0.5)


def magma_underglow(size: tuple[int, int], seed: int) -> Image.Image:
    """Big soft low-frequency blobs = molten patches glowing under the crust."""
    width, height = size
    rng = random.Random(seed)
    noise = Image.new("L", size)
    noise.putdata([rng.randrange(0, 256) for _ in range(width * height)])
    return noise.filter(ImageFilter.GaussianBlur(max(6.0, min(width, height) / 22.0)))


def fire_veins(size: tuple[int, int], seed: int) -> Image.Image:
    """Dense branching fissure network used as the molten-lava crack mask."""
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(44):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(6, 12)):
            angle += rng.uniform(-0.85, 0.85)
            x += int(math.cos(angle) * rng.randrange(11, 32))
            y += int(math.sin(angle) * rng.randrange(11, 32))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(185, 252), width=rng.choice([1, 1, 2]), joint="curve")

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
            draw.line(branch, fill=rng.randrange(150, 220), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.22))


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    mottle = rock_mottle((width, height), 94000 + index * 211).load()
    under = magma_underglow((width, height), 47000 + index * 197).load()

    cracks = fire_veins((width, height), 66000 + index * 173)
    cracks = ImageChops.multiply(cracks, alpha)

    eroded = alpha.filter(ImageFilter.MinFilter(9))
    inner_edge = ImageChops.subtract(alpha, eroded).filter(ImageFilter.GaussianBlur(1.0))
    glow = ImageChops.lighter(
        cracks.filter(ImageFilter.GaussianBlur(5.0)),
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
            grain = (mottle[x, y] - 128) * 0.24
            crack = crack_pix[x, y] / 255.0
            edge = edge_pix[x, y] / 255.0
            heat = glow_pix[x, y] / 255.0
            # only the brightest underglow blobs glow (sparse molten patches)
            molten = max(0.0, (under[x, y] / 255.0) - 0.46) / 0.54
            molten *= molten  # sharpen falloff

            # Charred volcanic basalt base: dark, warm (red>green>blue), keeps shading.
            base = 24 + lum * 0.42 + grain
            nr = base * 1.30 + 14
            ng = base * 0.74 + 5
            nb = base * 0.55 + 3

            # Magma glowing beneath the crust.
            nr += molten * 132
            ng += molten * 50
            nb += molten * 8

            # Inner heat halo warms the rock around each vein.
            nr += heat * 112 + edge * 72
            ng += heat * 46 + edge * 26
            nb += heat * 9

            # Molten lava filling the fissures: bright orange seam.
            if crack > 0.10:
                nr = nr * (1.0 - crack * 0.52) + 255 * crack * 0.88
                ng = ng * (1.0 - crack * 0.46) + 150 * crack * 0.80
                nb = nb * (1.0 - crack * 0.34) + 28 * crack * 0.52

            # Hottest vein cores blow out to yellow-white.
            if crack > 0.55:
                nr = nr * 0.42 + 255 * 0.58
                ng = ng * 0.46 + 236 * 0.54
                nb = nb * 0.56 + 86 * 0.44

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
        print(f"Volcanic fire golem: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins as volcanic fire-body golems.")


if __name__ == "__main__":
    main()
