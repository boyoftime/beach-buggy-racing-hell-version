"""v42 - Chaos speed for the Grand Prix (Formula) car.

The opponents drive Formula now (v41) but its top speed was stock-ish.  Top speed is
governed by the engine Max RPM (+ rev headroom + drag), so crank them to chaos:
  - Stage Max RPM 9000/10000/11000/12000/12500 -> 16000/19000/22000/26000/30000
  - Engine Headroom RPM 1500 -> 3000 (more boost-over-rev room)
  - Drag Coeff 0.12 -> 0.07 (already monster-light from v41; now slipperier)
  - Mass kept 350.  Audio already Engine/F1_V12 (high-rev), so no pitch glitch.

Opponents race Stage 3 (-> 26000 RPM) so the whole grid screams.  This also affects a
player-driven Grand Prix (intended chaos).  CarDB Formula only; backup saved.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CARDB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "CarDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

CHAOS_RPM = [16000, 19000, 22000, 26000, 30000]
HEADROOM_RPM = 3000
DRAG = 0.07


def set_keys(node, targets):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k in targets and not isinstance(v, (dict, list)):
                if node[k] != targets[k]:
                    node[k] = targets[k]
                    n += 1
            else:
                n += set_keys(v, targets)
    elif isinstance(node, list):
        for item in node:
            n += set_keys(item, targets)
    return n


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v42_grandprix_chaos_speed_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CARDB, backup_dir / CARDB.name)

    data = json.loads(CARDB.read_text(encoding="utf-8"))
    formula = data["Formula"]

    # Per-stage Max RPM -> chaos.
    stages = formula.get("Stages", [])
    rpm_changes = []
    for i, stage in enumerate(stages):
        eng = stage.get("Engine")
        if not isinstance(eng, dict):
            continue
        new_rpm = CHAOS_RPM[i] if i < len(CHAOS_RPM) else CHAOS_RPM[-1]
        old = eng.get("Max RPM")
        eng["Max RPM"] = new_rpm
        rpm_changes.append((i, old, new_rpm))

    # Top-level engine headroom + drag (drag lives in a chassis/aero subtree).
    formula.setdefault("Engine", {})["Headroom RPM"] = HEADROOM_RPM
    drag_changes = set_keys(formula, {"Drag Coeff": DRAG})

    CARDB.write_text(json.dumps(data, indent=1), encoding="utf-8")
    now = time.time()
    os.utime(CARDB, (now, now))

    print(f"Backup: {backup_dir}")
    print("Stage Max RPM changes (stage, old, new):")
    for c in rpm_changes:
        print("   ", c)
    print(f"Headroom RPM -> {HEADROOM_RPM}")
    print(f"Drag Coeff fields set to {DRAG}: {drag_changes}")


if __name__ == "__main__":
    main()
