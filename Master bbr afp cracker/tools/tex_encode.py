"""PNG -> Vector Unit texture blob.

Three encode paths, picked by sniffing the format code in the original .bin's
header:

  - Desktop  (DXGI codes):   write fmt 28 (RGBA8_UNORM) + 65-byte header.
  - Android compressed (ETC1 / ETC2 / ETC2-EAC / ETC2-PA1): encode the user's
    PNG with `etcpak` to match the original block format, reuse the original
    70-byte header verbatim, patch in the new payload size + mip count = 1.
  - Android uncompressed (GL_RGB / GL_RGBA): write fmt 6408 with a 70-byte
    header modelled on the in-game GL_RGBA texture (Pfx/Noise.bin). Note: the
    Samsung GLES driver rejects uncompressed RGBA at NPOT dimensions, so this
    path only really works for small, power-of-two replacements.

ETC encode requires both dimensions to be a multiple of 4 (4x4 blocks). PNG
inputs that aren't get padded transparently before encoding.
"""
import struct, os
from PIL import Image


# Format codes used by the Android edition (mirror tex_decode._ANDROID_FMTS).
_ANDROID_FMTS = {6407, 6408, 36196, 37492, 37494, 37496, 37497}


def _read_original_format(path):
    """Read the 4-byte format code from the original .bin header."""
    try:
        with open(path, 'rb') as f:
            data = f.read(80)
        bbr2_android = _parse_bbr2_android_header(data)
        if bbr2_android:
            return ('bbr2_android', bbr2_android)
        bbr2 = _parse_bbr2_header(data)
        if bbr2:
            return ('bbr2', bbr2)
        blitz = _parse_blitz_android_header(data)
        if blitz:
            return ('blitz_android', blitz)
        return struct.unpack_from('<16I', data, 1)[8]
    except Exception:
        return None

def _parse_bbr2_android_header(data):
    if len(data) < 42:
        return None
    try:
        prefix0, prefix1, prefix2, prefix3, kind, fmt, w, h, mips, payload_size = struct.unpack_from('<10I', data, 2)
    except struct.error:
        return None
    if (
        prefix0 in (0, 1) and prefix1 in (0, 1) and prefix2 in (0, 1) and prefix3 == 1
        and kind in (0, 2) and fmt in {1, 3, 5, 16, 35, 36}
        and 0 < w <= 4096 and 0 < h <= 4096
    ):
        return {
            'fmt': fmt, 'w': w, 'h': h, 'mips': max(1, mips),
            'payload_size': payload_size, 'kind': kind,
        }
    return None


def _parse_bbr2_header(data):
    if len(data) < 41:
        return None
    try:
        fmt = struct.unpack_from('<I', data, 20)[0] >> 8
        w = struct.unpack_from('<I', data, 24)[0] >> 8
        h = struct.unpack_from('<I', data, 28)[0] >> 8
        mips = struct.unpack_from('<I', data, 32)[0] >> 8
        payload_size = struct.unpack_from('<I', data, 36)[0] >> 8
    except struct.error:
        return None
    if fmt in {1, 3, 5, 17, 18, 19} and 0 < w <= 4096 and 0 < h <= 4096:
        return {'fmt': fmt, 'w': w, 'h': h, 'mips': max(1, mips), 'payload_size': payload_size}
    return None


def _parse_blitz_android_header(data):
    if len(data) < 65:
        return None
    try:
        w = struct.unpack_from('<I', data, 20)[0]
        h = struct.unpack_from('<I', data, 24)[0]
        mips = struct.unpack_from('<I', data, 28)[0]
        fmt = struct.unpack_from('<I', data, 32)[0]
        payload_size = struct.unpack_from('<I', data, 61)[0]
    except struct.error:
        return None
    if (
        fmt in {33776, 33777, 33778, 33779, 36196, 6407, 6408}
        and 0 < w <= 4096 and 0 < h <= 4096
        and 0 < max(1, mips) <= 16
        and 0 <= payload_size <= 128 * 1024 * 1024
    ):
        return {'fmt': fmt, 'w': w, 'h': h, 'mips': max(1, mips), 'payload_size': payload_size}
    return None


def _round_up_to_multiple(v, m):
    return ((v + m - 1) // m) * m


def _flip_and_pad_to_block(img, block=4):
    """Flip top-to-bottom (PNG -> OpenGL convention) and pad with transparent
    pixels so width and height are multiples of `block`. Returns the padded
    image plus its (orig_w, orig_h, padded_w, padded_h)."""
    flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    w, h = flipped.size
    pw = _round_up_to_multiple(w, block)
    ph = _round_up_to_multiple(h, block)
    if (pw, ph) == (w, h):
        return flipped, w, h, w, h
    # Pad on the right and bottom (image origin stays in upper-left for the
    # padded buffer, which is what etcpak expects).
    canvas = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    canvas.paste(flipped, (0, 0))
    return canvas, w, h, pw, ph


def _encode_one_mip(rgba_bytes, w, h, fmt):
    """Encode a single mip's RGBA pixel buffer with the right etcpak entrypoint."""
    import etcpak
    if fmt in (33776, 33777):                  # GL S3TC DXT1 / BC1
        return etcpak.compress_bc1(rgba_bytes, w, h)
    if fmt in (33778, 33779):                  # GL S3TC DXT3/DXT5; encode as BC3/DXT5
        return etcpak.compress_bc3(rgba_bytes, w, h)
    if fmt == 36196:                          # GL_ETC1_RGB8_OES
        return etcpak.compress_etc1_rgb(rgba_bytes, w, h)
    if fmt == 37492:                          # GL_COMPRESSED_RGB8_ETC2
        return etcpak.compress_etc2_rgb(rgba_bytes, w, h)
    if fmt in (37494, 37496, 37497):          # ETC2 with 1-bit / 8-bit alpha
        return etcpak.compress_etc2_rgba(rgba_bytes, w, h)
    raise ValueError(f'unsupported Android compressed format {fmt}')


def _build_mip_chain(img, mip_count, fmt):
    """Generate `mip_count` ETC mips from the user's PNG. Each mip halves the
    previous dimensions (floor, min 1). Each mip is flipped vertically (PNG ->
    OpenGL convention) and padded so its dimensions are multiples of 4 before
    being encoded. Returns the concatenated payload bytes."""
    base_w, base_h = img.size
    chunks = []
    for level in range(mip_count):
        mw = max(1, base_w >> level)
        mh = max(1, base_h >> level)
        # High-quality downscale for mips beyond level 0
        if level == 0:
            mip_img = img
        else:
            mip_img = img.resize((mw, mh), Image.Resampling.LANCZOS)
        # Flip top-to-bottom + pad to 4-block grid
        flipped = mip_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        pw = _round_up_to_multiple(mw, 4)
        ph = _round_up_to_multiple(mh, 4)
        if (pw, ph) == (mw, mh):
            padded = flipped
        else:
            padded = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
            padded.paste(flipped, (0, 0))
        chunks.append(_encode_one_mip(padded.tobytes(), pw, ph, fmt))
    return b''.join(chunks)


def _build_rgba_mip_chain(img, mip_count):
    chunks = []
    base_w, base_h = img.size
    for level in range(mip_count):
        mw = max(1, base_w >> level)
        mh = max(1, base_h >> level)
        mip_img = img if level == 0 else img.resize((mw, mh), Image.Resampling.LANCZOS)
        chunks.append(mip_img.convert('RGBA').tobytes())
    return b''.join(chunks)


def _build_rgb565_mip_chain(img, mip_count):
    chunks = []
    base_w, base_h = img.size
    for level in range(mip_count):
        mw = max(1, base_w >> level)
        mh = max(1, base_h >> level)
        mip_img = img if level == 0 else img.resize((mw, mh), Image.Resampling.LANCZOS)
        rgb = mip_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB')
        out = bytearray()
        for r, g, b in rgb.getdata():
            packed = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            out.extend(struct.pack('<H', packed))
        chunks.append(bytes(out))
    return b''.join(chunks)

def _build_bbr2_android_mip_chain(img, mip_count, fmt):
    base_w, base_h = img.size
    chunks = []
    for level in range(mip_count):
        mw = max(1, base_w >> level)
        mh = max(1, base_h >> level)
        mip_img = img if level == 0 else img.resize((mw, mh), Image.Resampling.LANCZOS)
        pw = _round_up_to_multiple(mw, 4)
        ph = _round_up_to_multiple(mh, 4)
        if (pw, ph) == (mw, mh):
            padded = mip_img
        else:
            padded = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
            padded.paste(mip_img, (0, 0))
        chunks.append(_encode_one_mip(padded.tobytes(), pw, ph, fmt))
    return b''.join(chunks)


def _encode_bbr2_uncompressed(img, original_bin_path, info):
    if not (original_bin_path and os.path.exists(original_bin_path)):
        raise FileNotFoundError('BBR2 texture encode needs the original .bin header')
    with open(original_bin_path, 'rb') as f:
        header = bytearray(f.read(41))
    if len(header) < 41:
        header.extend(b'\x00' * (41 - len(header)))

    w, h = img.size
    mip_count = max(1, int(info.get('mips') or 1))
    payload = _build_rgba_mip_chain(img, mip_count)

    def put_fixed(off, val):
        struct.pack_into('<I', header, off, int(val) << 8)

    put_fixed(20, 5)          # BBR2 raw RGBA
    put_fixed(24, w)
    put_fixed(28, h)
    put_fixed(32, mip_count)
    put_fixed(36, len(payload))
    return bytes(header) + payload

def _encode_bbr2_android(img, original_bin_path, info):
    if not (original_bin_path and os.path.exists(original_bin_path)):
        raise FileNotFoundError('BBR2 Android texture encode needs the original .bin header')
    with open(original_bin_path, 'rb') as f:
        header = bytearray(f.read(42))
    if len(header) < 42:
        header.extend(b'\x00' * (42 - len(header)))

    fmt = int(info['fmt'])
    w, h = img.size
    mip_count = max(1, int(info.get('mips') or 1))

    if fmt == 5:
        payload = _build_rgba_mip_chain(img, mip_count)
    elif fmt == 16:
        payload = _build_bbr2_android_mip_chain(img, mip_count, 37492)
    elif fmt == 35:
        payload = _build_bbr2_android_mip_chain(img, mip_count, 37494)
        fmt = 36
    elif fmt in (1, 3, 36):
        payload = _build_bbr2_android_mip_chain(img, mip_count, 37496)
        if fmt == 3:
            # Normal-map style textures are accepted as editable RGBA previews;
            # keep the original format code so the asset lookup stays stable.
            pass
    else:
        raise ValueError(f'unsupported BBR2 Android texture format {fmt}')

    def put_u32(off, val):
        struct.pack_into('<I', header, off, int(val))

    put_u32(22, fmt)
    put_u32(26, w)
    put_u32(30, h)
    put_u32(34, mip_count)
    put_u32(38, len(payload))
    return bytes(header) + payload


def _encode_blitz_android(img, original_bin_path, info):
    if not (original_bin_path and os.path.exists(original_bin_path)):
        raise FileNotFoundError('Blitz texture encode needs the original .bin header')
    with open(original_bin_path, 'rb') as f:
        header = bytearray(f.read(65))
    if len(header) < 65:
        header.extend(b'\x00' * (65 - len(header)))

    fmt = int(info['fmt'])
    mip_count = max(1, int(info.get('mips') or 1))
    w, h = img.size

    if fmt == 6407:
        payload = _build_rgb565_mip_chain(img, mip_count)
    elif fmt == 6408:
        payload = _build_rgba_mip_chain(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM), mip_count)
    elif fmt in (33776, 33777, 33778, 33779, 36196, 37492, 37494, 37496, 37497):
        payload = _build_mip_chain(img, mip_count, fmt)
        if fmt == 33778:
            # The encoder provides BC3/DXT5, which the engine already uses for
            # the shipped alpha textures.
            fmt = 33779
    else:
        raise ValueError(f'unsupported Blitz texture format {fmt}')

    def put_u32(off, val):
        struct.pack_into('<I', header, off, int(val))

    put_u32(20, w)
    put_u32(24, h)
    put_u32(28, mip_count)
    put_u32(32, fmt)
    put_u32(49, w)
    put_u32(53, h)
    put_u32(57, mip_count)
    put_u32(61, len(payload))
    return bytes(header) + payload


def _encode_android_compressed(img, fmt, original_bin_path):
    """Re-encode the PNG as the original .bin's compressed format with the
    original mip count. The 70-byte header is copied verbatim from the
    original so engine-derived fields stay consistent; only width, height,
    mip count, and trailing payload size are patched.

    The mip chain is critical: textures originally shipped with N mips need
    all N mips re-encoded, otherwise the GPU's mipmap sampler returns black
    for any LOD beyond mip 0 (this is what made replaced ETC1 ads invisible)."""
    if not (original_bin_path and os.path.exists(original_bin_path)):
        raise FileNotFoundError(
            'Android compressed re-encode needs the original .bin to copy the '
            'header from — re-extract the APF first.'
        )

    with open(original_bin_path, 'rb') as f:
        original_bytes = f.read()
    header = bytearray(original_bytes[:70])
    if len(header) < 70:
        header.extend(b'\x00' * (70 - len(header)))
    orig_mip_count = struct.unpack_from('<I', header, 1 + 7*4)[0] or 1

    # Generate the full mip chain matching the original's mip count.
    payload = _build_mip_chain(img, orig_mip_count, fmt)

    w, h = img.size

    def put_u32(off, val):
        struct.pack_into('<I', header, off, val)

    put_u32(1 + 5*4,  w)
    put_u32(1 + 6*4,  h)
    put_u32(1 + 7*4,  orig_mip_count)
    put_u32(66, len(payload))

    # ETC2-PA1 (37494) gets re-encoded as ETC2-EAC (37496) because etcpak
    # doesn't ship a PA1 encoder. Update the format byte so the engine decodes
    # accordingly.
    if fmt == 37494:
        put_u32(1 + 8*4, 37496)

    return bytes(header) + payload


def _encode_android_uncompressed(img):
    """Fallback for GL_RGB / GL_RGBA originals. Writes fmt 6408 (GL_RGBA) with
    a 70-byte header modelled on Pfx/Noise.bin. Note: the Samsung GLES driver
    chokes on this at NPOT dimensions — prefer the compressed path."""
    flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    w, h = flipped.size
    pixels = flipped.tobytes()
    needed = w * h * 4

    header = bytearray(70)
    header[0] = 0x01

    def put_u32(off, val):
        struct.pack_into('<I', header, off, val)

    put_u32(1,        0)
    put_u32(5,        0)
    put_u32(9,        1)
    put_u32(13,       1)
    put_u32(17,       0)
    put_u32(1 + 5*4,  w)
    put_u32(1 + 6*4,  h)
    put_u32(1 + 7*4,  1)
    put_u32(1 + 8*4,  6408)      # GL_RGBA
    put_u32(1 + 9*4,  5121)      # GL_UNSIGNED_BYTE
    put_u32(1 + 10*4, 256)
    put_u32(1 + 11*4, 256 * w)
    put_u32(1 + 12*4, 256 * w)
    put_u32(1 + 13*4, 1024)
    put_u32(1 + 14*4, 1024)
    put_u32(1 + 15*4, 256)
    header[65] = 0x00
    struct.pack_into('<I', header, 66, needed)

    return bytes(header) + pixels


def _encode_desktop(img, original_bin_path):
    """Desktop edition: DXGI_R8G8B8A8_UNORM (fmt 28) + 65-byte header."""
    img = img.convert('RGBA')
    w, h = img.size
    pixels = img.tobytes()
    needed = w * h * 4

    if original_bin_path and os.path.exists(original_bin_path):
        with open(original_bin_path, 'rb') as f:
            header = bytearray(f.read(65))
    else:
        header = bytearray(65)

    def put_u32(off, val):
        struct.pack_into('<I', header, off, val)

    put_u32(1 + 5*4,  w)
    put_u32(1 + 6*4,  h)
    put_u32(1 + 7*4,  1)
    put_u32(1 + 8*4,  28)
    put_u32(1 + 9*4,  1)
    put_u32(1 + 10*4, w)
    put_u32(1 + 11*4, h)
    put_u32(1 + 14*4, 1)
    put_u32(1 + 15*4, needed)

    return bytes(header) + pixels


def encode_png_as_texture(png_path, original_bin_path=None):
    """Pick the right encode path based on the original .bin's format code."""
    img = Image.open(png_path).convert('RGBA')
    fmt = _read_original_format(original_bin_path) if original_bin_path else None

    if isinstance(fmt, tuple) and fmt[0] == 'bbr2':
        return _encode_bbr2_uncompressed(img, original_bin_path, fmt[1])
    if isinstance(fmt, tuple) and fmt[0] == 'bbr2_android':
        return _encode_bbr2_android(img, original_bin_path, fmt[1])
    if isinstance(fmt, tuple) and fmt[0] == 'blitz_android':
        return _encode_blitz_android(img, original_bin_path, fmt[1])

    if fmt in (36196, 37492, 37494, 37496, 37497):
        return _encode_android_compressed(img, fmt, original_bin_path)
    if fmt in (6407, 6408):
        return _encode_android_uncompressed(img)
    return _encode_desktop(img, original_bin_path)
