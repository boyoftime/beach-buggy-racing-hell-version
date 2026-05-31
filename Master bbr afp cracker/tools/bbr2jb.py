"""BBR2 little-endian binary JSON parser.

BBR2 moved away from the older VUJB magic wrapper. Assets are still a compact
typed tree, but start with:

  u32 version_or_tag, u32 total_size, <root value at offset 8>

Objects store FNV-1a 64-bit hashes for field names. We recover readable field
names when the matching string appears elsewhere in the same asset.
"""
import base64
import struct


def fnv1a64(text):
    h = 0xCBF29CE484222325
    for b in text.encode('utf-8'):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _cstring_candidates(data):
    out = {}
    for part in data.split(b'\x00'):
        if not part or len(part) > 240:
            continue
        try:
            text = part.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if not text or any(ord(c) < 32 for c in text):
            continue
        out.setdefault(fnv1a64(text), text)
    return out


class _Reader:
    def __init__(self, data):
        self.data = data
        self.names = _cstring_candidates(data)
        self.seen = set()

    def u32(self, off):
        return struct.unpack_from('<I', self.data, off)[0]

    def i32(self, off):
        return struct.unpack_from('<i', self.data, off)[0]

    def f32(self, off):
        return struct.unpack_from('<f', self.data, off)[0]

    def parse(self, off):
        if off < 0 or off + 4 > len(self.data):
            return {'__bbr2_type__': 'bad_offset', 'offset': off}
        if off in self.seen:
            return {'__bbr2_type__': 'ref_loop', 'offset': off}

        t = self.u32(off)
        if t == 0:
            return None
        if t == 1:
            return {'__bbr2_type__': 'int', 'value': self.i32(off + 4)}
        if t == 2:
            return {'__bbr2_type__': 'float', 'value': self.f32(off + 4)}
        if t == 3:
            return {'__bbr2_type__': 'bool', 'value': bool(self.u32(off + 4))}
        if t == 4:
            n = self.u32(off + 4)
            raw = self.data[off + 8:off + 8 + n]
            if n > len(self.data) - off - 8 or b'\x00' not in raw:
                return {'__bbr2_type__': 'string_ref', 'value': n}
            text = raw.split(b'\x00', 1)[0].decode('utf-8', 'replace')
            if any(ord(c) < 32 for c in text):
                return {'__bbr2_type__': 'string_ref', 'value': n}
            return {'__bbr2_type__': 'string', 'value': text}
        if t == 5:
            self.seen.add(off)
            count = self.u32(off + 4)
            values = []
            base = off
            table = off + 8
            for i in range(count):
                rel = self.u32(table + i * 4)
                values.append(self.parse(base + rel))
            self.seen.remove(off)
            return {'__bbr2_type__': 'array', 'items': values}
        if t == 6:
            self.seen.add(off)
            count = self.u32(off + 4)
            entries = []
            table = off + 8
            for i in range(count):
                entry_off = table + i * 16
                h = struct.unpack_from('<Q', self.data, entry_off)[0]
                aux = self.u32(entry_off + 8)
                rel = self.u32(entry_off + 12)
                key = self.names.get(h)
                entries.append({
                    'key': key or f'#{h:016x}',
                    'hash': f'{h:016x}',
                    'aux': aux,
                    'value': self.parse(off + rel),
                })
            self.seen.remove(off)
            return {'__bbr2_type__': 'object', 'entries': entries}
        if t == 8:
            n = self.u32(off + 4)
            raw = self.data[off + 8:off + 8 + n]
            return {
                '__bbr2_type__': 'bytes',
                'base64': base64.b64encode(raw).decode('ascii'),
            }
        return {'__bbr2_type__': 'unknown', 'type': t, 'offset': off}


def looks_like_bbr2jb(data):
    if len(data) < 12:
        return False
    version, size, root_type = struct.unpack_from('<III', data, 0)
    return version == 1 and size == len(data) and root_type in (0, 1, 2, 3, 4, 5, 6, 8)


def parse_bbr2jb(data):
    if not looks_like_bbr2jb(data):
        raise ValueError('not BBR2 binary JSON')
    version, size = struct.unpack_from('<II', data, 0)
    return {
        '__bbr2jb__': True,
        'version': version,
        'size': size,
        'root': _Reader(data).parse(8),
    }
