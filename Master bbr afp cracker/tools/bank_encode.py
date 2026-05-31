"""Rebuild a multi-sample FSB5 SFX bank (Assets/VuAudioBankAsset/*.bin).

The source bank is FADPCM (FMOD proprietary, no public encoder). We re-encode
every sample as PCM16 which FMOD will still play; the file just gets larger.

Outer file layout:
  [1b tag 0x01][4b wrap_size][RIFF FEV container with SND->FSB5][optional tail]

Three size fields must be updated by `delta = new_fsb5 - old_fsb5`:
  wrap_size @ 0x1   RIFF size @ 0x9   SND chunk size (scanned)

FSB5 sample-header u64 bit layout (from vgmstream's src/meta/fsb5.c):
  bit  0     next_chunk flag (extra chunks follow; always 0 for raw PCM16)
  bits 1-4   frequency-table index
  bits 5-6   channels - 1
  bits 7-33  data_offset >> 5  (27-bit field; vgmstream left-shifts by 5, so
             each sample's PCM must be 32-byte aligned, NOT 16-byte)
  bits 34-63 numSamples (per-channel frame count)
"""
import os, struct, wave

FREQ_TABLE = [4000, 8000, 11000, 11025, 16000, 22050, 24000, 32000,
              44100, 48000, 96000, 192000]


def _read_wav_pcm16(path):
    with wave.open(path, 'rb') as w:
        ch = w.getnchannels()
        rate = w.getframerate()
        sw = w.getsampwidth()
        n  = w.getnframes()
        pcm = w.readframes(n)
    if sw != 2:
        raise ValueError(f'{os.path.basename(path)}: need 16-bit PCM (got {sw*8}-bit)')
    if rate not in FREQ_TABLE:
        raise ValueError(f'{os.path.basename(path)}: bad rate {rate} Hz; allowed {FREQ_TABLE}')
    if ch not in (1, 2):
        raise ValueError(f'{os.path.basename(path)}: {ch} channels (need 1 or 2)')
    return ch, rate, n, pcm


def _pad32(b: bytes) -> bytes:
    rem = len(b) % 32
    return b + b'\x00' * (32 - rem) if rem else b


def build_fsb5_pcm16(samples):
    """samples: list of (name, channels, rate, numFrames, pcm_bytes).
    Returns raw FSB5 block bytes."""
    n = len(samples)

    # Sample headers: one u64 each for PCM16 with no extra chunks.
    sh_buf = bytearray()
    data_buf = bytearray()
    for (_name, ch, rate, nframes, pcm) in samples:
        freq_idx = FREQ_TABLE.index(rate)
        data_off = len(data_buf)                 # 32-aligned (pcm is pre-padded)
        if data_off & 0x1F:
            raise RuntimeError('data offset misalignment')
        # u64 entry: next_chunk(1) | freq_idx(4) | channels-1(2) | data_off>>5(27) | numSamples(30)
        # vgmstream reads the 27-bit field then shifts left by 5, so pad samples to 32-byte.
        entry = (0                                 # next_chunk = 0
                 | (freq_idx & 0xF)      << 1
                 | ((ch - 1) & 0x3)      << 5
                 | ((data_off >> 5) & 0x07FFFFFF) << 7
                 | (nframes & 0x3FFFFFFF) << 34)
        sh_buf.extend(struct.pack('<Q', entry))
        data_buf.extend(_pad32(pcm))

    # Name table: N×u32 offsets (relative to name-table start), then null-terminated names,
    # whole thing padded to multiple of 4.
    names = [s[0] for s in samples]
    name_bytes_blobs = [name.encode('ascii', 'replace') + b'\x00' for name in names]
    offsets = []
    running = 4 * n                              # N offsets come first
    for blob in name_bytes_blobs:
        offsets.append(running)
        running += len(blob)
    nt_buf = bytearray()
    for off in offsets:
        nt_buf.extend(struct.pack('<I', off))
    for blob in name_bytes_blobs:
        nt_buf.extend(blob)
    while len(nt_buf) % 4:
        nt_buf.append(0)

    sh_size = len(sh_buf)
    nt_size = len(nt_buf)
    sd_size = len(data_buf)

    header = struct.pack(
        '<4sIIIIII I 12s 16s',
        b'FSB5',
        1,          # version
        n,          # numSamples
        sh_size,
        nt_size,
        sd_size,
        2,          # mode: PCM16
        0,          # extra
        b'\x00' * 12,
        b'\x00' * 16,
    )
    assert len(header) == 0x3C

    return bytes(header + sh_buf + nt_buf + data_buf)


def _find_snd_size_field(data, fsb5_off):
    """FSB5 sits inside an FEV 'SND ' chunk. Scan backwards up to 64 bytes to
    find the 'SND ' FourCC; its 4-byte LE size field is right after it."""
    start = max(0, fsb5_off - 64)
    tag_off = data.rfind(b'SND ', start, fsb5_off)
    if tag_off < 0:
        raise RuntimeError("could not locate enclosing 'SND ' chunk")
    return tag_off + 4   # size field is 4 bytes after the FourCC


def _find_sndh_size_fields(data, fsb5_off, old_fsb5_size):
    """Each 'SNDH' chunk body carries a u32 FSB5 byte size. FMOD uses it to
    bound its read of the bank, so a stale value silently kills playback."""
    hits = []
    off = 0
    while True:
        i = data.find(b'SNDH', off)
        if i < 0:
            break
        off = i + 4
        sz = struct.unpack_from('<I', data, i + 4)[0]
        if sz == 0:
            continue
        body = data[i + 8 : i + 8 + sz]
        for j in range(0, len(body) - 3, 4):
            if struct.unpack_from('<I', body, j)[0] == old_fsb5_size:
                hits.append(i + 8 + j)
    return hits


def encode_bank_bin(original_bin_path, wav_dir, verbose=False):
    """Read `original_bin_path` (the *.bin file extracted from the APF),
    look for WAVs in `wav_dir`, rebuild the FSB5 block with PCM16 data, and
    return the new .bin bytes.

    WAV filenames must match the original sample names with a `NNN_` index
    prefix (e.g. `000_fireball_fire.wav`) — that's what fsb5_decode writes.
    The index drives sample order; the text after `_` is the restored name.
    """
    with open(original_bin_path, 'rb') as f:
        data = f.read()

    fsb5_off = data.find(b'FSB5')
    if fsb5_off < 0:
        raise RuntimeError('no FSB5 magic')
    ver, numSamp, shSize, ntSize, sdSize, mode = struct.unpack_from('<IIIIII', data, fsb5_off + 4)
    old_fsb5_size = 0x3C + shSize + ntSize + sdSize

    # Read original sample names so we can sanity-check + preserve order
    orig_names = []
    if ntSize:
        nt_off = fsb5_off + 0x3C + shSize
        for i in range(numSamp):
            rel = struct.unpack_from('<I', data, nt_off + i * 4)[0]
            z = data.index(b'\x00', nt_off + rel)
            orig_names.append(data[nt_off + rel:z].decode('ascii', 'replace'))

    # Match WAV files to sample indices
    wavs_by_idx = {}
    for fn in os.listdir(wav_dir):
        if not fn.lower().endswith('.wav'):
            continue
        stem = fn[:-4]
        if '_' in stem and stem[:3].isdigit():
            idx = int(stem[:3])
            name = stem[4:]
        else:
            # no prefix — can happen for single-sample banks (e.g. music streams)
            idx = 0
            name = stem
        wavs_by_idx[idx] = (os.path.join(wav_dir, fn), name)

    if len(wavs_by_idx) < numSamp:
        missing = set(range(numSamp)) - set(wavs_by_idx.keys())
        raise RuntimeError(f'missing WAVs for sample indices: {sorted(missing)}')

    # Load each WAV, build sample list
    samples = []
    for i in range(numSamp):
        path, name = wavs_by_idx[i]
        # Prefer original name if mismatch — the game looks samples up by name
        final_name = orig_names[i] if i < len(orig_names) and orig_names[i] else name
        ch, rate, nframes, pcm = _read_wav_pcm16(path)
        if verbose:
            print(f'  [{i:03d}] {final_name} -> {ch}ch {rate}Hz {nframes} frames ({len(pcm)} B)')
        samples.append((final_name, ch, rate, nframes, pcm))

    new_fsb5 = build_fsb5_pcm16(samples)
    delta = len(new_fsb5) - old_fsb5_size
    if verbose:
        print(f'FSB5: {old_fsb5_size:,} -> {len(new_fsb5):,} bytes (delta {delta:+,})')

    # Splice
    out = bytearray(data[:fsb5_off])
    out.extend(new_fsb5)
    out.extend(data[fsb5_off + old_fsb5_size:])

    # Patch 3 ancestor size fields (WRAP, RIFF, SND)
    snd_size_off = _find_snd_size_field(data, fsb5_off)
    for size_off in (0x1, 0x9, snd_size_off):
        cur = struct.unpack_from('<I', out, size_off)[0]
        struct.pack_into('<I', out, size_off, cur + delta)
        if verbose:
            print(f'  patched size @0x{size_off:X}: {cur:,} -> {cur + delta:,}')

    # Plus every FEV SNDH body field that stored the old FSB5 size
    for sndh_off in _find_sndh_size_fields(data, fsb5_off, old_fsb5_size):
        struct.pack_into('<I', out, sndh_off, old_fsb5_size + delta)
        if verbose:
            print(f'  patched SNDH fsb5 size @0x{sndh_off:X}: {old_fsb5_size:,} -> {old_fsb5_size + delta:,}')

    return bytes(out)
