"""Pacific Drive (PenDriverPro, UE4) save file codec.

File layout (all little-endian):

  SAVC container
    0x00  char[4]  "SAVC"
    0x04  u32      container version (1)
    0x08  u8[8]    zero
    0x10  16 x section entry (24 bytes each):
            char[4] tag      ("OPTS", "META", "GAME", "CHKP", or zero = unused)
            u32     offset   absolute file offset of the payload
            u32     slot     bytes reserved for the section (next offset = offset + slot)
            u32     size     bytes actually used inside the slot
            u32     format   1 = JSON text, 2 = binary, 6 = binary + LZ4 block
            u32     rawsize  decompressed size (format 6 only, else 0)

  Binary payload ("Fig" serializer, PDFeature_Fig plugin)
    u32 6, u32 3          header (kept verbatim; JSON variant says "_version": 3)
    <type> <value>        root value, normally a dynamic struct

Type descriptors are a byte code, containers are followed by their element
descriptors (array: elem, map: key + value).  See TYPES below.
"""
import base64
import json
import struct

# ---------------------------------------------------------------- LZ4 block

def lz4_decompress(src, raw_size):
    dst = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]; i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]; i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = token & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        s = len(dst) - off
        if off >= ml:
            dst += dst[s:s + ml]
        else:
            for k in range(ml):
                dst.append(dst[s + k])
    if len(dst) != raw_size:
        raise ValueError('LZ4: got %d bytes, expected %d' % (len(dst), raw_size))
    return bytes(dst)


def lz4_compress(src):
    """Greedy LZ4 block compressor (valid stream, not size-optimal)."""
    n = len(src)
    out = bytearray()
    table = {}
    anchor = i = 0
    limit = n - 12  # last 5 bytes must be literals, last match starts >= 12 from end

    def emit(lit_start, lit_end, off, mlen):
        lit = lit_end - lit_start
        tok_l = 15 if lit >= 15 else lit
        if mlen is None:
            tok_m = 0
        else:
            tok_m = 15 if mlen - 4 >= 15 else mlen - 4
        out.append((tok_l << 4) | tok_m)
        if lit >= 15:
            r = lit - 15
            while r >= 255:
                out.append(255); r -= 255
            out.append(r)
        out.extend(src[lit_start:lit_end])
        if mlen is not None:
            out.append(off & 0xff); out.append(off >> 8)
            if mlen - 4 >= 15:
                r = mlen - 4 - 15
                while r >= 255:
                    out.append(255); r -= 255
                out.append(r)

    while i < limit:
        key = src[i:i + 4]
        cand = table.get(key)
        table[key] = i
        if cand is not None and i - cand <= 0xffff:
            m = 4
            mmax = n - 5 - i
            while m < mmax and src[cand + m] == src[i + m]:
                m += 1
            emit(anchor, i, i - cand, m)
            i += m
            anchor = i
        else:
            i += 1
    emit(anchor, n, 0, None)
    return bytes(out)

# ---------------------------------------------------------------- types

# code -> letter.  The exe holds the game's own table, indexed by code:
#   "-BIFSNXVRQZCLGTD:^$AM*>#E@~"  (UTF-16 string next to "_mk"/"_mv")
# Codes marked (unseen) never occur in the sample saves; their layout is
# inferred from the UE4 type they name.
TYPES = {
    0x01: 'B',   # bool, stored as u32
    0x02: 'I',   # int32
    0x03: 'F',   # float32
    0x04: 'S',   # FString
    0x05: 'N',   # FName (as FString)
    0x06: 'X',   # FText (UE native serialization, kept as base64)
    0x07: 'V',   # FVector: 3 x float32 (unseen)
    0x08: 'R',   # FRotator: 3 x float32 (pitch, yaw, roll)
    0x09: 'Q',   # FQuat: 4 x float32 (unseen)
    0x0A: 'Z',   # FTransform: quat xyzw, translation xyz, scale xyz (10 x float32)
    0x0B: 'C',   # FColor: 4 x u8, stored order b, g, r, a (unseen)
    0x0C: 'L',   # FLinearColor: 4 x float32 (r, g, b, a)
    0x0D: 'G',   # FGuid (16 bytes, shown as 32 hex like UE)
    0x0E: 'T',   # FGameplayTag (as FString)
    0x0F: 'D',   # FDateTime: int64 ticks (100 ns since 0001-01-01)
    0x10: ':',   # struct: u32 count, {FString name, type, value}
    0x11: '^',   # class path (FString)
    0x12: '$',   # object reference
    0x13: 'A',   # array<elem>
    0x14: 'M',   # map<key, value>: u32 n, u32 n, keys..., values...
    0x15: '*',   # dynamic struct (same encoding as ':')
    0x16: '>',   # object record {_class,_name,_outer,_data}
    0x17: '#',   # byte blob: u32 length + bytes (JPEG thumbnails), base64 in JSON
    0x18: 'E',   # int64
    0x19: '@',   # soft object path (FString)
    0x1A: '~',   # soft class path (FString)
}
LETTERS = {v: k for k, v in TYPES.items()}
STRUCTS = (0x10, 0x15, 0x16)
STRINGS = (0x04, 0x05, 0x0E, 0x11, 0x19, 0x1A)
FLOATVECS = {0x07: 3, 0x08: 3, 0x09: 4, 0x0C: 4}  # code -> number of float32 components


def type_to_str(t):
    s = TYPES.get(t[0], '<%02x>' % t[0])
    for sub in t[1:]:
        s += type_to_str(sub)
    return s


def str_to_type(s):
    def rd(i):
        if s[i] == '<':
            code = int(s[i + 1:i + 3], 16); i += 4
        else:
            code = LETTERS[s[i]]; i += 1
        if code == 0x13:
            e, i = rd(i); return (code, e), i
        if code == 0x14:
            k, i = rd(i); v, i = rd(i); return (code, k, v), i
        return (code,), i
    t, i = rd(0)
    if i != len(s):
        raise ValueError('bad type descriptor %r' % s)
    return t


def ticks_to_str(ticks):
    import datetime
    days, rem = divmod(ticks, 864000000000)
    d = datetime.date.fromordinal(days + 1)
    secs, frac = divmod(rem, 10000000)
    return '%04d.%02d.%02d-%02d.%02d.%02d.%07d' % (
        d.year, d.month, d.day, secs // 3600, secs // 60 % 60, secs % 60, frac)


def str_to_ticks(s):
    import datetime
    date, time = s.split('-')
    y, mo, d = (int(x) for x in date.split('.'))
    h, mi, se, frac = time.split('.')
    frac = int(frac.ljust(7, '0')[:7])
    days = datetime.date(y, mo, d).toordinal() - 1
    return ((days * 86400 + int(h) * 3600 + int(mi) * 60 + int(se)) * 10000000) + frac


def guid_str(b):
    return '%08X%08X%08X%08X' % struct.unpack('<4I', b)


def guid_bytes(s):
    return struct.pack('<4I', *(int(s[i:i + 8], 16) for i in range(0, 32, 8)))


class FormatError(Exception):
    pass

# ---------------------------------------------------------------- reader

class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def fail(self, msg):
        raise FormatError('%s at 0x%x' % (msg, self.p))

    def raw(self, n):
        if self.p + n > len(self.d):
            self.fail('unexpected end of data')
        v = self.d[self.p:self.p + n]; self.p += n
        return v

    def u8(self):
        return self.raw(1)[0]

    def i8(self):
        return struct.unpack('<b', self.raw(1))[0]

    def u32(self):
        return struct.unpack('<I', self.raw(4))[0]

    def i32(self):
        return struct.unpack('<i', self.raw(4))[0]

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ''
        if n > 0:
            b = self.raw(n)
            if b[-1] != 0:
                self.fail('FString not NUL-terminated')
            return b[:-1].decode('latin-1')
        b = self.raw(-n * 2)
        return b[:-2].decode('utf-16-le')

    def typ(self):
        code = self.u8()
        if code == 0x13:
            return (code, self.typ())
        if code == 0x14:
            return (code, self.typ(), self.typ())
        if code not in TYPES:
            self.p -= 1
            self.fail('unknown type code 0x%02x' % code)
        return (code,)

    # FText: skip over the UE serialization, return the raw bytes
    def text_raw(self):
        start = self.p
        self._text()
        return self.d[start:self.p]

    def _text(self):
        self.u32()                      # flags
        h = self.i8()                   # ETextHistoryType
        if h == -1:                     # None
            if self.u32():
                self.fstring()
        elif h == 0:                    # Base: namespace, key, source
            self.fstring(); self.fstring(); self.fstring()
        elif h == 1:                    # NamedFormat
            self._text()
            for _ in range(self.i32()):
                self.fstring(); self._fav()
        elif h == 2:                    # OrderedFormat
            self._text()
            for _ in range(self.i32()):
                self._fav()
        elif h == 3:                    # ArgumentFormat
            self._text()
            for _ in range(self.i32()):
                self.fstring(); self._fav()
        elif h in (4, 5, 6):            # AsNumber / AsPercent / AsCurrency
            if h == 6:
                self.fstring()
            self._fav()
            if self.u32():              # FNumberFormattingOptions
                self.raw(4 + 4 + 1 + 4 * 4)
            self.fstring()              # target culture
        elif h == 7:                    # AsDate
            self.raw(8); self.i8(); self.fstring(); self.fstring()
        elif h == 8:                    # AsTime
            self.raw(8); self.i8(); self.fstring(); self.fstring()
        elif h == 9:                    # AsDateTime
            self.raw(8); self.i8(); self.i8(); self.fstring(); self.fstring()
        elif h == 10:                   # Transform
            self._text(); self.u8()
        elif h == 11:                   # StringTableEntry
            self.fstring(); self.fstring()
        else:
            self.fail('unsupported FText history %d' % h)

    def _fav(self):
        k = self.i8()
        if k in (0, 1, 3):
            self.raw(8)
        elif k == 2:
            self.raw(4)
        elif k == 4:
            self._text()
        elif k == 5:
            self.raw(1)
        else:
            self.fail('unsupported FFormatArgumentValue type %d' % k)

    def ref(self):
        kind = self.u8()
        if kind == 0:
            return None
        cls = self.fstring()
        if kind == 1:
            return '@%s|%s' % (guid_str(self.raw(16)), cls)
        if kind == 2:
            return '$%s|%s' % (self.fstring(), cls)
        if kind == 3:
            return '*%s|%s' % (self.fstring(), cls)
        self.p -= 1
        self.fail('unknown object ref kind %d' % kind)

    def value(self, t):
        c = t[0]
        if c == 0x01:
            v = self.u32()
            return bool(v) if v in (0, 1) else v
        if c == 0x02:
            return self.i32()
        if c == 0x03:
            return struct.unpack('<f', self.raw(4))[0]
        if c == 0x18:
            return struct.unpack('<q', self.raw(8))[0]
        if c == 0x0D:
            return guid_str(self.raw(16))
        if c == 0x0B:
            return list(self.raw(4))
        if c == 0x0A:
            f = struct.unpack('<10f', self.raw(40))
            return {'rot': list(f[0:4]), 'loc': list(f[4:7]), 'scale': list(f[7:10])}
        if c in FLOATVECS:
            return list(struct.unpack('<%df' % FLOATVECS[c], self.raw(4 * FLOATVECS[c])))
        if c in STRINGS:
            return self.fstring()
        if c == 0x0F:
            return ticks_to_str(struct.unpack('<q', self.raw(8))[0])
        if c == 0x06:
            return base64.b64encode(self.text_raw()).decode()
        if c == 0x17:
            return base64.b64encode(self.raw(self.u32())).decode()
        if c == 0x12:
            return self.ref()
        if c in STRUCTS:
            out = {}
            for _ in range(self.u32()):
                name = self.fstring()
                ft = self.typ()
                out['%s|%s' % (name, type_to_str(ft))] = self.value(ft)
            return out
        if c == 0x13:
            return [self.value(t[1]) for _ in range(self.u32())]
        if c == 0x14:
            n1 = self.u32(); n2 = self.u32()
            if n1 != n2:
                self.fail('map counts differ (%d/%d)' % (n1, n2))
            ks = [self.value(t[1]) for _ in range(n1)]
            vs = [self.value(t[2]) for _ in range(n1)]
            return [[k, v] for k, v in zip(ks, vs)]
        self.fail('no decoder for type 0x%02x' % c)

# ---------------------------------------------------------------- writer

class Writer:
    def __init__(self):
        self.b = bytearray()

    def u8(self, v): self.b.append(v)
    def u32(self, v): self.b += struct.pack('<I', v)
    def i32(self, v): self.b += struct.pack('<i', v)

    def fstring(self, s):
        if s == '':
            self.i32(0)
        elif all(ord(ch) < 0x100 for ch in s):
            e = s.encode('latin-1') + b'\0'
            self.i32(len(e)); self.b += e
        else:
            e = s.encode('utf-16-le') + b'\0\0'
            self.i32(-(len(e) // 2)); self.b += e

    def typ(self, t):
        self.u8(t[0])
        for sub in t[1:]:
            self.typ(sub)

    def ref(self, v):
        if v is None:
            self.u8(0); return
        kind = {'@': 1, '$': 2, '*': 3}[v[0]]
        body, cls = v[1:].rsplit('|', 1)
        self.u8(kind)
        self.fstring(cls)
        if kind == 1:
            self.b += guid_bytes(body)
        else:
            self.fstring(body)

    def value(self, t, v):
        c = t[0]
        if c == 0x01:
            self.u32(int(v))
        elif c == 0x02:
            self.i32(v)
        elif c == 0x03:
            self.b += struct.pack('<f', v)
        elif c == 0x18:
            self.b += struct.pack('<q', v)
        elif c == 0x0D:
            self.b += guid_bytes(v)
        elif c == 0x0B:
            self.b += bytes(v)
        elif c == 0x0A:
            f = list(v['rot']) + list(v['loc']) + list(v['scale'])
            if len(f) != 10:
                raise FormatError('bad transform %r' % (v,))
            self.b += struct.pack('<10f', *f)
        elif c in FLOATVECS:
            if len(v) != FLOATVECS[c]:
                raise FormatError('expected %d floats, got %r' % (FLOATVECS[c], v))
            self.b += struct.pack('<%df' % FLOATVECS[c], *v)
        elif c in STRINGS:
            self.fstring(v)
        elif c == 0x0F:
            self.b += struct.pack('<q', str_to_ticks(v))
        elif c == 0x06:
            self.b += base64.b64decode(v)
        elif c == 0x17:
            blob = base64.b64decode(v)
            self.u32(len(blob)); self.b += blob
        elif c == 0x12:
            self.ref(v)
        elif c in STRUCTS:
            self.u32(len(v))
            for key, fv in v.items():
                name, ts = key.rsplit('|', 1)
                ft = str_to_type(ts)
                self.fstring(name)
                self.typ(ft)
                self.value(ft, fv)
        elif c == 0x13:
            self.u32(len(v))
            for e in v:
                self.value(t[1], e)
        elif c == 0x14:
            self.u32(len(v)); self.u32(len(v))
            for k, _ in v:
                self.value(t[1], k)
            for _, e in v:
                self.value(t[2], e)
        else:
            raise FormatError('no encoder for type 0x%02x' % c)

# ---------------------------------------------------------------- payload

def decode_payload(data):
    """Binary section payload -> JSON-able document."""
    r = Reader(data)
    header = [r.u32(), r.u32()]
    t = r.typ()
    root = r.value(t)
    if r.p != len(data):
        raise FormatError('%d trailing bytes after root value' % (len(data) - r.p))
    return {'header': header, 'type': type_to_str(t), 'root': root}


def encode_payload(doc):
    w = Writer()
    for h in doc['header']:
        w.u32(h)
    t = str_to_type(doc['type'])
    w.typ(t)
    w.value(t, doc['root'])
    return bytes(w.b)

# ---------------------------------------------------------------- container

FMT_JSON, FMT_BINARY, FMT_LZ4 = 1, 2, 6
HEADER_SIZE = 0x10 + 16 * 24


class Section:
    def __init__(self, tag, fmt, data, slot=None, packed=None):
        self.tag = tag        # str
        self.fmt = fmt        # FMT_*
        self.data = data      # decoded payload bytes (decompressed)
        self.slot = slot      # original reserved size (JSON saves pad to 4 KiB)
        self.packed = packed  # (data, stored bytes) as read, reused if unchanged

    def doc(self):
        if self.fmt == FMT_JSON:
            return json.loads(self.data.decode('utf-8'))
        if not self.data:
            return None
        return decode_payload(self.data)


class SaveFile:
    def __init__(self):
        self.version = 1
        self.sections = []

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls.parse(f.read())

    @classmethod
    def parse(cls, d):
        if d[:4] != b'SAVC':
            raise FormatError('not a SAVC file')
        sf = cls()
        sf.version = struct.unpack_from('<I', d, 4)[0]
        for i in range(16):
            tag, off, slot, size, fmt, raw = struct.unpack_from('<4sIIIII', d, 0x10 + i * 24)
            if tag == b'\0\0\0\0':
                continue
            stored = d[off:off + size]
            blob = lz4_decompress(stored, raw) if fmt == FMT_LZ4 and size else stored
            sf.sections.append(Section(tag.decode('ascii'), fmt, blob, slot, (blob, stored)))
        return sf

    def section(self, tag):
        for s in self.sections:
            if s.tag == tag:
                return s
        return None

    def build(self, compress=None):
        """Serialize. compress=None keeps each section's format, False stores
        binary sections uncompressed (format 2), True LZ4-compresses them."""
        if len(self.sections) > 16:
            raise FormatError('too many sections')
        table = bytearray()
        body = bytearray()
        off = HEADER_SIZE
        for s in self.sections:
            fmt, blob, raw = s.fmt, s.data, 0
            if blob and fmt in (FMT_BINARY, FMT_LZ4) and compress is not None:
                fmt = FMT_LZ4 if compress else FMT_BINARY
            if fmt == FMT_LZ4 and blob:
                raw = len(blob)
                if fmt == s.fmt and s.packed and s.packed[0] == blob:
                    blob = s.packed[1]
                else:
                    blob = lz4_compress(blob)
            slot = len(blob)
            if fmt == FMT_JSON:
                slot = max(s.slot or 0, (len(blob) + 4095) // 4096 * 4096)
            elif not blob and s.slot:
                slot = s.slot
            table += struct.pack('<4sIIIII', s.tag.encode('ascii'), off, slot, len(blob), fmt, raw)
            body += blob + b'\0' * (slot - len(blob))
            off += slot
        # unused entries point at the end of the data, like the game does
        while len(table) < 16 * 24:
            table += struct.pack('<4sIIIII', b'\0\0\0\0', off, 0, 0, 0, 0)
        return b'SAVC' + struct.pack('<I', self.version) + b'\0' * 8 + bytes(table) + bytes(body)
