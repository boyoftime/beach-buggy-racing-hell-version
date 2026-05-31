import os
import struct

ROOT = os.path.dirname(os.path.abspath(__file__))
STRING_DIR = os.path.join(ROOT, "extracted", "Assets", "VuStringAsset")
NREC = 1499

TITLE_HASH = 0x53712F5B
BODY_HASH = 0x81E541AD

TITLE_OLD = b"Follow Someless YouTube"
BODY_OLD = b"Modded by Someless! YouTube: search @Someless to find more mods."

TITLE_NEW = "Visit someless website"
BODY_NEW = "https://vectorunit.someless.top/ for Someless BBR mods and tips."


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


def read_pool_string(data, pool_start, rel_off):
    start = pool_start + rel_off
    if start < pool_start or start >= len(data):
        return None
    end = data.find(b"\x00", start)
    if end < 0:
        return None
    try:
        return data[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return None


def patch_file(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())

    record_start = find_chartable_end(data) + 1
    pool_start = record_start + NREC * 8
    if pool_start >= len(data):
        return []

    title_abs = data.find(TITLE_OLD)
    body_abs = data.find(BODY_OLD)
    if title_abs < 0:
        title_abs = data.find(TITLE_NEW.encode("utf-8"))
    if body_abs < 0:
        body_abs = data.find(BODY_NEW.encode("utf-8"))
    if title_abs < pool_start or body_abs < pool_start:
        return []

    title_end = data.find(b"\x00", title_abs)
    body_end = data.find(b"\x00", body_abs)
    if title_end < 0 or body_end < 0:
        return []

    slots = {
        TITLE_HASH: (title_abs, title_end, TITLE_NEW),
        BODY_HASH: (body_abs, body_end, BODY_NEW),
    }

    patched = []
    for start, end, replacement in slots.values():
        old_len = end - start
        encoded = replacement.encode("utf-8")
        if len(encoded) > old_len:
            raise RuntimeError(f"{replacement!r} is {len(encoded)} bytes, slot is {old_len}")
        data[start:end] = encoded + b" " * (old_len - len(encoded))

    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, key_hash = struct.unpack_from("<II", data, record_offset)
        if key_hash not in slots:
            continue
        start, _end, replacement = slots[key_hash]
        struct.pack_into("<I", data, record_offset, start - pool_start)
        patched.append((read_pool_string(data, pool_start, rel_off), replacement, key_hash))

    if patched:
        with open(path, "wb") as f:
            f.write(data)
    return patched


def main():
    total = 0
    for name in sorted(os.listdir(STRING_DIR)):
        if not name.lower().endswith(".bin"):
            continue
        path = os.path.join(STRING_DIR, name)
        patched = patch_file(path)
        if patched:
            total += len(patched)
            print(f"{name}: patched {len(patched)} string record(s)")
            for old, new, key_hash in patched:
                print(f"  0x{key_hash:08x}: {old!r} -> {new!r}")
    print(f"Total patched records: {total}")


if __name__ == "__main__":
    main()
