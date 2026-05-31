"""v41 - Give every career opponent the Grand Prix (Formula) car, monster-tuned.

Follow-up to v40 (everyone on the Dune looked samey).  Switch all non-tutorial
opponents to the sleek Grand Prix car (internal name "Formula"), and monster-buff
Formula so it stays as fast as the v15 Dune:
  - Opponents.bin: every non-tutorial Car cell -> "Formula"
  - CarDB Formula: Mass 600 -> 350, Drag Coeff 0.25 -> 0.12 (matches Dune monster).
    Formula already has Dune-level stage Max RPM (9000..12500), so no RPM change needed.

Tutorial opponents left stock.  Backups saved for both files.
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
CAR = "Formula"
MONSTER_MASS = 350
MONSTER_DRAG = 0.12


class Sheet:
    def __init__(self, path: Path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        self.row_count = struct.unpack_from("<I", self.data, 0x0C)[0]
        self.row_offsets = [struct.unpack_from("<I", self.data, 0x18 + 4 * i)[0] for i in range(self.row_count)]
        self.string_pool = struct.unpack_from("<I", self.data, 0x04)[0] + 8
        self.strings = self._scan_strings()
        self.columns = self.row_values(0)
        self.col_index = {n: i for i, n in enumerate(self.columns)}

    def _scan_strings(self):
        out, pos, end = {}, self.string_pool, len(self.data)
        while pos < end:
            z = self.data.find(b"\0", pos)
            if z < 0:
                break
            out.setdefault(self.data[pos:z].decode("ascii", "replace"), pos)
            pos = z + 1
        return out

    def _cell_addr(self, row, col):
        root = self.row_offsets[row] + 8
        rel = struct.unpack_from("<I", self.data, root + 16 + 4 * col)[0]
        return root + rel

    def _read_cstr(self, pos):
        z = self.data.find(b"\0", pos)
        return self.data[pos:z].decode("ascii", "replace")

    def cell_value(self, row, col):
        cell = self._cell_addr(row, col)
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ == 0: return None
        if typ == 1: return struct.unpack_from("<i", self.data, cell + 8)[0]
        if typ == 2: return struct.unpack_from("<f", self.data, cell + 8)[0]
        if typ == 4:
            rel = struct.unpack_from("<I", self.data, cell + 8)[0]
            return self._read_cstr(cell + rel)
        raise ValueError(f"type {typ}")

    def row_values(self, row):
        root = self.row_offsets[row] + 8
        count = struct.unpack_from("<I", self.data, root + 4)[0]
        return [self.cell_value(row, c) for c in range(count)]

    def set_string(self, row, column, value):
        if value not in self.strings:
            raise ValueError(f"{value!r} not in pool")
        cell = self._cell_addr(row, self.col_index[column])
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ != 4:
            raise ValueError(f"{column} row {row} type {typ} not string")
        if self.cell_value(row, self.col_index[column]) == value:
            return False
        rel = self.strings[value] - cell
        if rel <= 0:
            raise ValueError(f"cannot point row {row} forward to {value!r}")
        struct.pack_into("<I", self.data, cell + 8, rel)
        return True

    def write(self):
        self.path.write_bytes(self.data)


def set_keys(node, targets):
    """Recursively set any matching keys; returns count of changes."""
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
    backup_dir = BACKUP_ROOT / f"v41_all_opponents_grandprix_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPPONENTS, backup_dir / OPPONENTS.name)
    shutil.copy2(CARDB, backup_dir / CARDB.name)

    # 1) Opponents -> Formula
    sheet = Sheet(OPPONENTS)
    changed = 0
    for row in range(1, sheet.row_count):
        name = str(sheet.row_values(row)[sheet.col_index["Name"]])
        if name.startswith("Tutorial"):
            continue
        changed += int(sheet.set_string(row, "Car", CAR))
    sheet.write()

    # 2) Monster-buff Formula in CarDB
    data = json.loads(CARDB.read_text(encoding="utf-8"))
    formula = data[CAR]
    edits = set_keys(formula, {"Mass": MONSTER_MASS, "Drag Coeff": MONSTER_DRAG})
    CARDB.write_text(json.dumps(data, indent=1), encoding="utf-8")
    now = time.time()
    os.utime(CARDB, (now, now))

    print(f"Backup: {backup_dir}")
    print(f"Opponents switched to {CAR}: {changed}")
    print(f"CarDB Formula physics fields changed (Mass/Drag): {edits}")


if __name__ == "__main__":
    main()
