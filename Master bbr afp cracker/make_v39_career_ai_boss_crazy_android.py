"""v39 - Make every career AI driver as crazy as the bosses.

Scan showed all non-Tutorial AI personalities already share the boss BEHAVIOR
(Aggro 1.5, AbilityFrequency 0.2, BossPowerUpFrequency 0.2, BoostFrequency 1,
ThrottleDownFrequency 999, full boss attack/powerup weights).  The only things that
made bosses crazier than the regular career classes were:
  - ReactionTime: bosses 0.03 vs classes 0.05 (faster reflexes)
  - Performance:  bosses TopSpeed 8 / Handling 9 / Toughness 40
                  classes TopSpeed 6 / Handling 8 / Toughness 30 (Accel 10)

This raises every personality EXCEPT Tutorial to boss-or-better reaction + performance:
  ReactionTime -> 0.03, Performance -> {Toughness 40, Handling 9, TopSpeed 8,
  Acceleration max(existing,6)} so the classes keep their higher Accel 10 and gain the
  boss top speed/handling/toughness/reflexes.  Aggression/attack behavior is left at the
  already-boss-level values, so no new zigzag/flip behavior is introduced.

Edits VuDBAsset/AiPersonalityDB.bin.json in place; 3_pack picks it up as a vujb edit.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "AiPersonalityDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

BOSS_PERF = {"Toughness": 40.0, "Handling": 9.0, "TopSpeed": 8.0, "Acceleration": 6.0}
BOSS_REACTION = 0.03


def main() -> None:
    data = json.loads(DB.read_text(encoding="utf-8"))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_ROOT / f"v39_career_ai_boss_crazy_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, backup / DB.name)

    changed = []
    for name, p in data.items():
        if not isinstance(p, dict):
            continue
        if name == "Tutorial":
            continue  # keep the intro easy

        before = (p.get("ReactionTime"), dict(p.get("Performance", {}) or {}))

        # Faster reflexes (boss-level), never slower than current.
        cur_rt = p.get("ReactionTime")
        if cur_rt is None or cur_rt > BOSS_REACTION:
            p["ReactionTime"] = BOSS_REACTION

        # Boss-or-better performance: take the max of current vs boss per stat.
        perf = p.setdefault("Performance", {})
        for stat, boss_val in BOSS_PERF.items():
            perf[stat] = max(float(perf.get(stat, 0.0)), boss_val)

        after = (p.get("ReactionTime"), dict(p["Performance"]))
        if before != after:
            changed.append(name)

    DB.write_text(json.dumps(data, indent=2), encoding="utf-8")
    now = time.time()
    os.utime(DB, (now, now))

    print(f"Backed up AiPersonalityDB to: {backup}")
    print(f"Upgraded {len(changed)} personalities to boss-crazy: {', '.join(changed)}")
    print("Tutorial left easy.")


if __name__ == "__main__":
    main()
