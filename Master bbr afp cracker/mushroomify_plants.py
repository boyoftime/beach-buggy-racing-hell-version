"""Replace all trees/plants/foliage in every map with mushrooms + mangroves.

Source palette is restricted to flora from Mushroom Grotto (CaveA) and Misty
Marsh (SwampA): Mushroom A/B/C + glowing MushroomD, and Mangrove A/B/C.

- Each plant is an entity with a `type` ref (e.g. "#Plant/PlantBreakable_PalmA")
  plus a transform. We retarget the `type` and adjust the scale.
- Tall trees -> big mushrooms (scaled up) or mangroves (tree size).
- Ground foliage -> small mushrooms (fixed scale; foliage scales are flat/wide).
- Existing mushrooms/mangroves are left untouched.

Templates (with the plant instances) live in VuTemplateAsset/Levels/*.bin.json
and the menu scene Screens/Background.bin.json. The asset dependency lists
live in the per-mode VuProjectAsset/*.bin.json, so the mushroom + mangrove
assets are added there so they load in maps that never had them.
"""
from __future__ import annotations

import json
import glob
import os
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "extracted" / "Assets"
LEVELS = ASSETS / "VuTemplateAsset" / "Levels"
PROJECTS = ASSETS / "VuProjectAsset"
BACKGROUND = PROJECTS / "Screens" / "Background.bin.json"
BACKUP = HERE / "mod_backups" / f"mushroomify_{time.strftime('%Y%m%d_%H%M%S')}"

MUSH_A = "#Prop/PropBreakable_Mushroom_A"
MUSH_B = "#Prop/PropBreakable_Mushroom_B"
MUSH_C = "#Prop/PropBreakable_Mushroom_C"
MUSH_D = "#Prop/Prop_MushroomD_Glow"
MANG_A = "#Plant/Plant_MangroveA"
MANG_B = "#Plant/Plant_MangroveB"
MANG_C = "#Plant/Plant_MangroveC"

# tall plants -> scaled up. ("mush"=big mushroom, "mang"=tree-size mangrove)
TREE_MAP = {
    "#Plant/PlantBreakable_PalmA": (MUSH_A, "mush"),
    "#Plant/PlantBreakable_PalmB": (MUSH_B, "mush"),
    "#Plant/PlantBreakable_AlienCactusA": (MUSH_A, "mush"),
    "#Plant/PlantBreakable_AlienCactusB": (MUSH_D, "mush"),
    "#Plant/Plant_TropicalA": (MUSH_C, "mush"),
    "#Plant/PlantBreakable_Evergreen": (MANG_A, "mang"),
    "#Plant/PlantBreakable_AlienCactusC": (MANG_B, "mang"),
    "#Plant/Plant_TropicalB": (MANG_C, "mang"),
}

# ground foliage -> mushrooms. value = (target, fixed uniform scale).
# grass/flowers -> tiny, tree-clusters -> medium, others -> small.
FOLIAGE_MAP = {
    # tropical / evergreen clusters
    "#Foliage/Foliage_TropicalA": (MUSH_A, 1.2),
    "#Foliage/Foliage_TropicalB": (MUSH_B, 1.2),
    "#Foliage/Foliage_TropicalC": (MUSH_C, 1.2),
    "#Foliage/Foliage_TropicalD": (MUSH_D, 1.2),
    "#Foliage/Foliage_EvergreenA": (MUSH_C, 1.2),
    "#Foliage/Foliage_EvergreenB": (MUSH_A, 1.2),
    # tree-cluster billboards -> medium mushrooms
    "#Foliage/Foliage_TreesA": (MUSH_A, 1.6),
    "#Foliage/Foliage_TreesB": (MUSH_B, 1.6),
    "#Foliage/Foliage_TreesC": (MUSH_C, 1.6),
    "#Foliage/Foliage_TreesD": (MUSH_A, 1.6),
    # grasses -> tiny ground mushrooms
    "#Foliage/Foliage_GrassesA": (MUSH_A, 0.8),
    "#Foliage/Foliage_GrassesB": (MUSH_B, 0.8),
    "#Foliage/Foliage_GrassesC": (MUSH_C, 0.8),
    "#Foliage/Foliage_GrassesD": (MUSH_A, 0.8),
    # flowers -> tiny glowing mushrooms
    "#Foliage/Foliage_FlowerA": (MUSH_D, 0.8),
    # alien plants
    "#Foliage/Foliage_AlienA": (MUSH_A, 1.0),
    "#Foliage/Foliage_AlienB": (MUSH_B, 1.0),
    "#Foliage/Foliage_AlienC": (MUSH_C, 1.0),
    "#Foliage/Foliage_AlienD": (MUSH_D, 1.0),
    # cave plants (Mushroom Grotto)
    "#Foliage/Foliage_CaveA": (MUSH_A, 1.0),
    "#Foliage/Foliage_CaveB": (MUSH_B, 1.0),
    "#Foliage/Foliage_CaveC": (MUSH_C, 1.0),
    "#Foliage/Foliage_CaveD": (MUSH_D, 1.0),
    # coral (Aquarius) -> mushrooms
    "#Foliage/Foliage_CoralA": (MUSH_A, 1.0),
    "#Foliage/Foliage_CoralB": (MUSH_B, 1.0),
    "#Foliage/Foliage_CoralD": (MUSH_D, 1.0),
}

DEPS = {
    "VuTemplateAsset": [
        "Prop/PropBreakable_Mushroom_A", "Prop/PropBreakable_Mushroom_B",
        "Prop/PropBreakable_Mushroom_C", "Prop/Prop_MushroomD_Glow",
        "Plant/Plant_MangroveA", "Plant/Plant_MangroveB",
        "Plant/Plant_MangroveC", "Plant/Plant_MangroveD",
    ],
    "VuStaticModelAsset": [
        "Prop/Mushroom_A", "Prop/Mushroom_A_Glow", "Prop/Mushroom_A_broken",
        "Prop/Mushroom_B", "Prop/Mushroom_B_Glow", "Prop/Mushroom_B_broken",
        "Prop/Mushroom_C", "Prop/Mushroom_C_Glow", "Prop/Mushroom_C_broken",
        "Prop/Mushroom_D_Glow",
        "Plant/Mangrove_A", "Plant/Mangrove_A_highres", "Plant/Mangrove_A_ref",
        "Plant/Mangrove_B", "Plant/Mangrove_B_highres", "Plant/Mangrove_B_ref",
        "Plant/Mangrove_C", "Plant/Mangrove_C_ref", "Plant/Mangrove_D",
    ],
    "VuCollisionMeshAsset": [
        "Plant/Mangrove_A_col", "Plant/Mangrove_B_col",
        "Plant/Mangrove_C_col", "Plant/Mangrove_D_col",
    ],
    "VuMaterialAsset": [
        "Prop/Mushroom", "Prop/Mushroom_Glow",
        "Plant/LeavesA", "Plant/TreeTrunk", "Plant/TreeTrunk_ref",
    ],
    "VuTextureAsset": [
        "Prop/Mushroom", "Prop/Mushroom_m",
        "Plant/LeavesA", "Plant/Bark_dtl", "Plant/TreeTrunk", "Plant/TreeTrunk_N",
    ],
}


def backup(path: Path) -> None:
    rel = path.relative_to(HERE)
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(path, dst)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def set_uniform_scale(comps: dict, value: float) -> None:
    tc = comps.setdefault("VuTransformComponent", {}).setdefault("Properties", {})
    tc["Scale"] = {"X": value, "Y": value, "Z": value}


def cur_scale_max(comps: dict) -> float:
    sc = comps.get("VuTransformComponent", {}).get("Properties", {}).get("Scale")
    if not isinstance(sc, dict):
        return 1.0
    return max(abs(sc.get("X", 1.0)), abs(sc.get("Y", 1.0)), abs(sc.get("Z", 1.0))) or 1.0


def swap_plants(root) -> dict:
    counts = {"tree_mush": 0, "tree_mang": 0, "foliage": 0}

    def walk(o):
        if isinstance(o, dict):
            t = o.get("type")
            if isinstance(t, str):
                comps = o.get("data", {}).get("Components") if isinstance(o.get("data"), dict) else None
                if t in TREE_MAP and isinstance(comps, dict):
                    new_t, kind = TREE_MAP[t]
                    o["type"] = new_t
                    base = cur_scale_max(comps)
                    if kind == "mush":
                        set_uniform_scale(comps, clamp(base * 2.6, 1.5, 6.0))
                        counts["tree_mush"] += 1
                    else:
                        set_uniform_scale(comps, clamp(base, 0.8, 2.0))
                        counts["tree_mang"] += 1
                elif t in FOLIAGE_MAP and isinstance(comps, dict):
                    new_t, fscale = FOLIAGE_MAP[t]
                    o["type"] = new_t
                    set_uniform_scale(comps, fscale)
                    counts["foliage"] += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(root)
    return counts


def add_deps(data) -> int:
    ad = data.get("AssetData")
    if not isinstance(ad, list):
        return 0
    rows = {r[0]: r for r in ad if isinstance(r, list) and r}
    added = 0
    for atype, names in DEPS.items():
        row = rows.get(atype)
        if row is None:
            row = [atype]
            ad.append(row)
            rows[atype] = row
        existing = set(row[1:])
        for n in names:
            if n not in existing:
                row.append(n)
                added += 1
    if added:
        for row in ad:
            if isinstance(row, list) and len(row) > 2:
                row[:] = [row[0]] + sorted(row[1:])
    return added


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.utime(path, None)


def main() -> None:
    print("== Swapping plants in level templates ==")
    for path in sorted(LEVELS.glob("*.bin.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = swap_plants(data)
        if sum(counts.values()):
            backup(path)
            save(path, data)
        print(f"  {path.name:22} trees->mush={counts['tree_mush']:4} "
              f"trees->mang={counts['tree_mang']:4} foliage={counts['foliage']:4}")

    print("\n== Swapping plants in menu Background ==")
    data = json.loads(BACKGROUND.read_text(encoding="utf-8"))
    counts = swap_plants(data)
    add_deps(data)
    backup(BACKGROUND)
    save(BACKGROUND, data)
    print(f"  Background.bin.json    {counts}")

    print("\n== Adding mushroom + mangrove deps to project files ==")
    total = 0
    for path in sorted(PROJECTS.glob("*.bin.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        n = add_deps(data)
        if n:
            backup(path)
            save(path, data)
            total += 1
    print(f"  updated {total} project files")
    print(f"\nBackups in: {BACKUP}")
    print("Done. Repack with: py 3_pack.py")


if __name__ == "__main__":
    main()
