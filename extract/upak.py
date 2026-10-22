"""Minimal reader for UE4 .pak files, version 11 (UE 4.26/4.27), unencrypted, Zlib/none."""
import hashlib
import io
import os
import struct
import zlib

PAK_MAGIC = 0x5A6F12E1


class Buf:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        if len(v) != n:
            raise EOFError('pak index truncated')
        self.p += n
        return v

    def u8(self): return self.raw(1)[0]
    def u32(self): return struct.unpack('<I', self.raw(4))[0]
    def i32(self): return struct.unpack('<i', self.raw(4))[0]
    def u64(self): return struct.unpack('<Q', self.raw(8))[0]
    def i64(self): return struct.unpack('<q', self.raw(8))[0]

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ''
        if n > 0:
            return self.raw(n)[:-1].decode('latin-1')
        return self.raw(-n * 2)[:-2].decode('utf-16-le')


class Entry:
    __slots__ = ('path', 'offset', 'size', 'usize', 'method', 'blocks', 'encrypted', 'block_size')


class PakFile:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        size = os.path.getsize(path)
        self.f.seek(size - 512)
        tail = self.f.read(512)
        i = tail.rfind(struct.pack('<I', PAK_MAGIC))
        if i < 0:
            raise ValueError('not a pak: %s' % path)
        if tail[i - 1]:
            raise ValueError('encrypted pak index is not supported')
        ver, idx_off, idx_size = struct.unpack_from('<IQQ', tail, i + 4)
        if ver < 10:
            raise ValueError('pak version %d not supported' % ver)
        self.version = ver
        self.methods = [None] + [tail[i + 44 + k * 32:i + 76 + k * 32].split(b'\0')[0].decode() for k in range(5)]
        self.f.seek(idx_off)
        idx = Buf(self.f.read(idx_size))
        self.mount = idx.fstring()
        count = idx.i32()
        idx.u64()  # path hash seed
        if idx.u32():
            idx.raw(8 + 8 + 20)
        if not idx.u32():
            raise ValueError('pak has no full directory index')
        fdi_off, fdi_size = idx.i64(), idx.i64()
        idx.raw(20)
        enc_size = idx.i32()
        self.encoded = idx.raw(enc_size)
        n_plain = idx.i32()
        self.plain = []
        for _ in range(n_plain):
            self.plain.append(self._read_full_entry(idx))
        self.f.seek(fdi_off)
        fdi = Buf(self.f.read(fdi_size))
        self.entries = {}
        mount = self.mount.replace('../../../', '')
        for _ in range(fdi.i32()):
            d = fdi.fstring()
            for _ in range(fdi.i32()):
                name = fdi.fstring()
                loc = fdi.i32()
                if loc == -0x80000000 or loc == 0x7fffffff:
                    continue
                e = self._decode(loc)
                e.path = (mount + d + name).lstrip('/')
                self.entries[e.path] = e
        assert len(self.entries) <= count

    def _read_full_entry(self, b):
        e = Entry()
        e.offset, e.size, e.usize = b.i64(), b.i64(), b.i64()
        e.method = b.u32()
        b.raw(20)
        e.blocks = []
        if e.method:
            for _ in range(b.u32()):
                s, t = b.i64(), b.i64()
                e.blocks.append((s, t))
        e.encrypted = bool(b.u8() & 1)
        e.block_size = b.u32()
        return e

    def _decode(self, loc):
        if loc < 0:
            return self.plain[-loc - 1]
        b = Buf(self.encoded, loc)
        v = b.u32()
        e = Entry()
        bs = v & 0x3f
        e.block_size = b.u32() if bs == 0x3f else bs << 11
        nblocks = (v >> 6) & 0xffff
        e.encrypted = bool(v & (1 << 22))
        e.method = (v >> 23) & 0x3f
        e.offset = b.u32() if v & (1 << 31) else b.u64()
        e.usize = b.u32() if v & (1 << 30) else b.u64()
        e.size = (b.u32() if v & (1 << 29) else b.u64()) if e.method else e.usize
        # size of the FPakEntry header stored in front of the data
        hdr = 8 + 8 + 8 + 4 + 20 + 1 + 4 + ((4 + 16 * nblocks) if e.method else 0)
        e.blocks = []
        if e.method:
            start = hdr
            if nblocks == 1 and not e.encrypted:
                e.blocks.append((start, start + e.size))
            else:
                for _ in range(nblocks):
                    n = b.u32()
                    e.blocks.append((start, start + n))
                    start += (n + 15) & ~15 if e.encrypted else n
        else:
            e.blocks = None
        return e

    def read(self, path):
        e = self.entries[path]
        if e.encrypted:
            raise ValueError('encrypted entry %s' % path)
        if not e.method:
            hdr = 8 + 8 + 8 + 4 + 20 + 1 + 4
            self.f.seek(e.offset + hdr)
            return self.f.read(e.usize)
        name = self.methods[e.method]
        out = bytearray()
        for s, t in e.blocks:
            self.f.seek(e.offset + s)
            chunk = self.f.read(t - s)
            if name == 'Zlib':
                out += zlib.decompress(chunk)
            else:
                raise ValueError('compression %s not supported' % name)
        return bytes(out[:e.usize])


class PakSet:
    """All paks of a game; later chunks override earlier ones."""

    def __init__(self, paks_dir):
        self.paks = []
        self.index = {}
        for fn in sorted(os.listdir(paks_dir)):
            if fn.endswith('.pak'):
                p = PakFile(os.path.join(paks_dir, fn))
                self.paks.append(p)
                for path in p.entries:
                    self.index[path] = p

    def __contains__(self, path):
        return path in self.index

    def read(self, path):
        return self.index[path].read(path)

    def list(self, prefix='', suffix=''):
        return [p for p in self.index if p.startswith(prefix) and p.endswith(suffix)]
