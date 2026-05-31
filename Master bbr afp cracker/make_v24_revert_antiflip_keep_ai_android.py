"""Revert v23 anti-flip CarDB changes while keeping AI path cleanup.

The v23 anti-flip values caused road shaking on device.  Restore only CarDB from
the v23 pre-patch backup, leaving AiPersonalityDB and level waypoint edits in
place so AI still follows the main path with less zigzagging.
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "extracted" / "Assets"
CAR_DB = ASSETS / "VuDBAsset" / "CarDB.bin.json"
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


def main() -> None:
    v23_backup = newest_dir("v23_ai_mainline_antiflip_*")
    source = v23_backup / "VuDBAsset" / "CarDB.bin.json"
    if not source.exists():
        raise SystemExit(f"Missing v23 CarDB backup: {source}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_backup = BACKUP_ROOT / f"v24_revert_antiflip_keep_ai_{stamp}"
    current_backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CAR_DB, current_backup / "CarDB.bin.json")

    shutil.copyfile(source, CAR_DB)
    now = time.time()
    os.utime(CAR_DB, (now, now))

    print(f"Backed up current v23 CarDB to: {current_backup}")
    print(f"Restored stable CarDB from: {source}")
    print("Kept AiPersonalityDB and level waypoint mainline edits from v23.")


if __name__ == "__main__":
    main()
