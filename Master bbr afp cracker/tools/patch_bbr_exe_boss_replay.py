from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path


GAME_EXE = Path(r"C:\beach buggy remix\PurpleWindowsStore.exe")

# In VuEventListEntity click handling:
#   cmp byte ptr [rsi+0x39], 0
#   je  normal_boss_chosen
# If the selected event is a boss and IsBeaten is true, the original code falls
# through to OnBossBeaten. We replace that conditional jump with an unconditional
# jump to the same normal chosen path.
ORIGINAL = bytes.fromhex("443876390f8478000000")
PATCHED = bytes.fromhex("44387639e97900000090")


def patch_file(path: Path, restore: bool) -> None:
    data = bytearray(path.read_bytes())
    src, dst = (PATCHED, ORIGINAL) if restore else (ORIGINAL, PATCHED)
    action = "restore" if restore else "patch"

    src_hits = [i for i in range(len(data)) if data.startswith(src, i)]
    dst_hits = [i for i in range(len(data)) if data.startswith(dst, i)]

    if len(src_hits) == 1:
        offset = src_hits[0]
        if not restore:
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = path.with_name(f"{path.name}.before_boss_replay_exe_{stamp}.bak")
            backup.write_bytes(data)
            print(f"backup: {backup}")
        data[offset : offset + len(src)] = dst
        path.write_bytes(data)
        print(f"{action}ed {path} at file offset 0x{offset:x}")
        return

    if len(dst_hits) == 1:
        print(f"already {'restored' if restore else 'patched'} at file offset 0x{dst_hits[0]:x}")
        return

    raise SystemExit(
        f"Could not find unique boss replay branch. "
        f"source hits={len(src_hits)}, target hits={len(dst_hits)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=GAME_EXE)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    patch_file(args.exe, args.restore)


if __name__ == "__main__":
    main()
