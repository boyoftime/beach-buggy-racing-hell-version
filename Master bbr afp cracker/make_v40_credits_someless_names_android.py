import shutil
import struct
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRING_DIR = ROOT / "extracted" / "Assets" / "VuStringAsset"
BACKUP_ROOT = ROOT / "mod_backups"
NREC = 1499

REPLACEMENTS = {
    0x7B855AFB: "LicordDev",
    0x7BA70DB6: "ANYAOGU .C. ZABDIEL",
    0xB5790829: "someless",
}


def utf8_clen(b0):
    if b0 < 0x80:
        return 1
    if b0 < 0xC0:
        return -1
    if b0 < 0xE0:
        return 2
    if b0 < 0xF0:
        return 3
    if b0 < 0xF8:
        return 4
    return -1


def find_chartable_end(data):
    i = 0
    prev = -1
    while i < len(data):
        clen = utf8_clen(data[i])
        if clen < 0 or i + clen > len(data):
            break
        try:
            cp = ord(data[i : i + clen].decode("utf-8"))
        except UnicodeDecodeError:
            break
        if cp <= prev:
            break
        prev = cp
        i += clen
    return i


def sections(data):
    record_start = find_chartable_end(data) + 1
    pool_start = record_start + NREC * 8
    if pool_start >= len(data):
        raise RuntimeError("string pool starts past end of file")
    return record_start, pool_start


def read_string(data, start):
    end = data.find(b"\x00", start)
    if end < 0:
        raise RuntimeError("unterminated string in string pool")
    return data[start:end].decode("utf-8", errors="replace")


def patch_file(path):
    data = bytearray(path.read_bytes())
    record_start, pool_start = sections(data)
    records = []
    changed = []

    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, key_hash = struct.unpack_from("<II", data, record_offset)
        text = read_string(data, pool_start + rel_off)
        if key_hash in REPLACEMENTS:
            new_text = REPLACEMENTS[key_hash]
            if text != new_text:
                changed.append((key_hash, text, new_text))
            text = new_text
        records.append((record_offset, key_hash, text))

    if not changed:
        return []

    new_pool = bytearray()
    for record_offset, _key_hash, text in records:
        new_rel = len(new_pool)
        struct.pack_into("<I", data, record_offset, new_rel)
        new_pool.extend(text.encode("utf-8") + b"\x00")

    rebuilt = data[:pool_start] + new_pool
    path.write_bytes(rebuilt)
    return changed


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v40_credits_someless_names_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for path in sorted(STRING_DIR.glob("*.bin")):
        shutil.copy2(path, backup_dir / path.name)
        changes = patch_file(path)
        total += len(changes)
        print(f"{path.name}: patched {len(changes)}")
        for key_hash, old, new in changes:
            print(f"  0x{key_hash:08x}: {old!r} -> {new!r}")

    print(f"Backup: {backup_dir}")
    print(f"Total credits text changes: {total}")


if __name__ == "__main__":
    main()
