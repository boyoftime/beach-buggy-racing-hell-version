import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRING_DIR = ROOT / "extracted" / "Assets" / "VuStringAsset"
BACKUP_STRING_DIR = ROOT / "workspace_backups" / "extracted_20260528_164710" / "Assets" / "VuStringAsset"
NREC = 1499
WRONG_HASH = 0xE01CDF4B
MORE_GAMES_HASH = 0xE2B2705A
NEW_TEXT = "More mods Games"


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


def read_string(data, start):
    end = data.find(b"\x00", start)
    if end < 0:
        return None
    return data[start:end].decode("utf-8", errors="replace")


def get_record_text(data, key_hash):
    record_start = find_chartable_end(data) + 1
    pool_start = record_start + NREC * 8
    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, current_hash = struct.unpack_from("<II", data, record_offset)
        if current_hash == key_hash:
            return read_string(data, pool_start + rel_off)
    return None


def point_record_to_appended_text(data, key_hash, text):
    record_start = find_chartable_end(data) + 1
    pool_start = record_start + NREC * 8
    new_rel = len(data) - pool_start
    old_text = None

    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, current_hash = struct.unpack_from("<II", data, record_offset)
        if current_hash != key_hash:
            continue
        old_text = read_string(data, pool_start + rel_off)
        struct.pack_into("<I", data, record_offset, new_rel)
        data.extend(text.encode("utf-8") + b"\x00")
        return old_text
    return None


def patch_file(path):
    data = bytearray(path.read_bytes())
    backup_path = BACKUP_STRING_DIR / path.name
    repaired = None
    if backup_path.exists():
        repair_text = get_record_text(backup_path.read_bytes(), WRONG_HASH)
        if repair_text:
            repaired = point_record_to_appended_text(data, WRONG_HASH, repair_text)

    old_label = point_record_to_appended_text(data, MORE_GAMES_HASH, NEW_TEXT)
    if repaired is not None or old_label is not None:
        path.write_bytes(data)
    return repaired, old_label


def main():
    total = 0
    print(f"Repair hash: 0x{WRONG_HASH:08x}")
    print(f"More Games hash: 0x{MORE_GAMES_HASH:08x}")
    for path in sorted(STRING_DIR.glob("*.bin")):
        repaired, old_label = patch_file(path)
        total += int(old_label is not None)
        repaired_safe = "" if repaired is None else repaired.encode("unicode_escape").decode("ascii")
        old_label_safe = "" if old_label is None else old_label.encode("unicode_escape").decode("ascii")
        print(f"{path.name}: repaired {repaired_safe!r}; label {old_label_safe!r} -> {NEW_TEXT!r}")
    print(f"Total label records patched: {total}")


if __name__ == "__main__":
    main()
