"""Android: menu volcano sky + orange fog zones + remove menu plants,
and shrink mangroves on non-swamp maps (matches the final PC state).

Run LAST, after lava + atmosphere + mushroomify.
"""
import json, os, shutil, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "extracted" / "Assets"
LEVELS = ASSETS / "VuTemplateAsset" / "Levels"
BG = ASSETS / "VuProjectAsset" / "Screens" / "Background.bin.json"
BACKUP = HERE / "mod_backups" / f"android_menu_mangroves_{time.strftime('%Y%m%d_%H%M%S')}"
BACKUP.mkdir(parents=True, exist_ok=True)

SKY_MODEL = "Skybox/Skybox_Volcano"
SKY_CUBE = "HazyOrange_cube"
FOGC = {"R": 246, "G": 163, "B": 45, "A": 255}
DFOGC = {"R": 220, "G": 159, "B": 52, "A": 255}
MANG_SCALE = 0.45
EXCLUDE = {"SwampA", "SwampB"}


def save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.utime(p, None)


def add_deps(data):
    ad = data.get("AssetData")
    if not isinstance(ad, list):
        return
    rows = {r[0]: r for r in ad if isinstance(r, list) and r}
    want = {
        "VuStaticModelAsset": "Skybox/Skybox_Volcano",
        "VuCubeTextureAsset": "HazyOrange_cube",
        "VuMaterialAsset": "Skybox/BlueSky",
        "VuTextureAsset": "Skybox/BlueSky",
    }
    for atype, name in want.items():
        row = rows.get(atype)
        if row is None:
            row = [atype]; ad.append(row); rows[atype] = row
        if name not in row[1:]:
            row.append(name)
    for r in ad:
        if isinstance(r, list) and len(r) > 2:
            r[:] = [r[0]] + sorted(r[1:])


# ---- menu Background: volcano sky, orange fog everywhere, remove all plants ----
shutil.copy2(BG, BACKUP / "Background.bin.json")
d = json.loads(BG.read_text(encoding="utf-8"))

def is_plant(o):
    if not isinstance(o, dict):
        return False
    t = o.get("type")
    if isinstance(t, str) and ((t.startswith("#Prop/") and "Mushroom" in t)
                               or t.startswith("#Plant/") or t.startswith("#Foliage/")):
        return True
    comps = o.get("data", {}).get("Components", {}) if isinstance(o.get("data"), dict) else {}
    c = comps.get("Vu3dDrawStaticModelComponent", {})
    ma = c.get("Properties", {}).get("Model Asset", "") if isinstance(c, dict) else ""
    return isinstance(ma, str) and any(k in ma for k in ("Mushroom", "Palm", "Mangrove", "Plant/", "Foliage"))

removed = [0]
def edit_bg(o):
    if isinstance(o, dict):
        nm = o.get("name")
        pr = o.get("data", {}).get("Properties") if isinstance(o.get("data"), dict) else None
        if nm in ("SkyBox01", "SwapSkybox01") and isinstance(pr, dict):
            pr["Model Asset"] = SKY_MODEL
        if isinstance(pr, dict) and pr.get("Asset Type") == "VuCubeTextureAsset" and pr.get("Asset Name") == "Proxy_cube":
            pr["Subst Asset Name"] = SKY_CUBE
        if isinstance(pr, dict) and "Fog Color" in pr:
            pr["Fog Color"] = dict(FOGC)
            pr["Depth Fog Color"] = dict(DFOGC)
        for k in list(o.keys()):
            o[k] = edit_bg(o[k])
        return o
    if isinstance(o, list):
        out = []
        for v in o:
            if is_plant(v):
                removed[0] += 1
                continue
            out.append(edit_bg(v))
        return out
    return o

d = edit_bg(d)
add_deps(d)
save(BG, d)
print(f"Menu Background: volcano sky + orange fog set, removed {removed[0]} plant entities")

# ---- mangrove shrink on non-swamp maps ----
for f in sorted(LEVELS.glob("*.bin.json")):
    if f.stem.replace(".bin", "") in EXCLUDE:
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    n = [0]
    def w(o):
        if isinstance(o, dict):
            t = o.get("type")
            if isinstance(t, str) and "Mangrove" in t:
                tc = o.get("data", {}).get("Components", {}).get("VuTransformComponent", {}).setdefault("Properties", {})
                tc["Scale"] = {"X": MANG_SCALE, "Y": MANG_SCALE, "Z": MANG_SCALE}
                n[0] += 1
            for v in o.values():
                w(v)
        elif isinstance(o, list):
            for v in o:
                w(v)
    w(data)
    if n[0]:
        shutil.copy2(f, BACKUP / f.name)
        save(f, data)
        print(f"  {f.name:22} shrank {n[0]} mangroves -> {MANG_SCALE}")

print(f"\nBackup: {BACKUP}")
