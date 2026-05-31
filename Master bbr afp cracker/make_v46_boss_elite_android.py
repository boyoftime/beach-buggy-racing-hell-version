"""v46 - Make every BOSS an elite, near-unbeatable, perfectly precise driver.

Targets the 12 boss personalities (Boss* + DuelSkeleton).  Leaves the regular career
classes on their v45 super-boost; bosses are pushed clearly above them.

Per boss:
  Ability / powerup spam (lower frequency value = used MORE often):
    AbilityFrequency 0.2 -> 0.02, BossPowerUpFrequency 0.2 -> 0.02,
    BoostFrequency 1 -> 0.1, SpikesFrequency 20 -> 2.
  Perfect precision (no mistakes / no wobble):
    PowerslideBendiness/SpikesBendiness/BoostBendiness/ThrottleDownBendiness 0.55 -> 0.0,
    ReactionTime 0.03 -> 0.01, Avoidance 0.7 -> 1.0 (dodges every hazard),
    ThrottleDownFrequency 999 kept (never eases off), MaximumLead 0 (no cap).
  Aggression:  Aggro 1.5 -> 5.0.
  Elite performance:  {Toughness 60, Handling 10, TopSpeed 9, Acceleration 10}.
  Uses ALL powerups maximally:  every PowerUpWeights entry -> 100; offensive
    BehaviorWeights -> 100 (PowerSlide kept 0.05, PowerUpDropped 0).
  RaceScript:  elite boost - all phases DesiredCarPack "Ahead",
    Performance {TopSpeed 2.0, Acceleration 2.0, Handling>=1, Toughness>=1}.

AiPersonalityDB only.  Backup saved.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIDB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "AiPersonalityDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

ELITE_PERF = {"Toughness": 60.0, "Handling": 10.0, "TopSpeed": 9.0, "Acceleration": 10.0}
OFFENSIVE = {"PowerUpThrow", "PowerUpSeek", "PowerUpShield", "PowerUpToughness",
             "PowerUpGlobal", "PowerUpLongShot", "SpikedTires", "Boost"}


def elite_phase(existing):
    cur = (existing or {}).get("Performance", {}) or {}
    return {
        "DesiredCarPack": "Ahead",
        "Performance": {
            "Toughness": max(1.0, float(cur.get("Toughness", 1.0))),
            "Handling": max(1.0, float(cur.get("Handling", 1.0))),
            "TopSpeed": 2.0,
            "Acceleration": 2.0,
        },
    }


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v46_boss_elite_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AIDB, backup_dir / AIDB.name)

    ai = json.loads(AIDB.read_text(encoding="utf-8"))
    bosses = [k for k in ai if k.startswith("Boss") or k == "DuelSkeleton"]

    for name in bosses:
        p = ai[name]
        # frequencies (lower = more often)
        p["AbilityFrequency"] = 0.02
        p["BossPowerUpFrequency"] = 0.02
        p["BoostFrequency"] = 0.1
        p["SpikesFrequency"] = 2
        # precision / no mistakes
        for bend in ("PowerslideBendiness", "SpikesBendiness", "BoostBendiness", "ThrottleDownBendiness"):
            if bend in p:
                p[bend] = 0.0
        p["ReactionTime"] = 0.01
        p["Avoidance"] = 1.0
        p["ThrottleDownFrequency"] = 999.0
        p["MaximumLead"] = 0
        p["Aggro"] = 5.0
        # elite performance
        p["Performance"] = dict(ELITE_PERF)
        # use every powerup maximally
        for entry in p.get("PowerUpWeights", []):
            for k in entry:
                entry[k] = 100.0
        for entry in p.get("BehaviorWeights", []):
            for k in entry:
                if k in OFFENSIVE:
                    entry[k] = 100.0
                elif k == "PowerUpDropped":
                    entry[k] = 0.0
        # elite race-script boost
        rs = p.setdefault("RaceScript", {})
        for phase in ("Early", "Mid", "Late"):
            rs[phase] = elite_phase(rs.get(phase))

    AIDB.write_text(json.dumps(ai, indent=2), encoding="utf-8")
    now = time.time()
    os.utime(AIDB, (now, now))

    print(f"Backup: {backup_dir}")
    print(f"Elite bosses ({len(bosses)}): {', '.join(bosses)}")


if __name__ == "__main__":
    main()
