"""High level helpers on top of pdsave: paths, search, typed edits, currencies, items."""
import copy
import json
import os
import random
import re
import shutil
import time
import uuid

import pdsave

# ---------------------------------------------------------------- documents

class Save:
    """A loaded save: SaveFile plus decoded documents of its binary sections."""

    def __init__(self, path):
        self.path = path
        self.file = pdsave.SaveFile.load(path)
        self.docs = {}
        for s in self.file.sections:
            if s.data and s.fmt in (pdsave.FMT_BINARY, pdsave.FMT_LZ4):
                self.docs[s.tag] = pdsave.decode_payload(s.data)
            elif s.data and s.fmt == pdsave.FMT_JSON:
                self.docs[s.tag] = None  # legacy text save, not editable here
        if not any(self.docs.values()):
            raise pdsave.FormatError('no binary sections to edit (legacy JSON save?)')

    def root(self, tag='GAME'):
        return self.docs[tag]['root']

    def save(self, path=None, backup=True, compress=None):
        path = path or self.path
        for s in self.file.sections:
            doc = self.docs.get(s.tag)
            if doc:
                s.data = pdsave.encode_payload(doc)
        out = self.file.build(compress=compress)
        # verify before touching the disk
        check = pdsave.SaveFile.parse(out)
        for s in check.sections:
            if self.docs.get(s.tag):
                pdsave.decode_payload(s.data)
        bak = None
        if backup and os.path.exists(path):
            bak = '%s.bak-%s' % (path, time.strftime('%Y%m%d-%H%M%S'))
            shutil.copy2(path, bak)
        tmp = path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(out)
        os.replace(tmp, path)
        return bak

# ---------------------------------------------------------------- keys / paths

def split_key(k):
    """'Name|TYPE' -> ('Name', 'TYPE')"""
    name, _, t = k.rpartition('|')
    return name, t


def is_map(t):
    return t.startswith('M')


def children(value, t):
    """Yield (step, display, value, type) for a container value."""
    if isinstance(value, dict) and (t is None or t[0] in ':*>'):
        for k, v in value.items():
            name, ft = split_key(k)
            yield name, k, v, ft
    elif t and t[0] == 'A':
        et = elem_types(t)[0]
        for i, v in enumerate(value):
            yield str(i), '[%d]' % i, v, et
    elif t and t[0] == 'M':
        kt, vt = elem_types(t)
        for i, (k, v) in enumerate(value):
            yield str(k), '{%s}' % (k,), v, vt


def elem_types(t):
    """Return the sub-descriptors of an 'A..' or 'M..' type string."""
    def rd(i):
        c = t[i]
        if c == '<':
            j = i + 4
        else:
            j = i + 1
        if c == 'A':
            _, j = rd(j)
        elif c == 'M':
            _, j = rd(j)
            _, j = rd(j)
        return t[i:j], j
    if t[0] == 'A':
        e, _ = rd(1)
        return (e,)
    k, j = rd(1)
    v, _ = rd(j)
    return (k, v)


def resolve(save, path):
    """Path like 'GAME/managers/_objects/<GUID>/_data/CurrencyTable'.
    Struct steps match the field name (type suffix optional), array steps are
    indices, map steps are the key text (or #index).  Returns
    (parent, key_or_index, value, type)."""
    parts = [p for p in path.split('/') if p]
    tag = parts.pop(0)
    doc = save.docs[tag]
    parent, key, value, t = doc, 'root', doc['root'], doc['type']
    for step in parts:
        found = False
        if t[0] in ':*>':
            for k in value:
                name, ft = split_key(k)
                if step == k or step == name:
                    parent, key, value, t = value, k, value[k], ft
                    found = True
                    break
        elif t[0] == 'A':
            i = int(step)
            parent, key, value, t = value, i, value[i], elem_types(t)[0]
            found = True
        elif t[0] == 'M':
            vt = elem_types(t)[1]
            if step.startswith('#'):
                i = int(step[1:])
                found = True
            else:
                for i, (k, _) in enumerate(value):
                    if str(k) == step:
                        found = True
                        break
            if found:
                parent, key, value, t = value[i], 1, value[i][1], vt
        if not found:
            raise KeyError('path step %r not found' % step)
    return parent, key, value, t


def parse_scalar(t, text):
    c = t[0]
    if c == 'B':
        low = text.strip().lower()
        if low in ('1', 'true', 'yes', 'on'):
            return True
        if low in ('0', 'false', 'no', 'off'):
            return False
        raise ValueError('expected true/false, got %r' % text)
    if c in 'IE':
        v = int(text, 0)
        lim = 31 if c == 'I' else 63
        if not -(1 << lim) <= v < (1 << lim):
            raise ValueError('value out of range for %s' % c)
        return v
    if c == 'F':
        return float(text)
    if c == '$':
        return None if text.strip() in ('', 'null', 'None') else text
    if c in 'SNT^@~':
        return text
    if c == 'D':
        pdsave.str_to_ticks(text)
        return text
    if c == 'G':
        if not re.fullmatch(r'[0-9A-Fa-f]{32}', text):
            raise ValueError('expected 32 hex digits')
        return text.upper()
    return json.loads(text)


def set_value(save, path, text):
    parent, key, value, t = resolve(save, path)
    if isinstance(value, (dict, list)) and t[0] not in 'VRQZCL':
        raise ValueError('%s is a container (%s); edit its children' % (path, t))
    new = parse_scalar(t, text)
    parent[key] = new
    return value, new, t

# ---------------------------------------------------------------- search

def walk(value, t, path, label=''):
    """Yield (path, value, type, label); label is the field name or map key text."""
    yield path, value, t, label
    if isinstance(value, (dict, list)) and t and t[0] in ':*>AM':
        for i, (step, _disp, v, ft) in enumerate(children(value, t)):
            label = step
            if t[0] == 'M':
                # map keys are often asset paths containing '/', address by index
                step = '#%d' % i
            yield from walk(v, ft, path + '/' + step, label)


def find(save, pattern, keys=True, values=True, limit=200):
    rx = re.compile(pattern, re.I)
    out = []
    for tag, doc in save.docs.items():
        if not doc:
            continue
        for path, v, t, label in walk(doc['root'], doc['type'], tag):
            hit = keys and rx.search(label)
            if not hit and values and not isinstance(v, (dict, list)) and v is not None:
                hit = rx.search(str(v))
            if hit:
                out.append((path, t, v))
                if len(out) >= limit:
                    return out
    return out

# ---------------------------------------------------------------- game specific

def object_tables(save):
    """All '_objects' dicts in GAME (managers + garage scene + ...)."""
    tables = []

    def rec(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k.startswith('_objects|'):
                    tables.append(x)
                elif isinstance(x, (dict, list)):
                    rec(x)
    rec(save.root('GAME'))
    return tables


def find_object(save, guid):
    guid = guid.upper()
    for tbl in object_tables(save):
        k = guid + '|>'
        if k in tbl:
            return tbl, tbl[k]
    raise KeyError('object %s not found' % guid)


def objects_of_class(save, suffix):
    for tbl in object_tables(save):
        for k, o in tbl.items():
            if isinstance(o, dict) and o.get('_class|^', '').endswith(suffix):
                yield k.split('|')[0], o


def ref_guid(ref):
    return ref[1:33] if ref and ref.startswith('@') else None


def short_asset(ref):
    """'*/Game/.../IA_X.IA_X|/Script/...' -> 'IA_X'"""
    if not ref:
        return str(ref)
    body = ref[1:].split('|')[0]
    return body.rsplit('.', 1)[-1].rsplit(':', 1)[-1]


def inventory_manager(save):
    for guid, o in objects_of_class(save, 'BP_InventoryManager_C'):
        return o['_data|*']
    raise KeyError('BP_InventoryManager not found')


def currencies(save):
    return inventory_manager(save)['CurrencyTable|M$E']


def resources(save):
    for guid, o in objects_of_class(save, 'BP_ResourceManager_C'):
        return o['_data|*']['CurrentValues|MNF']
    return []


def containers(save):
    """Named inventories of BP_InventoryManager -> list of (name, guid)."""
    inv = inventory_manager(save)
    out = []
    for k, v in inv.items():
        name, t = split_key(k)
        if t == '$' and ref_guid(v):
            out.append((name, ref_guid(v)))
        elif t == 'MT$':
            for tag, r in v:
                if ref_guid(r):
                    out.append(('%s[%s]' % (name, tag), ref_guid(r)))
    return out


def container_slots(save, guid):
    _, cont = find_object(save, guid)
    for r in cont.get('_data|*', {}).get('Slots|A$', []):
        g = ref_guid(r)
        if not g:
            continue
        _, slot = find_object(save, g)
        d = slot.get('_data|*', {})
        items = d.get('Items|A$', [])
        arche = None
        if items:
            _, it = find_object(save, ref_guid(items[0]))
            arche = it.get('_data|*', {}).get('Archetype|$')
        yield g, slot, items, arche or d.get('FilterItemType|$')


def _unique_names(tbl_list, prefix, count):
    used = set()
    lowest = 2147483647
    for tbl in tbl_list:
        for o in tbl.values():
            n = o.get('_name|N', '') if isinstance(o, dict) else ''
            if n.startswith(prefix + '_'):
                used.add(n)
                tail = n[len(prefix) + 1:]
                if tail.isdigit():
                    lowest = min(lowest, int(tail))
    out = []
    n = lowest - 1
    while len(out) < count:
        name = '%s_%d' % (prefix, n)
        if name not in used:
            out.append(name)
        n -= 1
    return out


def _new_guid(taken):
    while True:
        g = uuid.uuid4().hex.upper()
        if g not in taken:
            taken.add(g)
            return g


def add_items(save, slot_guid, count, force=False):
    """Clone the last item of a slot `count` times (with its sub-objects)."""
    tbl, slot = find_object(save, slot_guid)
    data = slot.setdefault('_data|*', {})
    items = data.get('Items|A$')
    if not items:
        raise ValueError('slot is empty: need one item to use as a template')
    cap = data.get('Capacity|I')
    if cap is not None and len(items) + count > cap and not force:
        raise ValueError('slot capacity %d would be exceeded (%d + %d); use force'
                         % (cap, len(items), count))
    tmpl_guid = ref_guid(items[-1])
    tmpl_tbl, tmpl = find_object(save, tmpl_guid)

    # collect the template's sub-object tree (objects whose _outer chain leads to it)
    tables = object_tables(save)
    by_outer = {}
    for t in tables:
        for k, o in t.items():
            og = ref_guid(o.get('_outer|$')) if isinstance(o, dict) else None
            if og:
                by_outer.setdefault(og, []).append((t, k.split('|')[0]))
    subtree = []
    stack = [tmpl_guid]
    while stack:
        g = stack.pop()
        for t, cg in by_outer.get(g, []):
            o = t[cg + '|>']
            cls = o.get('_class|^', '')
            if cls.endswith('ItemContainer') or cls.endswith('ItemSlot'):
                raise ValueError('template item owns an inventory (%s); cloning refused' % cls)
            subtree.append((t, cg))
            stack.append(cg)

    taken = set()
    for t in tables:
        taken.update(k.split('|')[0] for k in t)
    prefix = tmpl['_name|N'].rsplit('_', 1)[0]
    names = _unique_names(tables, prefix, count)
    added = []
    for i in range(count):
        remap = {tmpl_guid: _new_guid(taken)}
        for _, cg in subtree:
            remap[cg] = _new_guid(taken)
        blob = json.dumps([tmpl] + [t[cg + '|>'] for t, cg in subtree])
        for old, new in remap.items():
            blob = blob.replace(old, new)
        objs = json.loads(blob)
        objs[0]['_name|N'] = names[i]
        tmpl_tbl[remap[tmpl_guid] + '|>'] = objs[0]
        for (t, cg), o in zip(subtree, objs[1:]):
            t[remap[cg] + '|>'] = o
        items.append('@%s|%s' % (remap[tmpl_guid], items[-1].split('|', 1)[1]))
        added.append(remap[tmpl_guid])
    return added
