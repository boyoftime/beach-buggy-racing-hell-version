"""Make all front-end HP stage badges display as 1000HP.

Career series selection can still ask for Stage0/Stage1/Stage2 from profile
progression, even after the gameplay data has been forced to Stage3.  The badge
art lives in UI/Icon/Stage*.png, so copy the Stage3 artwork over the lower stage
badges to make the visible cards match the 1000HP mod.
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON_DIR = ROOT / "extracted" / "Assets" / "VuTextureAsset" / "UI" / "Icon"
BACKUP_ROOT = ROOT / "mod_backups"


def main() -> None:
    source = ICON_DIR / "Stage3.png"
    targets = [ICON_DIR / f"Stage{i}.png" for i in (0, 1, 2)]
    missing = [str(p) for p in [source, *targets] if not p.exists()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"stage_badges_1000hp_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in [source, *targets]:
        shutil.copy2(path, backup_dir / path.name)

    for target in targets:
        shutil.copy2(source, target)
        now = time.time()
        os.utime(target, (now, now))
        print(f"{target.name} -> Stage3 1000HP artwork")

    print(f"Backup: {backup_dir}")


if __name__ == "__main__":
    main()
