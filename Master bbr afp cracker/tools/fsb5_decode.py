"""Extract FMOD Sample Bank 5 (FSB5) audio streams to .wav files.

BBR stores audio in three wrappers across game editions:
  - Desktop  Expansion/VuAudioStreamAsset/*.bin   -> [4-byte size][FSB5, 1 sample]
  - Desktop  Assets/VuAudioBankAsset/*.bin        -> [1b tag][4b size][FEV...][FSB5, N samples][FEV tail]
  - Android  Expansion/VuAudioStreamAsset/*.bin   -> [4-byte prefix][raw MP3 + ID3v2]

For desktop streams we slice the FSB5 block and hand it to vgmstream-cli
(bundled at tools/bin/) which decodes FMOD's custom Vorbis to WAV.

For Android streams there's no FMOD wrapper at all — Vector Unit ships
plain MP3 files prefixed with a 4-byte header. We detect the ID3 marker,
strip the prefix, and save the result as `.mp3` (every player understands
it natively, no decode step needed).
"""
import os, sys, struct, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
VGM  = os.path.join(HERE, 'bin', 'vgmstream-cli.exe')


def find_fsb5(data: bytes) -> tuple[int, int]:
    """Return (offset, size) of the first FSB5 block inside `data`."""
    off = data.find(b'FSB5')
    if off < 0:
        raise ValueError('no FSB5 magic found')
    # header layout (relative to 'FSB5'):
    #  0  "FSB5"
    #  4  version          (u32)
    #  8  numSamples       (u32)
    # 12  sampleHeadersSize(u32)
    # 16  nameTableSize    (u32)
    # 20  sampleDataSize   (u32)
    # 24  mode             (u32)
    # 28  zero[4]
    # 32  hash[16]
    # 48  dummy[8]
    # 56  (v1 only) extra  [4]
    # 60  sample headers...
    ver, numSamp, shSize, ntSize, sdSize, mode = struct.unpack_from('<IIIIII', data, off + 4)
    exact = 0x3C + shSize + ntSize + sdSize
    return off, exact


def sample_names(fsb5: bytes) -> list[str]:
    """Return the list of sample names from the name table. Empty list if absent."""
    ver, numSamp, shSize, ntSize, sdSize, mode = struct.unpack_from('<IIIIII', fsb5, 4)
    if ntSize == 0:
        return []
    nt_off = 0x3C + shSize
    # name table: numSamp u32 offsets (relative to nt_off), then null-terminated strings.
    names = []
    for i in range(numSamp):
        rel = struct.unpack_from('<I', fsb5, nt_off + i * 4)[0]
        end = fsb5.index(b'\x00', nt_off + rel)
        names.append(fsb5[nt_off + rel:end].decode('ascii', 'replace'))
    return names


def _safe_name(s: str, fallback: str) -> str:
    s = ''.join(c if c.isalnum() or c in '._-' else '_' for c in s).strip('_')
    return s or fallback


def _android_mp3_offset(data: bytes) -> int:
    """If `data` is an Android-edition stream (4-byte prefix + MP3), return
    the byte offset where the MP3 payload starts. Otherwise return -1.

    Heuristic: the standard ID3v2 tag header `49 44 33` (ID3) appears
    immediately after a small fixed-width prefix (typically 4 bytes).
    Vector Unit's mobile streams use this layout for every music track.
    """
    # ID3 at offset 4 = 4-byte prefix then tag. Plain MP3 (no prefix) at 0.
    for off in (4, 0):
        if len(data) > off + 3 and data[off:off + 3] == b'ID3':
            return off
    # MP3 frame sync (0xFF 0xE0 mask 0xFFE0) — bare MP3 with no ID3 tag.
    for off in (4, 0):
        if len(data) > off + 1 and data[off] == 0xFF and (data[off + 1] & 0xE0) == 0xE0:
            return off
    return -1


def decode_bin(bin_path: str, out_dir: str, verbose: bool = True) -> int:
    """Decode every sample inside `bin_path` to WAV (or MP3) files in `out_dir`.

    Returns number of audio files written.
    """
    with open(bin_path, 'rb') as f:
        data = f.read()

    # Android stream: no FSB5 wrapper, just a 4-byte prefix and raw MP3.
    # Strip the prefix and write the MP3 byte-for-byte.
    mp3_off = _android_mp3_offset(data)
    if mp3_off >= 0 and data.find(b'FSB5') < 0:
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(bin_path))[0]
        out_path = os.path.join(out_dir, f'{base}.mp3')
        with open(out_path, 'wb') as out:
            out.write(data[mp3_off:])
        return 1

    if not os.path.isfile(VGM):
        raise RuntimeError(f'vgmstream-cli.exe missing at {VGM}')

    off, size = find_fsb5(data)
    fsb5 = data[off:off + size]
    names = sample_names(fsb5)
    n = len(names) if names else struct.unpack_from('<I', fsb5, 8)[0]

    os.makedirs(out_dir, exist_ok=True)
    # vgmstream needs a real file on disk
    with tempfile.NamedTemporaryFile(suffix='.fsb', delete=False) as tf:
        tf.write(fsb5)
        tmp_path = tf.name

    written = 0
    try:
        for i in range(n):
            name = _safe_name(names[i] if i < len(names) else '', f'sample_{i:03d}')
            # When a bank has >1 samples, prefix the index so the folder sorts naturally.
            if n > 1:
                out_name = f'{i:03d}_{name}.wav'
            else:
                out_name = f'{name}.wav'
            out_path = os.path.join(out_dir, out_name)
            # -s N : select subsong N (1-based)
            cmd = [VGM, '-s', str(i + 1), '-o', out_path, tmp_path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.isfile(out_path):
                if verbose:
                    print(f'  FAIL  {out_name}: {r.stderr.strip() or r.stdout.strip()}')
                continue
            written += 1
        return written
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Extract FSB5 audio from a BBR .bin file')
    ap.add_argument('bin_path')
    ap.add_argument('out_dir')
    args = ap.parse_args()
    n = decode_bin(args.bin_path, args.out_dir)
    print(f'{n} wav files written to {args.out_dir}')


if __name__ == '__main__':
    main()
