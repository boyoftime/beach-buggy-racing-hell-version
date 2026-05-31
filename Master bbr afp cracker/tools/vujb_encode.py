"""JSON -> VUJB binary encoder."""
import struct, io, base64

TYPE_NULL, TYPE_INT, TYPE_FLOAT, TYPE_BOOL, TYPE_STR, TYPE_ARR, TYPE_OBJ, TYPE_BYTES = 0, 1, 2, 3, 4, 5, 6, 8

def _write_value(buf, v):
    if v is None:
        buf.write(struct.pack('>I', TYPE_NULL))
        return
    if isinstance(v, bool):
        buf.write(struct.pack('>I', TYPE_BOOL))
        buf.write(bytes([1 if v else 0]))
    elif isinstance(v, int):
        buf.write(struct.pack('>I', TYPE_INT))
        buf.write(struct.pack('>i', v))
    elif isinstance(v, float):
        buf.write(struct.pack('>I', TYPE_FLOAT))
        buf.write(struct.pack('>f', v))
    elif isinstance(v, str):
        enc = v.encode('utf-8')
        buf.write(struct.pack('>II', TYPE_STR, len(enc)))
        buf.write(enc)
    elif isinstance(v, list):
        buf.write(struct.pack('>II', TYPE_ARR, len(v)))
        for item in v:
            _write_value(buf, item)
    elif isinstance(v, dict):
        # Raw byte-buffer sentinel — re-emit as type 8.
        if len(v) == 1 and '__vujb_t8__' in v:
            raw = base64.b64decode(v['__vujb_t8__'])
            buf.write(struct.pack('>II', TYPE_BYTES, len(raw)))
            buf.write(raw)
            return
        clean = {k: val for k, val in v.items() if not str(k).startswith('__')}
        buf.write(struct.pack('>II', TYPE_OBJ, len(clean)))
        for k, val in clean.items():
            ke = str(k).encode('utf-8')
            buf.write(struct.pack('>I', len(ke)))
            buf.write(ke)
            _write_value(buf, val)
    else:
        raise TypeError(f'unsupported JSON value type: {type(v).__name__}')

def encode(root, version=1):
    trailer_b64 = None
    if isinstance(root, dict):
        trailer_b64 = root.get('__vujb_trailer__')
    body = io.BytesIO()
    body.write(struct.pack('>I', version))
    _write_value(body, root)
    payload = body.getvalue()
    out = io.BytesIO()
    out.write(struct.pack('<I', 4 + len(payload)))
    out.write(b'VUJB')
    out.write(payload)
    if trailer_b64:
        out.write(base64.b64decode(trailer_b64))
    return out.getvalue()
