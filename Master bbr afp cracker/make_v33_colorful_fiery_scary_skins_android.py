"""v33 - Colorful fiery scary character skins.

v31/v32 collapsed the whole atlas into ONE rock tone, so characters went dim and
unreadable.  This pass keeps each character's ORIGINAL multi-colored diffuse (so
clothes/skin/features stay distinct and clearly visible) and instead:
- boosts vibrance + contrast so the colors POP (no more dim look),
- deepens shadows slightly for a menacing read,
- layers GLOWING fire cracks ON TOP via screen blend (orange seams, yellow-white
  hot cores) so the body keeps its colors between the cracks,
- adds a hot ember rim on UV-island edges and a soft heat halo around the veins.

Result: vivid, clearly-readable characters that look scary + fun, lit by fire
cracks - not a single-color golem.  Only Character/*/*.png diffuse atlases edited;
normal maps (_n) stay stock.  Restore->backup->repaint->retouch-mtime as before.
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
    backup_dir = BACKUP_ROOT / f"v33_colorful_fiery_scary_skins_{stamp}"
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


def screen(base: float, add: float) -> float:
    """Photographic screen blend - brightens, never darkens (good for glow)."""
    return 255.0 - (255.0 - base) * (255.0 - add) / 255.0


def fire_veins(size: tuple[int, int], seed: int) -> Image.Image:
    """Branching fissure network used as the glowing fire-crack mask."""
    width, height = size
    rng = random.Random(seed)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for _ in range(40):
        x = rng.randrange(width)
        y = rng.randrange(height)
        angle = rng.uniform(0, math.tau)
        points = [(x, y)]
        for _step in range(rng.randrange(6, 11)):
            angle += rng.uniform(-0.8, 0.8)
            x += int(math.cos(angle) * rng.randrange(11, 30))
            y += int(math.sin(angle) * rng.randrange(11, 30))
            points.append((max(0, min(width - 1, x)), max(0, min(height - 1, y))))
        draw.line(points, fill=rng.randrange(180, 250), width=rng.choice([1, 1, 2]), joint="curve")

        for _branch in range(rng.randrange(1, 3)):
            if len(points) <= 3:
                break
            bx, by = points[rng.randrange(1, len(points) - 1)]
            branch_angle = angle + rng.choice([-1, 1]) * rng.uniform(0.7, 1.5)
            branch = [(bx, by)]
            for _step in range(rng.randrange(2, 5)):
                branch_angle += rng.uniform(-0.4, 0.4)
                bx += int(math.cos(branch_angle) * rng.randrange(8, 20))
                by += int(math.sin(branch_angle) * rng.randrange(8, 20))
                branch.append((max(0, min(width - 1, bx)), max(0, min(height - 1, by))))
            draw.line(branch, fill=rng.randrange(150, 210), width=1)

    return mask.filter(ImageFilter.GaussianBlur(0.22))


def repaint(path: Path, index: int) -> None:
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    src = image.load()

    cracks = fire_veins((width, height), 68000 + index * 173)
    cracks = ImageChops.multiply(cracks, alpha)  # keep glow on opaque texels only

    eroded = alpha.filter(ImageFilter.MinFilter(7))
    inner_edge = ImageChops.subtract(alpha, eroded).filter(ImageFilter.GaussianBlur(1.0))
    halo = cracks.filter(ImageFilter.GaussianBlur(4.0))

    crack_pix = cracks.load()
    edge_pix = inner_edge.load()
    halo_pix = halo.load()

    SAT = 1.55       # vibrance boost so colors stay vivid and readable
    CONTRAST = 1.16  # punchier midtones (kills the dim look)

    out = Image.new("RGBA", image.size)
    dst = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            lum = luminance(r, g, b)

            # 1) Keep original color identity, but make it POP: saturate + contrast.
            nr = lum + (r - lum) * SAT
            ng = lum + (g - lum) * SAT
            nb = lum + (b - lum) * SAT
            nr = (nr - 128) * CONTRAST + 128 + 4
            ng = (ng - 128) * CONTRAST + 128 + 4
            nb = (nb - 128) * CONTRAST + 128 + 4

            # 2) Slightly deepen shadows for a menacing read (only very dark pixels).
            if lum < 70:
                shade = (70 - lum) / 70.0 * 0.30
                nr *= 1.0 - shade
                ng *= 1.0 - shade
                nb *= 1.0 - shade

            crack = crack_pix[x, y] / 255.0
            edge = edge_pix[x, y] / 255.0
            heat = halo_pix[x, y] / 255.0

            # 3) Glowing fire layered ON TOP via screen blend (body color shows between cracks).
            glow_r = crack * 255 * 0.95 + heat * 150 + edge * 120
            glow_g = crack * 150 * 0.85 + heat * 55 + edge * 45
            glow_b = crack * 30 * 0.55 + heat * 12 + edge * 8
            nr = screen(nr, glow_r)
            ng = screen(ng, glow_g)
            nb = screen(nb, glow_b)

            # 4) Hottest crack cores blow to yellow-white for the molten core.
            if crack > 0.55:
                nr = nr * 0.45 + 255 * 0.55
                ng = ng * 0.50 + 235 * 0.50
                nb = nb * 0.62 + 90 * 0.38

            dst[x, y] = (clamp(nr), clamp(ng), clamp(nb), a)

    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=78, threshold=3))
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
        print(f"Colorful fiery scary: {path.relative_to(CHAR_DIR).as_posix()}")

    print(f"Backed up current textures to: {current_backup}")
    print(f"Restored original colors from: {restored_from}")
    print(f"Repainted {len(textures)} skins: vivid colors + fire cracks (scary + fun).")


if __name__ == "__main__":
    main()
