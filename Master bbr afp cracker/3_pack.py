"""Repack every imported BBR APF archive from Studio's workspace."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))

from apf_pack import pack_apf

INPUT = os.path.join(os.getcwd(), "input")
EXTRACTED = os.path.join(os.getcwd(), "extracted")
OUTPUT = os.path.join(os.getcwd(), "output")
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


os.makedirs(OUTPUT, exist_ok=True)

apfs = sorted(glob.glob(os.path.join(INPUT, "*.apf")), key=lambda p: archive_stem(p).lower())
if not apfs:
    print("No APFs in input\\ - run extract first.")
    sys.exit(1)

if not os.path.exists(MARKER):
    print("Missing extracted\\.extract_time - run extract first.")
    sys.exit(1)

extract_time = os.path.getmtime(MARKER)
produced = []

for i, src in enumerate(apfs):
    name = os.path.basename(src)
    out_sub = archive_stem(src)
    edits_dir = os.path.join(EXTRACTED, out_sub)
    if not os.path.isdir(edits_dir):
        print(f"Skipping {name}: no extracted\\{out_sub}\\ folder")
        progress(i + 1, len(apfs))
        continue
    dst = os.path.join(OUTPUT, name)
    print(f"Packing {name}...")
    pack_apf(src, dst, edits_dir, extract_time)
    produced.append(name)
    progress(i + 1, len(apfs))

if produced:
    print("Done. Modded APFs are in:")
    print(f"    {OUTPUT}")
    print("Files: " + ", ".join(produced))
else:
    print("No APFs were packed.")
