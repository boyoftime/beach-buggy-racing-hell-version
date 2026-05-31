"""Animal Apocalypse - multiply the breakable road animals in BBR1 levels.

For every #NPC/NPCBreakable_* entity in the level templates, spawn extra
clones scattered in a small cluster around the original so the roads swarm
with smashable chickens, penguins, and seagulls.
"""
import copy
import glob
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, "extracted", "Assets", "VuTemplateAsset", "Levels")

EXTRA_CLONES = 80     # clones added per original -> 81x total
SPREAD = 45.0         # cluster radius in world units (wider road coverage)
Z_JITTER = 3.0        # small vertical jitter so they don't all sit at the same height
random.seed(1337)     # deterministic output


def is_breakable_npc(item):
    return (isinstance(item, dict)
            and isinstance(item.get("type"), str)
            and item["type"].startswith("#NPC/NPCBreakable_"))


def clone_npc(entity, idx):
    """Deep-copy an NPC entity, nudge its position, give it a unique name."""
    c = copy.deepcopy(entity)
    c["name"] = f"{entity.get('name', 'NPCBreakable')}_x{idx}"
    try:
        props = c["data"]["Components"]["VuTransformComponent"]["Properties"]
    except (KeyError, TypeError):
        return c
    pos = props.get("Position")
    if isinstance(pos, dict):
        ang = random.uniform(0, 2 * math.pi)
        dist = random.uniform(SPREAD * 0.25, SPREAD)
        pos["X"] = pos.get("X", 0.0) + math.cos(ang) * dist
        pos["Y"] = pos.get("Y", 0.0) + math.sin(ang) * dist
        pos["Z"] = pos.get("Z", 0.0) + random.uniform(-Z_JITTER * 0.3, Z_JITTER)
    rot = props.get("Rotation")
    if isinstance(rot, dict):
        rot["Z"] = random.uniform(-180.0, 180.0)
    return c


def multiply(node):
    """Recursively expand breakable-NPC arrays. Returns count of clones added."""
    added = 0
    if isinstance(node, list):
        new_list = []
        for item in node:
            if isinstance(item, (list, dict)):
                added += multiply(item)
            new_list.append(item)
            if is_breakable_npc(item):
                for i in range(1, EXTRA_CLONES + 1):
                    new_list.append(clone_npc(item, i))
                    added += 1
        node[:] = new_list
    elif isinstance(node, dict):
        for v in node.values():
            added += multiply(v)
    return added


total = 0
for path in sorted(glob.glob(os.path.join(LEVELS, "*.bin.json"))):
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    n = multiply(doc)
    if n:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        print(f"{os.path.basename(path):24s} +{n} animals")
        total += n

print(f"\nDone. Spawned {total} extra smashable animals across the roads.")
