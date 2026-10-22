"""UE4 .locres reader (versions 0-3)."""
import struct

from uasset import R

MAGIC = bytes.fromhex('0E147475674A03FC4A15909DC3377F1B')


def read_locres(data):
    """-> {namespace: {key: text}}"""
    r = R(data)
    if data[:16] == MAGIC:
        r.p = 16
        ver = r.u8()
    else:
        ver = 0
    strings = None
    if ver >= 1:
        arr_off = r.i64()
        save = r.p
        r.p = arr_off
        strings = []
        for _ in range(r.i32()):
            strings.append(r.fstring())
            if ver >= 3:
                r.i32()
        r.p = save
    if ver >= 3:
        r.u32()  # entries count
    out = {}
    for _ in range(r.u32()):
        if ver >= 2:
            r.u32()
        ns = r.fstring()
        d = out.setdefault(ns, {})
        for _ in range(r.u32()):
            if ver >= 2:
                r.u32()
            key = r.fstring()
            r.u32()  # source hash
            if ver >= 1:
                d[key] = strings[r.i32()]
            else:
                d[key] = r.fstring()
    return out
