"""Paint characters as fire-body racers.

This is closer to a Human-Torch style look than v25/v27:
- restore original diffuse textures first
- convert opaque character parts to a dark charred black/red base
- add strong yellow/orange lava cracks across body/clothes
- add hot edge glow along UV island borders for a fiery outline

Only diffuse Character/*/*.png textures are edited.  Normal maps stay stock.
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
    backup_dir = BACKUP_ROOT / f"v28_fire_body_character_skins_{stamp}"
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


def jagged_fire_lines(size: tuple[int, int], seed: int) -> Image.Image:
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(34):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(5, 11)):
            angle += rng.uniform(-0.8, 0.8)
            x += int(math.cos(angle) * rng.randrange(12, 34))
            y += int(math.sin(angle) * rng.randrange(12, 34))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))

        draw.line(points, fill=rng.randrange(165, 245), width=rng.choice([1, 1, 2]), joint="curve")

        if rng.random() < 0.75 and len(points) > 3:
            for _branch in range(rng.randrange(1, 3)):
                bx, by = points[rng.randrange(1, len(points) - 1)]
                branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.75, 1.45)
                branch = [(bx, by)]
                for _step in range(rng.randrange(2, 6)):
                    branch_angle += rng.uniform(-0.35, 0.35)
                    bx += int(math.cos(branch_angle) * rng.randrange(9, 22))
                    by += int(math.sin(branch_angle) * rng.randrange(9, 22))
                    branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
                draw.line(branch, fill=rng.randrange(125, 205), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.25))


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")

    cracks = jagged_fire_lines((width, height), 38000 + index * 131)
    cracks = ImageChops.multiply(cracks, alpha)

    eroded = alpha.filter(ImageFilter.MinFilter(9))
    inner_edge = ImageChops.subtract(alpha, eroded).filter(ImageFilter.GaussianBlur(1.1))
    glow = ImageChops.lighter(
        cracks.filter(ImageFilter.GaussianBlur(4.2)),
        inner_edge.filter(ImageFilter.GaussianBlur(3.0)),
    )

    src = image.load()
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

            # Burn the body down to a readable charred base, with original
            # shading still driving the highlights.
            nr = lum * 0.13 + r * 0.05 + 18 + heat * 95 + edge * 58
            ng = lum * 0.055 + g * 0.025 + 5 + heat * 30 + edge * 22
            nb = lum * 0.035 + b * 0.018 + 3 + heat * 4

            if crack > 0.12:
                nr = nr * (1.0 - crack * 0.45) + 255 * crack * 0.82
                ng = ng * (1.0 - crack * 0.42) + 132 * crack * 0.72
                nb = nb * (1.0 - crack * 0.30) + 18 * crack * 0.45

            if crack > 0.62:
                nr = nr * 0.48 + 255 * 0.52
                ng = ng * 0.48 + 225 * 0.52
                nb = nb * 0.55 + 54 * 0.45

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=75, threshold=3))
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
        print(f"Fire body skin: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins as fire-body characters.")


if __name__ == "__main__":
    main()
