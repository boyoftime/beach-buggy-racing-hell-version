"""Pack a Vector Unit APF with edits pulled straight from `extracted/`.

User edits files directly under `extracted/Assets/` (or Expansion/). A file is
considered "edited" if its mtime is newer than the `.extract_time` marker that
`1_extract.py` drops next to the extracted tree. Edited files are re-encoded
and re-hashed; untouched entries pass through bit-exact from the original APF.
"""
import struct, os, zlib, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vujb_encode import encode as vujb_encode
from bbr2jb_encode import encode as bbr2jb_encode
from tex_encode import encode_png_as_texture
from fsb5_encode import stream_bin_from_wav

def fnv1a32(b):
    h = 0x811C9DC5
    for x in b:
        h ^= x; h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def _compress(data, flags):
    """Edited entries go out as zlib (Python's LZMA is not stream-compatible)."""
    hi = (flags >> 16) & 0xFFFF
    lo = flags & 0xFFFF
    if hi == 0: return data, flags
    if hi == 1: return zlib.compress(data, 9), flags
    if hi == 2: return zlib.compress(data, 9), (1 << 16) | lo
    if hi == 3: return zlib.compress(data, 9), (1 << 16) | lo
    raise ValueError(f'flags 0x{flags:08X}')

def _was_edited(path, since):
    """True if `path` exists and was modified after the extraction marker."""
    try:
        return os.path.getmtime(path) > since
    except OSError:
        return False

def _find_edit(name, edits_dir, since):
    """Return (bytes, kind) if the user edited this entry in `edits_dir`."""
    rel = name.replace('/', os.sep)

    json_path = os.path.join(edits_dir, rel + '.bin.json')
    if _was_edited(json_path, since):
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        if isinstance(doc, dict) and doc.get('__bbr2jb__'):
            return bbr2jb_encode(doc), 'json'
        return vujb_encode(doc), 'json'

    if name.startswith('VuTextureAsset/'):
        png_path = os.path.join(edits_dir, rel + '.png')
        if _was_edited(png_path, since):
            orig_bin = os.path.join(edits_dir, rel + '.bin')
            return encode_png_as_texture(png_path, original_bin_path=orig_bin), 'png'

    if name.startswith('VuAudioStreamAsset/'):
        wav_path = os.path.join(edits_dir, rel + '.wav')
        if _was_edited(wav_path, since):
            stream_name = os.path.splitext(os.path.basename(wav_path))[0]
            return stream_bin_from_wav(wav_path, stream_name), 'wav'

    bin_path = os.path.join(edits_dir, rel + '.bin')
    if _was_edited(bin_path, since):
        with open(bin_path, 'rb') as f: return f.read(), 'bin'

    return None

def pack_apf(source_apf, output_apf, edits_dir, since, verbose=True):
    with open(source_apf, 'rb') as f: raw = f.read()
    assert raw[:4] == b'FPUV'
    _ver, dir_off, _c, dir_size, _h = struct.unpack_from('<IIIII', raw, 4)

    entries = []
    p = dir_off; end = dir_off + dir_size
    while p < end:
        z = raw.index(b'\x00', p)
        name = raw[p:z].decode('ascii', 'replace'); p = z + 1
        offset, usize, csize, h, flags = struct.unpack_from('<IIIII', raw, p); p += 20
        entries.append({'name': name, 'orig_off': offset, 'usize': usize,
                         'csize': csize, 'hash': h, 'flags': flags})

    # Preserve the entire original 64-byte header — the game reads metadata
    # past the 5 fields we know about (e.g. a "WinStore" platform marker at
    # bytes 24..32 and a hash at bytes 20..24). Wiping that causes the game
    # to reject the file.
    edits_applied = []

    # Body layout order is NOT the same as directory order — the original
    # file stores entry bodies in offset order (alphabetical dir, custom
    # body order). Preserve body order so untouched entries stay bit-exact.
    body_order = sorted(entries, key=lambda e: e['orig_off'])
    header_size = min(e['orig_off'] for e in entries)
    out = bytearray(raw[:header_size])

    for e in body_order:
        edit = _find_edit(e['name'], edits_dir, since)
        if edit is None:
            e['new_off']   = len(out)
            out.extend(raw[e['orig_off']:e['orig_off'] + e['csize']])
            e['new_usize'] = e['usize']
            e['new_csize'] = e['csize']
            e['new_hash']  = e['hash']
        else:
            plain, kind = edit
            comp, new_flags = _compress(plain, e['flags'])
            e['new_off']   = len(out); out.extend(comp)
            e['new_usize'] = len(plain)
            e['new_csize'] = len(comp)
            e['new_hash']  = fnv1a32(plain)
            e['flags']     = new_flags
            edits_applied.append((e['name'], kind))

    dir_buf = bytearray()
    for e in entries:
        dir_buf.extend(e['name'].encode('ascii') + b'\x00')
        dir_buf.extend(struct.pack('<IIIII',
            e['new_off'], e['new_usize'], e['new_csize'],
            e['new_hash'], e['flags']))

    dir_offset = len(out)
    out.extend(dir_buf)
    # Overwrite only the fields whose values actually change when we swap
    # entry bodies. Platform marker, flags, and padding are preserved from
    # the original 64-byte header copied above.
    #   bytes  8..12 : directory offset (moves if any entry's csize changed)
    #   bytes 16..20 : directory size   (could change in principle; usually same)
    #   bytes 20..24 : fnv1a32 over the directory bytes — critical integrity
    #                  check. The game exits immediately if this doesn't match
    #                  the recomputed hash of the directory.
    struct.pack_into('<I', out, 8, dir_offset)
    struct.pack_into('<I', out, 16, len(dir_buf))
    struct.pack_into('<I', out, 20, fnv1a32(bytes(dir_buf)))
    # Trailing header hash at bytes 60..64 covers the first 60 bytes of the
    # header. Must be written after the other header fields settle.
    if header_size >= 24:
        struct.pack_into('<I', out, header_size - 4, fnv1a32(bytes(out[0:header_size - 4])))

    with open(output_apf, 'wb') as f: f.write(out)

    if verbose:
        print(f'  -> {output_apf}  ({len(out)/1_048_576:.2f} MB, {len(edits_applied)} edits)')
        for n, k in edits_applied:
            print(f'     [{k}] {n}')
    return len(edits_applied)
