import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRING_DIR = ROOT / "extracted" / "Assets" / "VuStringAsset"
NREC = 1499

REPLACEMENTS = {
    0x53712F5B: "Visit someless website",
    0x81E541AD: "https://vectorunit.someless.top/ for Someless BBR mods and tips.",
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


def read_string(data, start):
    end = data.find(b"\x00", start)
    if end < 0:
        return None, None
    try:
        return data[start:end].decode("utf-8"), end
    except UnicodeDecodeError:
        return None, end


def patch_file(path):
    data = bytearray(path.read_bytes())
    record_start = find_chartable_end(data) + 1
    pool_start = record_start + NREC * 8
    patched = []

    for i in range(NREC):
        record_offset = record_start + i * 8
        rel_off, key_hash = struct.unpack_from("<II", data, record_offset)
        if key_hash not in REPLACEMENTS:
            continue
        start = pool_start + rel_off
        old_text, end = read_string(data, start)
        if old_text is None:
            continue
        old_len = end - start
        new = REPLACEMENTS[key_hash].encode("utf-8")
        if len(new) > old_len:
            raise RuntimeError(f"{path.name}: replacement for 0x{key_hash:08x} is too long")
        data[start:end] = new + b" " * (old_len - len(new))
        patched.append((key_hash, old_text.strip(), REPLACEMENTS[key_hash]))

    if patched:
        path.write_bytes(data)
    return patched


def main():
    total = 0
    for path in sorted(STRING_DIR.glob("*.bin")):
        patched = patch_file(path)
        total += len(patched)
        print(f"{path.name}: patched {len(patched)}")
        for key_hash, old_text, new_text in patched:
            old_safe = old_text.encode("unicode_escape").decode("ascii")
            new_safe = new_text.encode("unicode_escape").decode("ascii")
            print(f"  0x{key_hash:08x}: {old_safe!r} -> {new_safe!r}")
    print(f"Total patched records: {total}")


if __name__ == "__main__":
    main()
