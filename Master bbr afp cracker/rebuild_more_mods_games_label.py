import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRING_DIR = ROOT / "extracted" / "Assets" / "VuStringAsset"
BACKUP_STRING_DIR = ROOT / "workspace_backups" / "extracted_20260528_164710" / "Assets" / "VuStringAsset"
NREC = 1499

WRONG_HASH = 0xE01CDF4B
MORE_GAMES_HASH = 0xE2B2705A
NEW_LABEL = "More mods Games"


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
    return record_start, pool_start


def read_string(data, start):
    end = data.find(b"\x00", start)
    if end < 0:
        raise RuntimeError("Unterminated string in string pool")
    return data[start:end].decode("utf-8", errors="replace")


def get_text_by_hash(data, key_hash):
    record_start, pool_start = sections(data)
    for i in range(NREC):
        rel_off, current_hash = struct.unpack_from("<II", data, record_start + i * 8)
        if current_hash == key_hash:
            return read_string(data, pool_start + rel_off)
    return None


def rebuild_file(path):
    data = bytearray(path.read_bytes())
    backup_path = BACKUP_STRING_DIR / path.name
    backup = backup_path.read_bytes() if backup_path.exists() else None
    record_start, pool_start = sections(data)

    records = []
    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, key_hash = struct.unpack_from("<II", data, record_offset)
        text = read_string(data, pool_start + rel_off)
        if key_hash == WRONG_HASH and backup is not None:
            text = get_text_by_hash(backup, WRONG_HASH) or text
        if key_hash == MORE_GAMES_HASH:
            text = NEW_LABEL
        records.append((record_offset, key_hash, text))

    new_pool = bytearray()
    for record_offset, _key_hash, text in records:
        new_rel = len(new_pool)
        struct.pack_into("<I", data, record_offset, new_rel)
        new_pool.extend(text.encode("utf-8") + b"\x00")

    rebuilt = data[:pool_start] + new_pool
    path.write_bytes(rebuilt)

    return get_text_by_hash(rebuilt, WRONG_HASH), get_text_by_hash(rebuilt, MORE_GAMES_HASH), len(data), len(rebuilt)


def main():
    for path in sorted(STRING_DIR.glob("*.bin")):
        repaired, label, old_len, new_len = rebuild_file(path)
        print(f"{path.name}: {old_len} -> {new_len}; repaired={repaired!a}; label={label!a}")


if __name__ == "__main__":
    main()
