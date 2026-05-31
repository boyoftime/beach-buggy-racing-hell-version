from pathlib import Path

ROOT = Path(__file__).resolve().parent
EN_BIN = ROOT / "extracted" / "Assets" / "VuStringAsset" / "en.bin"

REPLACEMENTS = {
    "Sign Up \ue010 Gift": "Someless Mods",
    "Like us on Facebook, and receive a 200\ue000 gift! Read the latest Beach Buggy news, and interact with the game makers!": (
        "Visit https://vectorunit.someless.top/ for Someless mods, tricks, guides and updates."
    ),
}


def replace_in_slot(data, old_text, new_text):
    old = old_text.encode("utf-8")
    new = new_text.encode("utf-8")
    start = data.find(old)
    if start < 0:
        if data.find(new) >= 0:
            return False
        raise RuntimeError(f"Could not find string slot: {old_text!r}")
    if len(new) > len(old):
        raise RuntimeError(f"Replacement too long for slot: {new_text!r}")
    data[start : start + len(old)] = new + b" " * (len(old) - len(new))
    return True


def main():
    data = bytearray(EN_BIN.read_bytes())
    patched = 0
    for old_text, new_text in REPLACEMENTS.items():
        if replace_in_slot(data, old_text, new_text):
            patched += 1
            print(f"{old_text!r} -> {new_text!r}")
    EN_BIN.write_bytes(data)
    print(f"Patched {patched} string slot(s)")


if __name__ == "__main__":
    main()
