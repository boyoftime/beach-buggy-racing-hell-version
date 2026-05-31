"""v43 - Restore each opponent's normal car, but monster-buff every racer car.

User wanted the visual variety back (each driver on their own car) AND an insane race.
Since the engine takes speed from the CAR (not the AI Performance multiplier), the fix
is to buff every car the opponents drive to Dune-monster-or-faster physics:

  1. Restore Opponents.bin car assignments from the pre-v40 backup (varied cars +
     v19 chaos stats; bosses keep their Dune).
  2. CarDB: for every racer car the opponents use, apply the proven non-flippy Dune
     monster config plus chaos RPM:
        Mass -> 350, Drag Coeff -> 0.12, Headroom RPM -> 2500,
        stage Max RPM -> 14000/16000/18000/21000/24000,
        engine audio -> Engine/F1_V12 (high-rev, avoids the pitch-cut glitch).

Player cars of those types also get fast (intended).  Backups saved.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTRACTED = ROOT / "extracted"
OPPONENTS = EXTRACTED / "Assets" / "VuSpreadsheetAsset" / "Opponents.bin"
CARDB = EXTRACTED / "Assets" / "VuDBAsset" / "CarDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

# Cars the career opponents actually drive (from the Opponents.bin scan).
TARGET_CARS = ["Muscle", "Euro", "Buggy", "Rally", "Moon", "Dune",
               "MonsterTruck", "Hearse", "Default"]

CHAOS_RPM = [14000, 16000, 18000, 21000, 24000]
MASS = 350
DRAG = 0.12
HEADROOM = 2500
AUDIO = "Engine/F1_V12"


def newest_backup(pattern: str) -> Path:
    matches = sorted([p for p in BACKUP_ROOT.glob(pattern) if p.is_dir()],
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise SystemExit(f"No backup matching {pattern}")
    return matches[0]


def buff_car(car: dict) -> int:
    n = 0
    # stages
    for i, stage in enumerate(car.get("Stages", [])):
        eng = stage.get("Engine")
        if isinstance(eng, dict):
            eng["Max RPM"] = CHAOS_RPM[i] if i < len(CHAOS_RPM) else CHAOS_RPM[-1]
            n += 1
    # top-level engine
    eng = car.setdefault("Engine", {})
    eng["Headroom RPM"] = HEADROOM
    eng.setdefault("Audio", {})["Run"] = AUDIO
    # mass + drag (recursive: each appears once per car)
    n += _set_keys(car, {"Mass": MASS, "Drag Coeff": DRAG})
    return n


def _set_keys(node, targets):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k in targets and not isinstance(v, (dict, list)):
                node[k] = targets[k]
                n += 1
            else:
                n += _set_keys(v, targets)
    elif isinstance(node, list):
        for item in node:
            n += _set_keys(item, targets)
    return n


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v43_default_cars_insane_race_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPPONENTS, backup_dir / OPPONENTS.name)
    shutil.copy2(CARDB, backup_dir / CARDB.name)

    # 1) Restore varied car assignments from the pre-v40 (Dune-switch) backup.
    src = newest_backup("v40_all_opponents_dune_*") / OPPONENTS.name
    if not src.exists():
        raise SystemExit(f"Missing varied-car backup: {src}")
    shutil.copyfile(src, OPPONENTS)
    now = time.time()
    os.utime(OPPONENTS, (now, now))
    print(f"Restored varied opponent cars from: {src}")

    # 2) Monster-buff every racer car.
    data = json.loads(CARDB.read_text(encoding="utf-8"))
    total = 0
    for name in TARGET_CARS:
        if name in data:
            c = buff_car(data[name])
            total += c
            print(f"  buffed {name}: {c} fields")
        else:
            print(f"  WARN: {name} not in CarDB")
    CARDB.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.utime(CARDB, (now, now))
    print(f"Total car fields changed: {total}")


if __name__ == "__main__":
    main()
