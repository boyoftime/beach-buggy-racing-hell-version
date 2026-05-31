import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRING_DIR = ROOT / "extracted" / "Assets" / "VuStringAsset"
BACKUP_ROOT = ROOT / "mod_backups"

REPLACEMENTS = [
    (b"Rana and Haedan", b"LicordDev"),
    (b'Elizabeth "Timm" Sewell', b"ANYAOGU .C. ZABDIEL"),
    (b"Third Party Software", b"someless"),
]


def padded(old, new):
    if len(new) > len(old):
        raise ValueError(f"{new!r} is longer than slot {old!r}")
    return new + b" " * (len(old) - len(new))


def patch_file(path):
    data = bytearray(path.read_bytes())
    changes = []
    for old, new in REPLACEMENTS:
        pos = data.find(old)
        if pos < 0:
            pos = data.find(padded(old, new))
        if pos < 0:
            continue
        current_end = data.find(b"\x00", pos)
        current = bytes(data[pos:current_end])
        data[pos : pos + len(old)] = padded(old, new)
        changes.append((current.rstrip(b" "), new))

    if changes:
        path.write_bytes(data)
        path.touch()
    return changes


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"v40_credits_safe_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for path in sorted(STRING_DIR.glob("*.bin")):
        shutil.copy2(path, backup_dir / path.name)
        changes = patch_file(path)
        total += len(changes)
        print(f"{path.name}: patched {len(changes)}")
        for old, new in changes:
            print(f"  {old.decode('utf-8', 'replace')!r} -> {new.decode('utf-8')!r}")

    print(f"Backup: {backup_dir}")
    print(f"Total safe credits text changes: {total}")


if __name__ == "__main__":
    main()
