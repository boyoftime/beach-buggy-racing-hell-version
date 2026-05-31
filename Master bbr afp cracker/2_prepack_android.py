"""Android/BBR audio pre-pack step.

Run after editing audio under extracted\\ and before running 3_pack.py.
This scans every extracted APF folder, so it works with Assets, Expansion,
HF, HW, and other BBR APFs that contain Vector Unit audio assets.
"""
import glob
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tools.bank_encode import encode_bank_bin

WS_ROOT = os.path.join(os.getcwd(), "extracted")
MARKER = os.path.join(WS_ROOT, ".extract_time")


def marker_mtime():
    return os.path.getmtime(MARKER) if os.path.exists(MARKER) else 0


def apf_roots():
    return [
        p for p in glob.glob(os.path.join(WS_ROOT, "*"))
        if os.path.isdir(p)
    ]


def rebuild_music_streams():
    """Wrap edited Android MP3 streams back into <4-byte length><mp3> bins."""
    cutoff = marker_mtime()
    rebuilt = 0
    for root in apf_roots():
        folder = os.path.join(root, "VuAudioStreamAsset")
        if not os.path.isdir(folder):
            continue
        for mp3 in glob.glob(os.path.join(folder, "*.mp3")):
            if os.path.getmtime(mp3) <= cutoff:
                continue
            bin_path = mp3[:-4] + ".bin"
            with open(mp3, "rb") as f:
                mp3_bytes = f.read()
            with open(bin_path, "wb") as f:
                f.write(struct.pack("<I", len(mp3_bytes)))
                f.write(mp3_bytes)
            rel = os.path.relpath(bin_path, WS_ROOT)
            print(f"  music: rebuilt {rel} ({len(mp3_bytes):,} bytes mp3 + 4-byte prefix)")
            rebuilt += 1
    return rebuilt


def rebuild_numbered_bank(bin_path, wav_dir, cutoff):
    edited = []
    for wav in glob.glob(os.path.join(wav_dir, "*.wav")):
        if os.path.getmtime(wav) <= cutoff:
            continue
        base = os.path.basename(wav)
        stem = os.path.splitext(base)[0]
        if os.path.basename(bin_path).lower() == "master.bin":
            if not ("_" in stem and stem[:3].isdigit()):
                continue
        edited.append(wav)
    if not edited:
        return False

    rel = os.path.relpath(bin_path, WS_ROOT)
    print(f"  sfx: {rel} - {len(edited)} edited wav(s), rebuilding bank...")
    new_bytes = encode_bank_bin(bin_path, wav_dir, verbose=False)
    with open(bin_path, "wb") as f:
        f.write(new_bytes)
    print(f"       wrote {os.path.basename(bin_path)} ({len(new_bytes):,} bytes)")
    return True


def rebuild_single_sample_music(bank_root, cutoff):
    """Rebuild BBR2 one-sample music banks from shared Master/*.wav files."""
    master_dir = os.path.join(bank_root, "Master")
    if not os.path.isdir(master_dir):
        return 0

    rebuilt = 0
    for wav_path in glob.glob(os.path.join(master_dir, "*.wav")):
        if os.path.getmtime(wav_path) <= cutoff:
            continue
        stem = os.path.splitext(os.path.basename(wav_path))[0]
        if "_" in stem and stem[:3].isdigit():
            continue
        bin_path = os.path.join(bank_root, stem + ".bin")
        if not os.path.isfile(bin_path):
            continue
        with tempfile.TemporaryDirectory() as td:
            shutil.copy2(wav_path, os.path.join(td, os.path.basename(wav_path)))
            rel = os.path.relpath(bin_path, WS_ROOT)
            print(f"  bbr2 audio: rebuilt {rel} from Master\\{os.path.basename(wav_path)}")
            new_bytes = encode_bank_bin(bin_path, td, verbose=False)
        with open(bin_path, "wb") as f:
            f.write(new_bytes)
        print(f"       wrote {os.path.basename(bin_path)} ({len(new_bytes):,} bytes)")
        rebuilt += 1
    return rebuilt


def rebuild_sfx_banks():
    cutoff = marker_mtime()
    rebuilt = 0
    for root in apf_roots():
        bank_root = os.path.join(root, "VuAudioBankAsset")
        if not os.path.isdir(bank_root):
            continue
        for bin_path in glob.glob(os.path.join(bank_root, "*.bin")):
            wav_dir = bin_path[:-4]
            if os.path.isdir(wav_dir) and rebuild_numbered_bank(bin_path, wav_dir, cutoff):
                rebuilt += 1
        rebuilt += rebuild_single_sample_music(bank_root, cutoff)
    return rebuilt


def main():
    if not os.path.exists(MARKER):
        print("No .extract_time marker - run 1_extract.py first.")
        sys.exit(1)

    print("Audio pre-pack: scanning all extracted APF folders for edited audio...")
    music = rebuild_music_streams()
    banks = rebuild_sfx_banks()
    print()
    if music + banks == 0:
        print("Nothing to do - no edited mp3 or wav files newer than .extract_time.")
    else:
        print(f"Done. {music} music stream(s) + {banks} audio bank(s) rebuilt.")
        print("Next: python 3_pack.py")


if __name__ == "__main__":
    main()
