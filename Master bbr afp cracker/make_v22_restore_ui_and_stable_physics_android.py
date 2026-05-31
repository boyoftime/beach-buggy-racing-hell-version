"""Restore normal HP badge art and back out unstable high-grip physics.

v21 replaced Stage0/1/2 badge textures with the Stage3 1000HP art.  This script
restores the original badge art from the v21 backup.  It also restores the DBs
that v20 changed for extra grip because those values can make cars shake on the
road at high speed.

SeriesDB and Opponents.bin are intentionally left alone so the career 1000HP
chaos data remains in the build.
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "extracted" / "Assets"
DB = ASSETS / "VuDBAsset"
ICONS = ASSETS / "VuTextureAsset" / "UI" / "Icon"
BACKUP_ROOT = ROOT / "mod_backups"


def newest_dir(pattern: str) -> Path:
    matches = sorted(
        [path for path in BACKUP_ROOT.glob(pattern) if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise SystemExit(f"No backup directory found for {pattern}")
    return matches[0]


def copy_fresh(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"Missing backup source: {src}")
    if not dst.parent.exists():
        raise SystemExit(f"Missing destination directory: {dst.parent}")
    shutil.copyfile(src, dst)
    now = time.time()
    os.utime(dst, (now, now))


def backup_current(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v22_restore_ui_stable_physics_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def main() -> None:
    badge_backup = newest_dir("stage_badges_1000hp_*")
    physics_backup = newest_dir("career_1000hp_grip_*")

    icon_paths = [ICONS / f"Stage{i}.png" for i in range(4)]
    db_paths = [
        DB / "CarDB.bin.json",
        DB / "SurfaceDB.bin.json",
        DB / "AiPersonalityDB.bin.json",
    ]
    current_backup = backup_current(icon_paths + db_paths)

    for i in range(4):
        copy_fresh(badge_backup / f"Stage{i}.png", ICONS / f"Stage{i}.png")

    for name in ("CarDB.bin.json", "SurfaceDB.bin.json", "AiPersonalityDB.bin.json"):
        copy_fresh(physics_backup / name, DB / name)

    print(f"Backed up current v21 files to: {current_backup}")
    print(f"Restored normal HP badge art from: {badge_backup}")
    print(f"Restored stable pre-v20 physics DBs from: {physics_backup}")
    print("Left SeriesDB and Opponents.bin unchanged for career 1000HP chaos.")


if __name__ == "__main__":
    main()
