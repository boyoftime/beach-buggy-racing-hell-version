"""v34 - Zombie blood-wounds character skins (vivid + readable).

Builds on what worked in v33: keep each character's ORIGINAL multi-colored diffuse,
boosted vibrant so they stay bright and clearly visible.  On top of that, apply a
heavy ZOMBIE pass:
- sickly undead pallor on skin-like pixels (kept readable, not washed out),
- MANY ragged dark wounds/gashes across the whole body,
- lots of bright red blood splatters + drips masked to opaque texture islands,
- darker eye/socket shadows for a scary undead read.

Fire cracks from v33 are intentionally NOT used here (fire + blood reads muddy).
Only Character/*/*.png diffuse atlases edited; normal maps (_n) stay stock.
Restore->backup->repaint->retouch-mtime pipeline as before.
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
    backup_dir = BACKUP_ROOT / f"v34_zombie_blood_wounds_skins_{stamp}"
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
    return luminance(r, g, b) > 165 and saturation(r, g, b) < 95


def wound_and_blood_masks(size: tuple[int, int], seed: int) -> tuple[Image.Image, Image.Image]:
    """Dense ragged wounds + heavy blood splatter/drips."""
    width, height = size
    rng = random.Random(seed)
    wounds = Image.new("L", size, 0)
    blood = Image.new("L", size, 0)
    wd = ImageDraw.Draw(wounds)
    bd = ImageDraw.Draw(blood)

    # Many ragged dark gashes.
    for _ in range(40):
        cx = rng.randrange(width)
        cy = rng.randrange(height)
        rx = rng.randrange(5, 20)
        ry = rng.randrange(3, 15)
        points = []
        for step in range(rng.randrange(7, 13)):
            ang = step / 11.0 * math.tau + rng.uniform(-0.28, 0.28)
            rr_x = rx * rng.uniform(0.55, 1.30)
            rr_y = ry * rng.uniform(0.55, 1.30)
            points.append((cx + int(math.cos(ang) * rr_x), cy + int(math.sin(ang) * rr_y)))
        wd.polygon(points, fill=rng.randrange(130, 230))
        if rng.random() < 0.7:
            wd.line(points + [points[0]], fill=255, width=1)

    # Lots of blood: splatters, drips, and fine spray.
    for _ in range(62):
        cx = rng.randrange(width)
        cy = rng.randrange(height)
        radius = rng.randrange(2, 9)
        bd.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=rng.randrange(140, 250))
        if rng.random() < 0.55:
            length = rng.randrange(12, 50)
            drift = rng.randrange(-9, 10)
            bd.line((cx, cy, cx + drift, min(height - 1, cy + length)),
                    fill=rng.randrange(130, 240), width=rng.choice([1, 1, 2]))
        if rng.random() < 0.45:
            for _dot in range(rng.randrange(3, 8)):
                dx = rng.randrange(-22, 23)
                dy = rng.randrange(-16, 17)
                rr = rng.randrange(1, 4)
                bd.ellipse((cx + dx - rr, cy + dy - rr, cx + dx + rr, cy + dy + rr),
                           fill=rng.randrange(100, 200))

    return (
        wounds.filter(ImageFilter.GaussianBlur(0.35)),
        blood.filter(ImageFilter.GaussianBlur(0.25)),
    )


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    # Protect bright eye/face details so the face still reads through the gore.
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
    protect = protect.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.7))
    protected_alpha = protect.load()
    skin_alpha = skin.filter(ImageFilter.GaussianBlur(0.4)).load()

    wounds, blood = wound_and_blood_masks((width, height), 73000 + index * 167)
    paint_area = ImageChops.subtract(alpha, protect)
    wounds = ImageChops.multiply(wounds, paint_area)
    blood = ImageChops.multiply(blood, paint_area)
    wound_pix = wounds.load()
    blood_pix = blood.load()

    SAT = 1.45       # keep colors vivid/readable
    CONTRAST = 1.12

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

            # Vivid base (keep identity, make it pop).
            nr = lum + (r - lum) * SAT
            ng = lum + (g - lum) * SAT
            nb = lum + (b - lum) * SAT
            nr = (nr - 128) * CONTRAST + 128 + 3
            ng = (ng - 128) * CONTRAST + 128 + 3
            nb = (nb - 128) * CONTRAST + 128 + 3

            # Sickly undead pallor on skin (readable, slight green-gray cast).
            if is_skin > 0.15:
                p = is_skin
                nr = nr * (1 - p * 0.28) + (lum * 0.55 + 96) * (p * 0.28)
                ng = ng * (1 - p * 0.20) + (lum * 0.60 + 108) * (p * 0.20)
                nb = nb * (1 - p * 0.30) + (lum * 0.45 + 84) * (p * 0.30)

            # Dark bruised wound base.
            if wound > 0.05:
                nr = nr * (1.0 - wound * 0.72) + 60 * wound * 0.72
                ng = ng * (1.0 - wound * 0.84) + 8 * wound * 0.84
                nb = nb * (1.0 - wound * 0.80) + 10 * wound * 0.80

            # Bright red blood on top.
            if blood_amt > 0.04:
                nr = nr * (1.0 - blood_amt * 0.62) + 180 * blood_amt * 0.80
                ng = ng * (1.0 - blood_amt * 0.78) + 10 * blood_amt * 0.78
                nb = nb * (1.0 - blood_amt * 0.72) + 14 * blood_amt * 0.72

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
        print(f"Zombie blood wounds: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins: vivid colors + zombie wounds & blood.")


if __name__ == "__main__":
    main()
