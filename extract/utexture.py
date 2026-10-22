"""Decode cooked UE4.26 Texture2D mips to Pillow images (DXT1/5, BC4/5/7, BGRA8, G8)."""
import io
import struct

from PIL import DdsImagePlugin, Image

from uasset import R, read_props

BULK_AT_END = 0x1
BULK_UNUSED = 0x20
BULK_INLINE = 0x40
BULK_SEPARATE = 0x100
BULK_64 = 0x2000


def _dds(fmt, w, h, data):
    """Wrap raw block data in a DDS header Pillow understands."""
    fourcc = {'PF_DXT1': b'DXT1', 'PF_DXT3': b'DXT3', 'PF_DXT5': b'DXT5',
              'PF_BC4': b'ATI1', 'PF_BC5': b'ATI2'}.get(fmt)
    hdr = bytearray(128)
    hdr[0:4] = b'DDS '
    struct.pack_into('<7I', hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(data), 0, 1)
    struct.pack_into('<2I', hdr, 76, 32, 0x4)
    ext = b''
    if fourcc:
        hdr[84:88] = fourcc
    else:  # BC7 via DX10 header
        hdr[84:88] = b'DX10'
        ext = struct.pack('<5I', 98, 3, 0, 1, 0)  # DXGI_FORMAT_BC7_UNORM
    struct.pack_into('<I', hdr, 108, 0x1000)
    return DdsImagePlugin.DdsImageFile(io.BytesIO(bytes(hdr) + ext + data))


def decode(fmt, w, h, data):
    if fmt in ('PF_DXT1', 'PF_DXT3', 'PF_DXT5', 'PF_BC4', 'PF_BC5', 'PF_BC7'):
        bw, bh = (w + 3) // 4 * 4, (h + 3) // 4 * 4
        img = _dds(fmt, bw, bh, data)
        img.load()
        img = img.crop((0, 0, w, h))
        if fmt == 'PF_BC5':
            img = img.convert('RGB')
        return img.convert('RGBA')
    if fmt == 'PF_B8G8R8A8':
        return Image.frombytes('RGBA', (w, h), data[:w * h * 4], 'raw', 'BGRA')
    if fmt == 'PF_G8':
        return Image.frombytes('L', (w, h), data[:w * h]).convert('RGBA')
    if fmt == 'PF_FloatRGBA':
        import array
        raise ValueError('float textures not supported')
    raise ValueError('pixel format %s not supported' % fmt)


def load_texture(pkg, max_size=256):
    """Return a Pillow image of the best mip <= max_size (or the smallest available)."""
    e = pkg.main_export()
    r = R(pkg.data, e['offset'])
    read_props(pkg, r)
    if r.u32():           # UObject: has object guid
        r.raw(16)
    r.raw(2)              # UTexture strip flags
    r.raw(2)              # UTexture2D strip flags
    if not r.u32():
        raise ValueError('texture is not cooked')
    fmt_name = pkg.fname(r)
    r.i64()               # skip offset
    sx, sy = r.i32(), r.i32()
    r.u32()               # packed data (slices / flags)
    fmt = r.fstring()
    r.i32()               # first mip to serialize
    mips = []
    for _ in range(r.i32()):
        r.u32()           # mip bCooked
        flags = r.u32()
        if flags & BULK_64:
            count, disk = r.i64(), r.i64()
        else:
            count, disk = r.i32(), r.i32()
        off = r.i64()
        data = None
        if not flags & BULK_UNUSED:
            if flags & BULK_SEPARATE:
                data = ('ubulk', off, disk)
            elif flags & BULK_AT_END:
                data = ('end', off, disk)
            else:
                data = pkg.data[r.p:r.p + disk]
                r.p += disk
        w, h, _d = r.i32(), r.i32(), r.i32()
        mips.append((w, h, data))
    # pick
    usable = [m for m in mips if m[2] is not None]
    if not usable:
        raise ValueError('no mip data')
    best = None
    for m in usable:
        if max(m[0], m[1]) <= max_size:
            best = m
            break
    best = best or usable[-1]
    w, h, data = best
    if isinstance(data, tuple):
        kind, off, size = data
        if kind == 'ubulk':
            data = pkg.ubulk[off:off + size]
        else:
            data = pkg.data[off:off + size]
    img = decode(fmt, w, h, data)
    if max(w, h) > max_size:
        img.thumbnail((max_size, max_size))
    return img
