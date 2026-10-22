"""Reader for cooked UE4.26 packages (.uasset + .uexp) with tagged properties."""
import struct

PKG_UNVERSIONED = 0x2000
PKG_FILTER_EDITOR_ONLY = 0x80000000


class R:
    def __init__(self, d, p=0):
        self.d = d
        self.p = p

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        if len(v) != n:
            raise EOFError('read past end at %d' % self.p)
        self.p += n
        return v

    def u8(self): return self.raw(1)[0]
    def i8(self): return struct.unpack('<b', self.raw(1))[0]
    def u16(self): return struct.unpack('<H', self.raw(2))[0]
    def i16(self): return struct.unpack('<h', self.raw(2))[0]
    def u32(self): return struct.unpack('<I', self.raw(4))[0]
    def i32(self): return struct.unpack('<i', self.raw(4))[0]
    def i64(self): return struct.unpack('<q', self.raw(8))[0]
    def u64(self): return struct.unpack('<Q', self.raw(8))[0]
    def f32(self): return struct.unpack('<f', self.raw(4))[0]

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ''
        if n > 0:
            return self.raw(n)[:-1].decode('utf-8', 'replace')
        return self.raw(-n * 2)[:-2].decode('utf-16-le', 'replace')


class Package:
    def __init__(self, uasset, uexp=b'', ubulk=b'', name=''):
        self.name = name
        self.ubulk = ubulk
        r = R(uasset)
        if r.u32() != 0x9E2A83C1:
            raise ValueError('bad package tag')
        legacy = r.i32()
        if legacy != -4:
            r.i32()
        self.ue4ver = r.i32()
        r.i32()
        for _ in range(r.i32()):
            r.raw(20)
        self.header_size = r.i32()
        r.fstring()
        self.flags = r.u32()
        name_count, name_off = r.i32(), r.i32()
        if not self.flags & PKG_FILTER_EDITOR_ONLY:
            r.fstring()
        r.i32(); r.i32()  # gatherable text
        export_count, export_off = r.i32(), r.i32()
        import_count, import_off = r.i32(), r.i32()
        if self.flags & PKG_UNVERSIONED:
            raise ValueError('unversioned properties not supported')

        r.p = name_off
        self.names = []
        for _ in range(name_count):
            self.names.append(r.fstring())
            r.u32()
        r.p = import_off
        self.imports = []
        for _ in range(import_count):
            cp, cn, outer, on = self.fname(r), self.fname(r), r.i32(), self.fname(r)
            self.imports.append({'class_package': cp, 'class': cn, 'outer': outer, 'name': on})
        r.p = export_off
        self.exports = []
        for _ in range(export_count):
            e = {'class': r.i32(), 'super': r.i32(), 'template': r.i32(), 'outer': r.i32(),
                 'name': self.fname(r), 'flags': r.u32(), 'size': r.i64(), 'offset': r.i64()}
            r.raw(4 * 3 + 16 + 4 + 4 * 2 + 4 * 5)
            self.exports.append(e)
        self.data = uasset + uexp

    def fname(self, r):
        i, n = r.i32(), r.i32()
        s = self.names[i]
        return s if n == 0 else '%s_%d' % (s, n - 1)

    def ref(self, idx):
        """Package index -> readable path."""
        if idx == 0:
            return None
        if idx < 0:
            imp = self.imports[-idx - 1]
            parts = [imp['name']]
            o = imp['outer']
            while o:
                imp2 = self.imports[-o - 1] if o < 0 else self.exports[o - 1]
                parts.append(imp2['name'])
                o = imp2['outer']
            path = parts[-1]
            if len(parts) > 1:
                path += '.' + parts[-2]
            if len(parts) > 2:
                path += ':' + '.'.join(reversed(parts[:-2]))
            return path
        e = self.exports[idx - 1]
        return '%s.%s' % (self.name, e['name'])

    def class_name(self, e):
        c = e['class']
        if c < 0:
            return self.imports[-c - 1]['name']
        if c > 0:
            return self.exports[c - 1]['name']
        return 'Class'

    def export_props(self, e):
        r = R(self.data, e['offset'])
        end = e['offset'] + e['size']
        props = read_props(self, r)
        return props, r.p, end

    def main_export(self):
        base = self.name.rsplit('/', 1)[-1]
        for e in self.exports:
            if e['name'] == base:
                return e
        return self.exports[0]


# ------------------------------------------------------------------ properties

NATIVE_STRUCTS = {
    'Vector': '<3f', 'Vector2D': '<2f', 'Rotator': '<3f', 'Quat': '<4f', 'LinearColor': '<4f',
    'Color': '<4B', 'IntPoint': '<2i', 'IntVector': '<3i', 'Vector4': '<4f', 'Box2D': None,
    'Guid': '<4I', 'DateTime': '<q', 'Timespan': '<q', 'FrameNumber': '<i',
}


def read_text(pkg, r):
    flags = r.u32()
    h = r.i8()
    if h == -1:
        if r.u32():
            return {'invariant': r.fstring()}
        return {'invariant': ''}
    if h == 0:
        return {'ns': r.fstring(), 'key': r.fstring(), 'src': r.fstring()}
    if h == 11:
        return {'table': pkg.fname(r), 'key': r.fstring()}
    raise ValueError('FText history %d in asset' % h)


def read_props(pkg, r, limit=None):
    out = {}
    while True:
        name = pkg.fname(r)
        if name == 'None':
            return out
        ptype = pkg.fname(r)
        size = r.i32()
        aidx = r.i32()
        extra = {}
        if ptype == 'StructProperty':
            extra['struct'] = pkg.fname(r)
            r.raw(16)
        elif ptype == 'BoolProperty':
            extra['bool'] = r.u8()
        elif ptype in ('ByteProperty', 'EnumProperty'):
            extra['enum'] = pkg.fname(r)
        elif ptype in ('ArrayProperty', 'SetProperty'):
            extra['inner'] = pkg.fname(r)
        elif ptype == 'MapProperty':
            extra['inner'] = pkg.fname(r)
            extra['value'] = pkg.fname(r)
        if r.u8():
            r.raw(16)
        start = r.p
        try:
            v = read_value(pkg, r, ptype, size, extra)
        except Exception as ex:  # keep going: unknown layouts are skipped by size
            v = {'_unparsed': ptype, '_err': str(ex)}
        r.p = start + size
        key = name if aidx == 0 else '%s[%d]' % (name, aidx)
        out[key] = v


def read_value(pkg, r, ptype, size, extra, in_container=False):
    if ptype == 'BoolProperty':
        return bool(extra['bool']) if not in_container else bool(r.u8())
    if ptype == 'IntProperty':
        return r.i32()
    if ptype == 'Int64Property':
        return r.i64()
    if ptype == 'UInt32Property':
        return r.u32()
    if ptype == 'Int8Property':
        return r.i8()
    if ptype == 'FloatProperty':
        return r.f32()
    if ptype == 'DoubleProperty':
        return struct.unpack('<d', r.raw(8))[0]
    if ptype in ('NameProperty',):
        return pkg.fname(r)
    if ptype == 'StrProperty':
        return r.fstring()
    if ptype == 'TextProperty':
        return read_text(pkg, r)
    if ptype in ('ObjectProperty', 'ClassProperty', 'WeakObjectProperty', 'InterfaceProperty'):
        i = r.i32()
        return {'ref': pkg.ref(i), 'idx': i}
    if ptype in ('SoftObjectProperty', 'SoftClassProperty'):
        return {'soft': pkg.fname(r), 'sub': r.fstring()}
    if ptype == 'ByteProperty':
        if in_container or extra.get('enum') in (None, 'None'):
            return r.u8() if size in (1, None) else pkg.fname(r)
        return pkg.fname(r)
    if ptype == 'EnumProperty':
        return pkg.fname(r)
    if ptype == 'StructProperty':
        return read_struct(pkg, r, extra['struct'])
    if ptype in ('ArrayProperty', 'SetProperty'):
        if ptype == 'SetProperty':
            r.i32()  # removed count
        n = r.i32()
        inner = extra['inner']
        if inner == 'StructProperty':
            # inner tag
            pkg.fname(r); pkg.fname(r); r.i32(); r.i32()
            sname = pkg.fname(r)
            r.raw(16)
            if r.u8():
                r.raw(16)
            return [read_struct(pkg, r, sname) for _ in range(n)]
        return [read_value(pkg, r, inner, None, {}, True) for _ in range(n)]
    if ptype == 'MapProperty':
        r.i32()
        n = r.i32()
        kt, vt = extra['inner'], extra['value']
        out = []
        for _ in range(n):
            k = read_value(pkg, r, kt, None, {'struct': None}, True) if kt != 'StructProperty' else read_props(pkg, r)
            v = read_value(pkg, r, vt, None, {'struct': None}, True) if vt != 'StructProperty' else read_props(pkg, r)
            out.append([k, v])
        return out
    raise ValueError('type %s' % ptype)


def read_struct(pkg, r, sname):
    if sname in NATIVE_STRUCTS and NATIVE_STRUCTS[sname]:
        fmt = NATIVE_STRUCTS[sname]
        return list(struct.unpack(fmt, r.raw(struct.calcsize(fmt))))
    if sname == 'GameplayTag':
        v = read_props(pkg, r)
        return v.get('TagName')
    if sname == 'GameplayTagContainer':
        return [pkg.fname(r) for _ in range(r.i32())]
    if sname in ('SoftObjectPath', 'SoftClassPath'):
        return {'soft': pkg.fname(r), 'sub': r.fstring()}
    return read_props(pkg, r)


def load(paks, path):
    """path like 'PenDriverPro/Content/X/Y' (without extension)."""
    ua = paks.read(path + '.uasset')
    ue = paks.read(path + '.uexp') if path + '.uexp' in paks else b''
    ub = paks.read(path + '.ubulk') if path + '.ubulk' in paks else b''
    game = '/' + path.replace('PenDriverPro/Content/', 'Game/').replace('Engine/Content/', 'Engine/')
    return Package(ua, ue, ub, game)


def game_to_pak(game_path):
    """'/Game/A/B.B' -> 'PenDriverPro/Content/A/B'"""
    p = game_path.split('.')[0]
    if p.startswith('/Game/'):
        return 'PenDriverPro/Content/' + p[6:]
    if p.startswith('/Engine/'):
        return 'Engine/Content/' + p[8:]
    return None


def read_string_table(pkg):
    """-> (namespace, {key: source text})"""
    e = pkg.main_export()
    r = R(pkg.data, e['offset'])
    read_props(pkg, r)
    if r.u32():
        r.raw(16)
    ns = r.fstring()
    out = {}
    for _ in range(r.i32()):
        k = r.fstring()
        out[k] = r.fstring()
    return ns, out


def read_datatable(pkg):
    """-> {row name: {props}}"""
    e = pkg.main_export()
    r = R(pkg.data, e['offset'])
    read_props(pkg, r)
    if r.u32():
        r.raw(16)
    rows = {}
    for _ in range(r.i32()):
        name = pkg.fname(r)
        rows[name] = read_props(pkg, r)
    return rows
