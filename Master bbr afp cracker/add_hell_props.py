"""Add Death Bat Alley 'hell' props (skeletons + flying death bats) to every
map and the menu Background. Uses original game models/textures (no texture
re-encode), placing instances at existing valid ground positions; bats are
raised into the air. Adds the needed asset dependencies to each project.
"""
import json, os, shutil, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "extracted" / "Assets"
LEVELS = ASSETS / "VuTemplateAsset" / "Levels"
PROJECTS = ASSETS / "VuProjectAsset"
BG = PROJECTS / "Screens" / "Background.bin.json"
BACKUP = HERE / "mod_backups" / f"hell_props_{time.strftime('%Y%m%d_%H%M%S')}"
BACKUP.mkdir(parents=True, exist_ok=True)

SKELS = ["#Prop/PropBreakable_Skeleton_A", "#Prop/PropBreakable_Skeleton_B", "#Prop/PropBreakable_Skeleton_C"]
BAT = "#NPC/NPC_Deathbat_Flying"
SKEL_PER_MAP = 70
BAT_PER_MAP = 10
SKEL_PER_MENU = 25
BAT_PER_MENU = 8
BAT_HEIGHT = 18.0          # raise bats this much on the Z (up) axis
EXCLUDE = {"LavaA"}        # already full of them

DEPS = {
    "VuAnimatedModelAsset": ["NPC/Deathbat"],
    "VuAnimationAsset": ["NPC/DeathBat/Deathbat_Attack", "NPC/DeathBat/Deathbat_Flap"],
    "VuMaterialAsset": ["NPC/Deathbat", "NPC/Deathbat_skinned", "Prop/Skeleton", "Prop/SkeletonA", "Prop/SkeletonC"],
    "VuStaticModelAsset": ["NPC/Deathbat_broken", "NPC/Deathbat_static",
        "Prop/Skeleton_A", "Prop/Skeleton_A_broken", "Prop/Skeleton_B", "Prop/Skeleton_B_broken",
        "Prop/Skeleton_B_lod1", "Prop/Skeleton_C", "Prop/Skeleton_C_broken", "Prop/Skeleton_C_lod1"],
    "VuTemplateAsset": ["NPC/NPC_Deathbat_Flying",
        "Prop/PropBreakable_Skeleton_A", "Prop/PropBreakable_Skeleton_B", "Prop/PropBreakable_Skeleton_C"],
    "VuTextureAsset": ["NPC/Deathbat", "Prop/Skeleton", "Prop/SkeletonA", "Prop/SkeletonA_N",
        "Prop/SkeletonC", "Prop/Skeleton_N"],
}


def save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.utime(p, None)


def collect_positions(root):
    pos = []
    def w(o):
        if isinstance(o, dict):
            t = o.get("type")
            if isinstance(t, str) and t.startswith("#"):
                p = o.get("data", {}).get("Components", {}).get("VuTransformComponent", {}).get("Properties", {}).get("Position")
                if isinstance(p, dict) and all(k in p for k in ("X", "Y", "Z")):
                    pos.append((p["X"], p["Y"], p["Z"]))
            for v in o.values():
                w(v)
        elif isinstance(o, list):
            for v in o:
                w(v)
    w(root)
    return pos


def find_prop_container(root):
    """First list/dict that directly holds a #Prop/ instance."""
    found = [None]
    def w(o):
        if found[0]:
            return
        if isinstance(o, list):
            if any(isinstance(x, dict) and str(x.get("type", "")).startswith("#Prop/") for x in o):
                found[0] = (o, "list"); return
            for x in o: w(x)
        elif isinstance(o, dict):
            for v in o.values():
                if isinstance(v, dict) and str(v.get("type", "")).startswith("#Prop/"):
                    found[0] = (o, "dict"); return
            for v in o.values(): w(v)
    w(root)
    return found[0]


def make_skel(stype, x, y, z, name):
    return {"data": {"Components": {
        "VuDepthFogComponent": {"WaterZ": -100000},
        "VuTransformComponent": {"Properties": {"Position": {"X": x, "Y": y, "Z": z}}}}},
        "type": stype, "name": name}


def make_bat(x, y, z, name):
    return {"data": {
        "ChildEntities": {"BreakableGameProp01": {"Components": {"VuDepthFogComponent": {"WaterZ": -100000}}}},
        "Components": {"VuTransformComponent": {"Properties": {"Position": {"X": x, "Y": y, "Z": z}}}}},
        "type": BAT, "name": name}


def add_entities(container, kind, entities):
    if kind == "list":
        container.extend(entities)
    else:
        for e in entities:
            container[e["name"]] = e


def inject(root, n_skel, n_bat, tag):
    pos = collect_positions(root)
    cont = find_prop_container(root)
    if not pos or not cont:
        return 0, 0
    container, kind = cont
    # sample evenly
    def sample(k):
        if k <= 0 or not pos:
            return []
        step = max(1, len(pos) // k)
        return pos[::step][:k]
    skel_pts = sample(n_skel)
    bat_pts = sample(n_bat)
    ents = []
    for i, (x, y, z) in enumerate(skel_pts):
        ents.append(make_skel(SKELS[i % 3], x, y, z, f"Hell{tag}Skel{i:03d}"))
    for i, (x, y, z) in enumerate(bat_pts):
        ents.append(make_bat(x, y, z + BAT_HEIGHT, f"Hell{tag}Bat{i:03d}"))
    add_entities(container, kind, ents)
    return len(skel_pts), len(bat_pts)


def add_deps(data):
    ad = data.get("AssetData")
    if not isinstance(ad, list):
        return
    rows = {r[0]: r for r in ad if isinstance(r, list) and r}
    for atype, names in DEPS.items():
        row = rows.get(atype)
        if row is None:
            row = [atype]; ad.append(row); rows[atype] = row
        existing = set(row[1:])
        for n in names:
            if n not in existing:
                row.append(n)
    for r in ad:
        if isinstance(r, list) and len(r) > 2:
            r[:] = [r[0]] + sorted(r[1:])


def main():
    print("== Injecting hell props into level templates ==")
    for f in sorted(LEVELS.glob("*.bin.json")):
        if f.stem.replace(".bin", "") in EXCLUDE:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        ns, nb = inject(data, SKEL_PER_MAP, BAT_PER_MAP, "")
        if ns or nb:
            shutil.copy2(f, BACKUP / f.name)
            save(f, data)
        print(f"  {f.name:22} +{ns} skeletons  +{nb} bats")

    print("\n== Menu Background ==")
    data = json.loads(BG.read_text(encoding="utf-8"))
    ns, nb = inject(data, SKEL_PER_MENU, BAT_PER_MENU, "Menu")
    add_deps(data)
    shutil.copy2(BG, BACKUP / "Background.bin.json")
    save(BG, data)
    print(f"  Background.bin.json    +{ns} skeletons  +{nb} bats")

    print("\n== Adding deps to all project files ==")
    cnt = 0
    for f in sorted(PROJECTS.glob("*.bin.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        before = json.dumps(data.get("AssetData"))
        add_deps(data)
        if json.dumps(data.get("AssetData")) != before:
            save(f, data); cnt += 1
    print(f"  updated {cnt} project files")
    print(f"\nBackup: {BACKUP}")


if __name__ == "__main__":
    main()
