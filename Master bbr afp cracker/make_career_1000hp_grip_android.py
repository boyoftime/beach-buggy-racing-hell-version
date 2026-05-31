"""Force every career series to 1000HP and improve high-speed cornering.

This is the follow-up to make_career_1000hp_chaos_android.py.  Opponents were
already moved to Stage 3; this patch changes the career series themselves to
Stage 3 so the front-end cup cards show/use 1000HP, then improves grip,
steering response, braking, and AI corner stability for the faster races.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB = ROOT / "extracted" / "Assets" / "VuDBAsset"
BACKUP_ROOT = ROOT / "mod_backups"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"career_1000hp_grip_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def set_if_changed(obj: dict, key: str, value) -> int:
    old = obj.get(key)
    if old == value:
        return 0
    obj[key] = value
    return 1


def patch_series(path: Path) -> int:
    data = load(path)
    changes = 0
    for series in data.values():
        if isinstance(series, dict) and "Stage" in series:
            changes += set_if_changed(series, "Stage", 3)
    save(path, data)
    return changes


def patch_car_db(path: Path) -> int:
    data = load(path)
    changes = 0

    default = data.get("Default", {})
    changes += set_if_changed(default, "Draw Distance", 500.0)
    changes += set_if_changed(default, "Ultra Draw Distance", 700.0)
    changes += set_if_changed(default, "Inertia Factor", 1.05)
    changes += set_if_changed(default, "Max Steering Angle", 58.0)
    changes += set_if_changed(default, "Power Slide Coeff", 0.65)
    changes += set_if_changed(default, "Power Slide Steering Factor", 2.25)
    changes += set_if_changed(default, "Power Slide Traction Factor", 0.45)

    chassis = default.get("Chassis", {})
    changes += set_if_changed(chassis, "Aero Lift", -45)
    changes += set_if_changed(chassis, "Air Steering Speed", 150)
    changes += set_if_changed(chassis, "Fast Steering Speed", 180)
    changes += set_if_changed(chassis, "Slow Steering Speed", 110)
    changes += set_if_changed(chassis, "Fast Steering Boat Speed", 150)
    changes += set_if_changed(chassis, "Slow Steering Boat Speed", 70)
    changes += set_if_changed(chassis, "Lat Skin Friction Coeff", 0.08)
    changes += set_if_changed(chassis, "Long Skin Friction Coeff", 0.02)
    changes += set_if_changed(chassis, "Power Slide Coeff", 0.22)
    changes += set_if_changed(chassis, "Water Power Slide Coeff", 0.1)
    stability = chassis.setdefault("Stability", {})
    changes += set_if_changed(stability, "X", 14)
    changes += set_if_changed(stability, "Y", 16)
    changes += set_if_changed(stability, "Z", 14)

    suspension = default.get("Suspension", {})
    changes += set_if_changed(suspension, "Power Slide Coeff", 0.22)
    changes += set_if_changed(suspension, "Visual Extension Rate", 3.0)

    for car_name, car in data.items():
        if car_name == "Default" or not isinstance(car, dict):
            continue

        engine = car.get("Engine")
        if isinstance(engine, dict):
            changes += set_if_changed(engine, "Max Braking Force", 24000)

        car_chassis = car.get("Chassis")
        if isinstance(car_chassis, dict):
            old_drag = car_chassis.get("Drag Coeff")
            if isinstance(old_drag, (int, float)) and old_drag > 0.13:
                changes += set_if_changed(car_chassis, "Drag Coeff", 0.13)

        car_suspension = car.get("Suspension")
        if isinstance(car_suspension, dict):
            changes += set_if_changed(car_suspension, "Damping Coeff", 7000.0)
            changes += set_if_changed(car_suspension, "Lower Spring Coeff", 28000.0)
            changes += set_if_changed(car_suspension, "Upper Spring Coeff", 56000.0)
            changes += set_if_changed(car_suspension, "Rollover Resistance", 2.8)
            changes += set_if_changed(car_suspension, "Wheelie Resistance", 2.2)
            changes += set_if_changed(car_suspension, "Power Slide Coeff", 0.22)
            changes += set_if_changed(car_suspension, "Visual Extension Rate", 3.0)

    save(path, data)
    return changes


def patch_surface_db(path: Path) -> int:
    data = load(path)
    changes = 0
    friction = {
        "<none>": 0.0,
        "Water": 0.0,
        "Oil": 0.18,
        "Ice": 0.52,
        "Snow": 0.65,
        "Sand": 0.70,
        "Mud": 0.65,
        "Ramp": 0.55,
    }
    for surface in data:
        if not isinstance(surface, dict) or "Friction" not in surface:
            continue
        name = surface.get("Name")
        target = friction.get(name, 0.90)
        changes += set_if_changed(surface, "Friction", target)
    save(path, data)
    return changes


def patch_ai(path: Path) -> int:
    data = load(path)
    changes = 0
    for name, ai in data.items():
        if name == "Tutorial" or not isinstance(ai, dict):
            continue
        perf = ai.setdefault("Performance", {})
        changes += set_if_changed(perf, "Handling", 9.0)
        changes += set_if_changed(ai, "Avoidance", 7.0)
        changes += set_if_changed(ai, "ReactionTime", 0.04 if name.startswith("Boss") else 0.07)
        changes += set_if_changed(ai, "PowerslideFrequency", 120)
        changes += set_if_changed(ai, "PowerslideBendiness", 1.55)
        changes += set_if_changed(ai, "BoostBendiness", 1.45)
        changes += set_if_changed(ai, "SpikesBendiness", 1.45)
        changes += set_if_changed(ai, "ThrottleDownBendiness", 1.55)
        if "MaximumLead" in ai:
            changes += set_if_changed(ai, "MaximumLead", 0)
    save(path, data)
    return changes


def main() -> None:
    paths = [
        DB / "SeriesDB.bin.json",
        DB / "CarDB.bin.json",
        DB / "SurfaceDB.bin.json",
        DB / "AiPersonalityDB.bin.json",
    ]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))

    backup_dir = backup(paths)
    print(f"Backup: {backup_dir}")
    print(f"SeriesDB changes: {patch_series(paths[0])}")
    print(f"CarDB handling changes: {patch_car_db(paths[1])}")
    print(f"SurfaceDB grip changes: {patch_surface_db(paths[2])}")
    print(f"AiPersonalityDB cornering changes: {patch_ai(paths[3])}")
    print("Career series now Stage 3 / 1000HP, with faster high-speed corner control.")


if __name__ == "__main__":
    main()
