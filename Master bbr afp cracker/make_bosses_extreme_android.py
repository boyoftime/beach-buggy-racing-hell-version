"""Make ALL career bosses (Leilani = BossHula, + the rest) EXTREME on Android:
grand-prix top speed, never ease off the throttle, and relentless aggressive
powerup attacks. Edits VuDBAsset/AiPersonalityDB.bin.json in the extracted tree.
"""
import json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI = HERE / "extracted" / "Assets" / "VuDBAsset" / "AiPersonalityDB.bin.json"

BOSSES = {"Boss","BossAlien","BossBeachBro","BossBunny","BossDisco","BossHula",
          "BossLucha","BossRad","BossRoller","BossSkeleton","BossTribal"}

# higher = more likely to use that aggressive behavior
BEHAVIOR = {
    "PowerUpThrow": 20.0, "PowerUpSeek": 30.0, "PowerUpDropped": 0.5,
    "PowerUpShield": 2.0, "PowerUpToughness": 3.0, "PowerUpGlobal": 30.0,
    "PowerUpLongShot": 30.0, "SpikedTires": 0.2, "Boost": 16.0,
    "PowerSlide": 0.2,
}
# weight offensive powerups heavily, junk/defensive low
POWERUP = {
    "Firework": 20.0, "Fireball": 24.0, "Scattershot": 20.0, "FreezeRay": 26.0,
    "EarthStrike": 32.0, "HomingMissile": 36.0, "Tornado": 26.0, "Lightning": 36.0,
    "RemoteControl": 30.0, "Confusion": 26.0, "BallChain": 30.0, "DeathBat": 36.0,
    "PoliceChase": 36.0, "Earthquake": 36.0, "NitroCar": 14.0, "LowGravity": 12.0,
    "BigTires": 1.0, "Toughness": 1.0, "BasicShield": 0.5,
    "OilSlick": 0.2, "ChickenCrate": 0.2, "MysteryCrate": 0.2, "Fake": 0.2, "Spring": 0.5,
}

def main():
    d = json.loads(AI.read_text(encoding="utf-8"))
    patched = []
    for name in sorted(BOSSES):
        ai = d.get(name)
        if not isinstance(ai, dict):
            continue
        for item in ai.get("BehaviorWeights", []):
            if isinstance(item, dict):
                for k in list(item):
                    if k in BEHAVIOR: item[k] = BEHAVIOR[k]
        for item in ai.get("PowerUpWeights", []):
            if isinstance(item, dict):
                for k in list(item):
                    if k in POWERUP: item[k] = POWERUP[k]
        # relentless attacks (lower frequency value = more often)
        ai["AbilityFrequency"] = 1
        ai["BossPowerUpFrequency"] = 1
        ai["BoostFrequency"] = 3
        ai["SpikesFrequency"] = 90
        ai["PowerslideFrequency"] = 90
        ai["ThrottleDownFrequency"] = 999.0   # never ease off the gas
        ai["Aggro"] = 5.0
        ai["Avoidance"] = 5.0
        ai["ReactionTime"] = 0.05
        ai["PowerslideBendiness"] = 1.15
        ai["SpikesBendiness"] = 1.15
        ai["BoostBendiness"] = 1.15
        ai["ThrottleDownBendiness"] = 1.0
        # grand-prix car: way faster, tougher
        ai["Performance"] = {"Toughness": 10.0, "Handling": 4.0, "TopSpeed": 3.5, "Acceleration": 6.0}
        rs = ai.setdefault("RaceScript", {})
        for phase in ("Early", "Mid", "Late"):
            rs.setdefault(phase, {})["DesiredCarPack"] = "Ahead"
        patched.append(name)

    AI.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.utime(AI, None)
    print("Patched bosses:")
    for n in patched:
        print(f"  - {n}" + ("   <= Leilani" if n == "BossHula" else ""))
    if "BossHula" not in patched:
        print("WARNING: BossHula (Leilani) not found!")

if __name__ == "__main__":
    main()
