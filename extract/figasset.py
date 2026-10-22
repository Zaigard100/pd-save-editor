"""Decode Fig blobs embedded in cooked assets (FNames are package name-map indices there)."""
import re
import struct
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pdsave  # noqa: E402

HEADER = b'\x06\x00\x00\x00\x03\x00\x00\x00'


class AssetReader(pdsave.Reader):
    def __init__(self, data, pos, pkg):
        super().__init__(data, pos)
        self.pkg = pkg

    def fname(self):
        i, n = struct.unpack('<ii', self.raw(8))
        s = self.pkg.names[i]
        return s if n == 0 else '%s_%d' % (s, n - 1)

    def value(self, t):
        if t[0] == 0x0E:
            return self.fname()
        return super().value(t)

    def _text(self):
        start = self.p
        self.u32()
        h = self.i8()
        if h == 11:
            self.raw(8)
            self.fstring()
            return
        self.p = start
        super()._text()


def decode_defaults(pkg, tail):
    """Find and decode the Fig defaults blob in an archetype's native tail."""
    for m in re.finditer(re.escape(HEADER), tail):
        r = AssetReader(tail, m.start() + 8, pkg)
        out = {}
        try:
            if r.typ() != (0x15,):
                continue
            for _ in range(r.u32()):
                name = r.fstring()
                ft = r.typ()
                out['%s|%s' % (name, pdsave.type_to_str(ft))] = r.value(ft)
        except (pdsave.FormatError, IndexError, UnicodeDecodeError, struct.error):
            pass
        if out.get('_data|*') is not None:
            return out
    return None
