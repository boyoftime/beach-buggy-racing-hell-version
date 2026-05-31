"""v45 - Make EVERY career AI move like it has a permanent super-boost.

Root cause of "one fast, rest slow": BBR's RaceScript Performance multipliers.  The
"loser" personalities (e.g. ClassALoser, used by many opponents) carry multipliers
BELOW 1.0 - TopSpeed 0.5, Acceleration 0.6 - so those cars are throttled slow no
matter which car they drive, while non-loser AI run full speed.

Fix:
  1. AiPersonalityDB: for every non-Tutorial personality, overwrite all RaceScript
     phases (Early/Mid/Late) with a uniform SUPER-BOOST and never a slowdown:
        DesiredCarPack "Ahead", Performance {TopSpeed 1.6, Acceleration 1.6,
        Handling >=1.0, Toughness >=1.0}.  No AI is ever held below full speed.
  2. CarDB Dune: pull back from the uncontrollable v44 rocket (42k RPM / 0.06 drag)
     to fast-but-DRIVABLE so the whole pack can actually sustain the speed instead
     of crashing: stage Max RPM 16000/18000/20000/23000/26000, Drag 0.09,
     Headroom 2800, Mass 350, F1_V12 audio.

Tutorial untouched.  Backups saved.
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
CARDB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "CarDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

BOOST_TS = 1.6
BOOST_ACC = 1.6
DUNE_RPM = [16000, 18000, 20000, 23000, 26000]
DUNE_DRAG = 0.09
DUNE_HEADROOM = 2800


def boosted_phase(existing: dict) -> dict:
    cur = (existing or {}).get("Performance", {}) or {}
    return {
        "DesiredCarPack": "Ahead",
        "Performance": {
            "Toughness": max(1.0, float(cur.get("Toughness", 1.0))),
            "Handling": max(1.0, float(cur.get("Handling", 1.0))),
            "TopSpeed": BOOST_TS,
            "Acceleration": BOOST_ACC,
        },
    }


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v45_uniform_ai_superboost_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AIDB, backup_dir / AIDB.name)
    shutil.copy2(CARDB, backup_dir / CARDB.name)

    # 1) Uniform super-boost RaceScript on every non-tutorial personality.
    ai = json.loads(AIDB.read_text(encoding="utf-8"))
    fixed = []
    for name, p in ai.items():
        if not isinstance(p, dict) or name == "Tutorial":
            continue
        rs = p.setdefault("RaceScript", {})
        for phase in ("Early", "Mid", "Late"):
            rs[phase] = boosted_phase(rs.get(phase))
        fixed.append(name)
    AIDB.write_text(json.dumps(ai, indent=2), encoding="utf-8")

    # 2) Dune -> fast but drivable.
    cars = json.loads(CARDB.read_text(encoding="utf-8"))
    dune = cars["Dune"]
    for i, stage in enumerate(dune.get("Stages", [])):
        eng = stage.get("Engine")
        if isinstance(eng, dict):
            eng["Max RPM"] = DUNE_RPM[i] if i < len(DUNE_RPM) else DUNE_RPM[-1]
    eng = dune.setdefault("Engine", {})
    eng["Headroom RPM"] = DUNE_HEADROOM
    eng.setdefault("Audio", {})["Run"] = "Engine/F1_V12"
    # set drag (recursive single occurrence)
    def setdrag(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "Drag Coeff" and not isinstance(v, (dict, list)):
                    node[k] = DUNE_DRAG
                else:
                    setdrag(v)
        elif isinstance(node, list):
            for it in node:
                setdrag(it)
    setdrag(dune)
    CARDB.write_text(json.dumps(cars, indent=1), encoding="utf-8")

    now = time.time()
    os.utime(AIDB, (now, now))
    os.utime(CARDB, (now, now))

    print(f"Backup: {backup_dir}")
    print(f"Super-boost applied to {len(fixed)} personalities: {', '.join(fixed)}")
    print(f"Dune RPM -> {DUNE_RPM}, Drag {DUNE_DRAG}, Headroom {DUNE_HEADROOM}")


if __name__ == "__main__":
    main()
