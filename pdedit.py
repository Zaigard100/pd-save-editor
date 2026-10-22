#!/usr/bin/env python3
"""Pacific Drive save editor (command line).

  pdedit.py info      SAVE
  pdedit.py export    SAVE OUT.json            full lossless dump
  pdedit.py import    IN.json SAVE             write SAVE from a dump (backup kept)
  pdedit.py find      SAVE REGEX               search field names / map keys / values
  pdedit.py get       SAVE PATH
  pdedit.py set       SAVE PATH VALUE
  pdedit.py currency  SAVE [NAME=VALUE ...]    e.g. MechXP=500000 AnchorJuice_Stable=999
  pdedit.py resource  SAVE [NAME=VALUE ...]    e.g. Fuel=75 CarHealth=795
  pdedit.py inventory SAVE [CONTAINER]         list containers / slots of one container
  pdedit.py additems  SAVE SLOT_GUID COUNT     clone the slot's item COUNT times

Every write keeps a timestamped SAVE.bak-* copy unless --no-backup is given.
"""
import argparse
import json
import sys

import pdsave
import pdtools


def cmd_info(a):
    s = pdtools.Save(a.save)
    print('file:', a.save)
    for sec in s.file.sections:
        print('  section %-4s format=%d size=%d' % (sec.tag, sec.fmt, len(sec.data)))
    if s.docs.get('META'):
        m = s.root('META').get('_data|:', {})
        for k in ('LastPlayed|D', 'Playtime|I', 'Level|S', 'RunCount|I', 'MilesDriven|F',
                  'ActiveMission|$', 'BuildHistory|AS'):
            if k in m:
                v = m[k]
                print('  %-14s %s' % (k.split('|')[0], pdtools.short_asset(v) if k.endswith('$') else v))
    if s.docs.get('OPTS'):
        o = s.root('OPTS')['_objects|*']
        for obj in o.values():
            d = obj.get('_data|*', {})
            print('  preset         %s' % d.get('ActiveGamePresetName|S'))
    if s.docs.get('GAME'):
        print('currencies:')
        for k, v in pdtools.currencies(s):
            print('  %-24s %d' % (pdtools.short_asset(k).replace('CA_', ''), v))
        print('resources:')
        for k, v in pdtools.resources(s):
            print('  %-24s %g' % (k, v))


def cmd_export(a):
    s = pdsave.SaveFile.load(a.save)
    out = {'version': s.version, 'sections': []}
    for sec in s.sections:
        out['sections'].append({'tag': sec.tag, 'format': sec.fmt, 'slot': sec.slot,
                                'doc': sec.doc() if sec.data else None})
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print('written', a.out)


def cmd_import(a):
    with open(a.json, encoding='utf-8') as f:
        src = json.load(f)
    sf = pdsave.SaveFile()
    sf.version = src['version']
    for e in src['sections']:
        doc = e['doc']
        if doc is None:
            data = b''
        elif e['format'] == pdsave.FMT_JSON:
            data = json.dumps(doc, indent='\t').encode()
        else:
            data = pdsave.encode_payload(doc)
        sf.sections.append(pdsave.Section(e['tag'], e['format'], data, e.get('slot')))
    out = sf.build(compress=False if a.no_compress else None)
    pdsave.SaveFile.parse(out)
    import os, shutil, time
    if os.path.exists(a.save) and not a.no_backup:
        bak = '%s.bak-%s' % (a.save, time.strftime('%Y%m%d-%H%M%S'))
        shutil.copy2(a.save, bak)
        print('backup', bak)
    with open(a.save, 'wb') as f:
        f.write(out)
    print('written', a.save)


def cmd_find(a):
    s = pdtools.Save(a.save)
    for path, t, v in pdtools.find(s, a.regex, limit=a.limit):
        shown = '<%d items>' % len(v) if isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False)
        print('%s  [%s]  %s' % (path, t, shown[:160]))


def cmd_get(a):
    s = pdtools.Save(a.save)
    _, _, v, t = pdtools.resolve(s, a.path)
    print('type:', t)
    print(json.dumps(v, indent=1, ensure_ascii=False)[:a.limit])


def _write(s, a):
    if a.dry_run:
        print('(dry run, nothing written)')
        return
    bak = s.save(backup=not a.no_backup, compress=False if a.no_compress else None)
    if bak:
        print('backup', bak)
    print('written', s.path)


def cmd_set(a):
    s = pdtools.Save(a.save)
    old, new, t = pdtools.set_value(s, a.path, a.value)
    print('%s [%s]: %r -> %r' % (a.path, t, old, new))
    _write(s, a)


def _assign_named(table, assigns, label, conv, keyname):
    changed = False
    for asg in assigns:
        name, _, val = asg.partition('=')
        hits = [e for e in table if name.lower() == keyname(e[0]).lower()]
        if not hits:
            hits = [e for e in table if name.lower() in keyname(e[0]).lower()]
        if len(hits) != 1:
            raise SystemExit('%s %r matches %d entries: %s' % (
                label, name, len(hits), ', '.join(keyname(e[0]) for e in table)))
        print('%s: %s -> %s' % (keyname(hits[0][0]), hits[0][1], val))
        hits[0][1] = conv(val)
        changed = True
    return changed


def cmd_currency(a):
    s = pdtools.Save(a.save)
    table = pdtools.currencies(s)
    keyname = lambda k: pdtools.short_asset(k).replace('CA_', '')
    if not a.assign:
        for k, v in table:
            print('%-24s %d' % (keyname(k), v))
        return
    _assign_named(table, a.assign, 'currency', int, keyname)
    _write(s, a)


def cmd_resource(a):
    s = pdtools.Save(a.save)
    table = pdtools.resources(s)
    if not a.assign:
        for k, v in table:
            print('%-24s %g' % (k, v))
        return
    _assign_named(table, a.assign, 'resource', float, str)
    _write(s, a)


def cmd_inventory(a):
    s = pdtools.Save(a.save)
    conts = pdtools.containers(s)
    if not a.container:
        for name, g in conts:
            _, c = pdtools.find_object(s, g)
            n = len(c.get('_data|*', {}).get('Slots|A$', []))
            print('%-50s %s  slots=%d' % (name, g, n))
        return
    match = [(n, g) for n, g in conts if a.container.lower() in n.lower() or a.container.upper() == g]
    if not match:
        raise SystemExit('no container matches %r' % a.container)
    for name, g in match:
        print('==', name, g)
        for sg, slot, items, arche in pdtools.container_slots(s, g):
            if items or a.all:
                cap = slot.get('_data|*', {}).get('Capacity|I')
                print('  slot %s  %3d/%-4s %s' % (sg, len(items), cap, pdtools.short_asset(arche)))


def cmd_additems(a):
    s = pdtools.Save(a.save)
    added = pdtools.add_items(s, a.slot, a.count, force=a.force)
    print('added %d items' % len(added))
    _write(s, a)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def add(name, fn, *args, write=False):
        sp = sub.add_parser(name)
        for arg in args:
            sp.add_argument(*arg[0], **arg[1])
        if write:
            sp.add_argument('--no-backup', action='store_true')
            sp.add_argument('--no-compress', action='store_true', help='store GAME uncompressed')
            sp.add_argument('--dry-run', action='store_true')
        sp.set_defaults(fn=fn)

    A = lambda *n, **kw: (n, kw)
    add('info', cmd_info, A('save'))
    add('export', cmd_export, A('save'), A('out'))
    add('import', cmd_import, A('json'), A('save'), A('--no-backup', action='store_true'),
        A('--no-compress', action='store_true'))
    add('find', cmd_find, A('save'), A('regex'), A('--limit', type=int, default=200))
    add('get', cmd_get, A('save'), A('path'), A('--limit', type=int, default=20000))
    add('set', cmd_set, A('save'), A('path'), A('value'), write=True)
    add('currency', cmd_currency, A('save'), A('assign', nargs='*'), write=True)
    add('resource', cmd_resource, A('save'), A('assign', nargs='*'), write=True)
    add('inventory', cmd_inventory, A('save'), A('container', nargs='?'), A('--all', action='store_true'))
    add('additems', cmd_additems, A('save'), A('slot'), A('count', type=int),
        A('--force', action='store_true'), write=True)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except (pdsave.FormatError, KeyError, ValueError) as e:
        raise SystemExit('error: %s' % e)


if __name__ == '__main__':
    main()
