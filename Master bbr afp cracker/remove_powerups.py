"""Remove all road powerup pickups from BBR1 race levels.

Strips every entity of type #Gameplay/Gameplay_Powerup and
#Gameplay/Gameplay_Powerups from the extracted VuProjectAsset level JSONs.
Other game-mode pickups (Derby toughness, Gallery missiles, Blitz boosts)
are left untouched.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "extracted", "Assets", "VuProjectAsset")

TARGET_TYPES = {"#Gameplay/Gameplay_Powerup", "#Gameplay/Gameplay_Powerups"}


def strip(node):
    """Recursively remove target entities. Returns count removed."""
    removed = 0
    if isinstance(node, list):
        keep = []
        for item in node:
            if isinstance(item, dict) and item.get("type") in TARGET_TYPES:
                removed += 1
                continue
            removed += strip(item)
            keep.append(item)
        node[:] = keep
    elif isinstance(node, dict):
        for v in node.values():
            removed += strip(v)
    return removed


total = 0
for path in sorted(glob.glob(os.path.join(PROJ, "*.bin.json"))):
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    n = strip(doc)
    if n:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        print(f"{os.path.basename(path):32s} removed {n} powerup entities")
        total += n

print(f"\nDone. Removed {total} powerup entities across race levels.")
