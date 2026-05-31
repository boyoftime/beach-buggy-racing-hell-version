"""Keep bosses fast, but stop launch wheelies/flips.

v36/v37 made bosses very strong by setting boss Performance.Acceleration to 12.
That launch torque makes some boss cars lift their front wheels and flip/struggle
when accelerating.  This patch does not touch CarDB physics.  It keeps boss
TopSpeed high and only softens boss acceleration multipliers.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AI_DB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "AiPersonalityDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    now = time.time()
    os.utime(path, (now, now))


def setv(obj: dict, key: str, value) -> int:
    if not isinstance(obj, dict) or obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def main() -> None:
    if not AI_DB.exists():
        raise SystemExit(f"Missing {AI_DB}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v39_boss_no_wheelie_launch_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AI_DB, backup_dir / AI_DB.name)

    data = load(AI_DB)
    changes = 0
    for name, ai in data.items():
        if not isinstance(ai, dict) or not name.startswith("Boss"):
            continue

        perf = ai.setdefault("Performance", {})
        changes += setv(perf, "TopSpeed", 8.0)
        changes += setv(perf, "Handling", 9.0)
        changes += setv(perf, "Toughness", 40.0)
        changes += setv(perf, "Acceleration", 6.0)

        # Some bosses also have phase-specific acceleration multipliers.  Keep
        # these modest so launch/mid-race boosts do not stack into wheelies.
        race_script = ai.get("RaceScript", {})
        if isinstance(race_script, dict):
            for phase_name, phase in race_script.items():
                if not isinstance(phase, dict):
                    continue
                phase_perf = phase.get("Performance")
                if not isinstance(phase_perf, dict) or "Acceleration" not in phase_perf:
                    continue
                target = 0.85 if phase_name == "Early" else 1.0
                old = phase_perf.get("Acceleration")
                if isinstance(old, (int, float)) and old > target:
                    phase_perf["Acceleration"] = target
                    changes += 1

    save(AI_DB, data)
    print(f"Backup: {backup_dir}")
    print(f"Boss no-wheelie acceleration changes: {changes}")
    print("Boss TopSpeed/ability spam kept; only acceleration was softened.")


if __name__ == "__main__":
    main()
