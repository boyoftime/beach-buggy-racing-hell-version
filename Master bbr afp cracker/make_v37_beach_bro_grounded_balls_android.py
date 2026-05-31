"""Keep Beach Bro's many balls, but stop them flying away.

v36 made Beach Bro chaotic with 55 dropped balls / 32 shot balls, but the balls
were too fast and bouncy.  This keeps the large counts and wide coverage, while
restoring speed/radius/mass/damping closer to stock so balls stay on the road.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CAR_EFFECT = ROOT / "extracted" / "Assets" / "VuDBAsset" / "CarEffectDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    now = time.time()
    os.utime(path, (now, now))


def setv(obj: dict, key: str, value) -> int:
    if obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def main() -> None:
    if not CAR_EFFECT.exists():
        raise SystemExit(f"Missing {CAR_EFFECT}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v37_beach_bro_grounded_balls_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CAR_EFFECT, backup_dir / CAR_EFFECT.name)

    data = load(CAR_EFFECT)
    beach = data["BeachBro"]
    ball = beach["BallData"]
    changes = 0

    # Keep the crowd-control quantity from v36.
    changes += setv(beach, "DropCount", 55)
    changes += setv(beach, "ShootCount", 32)
    changes += setv(beach, "Duration", 6)
    changes += setv(beach, "DropSpread", 260)
    changes += setv(beach, "ShootSpread", 40)

    # Grounded handling: close to stock speeds/size, with enough damping to settle.
    changes += setv(beach, "DropSpeed", 35)
    changes += setv(beach, "ShootSpeed", 145)
    changes += setv(ball, "LinearDamping", 0.35)
    changes += setv(ball, "Mass", 10)
    changes += setv(ball, "SelfCollisionTime", 5)
    changes += setv(ball, "Radius", 0.85)
    changes += setv(ball, "LifeTime", 18)

    # Keep the hit dangerous, but less sky-launchy than v36.
    changes += setv(data["BeachBroVictim"], "VerticalSpeed", 60)

    save(CAR_EFFECT, data)
    print(f"Backup: {backup_dir}")
    print(f"Beach Bro grounded ball changes: {changes}")


if __name__ == "__main__":
    main()
