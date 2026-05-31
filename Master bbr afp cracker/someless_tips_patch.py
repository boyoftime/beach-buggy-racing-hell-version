"""Replace the 24 rotating Pro Tip slots in every language string-bin with
@Someless YouTube promo messages. Works in-place on each .bin file.

Format (BBR1 v2026.05.18 Android):
  bytes 0..C-1      char table (variable per locale): sequence of UTF-8
                    codepoints, strictly increasing. C = chartable_end.
  byte  C           0x00 padding (between char table and records)
  bytes C+1..P-1    records: 1499 entries of 8 bytes each =
                      u32 LE offset (relative to pool start)
                      u32 LE FNV1a32 hash of the key name
  bytes P..EOF      string pool: NUL-terminated UTF-8 strings.

We resolve each record by hash, append a new promo string to the end of
the pool, and rewrite the record's offset field to point at it.
"""
import os, struct

EXTRACTED = r"C:/Users/someless/Desktop/BBR1/Master bbr afp cracker/extracted/Assets/VuStringAsset"
NREC = 1499

PROMO = [
    "Modded by Someless! Subscribe to YouTube @Someless for more wild mods like this one.",
    "Loving this mod? Hit subscribe on YouTube @Someless and never miss the next one!",
    "Want exclusive mods? YouTube @Someless drops fresh ones every week - go subscribe!",
    "Someless made this! Subscribe @Someless on YouTube to support more free mods.",
    "Enjoying the cars? Smash that subscribe button on YouTube - search @Someless!",
    "Tutorials, mod APKs and gameplay tricks - all on YouTube @Someless. Go subscribe!",
    "Big love from Someless! Subscribe @Someless on YouTube so I can keep modding.",
    "More mods coming soon! Subscribe to @Someless on YouTube to be the first to play.",
    "This game was modded with love by Someless. Show love back - subscribe @Someless!",
    "Tap subscribe on YouTube @Someless for crazy mods, free APKs and fun gameplay.",
    "The Someless Mod Squad needs YOU! Subscribe @Someless on YouTube - let's grow!",
    "Want more mods like this? Hit YouTube @Someless and subscribe - it's totally free.",
    "Modder spotlight: Someless. New mods drop weekly - subscribe @Someless on YouTube!",
    "Pro tip from Someless: subscribe to @Someless on YouTube for instant mod access.",
    "Like the game? You'll love my channel - YouTube @Someless. Hit subscribe!",
    "Someless is on YouTube! Search @Someless and subscribe for more BBR madness.",
    "Free mods, weekly uploads, friendly modder - YouTube @Someless. Subscribe now!",
    "Got a mod request? Comment on YouTube @Someless - and don't forget to subscribe!",
    "Behind this mod is Someless. Behind Someless: YOUR subscription. YouTube @Someless!",
    "Someless is modding non-stop. Help me grow - subscribe @Someless on YouTube today!",
    "Hey racer - subscribe to YouTube @Someless to unlock the next mod in your feed.",
    "Mods like this take hours to build. Show support - subscribe @Someless on YouTube.",
    "Someless Premium Mods drop only on YouTube @Someless. Go subscribe right now!",
    "Tell your friends about Someless! Share the channel @Someless on YouTube - let's grow.",
]
TIP_KEYS = [
    "Tip_PowerupsC","Tip_PowerupsA","Tip_DailyChallengeA","Tip_DailyChallengeB",
    "Tip_Powerslide","Tip_BoostStart","Tip_LevelUpB","Tip_LevelUpA",
    "Tip_Cloud","Tip_UpgradeA","Tip_TokensB","Tip_UpgradeAccel",
    "Tip_DriverA","Tip_DriverC","Tip_DriverB","Tip_DailyReward",
    "Tip_Gamepad","Tip_UpgradeTopSpeed","Tip_Shortcuts","Tip_UpgradeTough",
    "Tip_UpgradeHandling","Tip_EconomyA","Tip_PremiumA","Tip_FriendsA",
]
assert len(PROMO) == len(TIP_KEYS) == 24

def fnv1a32(s):
    h = 0x811c9dc5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h
KEY_HASHES = {fnv1a32(k): (i, k) for i, k in enumerate(TIP_KEYS)}

def utf8_clen(b0):
    if b0 < 0x80: return 1
    if b0 < 0xC0: return -1
    if b0 < 0xE0: return 2
    if b0 < 0xF0: return 3
    if b0 < 0xF8: return 4
    return -1

def find_chartable_end(data):
    i = 0; prev = -1
    while i < len(data):
        b = data[i]; cl = utf8_clen(b)
        if cl < 0 or i + cl > len(data): break
        try: cp = ord(data[i:i+cl].decode("utf-8"))
        except Exception: break
        if cp <= prev: break
        prev = cp; i += cl
    return i

def patch_file(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    rs = find_chartable_end(data) + 1
    ps = rs + NREC * 8
    if ps >= len(data):
        raise RuntimeError(f"{path}: pool_start {ps} past EOF {len(data)}")

    patched = []
    new_pool = bytearray()
    for i in range(NREC):
        ro = rs + i * 8
        off, h = struct.unpack_from("<II", data, ro)
        if h in KEY_HASHES:
            idx, key = KEY_HASHES[h]
            new_rel = (len(data) + len(new_pool)) - ps
            new_pool.extend(PROMO[idx].encode("utf-8") + b"\x00")
            struct.pack_into("<I", data, ro, new_rel)
            patched.append((idx, key))
    data.extend(new_pool)
    with open(path, "wb") as f:
        f.write(data)
    return rs, ps, patched

def main():
    files = ["en.bin","de.bin","es.bin","id.bin","ja.bin","ko.bin","ru.bin","zh-hant.bin"]
    for fn in files:
        p = os.path.join(EXTRACTED, fn)
        if not os.path.exists(p):
            print(f"  SKIP {fn} (missing)"); continue
        rs, ps, patched = patch_file(p)
        keys = [k for _, k in patched]
        print(f"{fn:14s}  rs={rs}  pool@{ps}  patched={len(patched)}/24")
        if len(patched) != 24:
            missing = set(TIP_KEYS) - set(keys)
            print(f"   missing: {sorted(missing)}")

if __name__ == "__main__":
    main()
