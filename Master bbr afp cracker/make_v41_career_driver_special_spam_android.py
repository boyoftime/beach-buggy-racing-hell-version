from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AI_DB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "AiPersonalityDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

BOSS_NAMES = {
    "Boss",
    "BossAlien",
    "BossBeachBro",
    "BossBunny",
    "BossDisco",
    "BossHula",
    "BossLucha",
    "BossRad",
    "BossRoller",
    "BossSkeleton",
    "BossTribal",
}

SKIP_NAMES = {"Tutorial"} | BOSS_NAMES

BOSSY_BEHAVIOR_WEIGHTS = {
    "PowerUpThrow": 80.0,
    "PowerUpSeek": 60.0,
    "PowerUpDropped": 0.0,
    "PowerUpShield": 12.0,
    "PowerUpToughness": 18.0,
    "PowerUpGlobal": 85.0,
    "PowerUpLongShot": 90.0,
    "SpikedTires": 12.0,
    "Boost": 45.0,
    "PowerSlide": 0.05,
}

BOSSY_POWERUP_WEIGHTS = [
    {"Firework": 55.0},
    {"Fireball": 65.0},
    {"Scattershot": 65.0},
    {"FreezeRay": 70.0},
    {"EarthStrike": 80.0},
    {"HomingMissile": 80.0},
    {"Tornado": 80.0},
    {"Lightning": 85.0},
    {"RemoteControl": 75.0},
    {"OilSlick": 20.0},
    {"ChickenCrate": 18.0},
    {"MysteryCrate": 18.0},
    {"BasicShield": 14.0},
    {"Toughness": 18.0},
    {"Fake": 16.0},
    {"Spring": 18.0},
    {"LowGravity": 60.0},
    {"BigTires": 12.0},
    {"Confusion": 70.0},
    {"NitroCar": 35.0},
    {"BallChain": 80.0},
    {"DeathBat": 95.0},
    {"PoliceChase": 85.0},
    {"Earthquake": 90.0},
]


def setv(obj: dict, key: str, value) -> int:
    if obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def set_weight(weights: list, key: str, value: float) -> int:
    found = False
    changes = 0
    for entry in weights:
        if isinstance(entry, dict) and key in entry:
            found = True
            if entry[key] != value:
                entry[key] = value
                changes += 1
    if not found:
        weights.append({key: value})
        changes += 1
    return changes


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v41_career_driver_special_spam_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AI_DB, backup_dir / AI_DB.name)

    data = json.loads(AI_DB.read_text(encoding="utf-8"))
    changed_records: list[str] = []
    changes = 0

    for name, ai in data.items():
        if not isinstance(ai, dict) or name in SKIP_NAMES:
            continue

        before_changes = changes
        changes += setv(ai, "AbilityFrequency", 0.2)
        changes += setv(ai, "BossPowerUpFrequency", 0.2)
        changes += setv(ai, "BoostFrequency", 1)
        changes += setv(ai, "SpikesFrequency", 20)
        changes += setv(ai, "MaximumLead", 0)

        behavior = ai.setdefault("BehaviorWeights", [])
        if not isinstance(behavior, list):
            behavior = []
            ai["BehaviorWeights"] = behavior
            changes += 1
        for key, value in BOSSY_BEHAVIOR_WEIGHTS.items():
            changes += set_weight(behavior, key, value)

        if ai.get("PowerUpWeights") != BOSSY_POWERUP_WEIGHTS:
            ai["PowerUpWeights"] = BOSSY_POWERUP_WEIGHTS
            changes += 1

        for phase in ai.setdefault("RaceScript", {}).values():
            if isinstance(phase, dict):
                changes += setv(phase, "DesiredCarPack", "Ahead")

        if changes != before_changes:
            changed_records.append(name)

    AI_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.utime(AI_DB, None)

    print(f"Backup: {backup_dir}")
    print(f"Changed AI personality records: {', '.join(changed_records)}")
    print(f"Total changes: {changes}")
    print("Kept performance/speed/CarDB unchanged; only special/powerup cadence and attack weights changed.")


if __name__ == "__main__":
    main()
