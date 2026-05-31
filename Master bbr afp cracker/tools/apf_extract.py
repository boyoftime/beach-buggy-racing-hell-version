"""Extract a Vector Unit APF archive into readable files (JSON + PNG)."""
import struct, os, json, zlib, lzma, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vujb import parse_vujb
from bbr2jb import looks_like_bbr2jb, parse_bbr2jb
from tex_decode import decode_texture

def _decompress(blob, usize, flags):
    hi = (flags >> 16) & 0xFFFF
    if hi == 0: return blob
    if hi == 1: return zlib.decompress(blob)
    if hi == 2:
        fixed = blob[:5] + struct.pack('<Q', usize) + blob[5:]
        return lzma.decompress(fixed, format=lzma.FORMAT_ALONE)
    if hi == 3: return _snappy_decompress(blob, usize)
    raise ValueError(f'flags 0x{flags:08X}')

def _snappy_decompress(blob, expected_size):
    """Decode a raw Snappy block.

    BBR2 APFs use Snappy for compression type 3. The block starts with Snappy's
    varint uncompressed length, followed by literal/copy tags.
    """
    i = 0
    shift = 0
    declared_size = 0
    while True:
        if i >= len(blob):
            raise ValueError('truncated snappy size')
        b = blob[i]
        i += 1
        declared_size |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
        if shift > 35:
            raise ValueError('invalid snappy size')
    if declared_size != expected_size:
        raise ValueError(f'snappy size {declared_size}, expected {expected_size}')

    out = bytearray()
    n = len(blob)
    while i < n:
        tag = blob[i]
        i += 1
        kind = tag & 0x03
        if kind == 0:
            length = tag >> 2
            if length < 60:
                length += 1
            else:
                nbytes = length - 59
                if i + nbytes > n:
                    raise ValueError('truncated snappy literal length')
                length = int.from_bytes(blob[i:i + nbytes], 'little') + 1
                i += nbytes
            if i + length > n:
                raise ValueError('truncated snappy literal')
            out.extend(blob[i:i + length])
            i += length
        elif kind == 1:
            length = ((tag >> 2) & 0x7) + 4
            if i >= n:
                raise ValueError('truncated snappy copy1')
            offset = ((tag & 0xE0) << 3) | blob[i]
            i += 1
            _snappy_copy(out, offset, length)
        elif kind == 2:
            length = (tag >> 2) + 1
            if i + 2 > n:
                raise ValueError('truncated snappy copy2')
            offset = blob[i] | (blob[i + 1] << 8)
            i += 2
            _snappy_copy(out, offset, length)
        else:
            length = (tag >> 2) + 1
            if i + 4 > n:
                raise ValueError('truncated snappy copy4')
            offset = int.from_bytes(blob[i:i + 4], 'little')
            i += 4
            _snappy_copy(out, offset, length)

    if len(out) != expected_size:
        raise ValueError(f'snappy output {len(out)}, expected {expected_size}')
    return bytes(out)

def _snappy_copy(out, offset, length):
    if offset <= 0 or offset > len(out):
        raise ValueError(f'invalid snappy offset {offset}')
    start = len(out) - offset
    for k in range(length):
        out.append(out[start + k])

def extract_apf(apf_path, out_dir, verbose=True):
    with open(apf_path, 'rb') as f: raw = f.read()
    assert raw[:4] == b'FPUV', f'not APF: {apf_path}'
    _ver, dir_off, _count, dir_size, _h = struct.unpack_from('<IIIII', raw, 4)

    entries = []
    p = dir_off; end = dir_off + dir_size
    while p < end:
        z = raw.index(b'\x00', p)
        name = raw[p:z].decode('ascii', 'replace'); p = z + 1
        if p + 20 > end: break
        offset, usize, csize, h, flags = struct.unpack_from('<IIIII', raw, p); p += 20
        entries.append((name, offset, usize, csize, flags))

    bin_written = json_written = png_written = errors = 0
    os.makedirs(out_dir, exist_ok=True)

    for name, off, usize, csize, flags in entries:
        try:
            data = _decompress(raw[off:off+csize], usize, flags)
        except Exception as e:
            errors += 1
            if verbose: print(f'  decomp FAIL: {name}: {e}')
            continue

        bin_path = os.path.join(out_dir, name.replace('/', os.sep)) + '.bin'
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        with open(bin_path, 'wb') as f: f.write(data)
        bin_written += 1

        # JSON side-product for VUJB assets
        if data[4:8] == b'VUJB':
            try:
                tree = parse_vujb(data)
                with open(bin_path + '.json', 'w', encoding='utf-8') as f:
                    json.dump(tree['root'], f, indent=2, ensure_ascii=False, default=str)
                json_written += 1
            except Exception:
                pass
        elif looks_like_bbr2jb(data):
            try:
                tree = parse_bbr2jb(data)
                with open(bin_path + '.json', 'w', encoding='utf-8') as f:
                    json.dump(tree, f, indent=2, ensure_ascii=False, default=str)
                json_written += 1
            except Exception:
                pass

        # PNG side-product for texture assets
        if name.startswith('VuTextureAsset/'):
            try:
                img, hdr, err = decode_texture(data)
                if img is not None:
                    img.save(bin_path[:-4] + '.png')
                    png_written += 1
            except Exception:
                pass

    if verbose:
        print(f'  {len(entries)} entries, {bin_written} blobs, {json_written} JSONs, {png_written} PNGs ({errors} errors)')
    return entries
