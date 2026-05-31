"""Paint characters with stylized zombie wounds and blood.

This restores original diffuse textures first, then applies a cartoon zombie pass:
- skin-like pixels become slightly pale/undead while keeping face readability
- sparse wound marks are added on skin and clothing/body areas
- red blood streaks/splatters are masked to opaque texture islands
- eyes/bright face details are protected from heavy blood coverage

Only Character/*/*.png diffuse textures are edited.  Normal maps stay stock.
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
    backup_dir = BACKUP_ROOT / f"v30_zombie_wounds_character_skins_{stamp}"
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


def likely_skin(r: int, g: int, b: int) -> bool:
    maxc = max(r, g, b)
    minc = min(r, g, b)
    return (
        r > 58
        and g > 32
        and b > 16
        and r >= g * 1.01
        and r >= b * 1.12
        and (r - g) < 125
        and (maxc - minc) > 12
    )


def likely_eye_or_bright_face_detail(r: int, g: int, b: int) -> bool:
    lum = luminance(r, g, b)
    return lum > 165 and saturation(r, g, b) < 95


def wound_and_blood_masks(size: tuple[int, int], seed: int) -> tuple[Image.Image, Image.Image]:
    width, height = size
    rng = random.Random(seed)
    wounds = Image.new("L", size, 0)
    blood = Image.new("L", size, 0)
    wd = ImageDraw.Draw(wounds)
    bd = ImageDraw.Draw(blood)

    # Ragged dark wounds.
    for _ in range(22):
        cx = rng.randrange(width)
        cy = rng.randrange(height)
        rx = rng.randrange(5, 18)
        ry = rng.randrange(3, 14)
        points = []
        for step in range(rng.randrange(7, 12)):
            ang = step / 10.0 * math.tau + rng.uniform(-0.25, 0.25)
            rr_x = rx * rng.uniform(0.55, 1.25)
            rr_y = ry * rng.uniform(0.55, 1.25)
            points.append((cx + int(math.cos(ang) * rr_x), cy + int(math.sin(ang) * rr_y)))
        wd.polygon(points, fill=rng.randrange(120, 220))
        if rng.random() < 0.65:
            wd.line(points + [points[0]], fill=255, width=1)

    # Blood splatters and short drips.
    for _ in range(34):
        cx = rng.randrange(width)
        cy = rng.randrange(height)
        radius = rng.randrange(2, 8)
        bd.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=rng.randrange(120, 245))
        if rng.random() < 0.45:
            length = rng.randrange(10, 42)
            drift = rng.randrange(-8, 9)
            bd.line((cx, cy, cx + drift, min(height - 1, cy + length)), fill=rng.randrange(120, 235), width=rng.choice([1, 1, 2]))
        if rng.random() < 0.35:
            for _dot in range(rng.randrange(2, 6)):
                dx = rng.randrange(-20, 21)
                dy = rng.randrange(-14, 15)
                rr = rng.randrange(1, 4)
                bd.ellipse((cx + dx - rr, cy + dy - rr, cx + dx + rr, cy + dy + rr), fill=rng.randrange(90, 190))

    return (
        wounds.filter(ImageFilter.GaussianBlur(0.35)),
        blood.filter(ImageFilter.GaussianBlur(0.25)),
    )


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    protect = Image.new("L", image.size, 0)
    skin = Image.new("L", image.size, 0)
    protect_pix = protect.load()
    skin_pix = skin.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if not a:
                continue
            if likely_skin(r, g, b):
                skin_pix[x, y] = 255
            if likely_eye_or_bright_face_detail(r, g, b):
                protect_pix[x, y] = 255

    protect = protect.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(0.7))
    protected_alpha = protect.load()
    skin_alpha = skin.filter(ImageFilter.GaussianBlur(0.4)).load()

    wounds, blood = wound_and_blood_masks((width, height), 71000 + index * 157)
    paint_area = ImageChops.subtract(alpha, protect)
    wounds = ImageChops.multiply(wounds, paint_area)
    blood = ImageChops.multiply(blood, paint_area)
    wound_pix = wounds.load()
    blood_pix = blood.load()

    out = Image.new("RGBA", image.size)
    dst = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            lum = luminance(r, g, b)
            is_skin = skin_alpha[x, y] / 255.0
            protected = protected_alpha[x, y] / 255.0
            wound = wound_pix[x, y] / 255.0 * (1.0 - protected)
            blood_amt = blood_pix[x, y] / 255.0 * (1.0 - protected)

            # Undead tint on skin; clothes keep more of their own color.
            if is_skin > 0.15:
                nr = r * 0.76 + lum * 0.12 + 18
                ng = g * 0.82 + lum * 0.10 + 28
                nb = b * 0.74 + lum * 0.08 + 20
            else:
                nr = r * 0.83 + lum * 0.08 + 4
                ng = g * 0.80 + lum * 0.07 + 3
                nb = b * 0.78 + lum * 0.06 + 3

            if wound > 0.05:
                # Dark bruised wound base.
                nr = nr * (1.0 - wound * 0.70) + 58 * wound * 0.70
                ng = ng * (1.0 - wound * 0.82) + 6 * wound * 0.82
                nb = nb * (1.0 - wound * 0.78) + 8 * wound * 0.78

            if blood_amt > 0.04:
                # Stylized readable blood, not full texture flooding.
                nr = nr * (1.0 - blood_amt * 0.55) + 165 * blood_amt * 0.75
                ng = ng * (1.0 - blood_amt * 0.70) + 8 * blood_amt * 0.70
                nb = nb * (1.0 - blood_amt * 0.65) + 12 * blood_amt * 0.65

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.75, percent=65, threshold=3))
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
        print(f"Zombie wounds: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins with zombie wounds and blood.")


if __name__ == "__main__":
    main()
