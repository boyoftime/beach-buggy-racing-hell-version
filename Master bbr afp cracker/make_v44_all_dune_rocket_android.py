"""v44 - Every opponent on the Dune, tuned to ROCKET speed.

  1. Opponents.bin: every non-tutorial Car cell -> "Dune".
  2. CarDB Dune: rocket engine -
        stage Max RPM -> 22000/26000/30000/36000/42000 (opponents race stage 3 = 36000),
        Headroom RPM -> 3500, Drag Coeff -> 0.06, Mass 350 kept,
        audio Engine/F1_V12 (high-rev, avoids pitch glitch).

Tutorial opponents untouched.  Backups saved.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OPPONENTS = ROOT / "extracted" / "Assets" / "VuSpreadsheetAsset" / "Opponents.bin"
CARDB = ROOT / "extracted" / "Assets" / "VuDBAsset" / "CarDB.bin.json"
BACKUP_ROOT = ROOT / "mod_backups"

DUNE = "Dune"
ROCKET_RPM = [22000, 26000, 30000, 36000, 42000]
HEADROOM = 3500
DRAG = 0.06
MASS = 350
AUDIO = "Engine/F1_V12"


class Sheet:
    def __init__(self, path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        self.row_count = struct.unpack_from("<I", self.data, 0x0C)[0]
        self.row_offsets = [struct.unpack_from("<I", self.data, 0x18 + 4 * i)[0] for i in range(self.row_count)]
        self.string_pool = struct.unpack_from("<I", self.data, 0x04)[0] + 8
        self.strings = self._scan()
        self.columns = self.row_values(0)
        self.col_index = {n: i for i, n in enumerate(self.columns)}

    def _scan(self):
        out, pos, end = {}, self.string_pool, len(self.data)
        while pos < end:
            z = self.data.find(b"\0", pos)
            if z < 0:
                break
            out.setdefault(self.data[pos:z].decode("ascii", "replace"), pos)
            pos = z + 1
        return out

    def _cell(self, row, col):
        root = self.row_offsets[row] + 8
        rel = struct.unpack_from("<I", self.data, root + 16 + 4 * col)[0]
        return root + rel

    def _cstr(self, pos):
        z = self.data.find(b"\0", pos)
        return self.data[pos:z].decode("ascii", "replace")

    def cell_value(self, row, col):
        cell = self._cell(row, col)
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ == 1: return struct.unpack_from("<i", self.data, cell + 8)[0]
        if typ == 4:
            rel = struct.unpack_from("<I", self.data, cell + 8)[0]
            return self._cstr(cell + rel)
        return None

    def row_values(self, row):
        root = self.row_offsets[row] + 8
        count = struct.unpack_from("<I", self.data, root + 4)[0]
        return [self.cell_value(row, c) for c in range(count)]

    def set_string(self, row, column, value):
        cell = self._cell(row, self.col_index[column])
        if struct.unpack_from("<I", self.data, cell)[0] != 4:
            return False
        if self.cell_value(row, self.col_index[column]) == value:
            return False
        rel = self.strings[value] - cell
        if rel <= 0:
            raise ValueError(f"cannot point row {row} forward to {value!r}")
        struct.pack_into("<I", self.data, cell + 8, rel)
        return True

    def write(self):
        self.path.write_bytes(self.data)


def _set_keys(node, targets):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k in targets and not isinstance(v, (dict, list)):
                node[k] = targets[k]; n += 1
            else:
                n += _set_keys(v, targets)
    elif isinstance(node, list):
        for it in node:
            n += _set_keys(it, targets)
    return n


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v44_all_dune_rocket_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPPONENTS, backup_dir / OPPONENTS.name)
    shutil.copy2(CARDB, backup_dir / CARDB.name)

    # 1) all opponents -> Dune
    sheet = Sheet(OPPONENTS)
    changed = 0
    for row in range(1, sheet.row_count):
        name = str(sheet.row_values(row)[sheet.col_index["Name"]])
        if name.startswith("Tutorial"):
            continue
        changed += int(sheet.set_string(row, "Car", DUNE))
    sheet.write()
    now = time.time()
    os.utime(OPPONENTS, (now, now))

    # 2) Dune -> rocket
    data = json.loads(CARDB.read_text(encoding="utf-8"))
    dune = data[DUNE]
    for i, stage in enumerate(dune.get("Stages", [])):
        eng = stage.get("Engine")
        if isinstance(eng, dict):
            eng["Max RPM"] = ROCKET_RPM[i] if i < len(ROCKET_RPM) else ROCKET_RPM[-1]
    eng = dune.setdefault("Engine", {})
    eng["Headroom RPM"] = HEADROOM
    eng.setdefault("Audio", {})["Run"] = AUDIO
    _set_keys(dune, {"Mass": MASS, "Drag Coeff": DRAG})
    CARDB.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.utime(CARDB, (now, now))

    print(f"Backup: {backup_dir}")
    print(f"Opponents set to Dune: {changed}")
    print(f"Dune rocket RPM: {ROCKET_RPM}, Headroom {HEADROOM}, Drag {DRAG}, Mass {MASS}")


if __name__ == "__main__":
    main()
