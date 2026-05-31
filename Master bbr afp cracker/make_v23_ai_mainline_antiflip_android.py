"""Make AI hold the main racing line and resist flipping.

This keeps the v22 stable physics baseline.  It does not touch surface grip,
springs, drag, aero, or global speed.  The goal is cleaner enemy behavior:
less zigzagging toward pickups/avoidance targets, no alternate waypoint routes,
and much stronger rollover/wheelie resistance.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "extracted" / "Assets"
DB = ASSETS / "VuDBAsset"
LEVELS = ASSETS / "VuTemplateAsset" / "Levels"
BACKUP_ROOT = ROOT / "mod_backups"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    now = time.time()
    os.utime(path, (now, now))


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v23_ai_mainline_antiflip_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        rel = path.relative_to(ASSETS)
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
    return backup_dir


def set_if_changed(obj: dict, key: str, value) -> int:
    if obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def set_weight(weights: list, key: str, value: float) -> int:
    changes = 0
    for entry in weights:
        if isinstance(entry, dict) and key in entry and entry[key] != value:
            entry[key] = value
            changes += 1
    return changes


def patch_ai_personality(path: Path) -> int:
    data = load(path)
    changes = 0
    for name, ai in data.items():
        if name == "Tutorial" or not isinstance(ai, dict):
            continue

        # Less lateral decision making: stay on the waypoint route instead of
        # weaving for pickups, hazards, or aggressive contact.
        changes += set_if_changed(ai, "Avoidance", 0.7)
        changes += set_if_changed(ai, "Aggro", 1.5)
        changes += set_if_changed(ai, "ReactionTime", 0.03 if name.startswith("Boss") else 0.05)
        changes += set_if_changed(ai, "PowerslideFrequency", 240)
        changes += set_if_changed(ai, "PowerslideBendiness", 0.55)
        changes += set_if_changed(ai, "BoostBendiness", 0.55)
        changes += set_if_changed(ai, "SpikesBendiness", 0.55)
        changes += set_if_changed(ai, "ThrottleDownBendiness", 0.55)

        perf = ai.setdefault("Performance", {})
        changes += set_if_changed(perf, "Handling", 8.0)
        changes += set_if_changed(perf, "Toughness", max(float(perf.get("Toughness", 1.0)), 30.0))

        behavior = ai.get("BehaviorWeights")
        if isinstance(behavior, list):
            changes += set_weight(behavior, "PowerUpSeek", 0.2)
            changes += set_weight(behavior, "PowerUpDropped", 0.0)
            changes += set_weight(behavior, "PowerUpShield", 0.5)
            changes += set_weight(behavior, "PowerUpToughness", 0.5)
            changes += set_weight(behavior, "SpikedTires", 0.1)
            changes += set_weight(behavior, "PowerSlide", 0.05)

    save(path, data)
    return changes


def patch_car_antiflip(path: Path) -> int:
    data = load(path)
    changes = 0

    default = data.get("Default")
    if isinstance(default, dict):
        suspension = default.setdefault("Suspension", {})
        changes += set_if_changed(suspension, "Rollover Resistance", 5.0)
        changes += set_if_changed(suspension, "Wheelie Resistance", 4.0)
        chassis = default.get("Chassis")
        if isinstance(chassis, dict):
            stability = chassis.setdefault("Stability", {})
            changes += set_if_changed(stability, "X", 8)
            changes += set_if_changed(stability, "Y", 10)
            changes += set_if_changed(stability, "Z", 8)

    for car_name, car in data.items():
        if car_name == "Default" or not isinstance(car, dict):
            continue
        suspension = car.get("Suspension")
        if isinstance(suspension, dict):
            changes += set_if_changed(suspension, "Rollover Resistance", 5.0)
            changes += set_if_changed(suspension, "Wheelie Resistance", 4.0)

    save(path, data)
    return changes


def walk_waypoints(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "VuAiWaypointEntity":
            yield obj
        for value in obj.values():
            yield from walk_waypoints(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_waypoints(value)


def patch_level_mainline(path: Path) -> int:
    data = load(path)
    changes = 0
    for waypoint in walk_waypoints(data):
        script = (
            waypoint.get("data", {})
            .get("Components", {})
            .get("VuScriptComponent", {})
        )
        refs = script.get("Refs")
        if isinstance(refs, dict) and "NextAlternate" in refs:
            refs.pop("NextAlternate", None)
            changes += 1

        ref_connections = script.get("RefConnections")
        if isinstance(ref_connections, list):
            kept = [
                conn
                for conn in ref_connections
                if not (isinstance(conn, dict) and conn.get("RefName") == "NextAlternate")
            ]
            if len(kept) != len(ref_connections):
                script["RefConnections"] = kept
                changes += len(ref_connections) - len(kept)

    if changes:
        save(path, data)
    return changes


def main() -> None:
    ai_path = DB / "AiPersonalityDB.bin.json"
    car_path = DB / "CarDB.bin.json"
    level_paths = sorted(path for path in LEVELS.glob("*.bin.json") if "VuAiWaypointEntity" in path.read_text(encoding="utf-8"))
    paths = [ai_path, car_path] + level_paths

    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))

    backup_dir = backup(paths)
    ai_changes = patch_ai_personality(ai_path)
    car_changes = patch_car_antiflip(car_path)
    level_changes = sum(patch_level_mainline(path) for path in level_paths)

    print(f"Backup: {backup_dir}")
    print(f"AiPersonalityDB line-holding changes: {ai_changes}")
    print(f"CarDB anti-flip changes: {car_changes}")
    print(f"Level waypoint alternate-route removals: {level_changes}")
    print("AI should stay closer to the primary path and resist flipping at 1000HP.")


if __name__ == "__main__":
    main()
