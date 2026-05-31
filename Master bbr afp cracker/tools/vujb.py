"""VUJB (Vector Unit JSON Binary) parser."""
import struct, base64

class _R:
    def __init__(self, data):
        self.d = data; self.p = 0
    def u32(self):
        v = struct.unpack_from('>I', self.d, self.p)[0]; self.p += 4; return v
    def f32(self):
        v = struct.unpack_from('>f', self.d, self.p)[0]; self.p += 4; return v
    def s(self, n):
        v = self.d[self.p:self.p+n]; self.p += n; return v
    def rem(self):
        return len(self.d) - self.p

def _read(r):
    if r.rem() < 4: return {'__trunc__': True}
    t = r.u32()
    if t == 0: return None                        # null / no value
    if t == 1: return struct.unpack('>i', r.s(4))[0]
    if t == 2: return r.f32()
    if t == 3: return bool(r.s(1)[0])
    if t == 4:
        n = r.u32()
        if n > r.rem(): return {'__bad_strlen__': n}
        return r.s(n).decode('utf-8', 'replace')
    if t == 5:
        n = r.u32()
        if n > 100000: return {'__bad_arrlen__': n}
        return [_read(r) for _ in range(n)]
    if t == 6:
        n = r.u32()
        if n > 100000: return {'__bad_objlen__': n}
        obj = {}
        for _ in range(n):
            kl = r.u32()
            if kl > r.rem() or kl > 1000:
                obj['__obj_partial__'] = True; return obj
            k = r.s(kl).decode('utf-8', 'replace')
            obj[k] = _read(r)
        return obj
    if t == 8:
        # Raw byte buffer: 4-byte count + N bytes. Preserved in JSON as base64
        # under a special key so the encoder can re-emit it losslessly.
        n = r.u32()
        if n > r.rem(): return {'__bad_t8_len__': n}
        return {'__vujb_t8__': base64.b64encode(r.s(n)).decode('ascii')}
    return {'__UNKNOWN_TYPE__': t, '__pos__': r.p - 4}

def parse_vujb(data):
    if data[4:8] != b'VUJB': raise ValueError('not VUJB')
    (ver,) = struct.unpack_from('>I', data, 8)
    # The outer size field (little-endian u32 at offset 0) covers [VUJB magic +
    # version + tree]. Any bytes past that are asset-level metadata (e.g. the
    # "IceA_Race\0" name suffix on project files). We stop the VUJB tree
    # reader at the declared size so trailer bytes don't leak into the tree,
    # then preserve them in the root so round-tripping is byte-exact.
    outer_size = struct.unpack_from('<I', data, 0)[0]
    tree_end = outer_size + 4   # +4 for the size field itself
    r = _R(data[12:tree_end])
    root = _read(r)
    trailer = data[tree_end:]
    if trailer and isinstance(root, dict):
        root['__vujb_trailer__'] = base64.b64encode(trailer).decode('ascii')
    return {'version': ver, 'root': root, 'consumed': r.p, 'remaining': r.rem()}
