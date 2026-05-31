from pathlib import Path

ROOT = Path(__file__).resolve().parent
EN_BIN = ROOT / "extracted" / "Assets" / "VuStringAsset" / "en.bin"

OLD_TEXT = "Follow us on X, and receive a 200\ue000 gift! Read the latest Beach Buggy news, and interact with the game makers!"
NEW_TEXT = "Follow Someless on TikTok for more mods."


def main():
    data = bytearray(EN_BIN.read_bytes())
    old = OLD_TEXT.encode("utf-8")
    new = NEW_TEXT.encode("utf-8")
    start = data.find(old)
    if start < 0:
        if data.find(new) >= 0:
            print("TikTok modal text already patched")
            return
        raise RuntimeError("Could not find X/Twitter modal text slot")
    if len(new) > len(old):
        raise RuntimeError("Replacement is too long for the existing string slot")
    data[start : start + len(old)] = new + b" " * (len(old) - len(new))
    EN_BIN.write_bytes(data)
    print(f"{OLD_TEXT!r} -> {NEW_TEXT!r}")


if __name__ == "__main__":
    main()
