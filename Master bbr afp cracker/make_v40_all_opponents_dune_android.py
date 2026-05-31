"""v40 - Give EVERY career opponent the monster Dune car (like the bosses).

Root cause of "career AI slow, only bosses fast": the engine ignores
AiPersonality.Performance for normal cars - speed comes from the CAR.  Bosses all
drive the v15 monster "Dune" (Mass 350, Drag 0.12, high RPM); normal opponents drive
stock slow cars (Muscle/Euro/Buggy/Rally/Moon/MonsterTruck/Hearse).

This sets the Car cell of every non-tutorial opponent in VuSpreadsheetAsset/Opponents.bin
to "Dune", so all career AI now drive the same fast monster car the bosses use.
Stage/stat/skill cells are left as already maxed by v19.  Tutorial rows untouched.
"""
from __future__ import annotations

import shutil
import struct
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OPPONENTS = ROOT / "extracted" / "Assets" / "VuSpreadsheetAsset" / "Opponents.bin"
BACKUP_ROOT = ROOT / "mod_backups"
DUNE = "Dune"


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


def main():
    if not OPPONENTS.exists():
        raise SystemExit(f"Missing {OPPONENTS}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v40_all_opponents_dune_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPPONENTS, backup_dir / OPPONENTS.name)

    sheet = Sheet(OPPONENTS)
    changed = 0
    skipped_tut = 0
    for row in range(1, sheet.row_count):
        name = str(sheet.row_values(row)[sheet.col_index["Name"]])
        if name.startswith("Tutorial"):
            skipped_tut += 1
            continue
        changed += int(sheet.set_string(row, "Car", DUNE))

    sheet.write()
    print(f"Backup: {backup_dir}")
    print(f"Opponents switched to {DUNE}: {changed}")
    print(f"Tutorial rows skipped: {skipped_tut}")


if __name__ == "__main__":
    main()
