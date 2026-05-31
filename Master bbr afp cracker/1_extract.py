"""Extract every imported BBR APF archive into the Studio workspace.

The app copies selected archives into workspace/input before running this
script. We support the standard BBR names (Assets.apf, Expansion.apf, HF.apf)
and any future BBR APF that uses the same Vector Unit container. Each archive
is extracted into workspace/extracted/<ArchiveStem>/.
"""
import glob
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))

from apf_extract import extract_apf
from fsb5_decode import decode_bin

INPUT = os.path.join(os.getcwd(), "input")
EXTRACTED = os.path.join(os.getcwd(), "extracted")
MARKER = os.path.join(EXTRACTED, ".extract_time")

CANONICAL = {
    "assets": "Assets",
    "expansion": "Expansion",
    "hf": "HF",
    "hw": "HW",
}


def archive_stem(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return CANONICAL.get(stem.lower(), stem)


def progress(done, total):
    pct = 100.0 if total <= 0 else max(0.0, min(100.0, done / total * 100.0))
    print(f"PROGRESS:{pct:.2f}", flush=True)


os.makedirs(INPUT, exist_ok=True)
os.makedirs(EXTRACTED, exist_ok=True)

apfs = sorted(glob.glob(os.path.join(INPUT, "*.apf")), key=lambda p: archive_stem(p).lower())
if not apfs:
    print("Nothing to extract. Drop Assets.apf, Expansion.apf, HF.apf, or another BBR APF into input\\.")
    sys.exit(1)

for i, src in enumerate(apfs):
    out_sub = archive_stem(src)
    out = os.path.join(EXTRACTED, out_sub)
    size_mb = os.path.getsize(src) / 1_048_576
    print(f"Extracting {os.path.basename(src)} ({size_mb:.1f} MB) -> extracted\\{out_sub}\\")
    extract_apf(src, out)
    progress(i + 0.75, len(apfs))

    for asset_type in ("VuAudioBankAsset", "VuAudioStreamAsset"):
        bin_dir = os.path.join(out, asset_type)
        if not os.path.isdir(bin_dir):
            continue
        for fn in sorted(os.listdir(bin_dir)):
            if not fn.lower().endswith(".bin"):
                continue
            bin_path = os.path.join(bin_dir, fn)
            stem = fn[:-4]
            wav_dir = bin_dir if asset_type == "VuAudioStreamAsset" else os.path.join(bin_dir, stem)
            print(f"  Dumping audio: {out_sub}/{asset_type}/{fn}")
            try:
                n = decode_bin(bin_path, wav_dir, verbose=False)
                print(f"    {n} wav file(s) -> {wav_dir}")
            except Exception as e:
                print(f"    audio dump skipped: {e}")
    progress(i + 1, len(apfs))

with open(MARKER, "w", encoding="utf-8") as f:
    f.write(str(time.time()))
os.utime(MARKER, None)

extract_ts = os.path.getmtime(MARKER) - 1
for wav in glob.glob(os.path.join(EXTRACTED, "**", "*.wav"), recursive=True):
    try:
        os.utime(wav, (extract_ts, extract_ts))
    except OSError:
        pass

print("Done. Edit files under extracted\\, then repack.")
