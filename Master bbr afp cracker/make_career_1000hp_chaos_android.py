"""Max career opponent car tier/stats and make bosses nastier.

BBR1's VuSpreadsheetAsset/Opponents.bin is a compact little-endian spreadsheet.
Rows are arrays; string cells point relatively into the shared string pool.
This patch keeps the file layout intact and only changes existing int/string
cell values.
"""
from __future__ import annotations

import shutil
import struct
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OPPONENTS = ROOT / "extracted" / "Assets" / "VuSpreadsheetAsset" / "Opponents.bin"
BACKUP_ROOT = ROOT / "mod_backups"

MAX_STAGE = 3
MAX_STAT = 5
CHAOS_SKILL = 10
BOSS_CAR = "Dune"


class Sheet:
    def __init__(self, path: Path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        self.row_count = struct.unpack_from("<I", self.data, 0x0C)[0]
        self.row_offsets = [
            struct.unpack_from("<I", self.data, 0x18 + 4 * i)[0]
            for i in range(self.row_count)
        ]
        self.string_pool = struct.unpack_from("<I", self.data, 0x04)[0] + 8
        self.strings = self._scan_strings()
        self.columns = self.row_values(0)
        self.col_index = {name: i for i, name in enumerate(self.columns)}

    def _scan_strings(self) -> dict[str, int]:
        out: dict[str, int] = {}
        pos = self.string_pool
        end = len(self.data)
        while pos < end:
            z = self.data.find(b"\0", pos)
            if z < 0:
                break
            text = self.data[pos:z].decode("ascii", "replace")
            out.setdefault(text, pos)
            pos = z + 1
        return out

    def _cell_addr(self, row: int, col: int) -> int:
        root = self.row_offsets[row] + 8
        rel = struct.unpack_from("<I", self.data, root + 16 + 4 * col)[0]
        return root + rel

    def _read_cstr(self, pos: int) -> str:
        z = self.data.find(b"\0", pos)
        return self.data[pos:z].decode("ascii", "replace")

    def cell_value(self, row: int, col: int):
        cell = self._cell_addr(row, col)
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ == 0:
            return None
        if typ == 1:
            return struct.unpack_from("<i", self.data, cell + 8)[0]
        if typ == 2:
            return struct.unpack_from("<f", self.data, cell + 8)[0]
        if typ == 4:
            rel = struct.unpack_from("<I", self.data, cell + 8)[0]
            return self._read_cstr(cell + rel)
        raise ValueError(f"Unsupported cell type {typ} at row {row}, col {col}")

    def row_values(self, row: int) -> list:
        root = self.row_offsets[row] + 8
        count = struct.unpack_from("<I", self.data, root + 4)[0]
        return [self.cell_value(row, col) for col in range(count)]

    def set_int(self, row: int, column: str, value: int) -> bool:
        cell = self._cell_addr(row, self.col_index[column])
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ != 1:
            raise ValueError(f"{column} in row {row} is type {typ}, not int")
        old = struct.unpack_from("<i", self.data, cell + 8)[0]
        if old == value:
            return False
        struct.pack_into("<i", self.data, cell + 8, value)
        return True

    def set_string(self, row: int, column: str, value: str) -> bool:
        if value not in self.strings:
            raise ValueError(f"String {value!r} is not already in the pool")
        cell = self._cell_addr(row, self.col_index[column])
        typ = struct.unpack_from("<I", self.data, cell)[0]
        if typ != 4:
            raise ValueError(f"{column} in row {row} is type {typ}, not string")
        old = self.cell_value(row, self.col_index[column])
        if old == value:
            return False
        rel = self.strings[value] - cell
        if rel <= 0:
            raise ValueError(f"Cannot point {column} in row {row} backward to {value!r}")
        struct.pack_into("<I", self.data, cell + 8, rel)
        return True

    def write(self) -> None:
        self.path.write_bytes(self.data)


def main() -> None:
    if not OPPONENTS.exists():
        raise SystemExit(f"Missing {OPPONENTS}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"career_1000hp_chaos_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPPONENTS, backup_dir / OPPONENTS.name)

    sheet = Sheet(OPPONENTS)
    changed_rows = 0
    changed_cells = 0
    boss_rows = 0

    for row in range(1, sheet.row_count):
        values = sheet.row_values(row)
        name = values[sheet.col_index["Name"]]
        if str(name).startswith("Tutorial"):
            continue

        before = changed_cells
        for column, value in (
            ("Stage", MAX_STAGE),
            ("Accel", MAX_STAT),
            ("Speed", MAX_STAT),
            ("Handling", MAX_STAT),
            ("Tough", MAX_STAT),
            ("Skill", CHAOS_SKILL),
        ):
            changed_cells += int(sheet.set_int(row, column, value))

        if str(name).startswith("Boss") or str(name).startswith("DuelSkeleton"):
            changed_cells += int(sheet.set_string(row, "Car", BOSS_CAR))
            boss_rows += 1

        if changed_cells != before:
            changed_rows += 1

    sheet.write()

    print(f"Backup: {backup_dir}")
    print(f"Rows changed: {changed_rows}")
    print(f"Cells changed: {changed_cells}")
    print(f"Boss/duel rows forced to {BOSS_CAR}: {boss_rows}")
    print(f"Non-tutorial opponents now target stage={MAX_STAGE}, stats={MAX_STAT}, skill={CHAOS_SKILL}")


if __name__ == "__main__":
    main()
