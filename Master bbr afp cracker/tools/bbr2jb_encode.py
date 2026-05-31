"""Encoder for the BBR2 little-endian binary JSON JSON form."""
import base64
import struct

from bbr2jb import fnv1a64


def _align4(buf):
    while len(buf) % 4:
        buf.append(0)


def _u32(v):
    return struct.pack('<I', v & 0xFFFFFFFF)


def _i32(v):
    return struct.pack('<i', int(v))


def _f32(v):
    return struct.pack('<f', float(v))


def _encode_value(node):
    if node is None:
        return _u32(0)

    if not isinstance(node, dict):
        if isinstance(node, bool):
            return _u32(3) + _u32(1 if node else 0)
        if isinstance(node, int):
            return _u32(1) + _i32(node)
        if isinstance(node, float):
            return _u32(2) + _f32(node)
        if isinstance(node, str):
            raw = node.encode('utf-8') + b'\x00'
            buf = bytearray(_u32(4) + _u32(((len(raw) + 3) // 4) * 4) + raw)
            _align4(buf)
            return bytes(buf)
        raise TypeError(f'unsupported BBR2 JSON value: {type(node).__name__}')

    t = node.get('__bbr2_type__')
    if t == 'int':
        return _u32(1) + _i32(node.get('value', 0))
    if t == 'float':
        return _u32(2) + _f32(node.get('value', 0.0))
    if t == 'bool':
        return _u32(3) + _u32(1 if node.get('value') else 0)
    if t == 'string':
        raw = str(node.get('value', '')).encode('utf-8') + b'\x00'
        buf = bytearray(_u32(4) + _u32(((len(raw) + 3) // 4) * 4) + raw)
        _align4(buf)
        return bytes(buf)
    if t == 'string_ref':
        return _u32(4) + _u32(int(node.get('value', 0)))
    if t == 'bytes':
        raw = base64.b64decode(node.get('base64', ''))
        buf = bytearray(_u32(8) + _u32(len(raw)) + raw)
        _align4(buf)
        return bytes(buf)
    if t == 'array':
        items = node.get('items', [])
        buf = bytearray(_u32(5) + _u32(len(items)) + b'\x00' * (4 * len(items)))
        starts = []
        for item in items:
            _align4(buf)
            starts.append(len(buf))
            buf.extend(_encode_value(item))
        for idx, start in enumerate(starts):
            struct.pack_into('<I', buf, 8 + idx * 4, start)
        return bytes(buf)
    if t == 'object':
        entries = node.get('entries', [])
        buf = bytearray(_u32(6) + _u32(len(entries)) + b'\x00' * (16 * len(entries)))
        child_starts = []
        for entry in entries:
            _align4(buf)
            child_starts.append(len(buf))
            buf.extend(_encode_value(entry.get('value')))
        for idx, entry in enumerate(entries):
            entry_off = 8 + idx * 16
            key = entry.get('key')
            h_text = entry.get('hash')
            if h_text:
                h = int(str(h_text).replace('0x', ''), 16)
            elif key and not str(key).startswith('#'):
                h = fnv1a64(str(key))
            else:
                raise ValueError(f'object entry {idx} needs hash or key')
            aux = int(entry.get('aux', 0))
            rel = child_starts[idx]
            struct.pack_into('<QII', buf, entry_off, h, aux, rel)
        return bytes(buf)

    raise TypeError(f'unsupported BBR2 node type: {t!r}')


def encode(root_json):
    if not root_json.get('__bbr2jb__'):
        raise ValueError('not a BBR2 binary JSON document')
    body = bytearray(_u32(int(root_json.get('version', 1))) + b'\x00\x00\x00\x00')
    body.extend(_encode_value(root_json.get('root')))
    struct.pack_into('<I', body, 4, len(body))
    return bytes(body)
