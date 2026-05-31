from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


APK = Path(r"C:\Users\someless\Desktop\sample\beach-buggy-mod_2026.05.18_an1.com.apk")
ARM64_LIB = "lib/arm64-v8a/libmain.so"

# Android arm64-v8a libmain.so equivalent of the Windows boss replay patch.
# Original:
#   ldrb w8, [x20,#0x31]
#   cmp  w8, #1
#   b.ne normal_boss_chosen
#   ... OnBossBeaten ...
#
# Patched:
#   ldrb w8, [x20,#0x31]
#   cmp  w8, #1
#   b    normal_boss_chosen
#   nop alignment byte budget is not needed because both are 4-byte ARM64 insns.
ARM64_ORIGINAL = bytes.fromhex("88c640391f050071e1010054")
ARM64_PATCHED = bytes.fromhex("88c640391f0500710f000014")


def patch_arm64(data: bytes) -> bytes:
    hits = [i for i in range(len(data)) if data.startswith(ARM64_ORIGINAL, i)]
    patched_hits = [i for i in range(len(data)) if data.startswith(ARM64_PATCHED, i)]
    if len(hits) == 1:
        offset = hits[0]
        out = bytearray(data)
        out[offset : offset + len(ARM64_ORIGINAL)] = ARM64_PATCHED
        print(f"patched {ARM64_LIB} at lib offset 0x{offset:x}")
        return bytes(out)
    if len(patched_hits) == 1:
        print(f"{ARM64_LIB} already patched at lib offset 0x{patched_hits[0]:x}")
        return data
    raise SystemExit(
        f"Could not find unique arm64 boss replay branch: "
        f"original={len(hits)}, patched={len(patched_hits)}"
    )


def copy_info(src: zipfile.ZipInfo) -> zipfile.ZipInfo:
    dst = zipfile.ZipInfo(src.filename, src.date_time)
    dst.comment = src.comment
    dst.extra = src.extra
    dst.internal_attr = src.internal_attr
    dst.external_attr = src.external_attr
    dst.create_system = src.create_system
    dst.compress_type = src.compress_type
    return dst


def patch_apk(apk: Path, out: Path) -> None:
    backup = apk.with_suffix(apk.suffix + ".before_android_boss_replay.bak")
    if not backup.exists():
        shutil.copy2(apk, backup)
        print(f"backup: {backup}")

    with zipfile.ZipFile(apk, "r") as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and (
                name.endswith(".RSA")
                or name.endswith(".DSA")
                or name.endswith(".EC")
                or name.endswith(".SF")
                or name.endswith("MANIFEST.MF")
            ):
                continue

            data = zin.read(info)
            if name == ARM64_LIB:
                data = patch_arm64(data)

            zout.writestr(copy_info(info), data)

    print(f"wrote unsigned patched APK: {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=APK)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    out = args.out or args.apk.with_name(args.apk.stem + "_boss_replay_unsigned.apk")
    patch_apk(args.apk, out)


if __name__ == "__main__":
    main()
