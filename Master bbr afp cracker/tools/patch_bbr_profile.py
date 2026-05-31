from __future__ import annotations

import argparse
import shutil
import struct
from datetime import datetime
from pathlib import Path


BOSSES = [
    b"Alien",
    b"Tribal",
    b"Bunny",
    b"Skeleton",
    b"BeachBro",
    b"Rad",
    b"Hula",
    b"Roller",
    b"Lucha",
    b"Disco",
]

BOSS_ALIASES = {
    "alien": "Alien",
    "tribal": "Tribal",
    "benny": "Bunny",
    "bunny": "Bunny",
    "mcskelly": "Skeleton",
    "skeleton": "Skeleton",
    "beachbro": "BeachBro",
    "beach_bro": "BeachBro",
    "rad": "Rad",
    "leilani": "Hula",
    "hula": "Hula",
    "roller": "Roller",
    "lucha": "Lucha",
    "disco": "Disco",
}


def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value


def update_header(data: bytearray) -> None:
    if data[:4] != b"RPUV":
        raise ValueError("not an RPUV profile")
    payload_len = len(data) - 16
    data[8:12] = struct.pack("<I", payload_len)
    data[12:16] = struct.pack("<I", fnv1a32(bytes(data[16:])))


def verify_header(data: bytes) -> tuple[bool, int, int, int]:
    if data[:4] != b"RPUV":
        return False, 0, 0, 0
    payload_len = struct.unpack("<I", data[8:12])[0]
    stored = struct.unpack("<I", data[12:16])[0]
    computed = fnv1a32(data[16:])
    return payload_len == len(data) - 16 and stored == computed, payload_len, stored, computed


def set_boss_beaten_flags(path: Path, beaten: bool, target_unbeaten: str | None = None) -> list[str]:
    data = bytearray(path.read_bytes())
    ok, payload_len, stored, computed = verify_header(bytes(data))
    if not ok:
        raise ValueError(
            f"{path} has invalid header before patch "
            f"(payload_len={payload_len}, stored=0x{stored:08x}, computed=0x{computed:08x})"
        )

    marker = b"IsBeaten\x00\x00\x00\x03"
    changed: list[str] = []
    for boss in BOSSES:
        start = data.find(boss)
        if start < 0:
            raise ValueError(f"{path}: missing boss block {boss.decode()}")
        marker_at = data.find(marker, start, start + 140)
        if marker_at < 0:
            raise ValueError(f"{path}: missing IsBeaten marker for {boss.decode()}")
        value_at = marker_at + len(marker)
        if target_unbeaten is not None:
            new_value = 0 if boss.decode() == target_unbeaten else 1
        else:
            new_value = 1 if beaten else 0
        old_value = data[value_at]
        data[value_at] = new_value
        if old_value != new_value:
            changed.append(f"{boss.decode()}:{old_value}->{new_value}")

    update_header(data)
    path.write_bytes(data)
    ok, _, stored, computed = verify_header(bytes(data))
    if not ok:
        raise ValueError(f"{path}: header verify failed after patch")
    print(f"{path.name}: {', '.join(changed) if changed else 'no flag changes'}")
    print(f"{path.name}: FNV-1a checksum 0x{stored:08x} verified")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local_state", type=Path)
    parser.add_argument("--bosses-unbeaten", action="store_true")
    parser.add_argument("--bosses-beaten", action="store_true")
    parser.add_argument(
        "--replay-boss",
        help="Set only this boss as unbeaten and leave all other boss gates beaten. Aliases: benny, leilani, mcskelly.",
    )
    args = parser.parse_args()

    selected_modes = sum(bool(value) for value in (args.bosses_unbeaten, args.bosses_beaten, args.replay_boss))
    if selected_modes != 1:
        raise SystemExit("choose exactly one of --bosses-unbeaten, --bosses-beaten, or --replay-boss")

    replay_boss = None
    if args.replay_boss:
        replay_boss = BOSS_ALIASES.get(args.replay_boss.lower(), args.replay_boss)
        if replay_boss.encode() not in BOSSES:
            raise SystemExit(f"unknown boss {args.replay_boss!r}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for name in ("profile", "profileback"):
        path = args.local_state / name
        backup = args.local_state / f"{name}.before_checksum_patch_{timestamp}.bak"
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
        set_boss_beaten_flags(path, beaten=args.bosses_beaten, target_unbeaten=replay_boss)


if __name__ == "__main__":
    main()
