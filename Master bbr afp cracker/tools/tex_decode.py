"""Vector Unit texture blob -> PIL Image.

Supports both the desktop (BBR Windows / Steam) BC1/BC3 formats and the
Android (BBR mobile) GL ES texture formats: ETC1, ETC2, ETC2 + EAC alpha,
ETC2 with 1-bit punchthrough alpha, and the uncompressed GL_RGB / GL_RGBA.
"""
import struct
import io
import numpy as np
import texture2ddecoder as td
from PIL import Image

# Compressed-block decoders. Desktop uses DXGI codes (small ints); Android
# uses OpenGL ES `internalformat` constants. They never collide so a single
# map works for both editions. Each entry's first item names the byte
# layout the decoder returns ('bgra' for desktop BCx, 'rgba' for ETC*).
COMPRESSED = {
    # Desktop / DXGI
    71: ('bgra', td.decode_bc1),
    72: ('bgra', td.decode_bc1),
    77: ('bgra', td.decode_bc3),
    78: ('bgra', td.decode_bc3),
    80: ('bgra', td.decode_bc4),
    83: ('bgra', td.decode_bc5),
    # Android / GL ES — texture2ddecoder returns BGRA byte order for these
    # too (same convention as its BCx decoders).
    36196: ('bgra', td.decode_etc1),                         # GL_ETC1_RGB8_OES
    37492: ('bgra', td.decode_etc2),                         # GL_COMPRESSED_RGB8_ETC2
    37494: ('bgra', td.decode_etc2a1),                       # GL_COMPRESSED_RGB8_PUNCHTHROUGH_ALPHA1_ETC2
    37496: ('bgra', td.decode_etc2a8),                       # GL_COMPRESSED_RGBA8_ETC2_EAC
    37497: ('bgra', td.decode_etc2a8),                       # GL_COMPRESSED_SRGB8_ALPHA8_ETC2_EAC
    # Older Blitz Android packs use OpenGL extension constants directly.
    33776: ('bgra', td.decode_bc1),                           # GL_COMPRESSED_RGB_S3TC_DXT1_EXT
    33777: ('bgra', td.decode_bc1),                           # GL_COMPRESSED_RGBA_S3TC_DXT1_EXT
    33778: ('bgra', td.decode_bc3),                           # GL_COMPRESSED_RGBA_S3TC_DXT3_EXT
    33779: ('bgra', td.decode_bc3),                           # GL_COMPRESSED_RGBA_S3TC_DXT5_EXT
}

# Format-code ranges. Desktop = small DXGI ints; Android = GL ES `internalformat`
# constants (all >= 6000). The two never collide, so the format code itself is
# enough to pick the right header size: desktop is 65 bytes, Android is 70.
_ANDROID_FMTS = {6407, 6408, 36196, 37492, 37494, 37496, 37497}

def _payload_offset(fmt: int) -> int:
    return 70 if fmt in _ANDROID_FMTS else 65

def parse_header(data):
    bbr2_android = _parse_bbr2_android_header(data)
    if bbr2_android:
        return bbr2_android
    bbr2 = _parse_bbr2_header(data)
    if bbr2:
        return bbr2
    blitz = _parse_blitz_android_header(data)
    if blitz:
        return blitz
    fields = struct.unpack_from('<16I', data, 1)
    return {'w': fields[5], 'h': fields[6], 'fmt': fields[8], 'mips': fields[9]}

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
        (fmt in COMPRESSED or fmt in {28, 51, 6407, 6408})
        and 0 < w <= 4096 and 0 < h <= 4096
        and 0 < max(1, mips) <= 16
        and 0 <= payload_size <= len(data) - 65
    ):
        return {
            'w': w, 'h': h, 'fmt': fmt, 'mips': max(1, mips),
            'blitz_android': True, 'payload_size': payload_size,
        }
    return None

def _parse_bbr2_android_header(data):
    if len(data) < 42:
        return None
    if data[26:28] == b'\xff\xd8':
        return {'w': 0, 'h': 0, 'fmt': 'jpeg', 'mips': 1, 'bbr2_android_jpeg': True, 'payload_size': len(data) - 26}
    try:
        prefix0, prefix1, prefix2, prefix3, kind, fmt, w, h, mips, payload_size = struct.unpack_from('<10I', data, 2)
    except struct.error:
        return None
    if (
        prefix0 in (0, 1) and prefix1 in (0, 1) and prefix2 in (0, 1) and prefix3 == 1
        and kind in (0, 2) and fmt in {1, 3, 5, 16, 35, 36}
        and 0 < w <= 4096 and 0 < h <= 4096
        and 0 < payload_size <= len(data) - 42
    ):
        return {
            'w': w, 'h': h, 'fmt': fmt, 'mips': mips,
            'bbr2_android': True, 'payload_size': payload_size,
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
    if fmt in {1, 3, 5, 17, 18, 19} and 0 < w <= 4096 and 0 < h <= 4096 and payload_size <= len(data) - 41:
        return {'w': w, 'h': h, 'fmt': fmt, 'mips': mips, 'bbr2': True, 'payload_size': payload_size}
    return None

def decode_texture(data):
    hdr = parse_header(data)
    fmt, w, h = hdr['fmt'], hdr['w'], hdr['h']
    if hdr.get('bbr2_android_jpeg'):
        return _decode_bbr2_android_texture(data, hdr)
    if w == 0 or h == 0 or w > 4096 or h > 4096:
        return None, hdr, f'weird dims {w}x{h}'
    if hdr.get('bbr2'):
        return _decode_bbr2_texture(data, hdr)
    if hdr.get('bbr2_android') or hdr.get('bbr2_android_jpeg'):
        return _decode_bbr2_android_texture(data, hdr)
    if hdr.get('blitz_android'):
        return _decode_blitz_android_texture(data, hdr)

    is_android = fmt in _ANDROID_FMTS
    payload = data[_payload_offset(fmt):]

    img = None

    # ---- Uncompressed pixel formats -------------------------------------
    if fmt == 28:  # DXGI_R8G8B8A8_UNORM (desktop)
        img = Image.frombytes('RGBA', (w, h), payload[:w*h*4], 'raw', 'RGBA')

    elif fmt == 6408:  # GL_RGBA — Android uncompressed 32-bit
        img = Image.frombytes('RGBA', (w, h), payload[:w*h*4], 'raw', 'RGBA')

    elif fmt == 6407:  # GL_RGB — Android uncompressed 24-bit
        img = Image.frombytes('RGB', (w, h), payload[:w*h*3], 'raw', 'RGB').convert('RGBA')

    elif fmt == 51:  # DXGI_R16_FLOAT (height / bump map)
        arr = np.frombuffer(payload[:w*h*2], dtype=np.float16).astype(np.float32)
        arr = np.nan_to_num(arr.reshape(h, w), nan=0.0, posinf=1.0, neginf=-1.0)
        lo, hi = float(arr.min()), float(arr.max())
        if hi > lo: arr = (arr - lo) / (hi - lo)
        else: arr = np.zeros_like(arr)
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), mode='L')

    # ---- Compressed block formats --------------------------------------
    else:
        entry = COMPRESSED.get(fmt)
        if not entry:
            return None, hdr, f'unsupported fmt {fmt}'
        raw_layout, dec = entry
        try:
            decoded = dec(payload, w, h)
        except Exception as e:
            return None, hdr, f'decode err: {e}'
        raw_mode = 'BGRA' if raw_layout == 'bgra' else 'RGBA'
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', raw_mode)

    # OpenGL textures are stored bottom-up (origin lower-left). PNG / desktop
    # users expect top-down (origin upper-left), so flip every Android image
    # before returning.
    if is_android and img is not None:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return img, hdr, None

def _decode_blitz_android_texture(data, hdr):
    fmt, w, h = hdr['fmt'], hdr['w'], hdr['h']
    payload = data[65:65 + hdr.get('payload_size', len(data) - 65)]

    if fmt == 28:
        img = Image.frombytes('RGBA', (w, h), payload[:w*h*4], 'raw', 'RGBA')
    elif fmt == 6408:
        img = Image.frombytes('RGBA', (w, h), payload[:w*h*4], 'raw', 'RGBA')
    elif fmt == 6407:
        need_rgb = w * h * 3
        need_565 = w * h * 2
        if len(payload) >= need_rgb:
            img = Image.frombytes('RGB', (w, h), payload[:need_rgb], 'raw', 'RGB').convert('RGBA')
        elif len(payload) >= need_565:
            pix = np.frombuffer(payload[:need_565], dtype='<u2').astype(np.uint32)
            r = ((pix >> 11) & 0x1F) * 255 // 31
            g = ((pix >> 5) & 0x3F) * 255 // 63
            b = (pix & 0x1F) * 255 // 31
            rgba = np.stack([r, g, b, np.full_like(r, 255)], axis=1).astype(np.uint8)
            img = Image.fromarray(rgba.reshape((h, w, 4)), mode='RGBA')
        else:
            return None, hdr, f'truncated RGB payload {len(payload)}'
    else:
        entry = COMPRESSED.get(fmt)
        if not entry:
            return None, hdr, f'unsupported Blitz texture fmt {fmt}'
        raw_layout, dec = entry
        try:
            decoded = dec(payload, w, h)
        except Exception as e:
            return None, hdr, f'decode err: {e}'
        raw_mode = 'BGRA' if raw_layout == 'bgra' else 'RGBA'
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', raw_mode)

    return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM), hdr, None

def _decode_bbr2_texture(data, hdr):
    fmt, w, h = hdr['fmt'], hdr['w'], hdr['h']
    payload = data[41:41 + hdr.get('payload_size', len(data) - 41)]
    img = None

    if fmt == 5:
        need = w * h * 4
        if len(payload) < need:
            return None, hdr, f'truncated RGBA payload {len(payload)} < {need}'
        img = Image.frombytes('RGBA', (w, h), payload[:need], 'raw', 'RGBA')
    elif fmt in (17, 18):
        decoded = td.decode_bc1(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    elif fmt in (1, 19):
        decoded = td.decode_bc3(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    elif fmt == 3:
        # BBR2 normal maps carry two BC5-style mip chains. The first plane is
        # the useful editable normal preview; the second appears auxiliary.
        first_plane = payload[:len(payload) // 2]
        decoded = td.decode_bc5(first_plane, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    else:
        return None, hdr, f'unsupported BBR2 texture fmt {fmt}'

    return img, hdr, None

def _decode_bbr2_android_texture(data, hdr):
    if hdr.get('bbr2_android_jpeg'):
        try:
            img = Image.open(io.BytesIO(data[26:])).convert('RGBA')
            hdr['w'], hdr['h'] = img.size
            return img, hdr, None
        except Exception as e:
            return None, hdr, f'jpeg decode err: {e}'

    fmt, w, h = hdr['fmt'], hdr['w'], hdr['h']
    payload = data[42:42 + hdr.get('payload_size', len(data) - 42)]

    if fmt == 5:
        need = w * h * 4
        if len(payload) < need:
            return None, hdr, f'truncated RGBA payload {len(payload)} < {need}'
        img = Image.frombytes('RGBA', (w, h), payload[:need], 'raw', 'RGBA')
    elif fmt in (16,):
        decoded = td.decode_etc2(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    elif fmt == 35:
        decoded = td.decode_etc2a1(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    elif fmt in (1, 36):
        decoded = td.decode_etc2a8(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    elif fmt == 3:
        decoded = td.decode_etc2a8(payload, w, h)
        img = Image.frombytes('RGBA', (w, h), decoded, 'raw', 'BGRA')
    else:
        return None, hdr, f'unsupported BBR2 Android texture fmt {fmt}'

    return img, hdr, None
