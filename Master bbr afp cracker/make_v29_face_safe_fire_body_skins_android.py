"""Fire-body characters with readable faces.

v28 made the whole atlas too dark, so faces became hard to read.  This restores
the original diffuse textures, protects skin/face-colored pixels, then applies
the charred fire-crack treatment only to non-skin clothing/armor/body texture
areas.  Normal maps stay stock.
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
    backup_dir = BACKUP_ROOT / f"v29_face_safe_fire_body_skins_{stamp}"
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


def saturation(r: int, g: int, b: int) -> int:
    return max(r, g, b) - min(r, g, b)


def likely_face_or_skin(r: int, g: int, b: int) -> bool:
    lum = luminance(r, g, b)
    sat = saturation(r, g, b)
    maxc = max(r, g, b)
    minc = min(r, g, b)

    human_skin = (
        r > 62
        and g > 34
        and b > 18
        and r >= g * 1.02
        and r >= b * 1.15
        and (r - g) < 120
        and (maxc - minc) > 14
    )
    pale_face_detail = lum > 145 and sat < 105
    return human_skin or pale_face_detail


def fire_lines(size: tuple[int, int], seed: int) -> Image.Image:
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(30):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(5, 10)):
            angle += rng.uniform(-0.75, 0.75)
            x += int(math.cos(angle) * rng.randrange(12, 32))
            y += int(math.sin(angle) * rng.randrange(12, 32))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(165, 245), width=rng.choice([1, 1, 2]), joint="curve")

        if rng.random() < 0.65 and len(points) > 3:
            bx, by = points[rng.randrange(1, len(points) - 1)]
            branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.75, 1.45)
            branch = [(bx, by)]
            for _step in range(rng.randrange(2, 5)):
                branch_angle += rng.uniform(-0.35, 0.35)
                bx += int(math.cos(branch_angle) * rng.randrange(9, 22))
                by += int(math.sin(branch_angle) * rng.randrange(9, 22))
                branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
            draw.line(branch, fill=rng.randrange(125, 205), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.22))


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    protected = Image.new("L", image.size, 0)
    protected_pix = protected.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a and likely_face_or_skin(r, g, b):
                protected_pix[x, y] = 255
    protected = protected.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.6))
    protect_pix = protected.load()

    cracks = fire_lines((width, height), 52000 + index * 139)
    fire_area = ImageChops.subtract(alpha, protected)
    cracks = ImageChops.multiply(cracks, fire_area)

    eroded = fire_area.filter(ImageFilter.MinFilter(9))
    inner_edge = ImageChops.subtract(fire_area, eroded).filter(ImageFilter.GaussianBlur(1.0))
    glow = ImageChops.lighter(
        cracks.filter(ImageFilter.GaussianBlur(4.0)),
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
            protect = protect_pix[x, y] / 255.0
            crack = crack_pix[x, y] / 255.0
            edge = edge_pix[x, y] / 255.0
            heat = glow_pix[x, y] / 255.0

            # Protected face/skin: preserve readability with a warm haunted tint.
            face_r = r * 0.90 + lum * 0.10 + 10
            face_g = g * 0.88 + lum * 0.07 + 6
            face_b = b * 0.84 + lum * 0.04 + 3

            # Fire-body base for non-skin texture regions.
            fire_r = lum * 0.13 + r * 0.05 + 18 + heat * 100 + edge * 58
            fire_g = lum * 0.055 + g * 0.025 + 5 + heat * 32 + edge * 22
            fire_b = lum * 0.035 + b * 0.018 + 3 + heat * 5

            if crack > 0.12:
                fire_r = fire_r * (1.0 - crack * 0.45) + 255 * crack * 0.82
                fire_g = fire_g * (1.0 - crack * 0.42) + 132 * crack * 0.72
                fire_b = fire_b * (1.0 - crack * 0.30) + 18 * crack * 0.45

            if crack > 0.62:
                fire_r = fire_r * 0.48 + 255 * 0.52
                fire_g = fire_g * 0.48 + 225 * 0.52
                fire_b = fire_b * 0.55 + 54 * 0.45

            nr = fire_r * (1.0 - protect) + face_r * protect
            ng = fire_g * (1.0 - protect) + face_g * protect
            nb = fire_b * (1.0 - protect) + face_b * protect

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=70, threshold=3))
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
        print(f"Face-safe fire skin: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins with readable faces and fire bodies.")


if __name__ == "__main__":
    main()
