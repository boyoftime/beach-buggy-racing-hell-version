"""Pack a WAV file into an FSB5 PCM16 container with the BBR 4-byte size prefix.

Used for VuAudioStreamAsset replacements (the 7 music streams).
No external tools needed — pure Python struct packing.

FMOD will load PCM16 FSB5 the same as Vorbis FSB5; the file is just larger.

Sample-entry bit layout (1×u64, little-endian):
  bit  0     : next_chunk  (0 = no extra codec chunks; 1 = Vorbis/XMA chunks follow)
  bits 1-4   : frequency table index  (see FREQ_TABLE)
  bits 5-6   : channels - 1
  bits 7-33  : data_offset >> 4  (bytes into sample-data section; 0 for first sample)
  bits 34-63 : numSamples  (PCM frame count, not byte count)
"""
import struct, wave, os

FREQ_TABLE = [4000, 8000, 11000, 11025, 16000, 22050, 24000, 32000,
              44100, 48000, 96000, 192000]


def stream_bin_from_wav(wav_path: str, sample_name: str) -> bytes:
    """Return the full .bin bytes for a VuAudioStreamAsset replacement.

    The result is: [4-byte LE size of FSB5] [FSB5 PCM16 data].
    Drop the result straight into the APF as the new entry payload.
    """
    with wave.open(wav_path, 'rb') as w:
        channels  = w.getnchannels()
        rate      = w.getframerate()
        sampwidth = w.getsampwidth()
        nframes   = w.getnframes()
        pcm       = w.readframes(nframes)

    if sampwidth != 2:
        raise ValueError(
            f'{os.path.basename(wav_path)}: must be 16-bit PCM '
            f'(got {sampwidth * 8}-bit). Re-export from your editor as 16-bit WAV.'
        )
    if rate not in FREQ_TABLE:
        raise ValueError(
            f'{os.path.basename(wav_path)}: unsupported sample rate {rate} Hz. '
            f'Supported: {FREQ_TABLE}'
        )
    if channels not in (1, 2):
        raise ValueError(
            f'{os.path.basename(wav_path)}: unsupported channel count {channels}.'
        )

    freq_idx = FREQ_TABLE.index(rate)

    # u64 sample entry (next_chunk=0 for PCM16, no extra chunks needed)
    entry_val = (freq_idx        <<  1) \
              | ((channels - 1)  <<  5) \
              | (nframes         << 34)
    sample_entry = struct.pack('<Q', entry_val)

    # Name table: one u32 offset (=4, pointing past the offset itself) + name\0 + pad
    name_bytes = sample_name.encode('ascii') + b'\x00'
    name_table = struct.pack('<I', 4) + name_bytes
    while len(name_table) % 4:
        name_table += b'\x00'

    sh_size = len(sample_entry)   # 8
    nt_size = len(name_table)
    sd_size = len(pcm)

    # FSB5 header — exactly 60 (0x3C) bytes
    #  +0x00  magic "FSB5"       (4)
    #  +0x04  version=1          (4)
    #  +0x08  numSamples=1       (4)
    #  +0x0C  sampleHeadersSize  (4)
    #  +0x10  nameTableSize      (4)
    #  +0x14  sampleDataSize     (4)
    #  +0x18  mode=2 (PCM16)     (4)
    #  +0x1C  extra=0            (4)
    #  +0x20  zeros              (12)
    #  +0x2C  hash (all-zero ok) (16)
    fsb5_header = struct.pack(
        '<4sIIIIII I 12s 16s',
        b'FSB5',
        1,          # version
        1,          # numSamples
        sh_size,
        nt_size,
        sd_size,
        2,          # mode: PCM16
        0,          # extra
        b'\x00' * 12,
        b'\x00' * 16,
    )
    assert len(fsb5_header) == 0x3C, f'header size wrong: {len(fsb5_header)}'

    fsb5 = fsb5_header + sample_entry + name_table + pcm

    # BBR wrapper: 4-byte LE payload size prefix
    return struct.pack('<I', len(fsb5)) + fsb5
