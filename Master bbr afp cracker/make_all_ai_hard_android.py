"""Make ALL normal/quick-race AI fast, aggressive and hard to beat.
Maxes every racing AI personality (Class* + Default + Challenge + DuelSkeleton)
and raises per-mode AI skill/brain in ConstantDB. Bosses keep their stronger v11
profile; Tutorial stays easy.
"""
import json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI = HERE / "extracted/Assets/VuDBAsset/AiPersonalityDB.bin.json"
CONST = HERE / "extracted/Assets/VuDBAsset/ConstantDB.bin.json"

# don't touch these (bosses already extreme; tutorial must stay easy)
SKIP = {"Tutorial"} | {k for k in ()}
BOSSES = {"Boss","BossAlien","BossBeachBro","BossBunny","BossDisco","BossHula",
          "BossLucha","BossRad","BossRoller","BossSkeleton","BossTribal"}

BEHAVIOR = {"PowerUpThrow":16.0,"PowerUpSeek":26.0,"PowerUpDropped":0.5,"PowerUpShield":2.0,
    "PowerUpToughness":3.0,"PowerUpGlobal":26.0,"PowerUpLongShot":26.0,"SpikedTires":0.2,
    "Boost":14.0,"PowerSlide":0.2}
POWERUP = {"Firework":16.0,"Fireball":20.0,"Scattershot":16.0,"FreezeRay":22.0,"EarthStrike":28.0,
    "HomingMissile":30.0,"Tornado":22.0,"Lightning":30.0,"RemoteControl":26.0,"Confusion":22.0,
    "BallChain":26.0,"DeathBat":30.0,"PoliceChase":30.0,"Earthquake":30.0,"NitroCar":14.0,
    "LowGravity":12.0,"BigTires":1.0,"Toughness":1.0,"BasicShield":0.5,"OilSlick":0.2,
    "ChickenCrate":0.2,"MysteryCrate":0.2,"Fake":0.2,"Spring":0.5}

def harden(ai):
    for item in ai.get("BehaviorWeights", []):
        if isinstance(item, dict):
            for k in list(item):
                if k in BEHAVIOR: item[k]=BEHAVIOR[k]
    for item in ai.get("PowerUpWeights", []):
        if isinstance(item, dict):
            for k in list(item):
                if k in POWERUP: item[k]=POWERUP[k]
    ai["AbilityFrequency"]=3
    ai["BossPowerUpFrequency"]=ai.get("BossPowerUpFrequency",15) if False else 3
    ai["BoostFrequency"]=4
    ai["SpikesFrequency"]=90
    ai["PowerslideFrequency"]=90
    ai["ThrottleDownFrequency"]=999.0
    ai["Aggro"]=4.0
    ai["Avoidance"]=4.0
    ai["ReactionTime"]=0.1
    ai["Performance"]={"Toughness":6.0,"Handling":3.0,"TopSpeed":2.6,"Acceleration":4.0}
    rs=ai.setdefault("RaceScript",{})
    for ph in ("Early","Mid","Late"):
        rs.setdefault(ph,{})["DesiredCarPack"]="Ahead"

def main():
    d=json.loads(AI.read_text(encoding="utf-8"))
    done=[]
    for name,ai in d.items():
        if name in SKIP or name in BOSSES or not isinstance(ai,dict):
            continue
        harden(ai); done.append(name)
    AI.write_text(json.dumps(d,ensure_ascii=False,indent=1),encoding="utf-8"); os.utime(AI,None)
    print("Hardened racing personalities:", ", ".join(sorted(done)))

    c=json.loads(CONST.read_text(encoding="utf-8"))
    # per-mode AI: stronger brain + skill
    for mode,cfg in c.get("Games",{}).items():
        if isinstance(cfg,dict) and isinstance(cfg.get("Ai"),dict):
            cfg["Ai"]["AiBrain"]="Default"
            cfg["Ai"]["AiSkill"]=10
    # championship opponents: max speed level
    bumped=0
    for st in c.get("CarChamps",{}).get("Stages",[]):
        for opp in st.get("Opponents",[]):
            if isinstance(opp,dict) and "Speed" in opp:
                opp["Speed"]=5; bumped+=1
    CONST.write_text(json.dumps(c,ensure_ascii=False,indent=1),encoding="utf-8"); os.utime(CONST,None)
    print(f"ConstantDB: per-mode AiSkill->10/Brain->Default; {bumped} champ opponents Speed->5")

if __name__=="__main__":
    main()
