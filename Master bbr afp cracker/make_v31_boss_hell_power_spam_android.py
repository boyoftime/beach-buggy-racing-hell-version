"""Make career bosses spam much stronger abilities and powerups.

No CarDB physics changes here.  This only touches boss AI usage cadence and
CarEffectDB ability/powerup effects so bosses become much harder without
reintroducing road shaking.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB = ROOT / "extracted" / "Assets" / "VuDBAsset"
BACKUP_ROOT = ROOT / "mod_backups"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    now = time.time()
    os.utime(path, (now, now))


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v31_boss_hell_power_spam_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def setv(obj: dict, key: str, value) -> int:
    if not isinstance(obj, dict):
        return 0
    if obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def set_weight(weights: list, key: str, value: float) -> int:
    if not isinstance(weights, list):
        return 0
    changes = 0
    found = False
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


def patch_ai(path: Path) -> int:
    data = load(path)
    changes = 0
    offensive_weights = {
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
    powerup_weights = [
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

    for name, ai in data.items():
        if not isinstance(ai, dict) or not name.startswith("Boss"):
            continue

        # These values behave like time/cooldown knobs in practice: smaller is meaner.
        changes += setv(ai, "AbilityFrequency", 0.2)
        changes += setv(ai, "BossPowerUpFrequency", 0.2)
        changes += setv(ai, "BoostFrequency", 1)
        changes += setv(ai, "SpikesFrequency", 20)
        changes += setv(ai, "MaximumLead", 0)

        perf = ai.setdefault("Performance", {})
        changes += setv(perf, "TopSpeed", 8.0)
        changes += setv(perf, "Acceleration", 12.0)
        changes += setv(perf, "Handling", 9.0)
        changes += setv(perf, "Toughness", 40.0)

        behavior = ai.setdefault("BehaviorWeights", [])
        for key, value in offensive_weights.items():
            changes += set_weight(behavior, key, value)
        if "PowerUpWeights" not in ai or not isinstance(ai.get("PowerUpWeights"), list):
            ai["PowerUpWeights"] = []
            changes += 1
        ai["PowerUpWeights"] = powerup_weights
        changes += 1

        for phase in ai.setdefault("RaceScript", {}).values():
            if isinstance(phase, dict):
                changes += setv(phase, "DesiredCarPack", "Ahead")

    save(path, data)
    return changes


def patch_missile(data: dict, name: str, *, speed=None, range_=None, radius=None, aoe=None, homing=None, cone=None) -> int:
    obj = data.get(name, {})
    md = obj.get("MissileData")
    changes = 0
    targets = md if isinstance(md, list) else [md]
    for missile in targets:
        if not isinstance(missile, dict):
            continue
        if speed is not None:
            changes += setv(missile, "Speed", speed)
        if range_ is not None:
            changes += setv(missile, "Range", range_)
        if radius is not None:
            changes += setv(missile, "CarCollisionRadius", radius)
        if aoe is not None:
            changes += setv(missile, "AoeDist", aoe)
        if homing is not None:
            changes += setv(missile, "HomingRange", homing)
        if cone is not None:
            changes += setv(missile, "TargetAcquisitionCone", cone)
    return changes


def patch_effects(path: Path) -> int:
    data = load(path)
    changes = 0

    # Beach Bro: many more beach balls, wider carpet, faster roll, harder spring hit.
    beach = data.get("BeachBro", {})
    changes += setv(beach, "ShootCount", 32)
    changes += setv(beach, "ShootSpeed", 230)
    changes += setv(beach, "ShootSpread", 65)
    changes += setv(beach, "Duration", 6)
    changes += setv(beach, "DropSpread", 340)
    changes += setv(beach, "DropCount", 55)
    changes += setv(beach, "DropSpeed", 80)
    ball = beach.get("BallData", {})
    changes += setv(ball, "LinearDamping", 0.04)
    changes += setv(ball, "Mass", 18)
    changes += setv(ball, "SelfCollisionTime", 0.25)
    changes += setv(ball, "Radius", 1.25)
    changes += setv(ball, "LifeTime", 22)
    changes += setv(data.get("BeachBroVictim", {}), "VerticalSpeed", 95)

    # Leilani/Hula: flower carpet becomes a stopping field.
    hula = data.get("Hula", {})
    changes += setv(hula, "Power", 4.0)
    changes += setv(hula, "MaxCount", 180)
    changes += setv(hula, "FadeTime", 3)
    changes += setv(hula, "Radius", 3.75)
    changes += setv(hula, "LifeTime", 32)
    changes += setv(hula, "Duration", 14)
    changes += setv(hula, "MaxHeight", 8.0)
    changes += setv(hula, "Speed", 95)
    flower = data.get("FlowerVictim", {})
    changes += setv(flower, "Duration", 10)
    changes += setv(flower, "PhysicsDamping", 0.02)
    changes += setv(flower, "PhysicsDuration", 7.0)
    changes += setv(flower, "SoftKillTime", 3)
    changes += setv(flower, "SplatPfxDist", 20)

    # Other character abilities: bigger areas, longer victim effects, harder hits.
    rad = data.get("Rad", {})
    changes += setv(rad, "Power", 4.0)
    changes += setv(rad, "MaxCount", 160)
    changes += setv(rad, "Radius", 3.0)
    changes += setv(rad, "LifeTime", 30)
    changes += setv(rad, "Duration", 14)
    changes += setv(rad, "Speed", 95)
    changes += setv(data.get("RadVictim", {}), "Duration", 8)
    changes += setv(data.get("RadVictim", {}), "PhysicsDamping", 0.05)

    bunny = data.get("Bunny", {})
    changes += setv(bunny, "MaxCount", 70)
    changes += setv(bunny, "Duration", 8)
    changes += patch_missile(data, "Bunny", speed=260, range_=450, radius=2.5)
    changes += setv(data.get("BunnyVictim", {}), "Duration", 8)
    changes += setv(data.get("BunnyVictim", {}), "SoftKillTime", 2)

    for effect_name in ("Roller", "Lucha"):
        obj = data.get(effect_name, {})
        changes += setv(obj, "Power", 5.0)
        changes += setv(obj, "TractionFactor", 3.0)
        changes += setv(obj, "Duration", 20)
        changes += setv(obj, "Speed", 85)
    changes += setv(data.get("WrestlingVictim", {}), "VerticalSpeed", 95)
    changes += setv(data.get("WrestlingVictim", {}), "Duration", 2)
    changes += setv(data.get("WrestlingVictim", {}), "Rotation", 720)

    tribal = data.get("Tribal", {}).get("MissileData", {})
    changes += setv(tribal, "LifeTime", 12.0)
    changes += setv(tribal, "CarApplyRadius", 55)
    changes += setv(tribal, "Speed", 320)
    curse = data.get("TikiCurse", {})
    changes += setv(curse, "Duration", 16)
    changes += setv(curse, "SoftKillTime", 3)
    changes += setv(curse, "SplatPfxDist", 22)

    disco = data.get("Disco", {})
    changes += setv(disco, "Duration", 3)
    disco_md = disco.get("MissileData", {})
    changes += setv(disco_md, "LifeTime", 12.0)
    changes += setv(disco_md, "CarApplyRadius", 60)
    changes += setv(disco_md, "Speed", 320)
    disco_v = data.get("DiscoVictim", {})
    changes += setv(disco_v, "Duration", 14)
    changes += setv(disco_v, "SteeringFactor", 5.0)
    changes += setv(disco_v, "SteeringErrorInterval", 0.15)
    changes += setv(disco_v, "SteeringErrorAmount", 1.0)
    changes += setv(disco_v, "SoftKillTime", 3)

    skeleton = data.get("Skeleton", {})
    changes += setv(skeleton, "Duration", 22)
    changes += setv(skeleton, "CarAlpha", 0.05)
    alien = data.get("Alien", {})
    changes += setv(alien, "Range", 260)
    changes += setv(alien, "Duration", 0.5)

    # Common offensive powerups that bosses now prefer heavily.
    changes += patch_missile(data, "Fireball", speed=320, range_=520, radius=4.0, aoe=22)
    changes += patch_missile(data, "Firework", speed=260, range_=420, radius=2.5)
    changes += patch_missile(data, "Scattershot", speed=300, range_=360, radius=3.0)
    changes += patch_missile(data, "Tornado", speed=280, range_=500, radius=2.5, homing=180, cone=180)
    changes += patch_missile(data, "RemoteControl", speed=280, range_=500, radius=2.5, cone=180)
    changes += patch_missile(data, "DeathBat", speed=320, radius=3.0, homing=220, cone=220)
    for victim_name in ("TornadoVictim", "ConfusionVictim", "LowGravityVictim", "OilyTiresVictim"):
        victim = data.get(victim_name, {})
        changes += setv(victim, "Duration", 10)
        if "SoftKillTime" in victim:
            changes += setv(victim, "SoftKillTime", 3)
    earthquake = data.get("EarthquakeVictim", {})
    changes += setv(earthquake, "Duration", 9)
    changes += setv(earthquake, "MaxImpulse", 55.0)
    changes += setv(earthquake, "ImpulseFrequency", 9.0)
    freeze = data.get("FreezeRayVictim", {})
    changes += setv(freeze, "Duration", 10)
    if "SteeringErrorAmount" in freeze:
        changes += setv(freeze, "SteeringErrorAmount", 1.0)

    save(path, data)
    return changes


def main() -> None:
    paths = [
        DB / "AiPersonalityDB.bin.json",
        DB / "CarEffectDB.bin.json",
    ]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))

    backup_dir = backup(paths)
    ai_changes = patch_ai(paths[0])
    effect_changes = patch_effects(paths[1])

    print(f"Backup: {backup_dir}")
    print(f"AiPersonalityDB boss spam changes: {ai_changes}")
    print(f"CarEffectDB boss/power effect changes: {effect_changes}")
    print("Bosses should spam abilities/powerups and cover much larger areas.")


if __name__ == "__main__":
    main()
