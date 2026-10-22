#!/usr/bin/env python3
"""Extract what the editor needs from the game's .pak files into ../gamedata/.

  python3 build_gamedata.py "/path/to/Pacific Drive"

Produces items.json (names in every game language, sizes, stacks, icons),
containers.json, presets.json, settings.json, strings.json, icons/*.png, fonts/*.
"""
import json
import os
import re
import sys

import uasset
import ulocres
import figasset
import upak
import utexture

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'gamedata')
log = print
DATA_VERSION = 4  # bump when the layout of gamedata/ changes
LANGS = ['en-US', 'ru', 'uk', 'de', 'fr', 'es', 'it', 'pl', 'pt-BR', 'tr', 'ja', 'ko', 'zh-CN', 'zh-TW']
LANG_KEY = {'en-US': 'en'}


def lk(lang):
    return LANG_KEY.get(lang, lang)


class Loc:
    def __init__(self, paks):
        self.paks = paks
        self.locres = {}
        for lang in LANGS:
            p = 'PenDriverPro/Content/Localization/Game/%s/Game.locres' % lang
            self.locres[lk(lang)] = ulocres.read_locres(paks.read(p)) if p in paks else {}
        self.tables = {}

    def table(self, table_id):
        """'/Game/StringTables/ST_X.ST_X' -> (namespace, {key: source})"""
        if table_id not in self.tables:
            try:
                self.tables[table_id] = uasset.read_string_table(uasset.load(self.paks, uasset.game_to_pak(table_id)))
            except Exception:  # noqa: BLE001 - missing tables just fall back to keys
                self.tables[table_id] = ('', {})
        return self.tables[table_id]

    def text(self, t):
        """FText dict from an asset -> {lang: string}"""
        if not t or not isinstance(t, dict):
            return {}
        if 'invariant' in t:
            return {lk(l): t['invariant'] for l in LANGS} if t['invariant'] else {}
        if 'table' in t:
            ns, src = self.table(t['table'])
            ns, key, source = ns, t['key'], src.get(t['key'], '')
        elif 'key' in t:
            ns, key, source = t.get('ns', ''), t['key'], t.get('src', '')
        else:
            return {}
        out = {}
        for lang in LANGS:
            v = self.locres[lk(lang)].get(ns, {}).get(key)
            out[lk(lang)] = v if v else source
        return {k: v for k, v in out.items() if v}

    def st(self, table, key):
        return self.text({'table': '/Game/StringTables/%s.%s' % (table, table), 'key': key})


def parse_ini_tuple_list(line):
    return re.findall(r'\((\w+), \(X=(\d+),Y=(\d+)\)\)', line), re.findall(r'\((\w+), (\d+)\)', line)


def lenient_json(text):
    text = re.sub(r'(?m)^\s*//.*$', '', text)
    text = re.sub(r'(?<=[,{\[\s"0-9el])\s*//[^\n]*', '', text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return json.loads(text)


def save_icon(paks, ref, name, cache):
    if not ref:
        return None
    if ref in cache:
        return cache[ref]
    fn = None
    try:
        img = utexture.load_texture(uasset.load(paks, uasset.game_to_pak(ref)), max_size=128)
        fn = 'icons/%s.png' % name
        img.save(os.path.join(OUT, fn), optimize=True)
    except Exception as ex:  # noqa: BLE001
        log('  icon failed', ref, ex)
    cache[ref] = fn
    return fn


def icon_info(icon):
    ref = (icon or {}).get('ResourceObject', {}).get('ref') if isinstance(icon, dict) else None
    tint = (icon or {}).get('TintColor', {}).get('SpecifiedColor') if isinstance(icon, dict) else None
    return ref, tint


def find_paks(game):
    """Accept the game folder, its PenDriverPro folder or the Paks folder itself."""
    for cand in (os.path.join(game, 'PenDriverPro', 'Content', 'Paks'), os.path.join(game, 'Content', 'Paks'), game):
        if os.path.isdir(cand) and any(f.endswith('.pak') for f in os.listdir(cand)):
            return cand
    raise FileNotFoundError('Pacific Drive .pak files not found under %s' % game)


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'Pacific Drive')
    build(game, OUT)


def game_version(paks):
    """ProjectVersion / BuildNumber from the game's DefaultGame.ini, e.g. ('1.15.0', '245')."""
    ini = paks.read('PenDriverPro/Config/DefaultGame.ini').decode('utf-8', 'replace')
    ver = re.search(r'^ProjectVersion=(.+?)\s*$', ini, re.M)
    num = re.search(r'^BuildNumber=(.+?)\s*$', ini, re.M)
    return (ver.group(1) if ver else ''), (num.group(1) if num else '')


def build(game, out_dir, logger=print):
    """Extract everything the editor needs from the game install into out_dir."""
    global OUT, log
    OUT, log = out_dir, logger
    paks = upak.PakSet(find_paks(game))
    os.makedirs(os.path.join(OUT, 'icons'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'fonts'), exist_ok=True)
    loc = Loc(paks)
    icons = {}

    ini = paks.read('PenDriverPro/Config/DefaultGame.ini').decode('utf-8', 'replace')
    grid = {}
    stacks = {}
    # paid packs / expansions, in EEntitlementId order (ENTITLEMENT_0, _1, ...)
    packs = []
    for line in ini.splitlines():
        if line.startswith('+Entitlements=('):
            g = lambda k: (re.search(k + r'="?([^",)]*)', line) or [None, ''])[1]
            disp = re.search(r'DisplayName=INVTEXT\("([^"]*)"\)', line)
            packs.append({'id': g('Name'), 'name': disp.group(1) if disp else g('Name'), 'steam': g('SteamAppID'),
                          'mount': g('MountableContentName'), 'index': len(packs)})
    for line in ini.splitlines():
        if line.startswith('ItemGridSizes=(('):
            grid = {k: [int(x), int(y)] for k, x, y in re.findall(r'\((\w+), \(X=(\d+),Y=(\d+)\)\)', line)}
        if line.startswith('ItemStackSizes=(('):
            stacks = {k: int(v) for k, v in re.findall(r'\((\w+), (\d+)\)', line)}

    # ---------------------------------------------------------- tuning
    tuning = {}
    try:
        tuning = lenient_json(paks.read('PenDriverPro/Content/Tuning/base.tune').decode('utf-8-sig', 'replace'))
    except ValueError as ex:
        log('  base.tune parse failed', ex)

    def tuned(v):
        """{TuningTag, TuningFloat} or number -> float"""
        if isinstance(v, dict):
            tag = v.get('TuningTag|T')
            if tag and tag in tuning and isinstance(tuning[tag], (int, float)):
                return float(tuning[tag])
            if 'TuningFloat|F' in v:
                return float(v['TuningFloat|F'])
            return None
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def summarize_defaults(d):
        out = {}
        ip = lambda k: d.get(k + '|:') or {}
        dur = ip('IP_Durability')
        if dur:
            out['maxDurability'] = tuned(dur.get('MaxDurability|:')) or dur.get('Durability|I')
            if dur.get('DestroyOnEmpty|B'):
                out['destroyOnEmpty'] = True
        hp = ip('IP_Health')
        if hp:
            out['maxHealth'] = tuned(hp.get('MaxHealth|:')) or hp.get('Health|F')
            pct = tuned(hp.get('MaxBreakPctMaxHealth|:'))
            if pct is not None and out['maxHealth']:
                out['maxBreak'] = round(out['maxHealth'] * pct, 4)
            ses = hp.get('WeightedBreakingSEs|M^F')
            if ses:
                out['breakEffects'] = [k for k, _ in ses]
        fat = ip('IP_Fatigue')
        if fat:
            out['fatigueBase'] = tuned(fat.get('MaxFatigueBase|:')) or fat.get('MaxFatigueThreshold|F')
        fu = ip('IP_Fuelable')
        if fu:
            out['maxFuel'] = fu.get('MaxFuel|F') or fu.get('Fuel|F')
        bt = ip('IP_Battery')
        if bt:
            out['maxBattery'] = bt.get('MaxBattery|F') or bt.get('Battery|F')
        ce = ip('IP_CarEquipment')
        slots = (ce.get('SupportedSlots|:') or {}).get('SlotMapping|MT:')
        if slots:
            out['slots'] = [k for k, _ in slots]
        if 'IP_Tintable|:' in d:
            t = d['IP_Tintable|:']
            out['tintable'] = {'paint': t.get('TintingEnabled|B', True) and t.get('PrimaryPart|B', True) is not False,
                               'decal': t.get('DecalEnabled|B', True) is not False}
        if 'IP_Locked|:' in d:
            out['lockable'] = True
        sec = d.get('IP_StatusEffectCondition|:')
        if sec is not None:
            out['seRules'] = {
                'tags': (sec.get('AllowedEffectTags|:') or {}).get('GameplayTags|AT') or [],
                'allowed': sec.get('AllowedEffects|A~') or [],
                'ignore': sec.get('EffectIgnoreLIst|A^') or [],
                'maxPer': dict(sec.get('MaxNumEffects|M^I') or []),
                'maxTag': dict(sec.get('MaxEffectsPerTarget|MTI') or []),
            }
        return out

    # ---------------------------------------------------------- items
    items = {}
    ia = sorted(p[:-7] for p in paks.list('PenDriverPro/Content/', '.uasset') if p.rsplit('/', 1)[1].startswith('IA_'))
    log('items:', len(ia))
    for p in ia:
        try:
            pkg = uasset.load(paks, p)
            e = pkg.main_export()
            if pkg.class_name(e) != 'ItemArchetype':
                continue
            props, tail_start, tail_end = pkg.export_props(e)
            defaults = figasset.decode_defaults(pkg, pkg.data[tail_start:tail_end]) or {}
        except Exception as ex:  # noqa: BLE001
            log('  skip', p, ex)
            continue
        name = p.rsplit('/', 1)[1]
        dsum = summarize_defaults(defaults.get('_data|*') or {})
        if name.startswith(('IA_Cosmetic_Paint_', 'IA_Cosmetic_Decal_')):
            pals = re.findall(r'(/Game/BaseArt/Palettes/[\w/]+\.BP_Palette_\w+?_C)', json.dumps(defaults))
            if pals:
                dsum['palette'] = pals[0]
        game_path = '/' + p.replace('PenDriverPro/Content/', 'Game/') + '.' + name
        gs = (props.get('GridSize') or '').split('::')[-1]
        ss = (props.get('NewStackSize') or '').split('::')[-1]
        ref, tint = icon_info(props.get('Icon'))
        iprops = [x.get('ref', '').rsplit('.', 1)[-1] for x in props.get('Properties', []) if isinstance(x, dict)]
        items[game_path] = {
            'id': name,
            'name': loc.text(props.get('Title')),
            'desc': loc.text(props.get('Description')),
            'category': props.get('Category') or '',
            'grid': gs,
            'size': grid.get(gs, [2, 2]),
            'tileOverride': [props.get('TileWidth'), props.get('TileHeight')] if props.get('TileWidth') or props.get('TileHeight') else None,
            'stack': stacks.get(ss, props.get('StackSize') or 1),
            'icon': save_icon(paks, ref, name, icons),
            'tint': tint,
            'props': iprops,
            'path': p.replace('PenDriverPro/Content/', ''),
            'tags': [t for t in props.get('ActorTags', []) if isinstance(t, str)],
            'logCategory': props.get('LogCategory') if isinstance(props.get('LogCategory'), str) else None,
            'unlockTag': props.get('UnlockTag') if isinstance(props.get('UnlockTag'), str) else None,
            'dlc': [packs[int(x.rsplit('_', 1)[1])]['id'] for x in (props.get('RequiredDLC') or [])
                    if isinstance(x, str) and x.rsplit('_', 1)[1].isdigit() and int(x.rsplit('_', 1)[1]) < len(packs)],
        }
        items[game_path].update(dsum)
    log('  with icon:', sum(1 for i in items.values() if i['icon']), ' with ru name:',
          sum(1 for i in items.values() if 'ru' in i['name']))

    # ---------------------------------------------------------- currencies
    currencies = {}
    for p in paks.list('PenDriverPro/Content/', '.uasset'):
        n = p.rsplit('/', 1)[1]
        if not n.startswith('CA_'):
            continue
        pkg = uasset.load(paks, p[:-7])
        e = pkg.main_export()
        if pkg.class_name(e) != 'CurrencyArchetype':
            continue
        props = pkg.export_props(e)[0]
        ref, tint = icon_info(props.get('Icon'))
        gp = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n[:-7]
        currencies[gp] = {'id': n[:-7], 'name': loc.text(props.get('Title')),
                          'icon': save_icon(paks, ref, n[:-7], icons) if 'PLACEHOLDER' not in (ref or '') else None,
                          'tint': tint}
    log('currencies:', len(currencies))

    # ---------------------------------------------------------- containers
    containers = {}
    for p in paks.list('PenDriverPro/Content/', '.uasset'):
        n = p.rsplit('/', 1)[1][:-7]
        if not n.startswith('CL_'):
            continue
        pkg = uasset.load(paks, p[:-7])
        e = pkg.main_export()
        props = pkg.export_props(e)[0]
        gp = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n
        zones = [{'attr': z.get('Attributes', 0), 'x': z['Location'][0], 'y': z['Location'][1],
                  'w': z['Size'][0], 'h': z['Size'][1]} for z in props.get('AttributeZones', []) if 'Location' in z]
        containers[gp.lower()] = containers[gp] = {'id': n, 'class': pkg.class_name(e), 'w': props.get('ContainerWidth'),
                          'h': props.get('ContainerHeight'), 'tile': props.get('TileSizeOverride'), 'zones': zones}

    # ---------------------------------------------------------- presets
    presets = {}
    for p in sorted(paks.list('PenDriverPro/Content/Backend/Presets/', '.json')):
        pid = p.rsplit('/', 1)[1][:-5]
        try:
            j = lenient_json(paks.read(p).decode('utf-8-sig'))
        except ValueError as ex:
            log('  preset parse failed', p, ex)
            continue

        def txt(v):
            if isinstance(v, dict) and 'stringtable' in v:
                path, key = v['stringtable'].rsplit('.', 1)
                return loc.text({'table': path, 'key': key})
            if isinstance(v, dict):
                return {LANG_KEY.get(k, k): s for k, s in v.items()}
            return {'en': v} if v else {}
        presets[pid] = {'title': txt(j.get('title')), 'desc': txt(j.get('description')),
                        'short': txt(j.get('description_short')), 'summaries': j.get('summaries', {}),
                        'settings': j.get('settings', {}), 'tuning': j.get('tuning', {})}
    log('presets:', list(presets))

    # ---------------------------------------------------------- settings menu
    pkg = uasset.load(paks, 'PenDriverPro/Content/UI/System/Settings/Pages/UMG_SettingsPage_Gameplay')
    exp = {}
    for i, e in enumerate(pkg.exports, 1):
        try:
            exp[i] = (pkg.class_name(e), e['name'], pkg.export_props(e)[0])
        except Exception:  # noqa: BLE001
            exp[i] = (pkg.class_name(e), e['name'], {})

    def widget_children(idx):
        cls, _n, props = exp[idx]
        out = []
        if cls in ('VerticalBox', 'Overlay', 'SizeBox'):
            for s in props.get('Slots', []) + ([props['Slot']] if False else []):
                si = s.get('idx', 0)
                if si > 0:
                    c = exp[si][2].get('Content', {}).get('idx', 0)
                    if c > 0:
                        out.append(c)
            if cls == 'SizeBox' and props.get('Slots') is None:
                pass
        for b in props.get('NamedSlotBindings', []):
            c = b.get('Content', {}).get('idx', 0)
            if c > 0:
                out.append(c)
        return out

    def flatten(idx, cat, acc):
        cls, name, props = exp[idx]
        if cls == 'UMG_SettingsSubCategory_C':
            cat = {'title': loc.text(props.get('Category')), 'id': name, 'items': []}
            acc.append(cat)
        elif cls.startswith('UMG_Setting_') and props.get('Variable'):
            kind = cls[len('UMG_Setting_'):-2].lower()
            item = {'var': props['Variable'], 'kind': kind, 'title': loc.text(props.get('Title') or props.get('TItle')),
                    'desc': loc.text(props.get('Description'))}
            for k in ('Min', 'Max', 'Resolution'):
                if k in props:
                    item[k.lower()] = props[k]
            if 'Values' in props:
                item['values'] = props['Values']
                vt = props.get('ValueTexts')
                if isinstance(vt, list):
                    item['value_texts'] = [loc.text(t) for t in vt]
                if 'RemappedValueOrder' in props:
                    item['order'] = props['RemappedValueOrder']
            if props.get('RequiredFeatures'):
                item['features'] = [f.get('FeatureName') for f in props['RequiredFeatures']]
            if cat is None:
                cat = {'title': {}, 'id': 'general', 'items': []}
                acc.append(cat)
            cat['items'].append(item)
        for c in widget_children(idx):
            flatten(c, cat, acc)

    roots = [i for i, (c, n, p) in exp.items() if c == 'WidgetTree']
    root_widget = exp[roots[0]][2].get('RootWidget', {}).get('idx') if roots else None
    settings = []
    if root_widget:
        flatten(root_widget, None, settings)
    log('settings categories:', [(c['id'], len(c['items'])) for c in settings])

    # ---------------------------------------------------------- status effects
    def bp_defaults(pak_path, depth=0):
        """Merged CDO properties of a blueprint class, parents first."""
        try:
            pkg = uasset.load(paks, pak_path)
        except Exception:  # noqa: BLE001
            return {}
        merged = {}
        for e in pkg.exports:
            if pkg.class_name(e) == 'BlueprintGeneratedClass' and e['super'] < 0 and depth < 8:
                parent = pkg.ref(e['super'])
                pp = uasset.game_to_pak(parent) if parent else None
                if pp and pp + '.uasset' in paks:
                    merged.update(bp_defaults(pp, depth + 1))
        for e in pkg.exports:
            if e['name'].startswith('Default__'):
                try:
                    merged.update(pkg.export_props(e)[0])
                except Exception:  # noqa: BLE001
                    pass
        return merged

    effects = {}
    for p in sorted(paks.list('PenDriverPro/Content/', '.uasset')):
        n = p.rsplit('/', 1)[1][:-7]
        if not (n.startswith('SE_') or n.startswith('UP_Garage')):
            continue
        d = bp_defaults(p[:-7])
        if not d:
            continue
        cls = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n + '_C'
        ref, tint = icon_info(d.get('Icon'))
        _, under = icon_info(d.get('Underlay'))
        effects[cls] = {'id': n, 'name': loc.text(d.get('Title') or d.get('DisplayName') or d.get('Description')),
                        'desc': loc.text(d.get('LogDescription') or (d.get('Description') if d.get('Title') else None)),
                        'icon': save_icon(paks, ref, 'SE_' + n, icons) if ref and 'PLACEHOLDER' not in ref else None,
                        'tint': under or tint, 'alert': (d.get('AlertLevel') or '').split('::')[-1],
                        'upgrade': n.startswith('UP_'),
                        'tags': [x for x in (d.get('Tags') or []) if isinstance(x, str)]}
    log('effects:', len(effects), 'named:', sum(1 for e in effects.values() if e['name']))

    # ---------------------------------------------------------- paint / decal palettes
    palette_names = {}
    for a, it in items.items():
        if it.get('palette') and it['palette'] not in palette_names:
            palette_names[it['palette']] = it['name']
    palettes = {}
    for p in sorted(paks.list('PenDriverPro/Content/BaseArt/Palettes/', '.uasset')):
        n = p.rsplit('/', 1)[1][:-7]
        if not n.startswith('BP_Palette_'):
            continue
        d = bp_defaults(p[:-7])
        cls = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n + '_C'
        color = d.get('Paint Color Tint') or d.get('PaintColorTint')
        palettes[cls] = {'id': n, 'kind': 'decal' if '_Decal_' in n else 'paint', 'color': color,
                         'name': palette_names.get(cls) or {}}
    log('palettes:', len(palettes))

    # ---------------------------------------------------------- research / upgrade graph
    def components(lst):
        out = []
        for c in lst or []:
            if (c.get('InputType') or '').endswith('Currency'):
                ref = (c.get('Currency') or {}).get('Archetype', {}).get('ref')
                if ref:
                    out.append({'currency': ref, 'qty': (c.get('Currency') or {}).get('Quantity')})
            else:
                ref = (c.get('Item') or {}).get('Archetype', {}).get('ref')
                if ref:
                    out.append({'item': ref, 'qty': (c.get('Item') or {}).get('Quantity')})
        return out

    def condition(pkg, c):
        """Unlock condition: text plus the logbook entries it checks (when it is a logbook filter)."""
        out = {'text': loc.text(c.get('ConditionText')), 'logbook': []}
        idx = (c.get('RequiredCondition') or {}).get('idx', 0)
        if pkg is not None and idx > 0:
            try:
                sub = pkg.export_props(pkg.exports[idx - 1])[0]
            except Exception:  # noqa: BLE001
                sub = {}
            out['kind'] = pkg.class_name(pkg.exports[idx - 1])
            for f in sub.get('SpecificLogbooks', []) or []:
                for k, v in f.items():
                    if isinstance(v, dict) and v.get('ref'):
                        out['logbook'].append(v['ref'])
                    elif k.startswith('ScanTag') and isinstance(v, str) and v != 'TagName':
                        out.setdefault('tags', []).append(v)
        return out

    graph = {'nodes': {}, 'groups': [], 'grid': None}
    gpkg = uasset.load(paks, 'PenDriverPro/Content/Gameplay/Inventory/Items/RecipeResearchGraph')
    gexp = {i: e for i, e in enumerate(gpkg.exports, 1)}
    gprops = {i: gpkg.export_props(e)[0] for i, e in gexp.items()}
    recipe_cache = {}
    for i, e in gexp.items():
        cls = gpkg.class_name(e)
        pr = gprops[i]
        if cls == 'GenericGraph':
            graph['grid'] = pr.get('GridSizeOverride')
        elif cls == 'GenericGraphGroup':
            graph['groups'].append({'title': loc.text(pr.get('CategoryTitle')), 'x': pr.get('Position', [0, 0])[0],
                                    'y': pr.get('Position', [0, 0])[1], 'w': pr.get('Width'), 'h': pr.get('Height')})
        elif cls in ('GenericGraphRecipeNode', 'GenericGraphUpgradeNode'):
            node = {'id': e['name'], 'kind': 'recipe' if 'Recipe' in pr else 'upgrade',
                    'x': pr.get('Position', [0, 0])[0], 'y': pr.get('Position', [0, 0])[1],
                    'start': bool(pr.get('bStartNode')), 'children': []}
            for c in pr.get('Connections', []):
                tgt = gprops.get(c.get('idx'), {}).get('Target', {})
                if tgt.get('idx', 0) > 0:
                    node['children'].append(gexp[tgt['idx']]['name'])
            if node['kind'] == 'recipe':
                rref = pr['Recipe'].get('ref')
                node['recipe'] = rref
                if rref not in recipe_cache:
                    try:
                        rp = uasset.load(paks, uasset.game_to_pak(rref))
                        rprops = rp.export_props(rp.main_export())[0]
                    except Exception:  # noqa: BLE001
                        rprops = {}
                    rec = rprops.get('Recipe') or {}
                    prods = [x.get('Item', {}).get('Archetype', {}).get('ref') for x in rec.get('Products', [])]
                    conds = []
                    for c in rprops.get('UnlockConditions', []) or []:
                        conds.append(condition(rp, c))
                    recipe_cache[rref] = {'conditions': conds, 'byDefault': bool(rprops.get('bIsUnlockedByDefault')),
                                          'product': prods[0] if prods else None,
                                          'qty': (rec.get('Products') or [{}])[0].get('Item', {}).get('Quantity'),
                                          'research': components(rprops.get('UnlockComponents')),
                                          'craft': components(rec.get('Components')),
                                          'category': rprops.get('Category')}
                node.update(recipe_cache[rref])
            else:
                ucls = pr['UpgradeClass'].get('ref')
                d = bp_defaults(uasset.game_to_pak(ucls))
                ref, tint = icon_info(d.get('UpgradeIcon') or d.get('Icon'))
                n = ucls.rsplit('.', 1)[-1]
                node.update({'upgrade': ucls, 'name': loc.text(d.get('UpgradeName') or d.get('Title')),
                             'desc': loc.text(d.get('UpgradeDescription') or d.get('Description')),
                             'icon': save_icon(paks, ref, 'UP_' + n, icons) if ref and 'PLACEHOLDER' not in ref else None,
                             'research': components(d.get('UnlockIngredients')),
                             'conditions': [condition(None, c) for c in d.get('RequiredConditions', [])
                                            if c.get('ConditionText')]})
            graph['nodes'][node['id']] = node
    log('graph nodes:', len(graph['nodes']), 'groups:', len(graph['groups']),
          'unnamed upgrades:', [n['upgrade'].rsplit('.', 1)[-1] for n in graph['nodes'].values()
                                if n['kind'] == 'upgrade' and not n['name']])

    # ---------------------------------------------------------- car quirks (conditions / behaviors)
    ns_q, qtable = loc.table('/Game/StringTables/ST_QuirkDetective.ST_QuirkDetective')
    qkeys = {k.lower(): k for k in qtable}
    part_alias = {'gearbox': 'gearbox', 'interiorlights': 'intlights', 'steeringwheel': 'steering', 'doors.frontleft': 'doors_fl',
                  'doors.frontright': 'doors_fr', 'doors.backleft': 'doors_bl', 'doors.backright': 'doors_br',
                  'doors.any': 'doors_any', 'doors.all': 'doors_all', 'tires': 'tire', 'tire': 'tire', 'wheels': 'tire',
                  'fuelgauge': 'dash', 'battery': 'battery'}

    type_alias = {'highspeed': 'speeding', 'lowspeed': 'slowing', 'carfriend': 'fiddle', 'itemsub': 'itemlost',
                  'itemadd': 'itemstore', 'turnonfast': 'faston', 'turnonslow': 'slowon', 'brighter': 'bright',
                  'dimmer': 'dim', 'wobbles': 'wobble'}
    behavior_type_alias = {'itemsub': 'itemloss'}

    def qtext(kind, tag):
        if not isinstance(tag, str) or tag == 'None':
            return {}
        tail = tag.split('.Type.')[-1] if kind != 'parts' else tag.split('Quirks.Parts.')[-1]
        tail = tail.lower()
        if kind == 'parts':
            cand = [part_alias.get(tail, tail), tail.replace('.', '_'), tail.split('.')[0]]
        else:
            alias = (behavior_type_alias.get(tail) if kind == 'behavior' else None) or type_alias.get(tail, tail)
            cand = [alias, tail]
        for c in cand:
            k = qkeys.get('quirks_%s_%s' % (kind, c) if kind == 'parts' else 'quirks_%s_type_%s' % (kind, c))
            if k:
                return loc.st('ST_QuirkDetective', k)
        return {}

    quirks = {'conditions': {}, 'behaviors': {}, 'sentence': loc.st('ST_QuirkDetective', 'quirk_detective_behavior_format')}
    for p in sorted(paks.list('PenDriverPro/Content/Gameplay/StatusEffects/Quirks/', '.uasset')):
        n = p.rsplit('/', 1)[1][:-7]
        if not n.startswith(('QC_', 'QB_')) or 'Base' in n:
            continue
        d = bp_defaults(p[:-7])
        cls = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n + '_C'
        if n.startswith('QC_'):
            quirks['conditions'][cls] = {'id': n, 'tag': d.get('ConditionIDTag'), 'part': d.get('ConditionPartTag'),
                                        'type': d.get('ConditionTypeTag'), 'random': d.get('CanBeRandomQuirkCondition', True),
                                        'partName': qtext('parts', d.get('ConditionPartTag')),
                                        'typeName': qtext('conditions', d.get('ConditionTypeTag'))}
        else:
            quirks['behaviors'][cls] = {'id': n, 'tag': d.get('BehaviorIDTag'), 'part': d.get('BehaviorPartTag'),
                                       'type': d.get('BehaviorTypeTag'), 'random': d.get('CanBeRandomQuirkBehavior', True),
                                       'allowed': d.get('AllowedConditionTags') or [], 'banned': d.get('BannedConditionTags') or [],
                                       'partName': qtext('parts', d.get('BehaviorPartTag')),
                                       'typeName': qtext('behavior', d.get('BehaviorTypeTag'))}
    miss = [v['id'] for v in list(quirks['conditions'].values()) + list(quirks['behaviors'].values()) if not v['partName'] or not v['typeName']]
    log('quirks: %d conditions, %d behaviors, unnamed: %s' % (len(quirks['conditions']), len(quirks['behaviors']), miss))

    # ---------------------------------------------------------- logbook (codex)
    def row_field(row, prefix):
        return next((v for k, v in row.items() if k.startswith(prefix)), None)

    logbook = {'categories': [], 'subcategories': [], 'entries': {}}
    for name, row in uasset.read_datatable(uasset.load(paks, 'PenDriverPro/Content/UI/LogBook/PageLayouts/DT_LogBook_Categories')).items():
        ref = (row_field(row, 'IconImage') or {}).get('ref')
        logbook['categories'].append({'id': name, 'tag': row_field(row, 'AltCategoryTag'), 'name': loc.text(row_field(row, 'PrettyName')),
                                      'icon': save_icon(paks, ref, 'LBC_' + name, icons) if ref else None})
    for name, row in uasset.read_datatable(uasset.load(paks, 'PenDriverPro/Content/UI/LogBook/PageLayouts/DT_LogBook_Subcategories')).items():
        logbook['subcategories'].append({'id': name, 'tag': row_field(row, 'SubcategoryTag'), 'name': loc.text(row_field(row, 'PrettyName'))})

    def add_entry(path, cls, props, title=None, extra=None):
        cat = props.get('LogCategory')
        if not isinstance(cat, str) or not cat.startswith('UI.Categories.Logbook'):
            return
        ref, tint = icon_info(props.get('Icon'))
        e = {'cls': cls, 'cat': cat, 'sub': props.get('Subcategory') if isinstance(props.get('Subcategory'), str) else None,
             'name': title if title is not None else loc.text(props.get('Title') or props.get('Name')),
             'desc': loc.text(props.get('Description')), 'lore': loc.text(props.get('Lore')),
             'icon': save_icon(paks, ref, 'LB_' + path.rsplit('.', 1)[-1], icons) if ref and 'PLACEHOLDER' not in ref else None,
             'tint': tint, 'unlockTag': props.get('UnlockTag') if isinstance(props.get('UnlockTag'), str) else None}
        if extra:
            e.update(extra)
        logbook['entries'][path] = e

    for a, it in items.items():
        if it.get('logCategory'):
            logbook['entries'][a] = {'cls': '/Script/PenDriverInventory.ItemArchetype', 'cat': it['logCategory'], 'item': True,
                                     'unlockTag': it.get('unlockTag')}
    for p in paks.list('PenDriverPro/Content/', '.uasset'):
        n = p.rsplit('/', 1)[1][:-7]
        if not n.startswith(('LOG_', 'RM_', 'DSS_')):
            continue
        try:
            pkg = uasset.load(paks, p[:-7])
            e = pkg.main_export()
            cls = pkg.class_name(e)
            props = pkg.export_props(e)[0]
        except Exception:  # noqa: BLE001
            continue
        gp = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n
        if cls == 'LogBookDataGeneric':
            add_entry(gp, '/Script/PenDriverInventory.LogBookDataGeneric', props)
        elif cls == 'RouteModifierAsset':
            add_entry(gp, '/Script/PenDriverPro.RouteModifierAsset', props)
        elif cls == 'DialogueSequenceSet':
            title, lines = {}, []
            for sq in props.get('Sequences', []) or []:
                sp = uasset.game_to_pak(sq.get('soft', '')) if isinstance(sq, dict) else None
                if not sp or sp + '.uasset' not in paks:
                    continue
                try:
                    dp = uasset.load(paks, sp)
                    dprops = dp.export_props(dp.main_export())[0]
                except Exception:  # noqa: BLE001
                    continue
                title = title or loc.text(dprops.get('Title'))
                for seg in dprops.get('Segments', []) or []:
                    for sd in seg.get('SubtitleData', []) or []:
                        if len(lines) < 40:
                            lines.append(loc.text(sd.get('Text')))
            add_entry(gp, '/Script/PenDriverPro.DialogueSequenceSet', props, title=title, extra={'lines': lines})
    log('logbook entries:', len(logbook['entries']), 'categories:', len(logbook['categories']))

    # ---------------------------------------------------------- world map (route planning table)
    worldmap = {'legs': {}, 'edges': [], 'background': None}
    wpkg = uasset.load(paks, 'PenDriverPro/Content/Systems/Routes/V2/WorldShape')
    wexp = {i: e for i, e in enumerate(wpkg.exports, 1)}
    wprops = {i: wpkg.export_props(e)[0] for i, e in wexp.items()}
    for i, e in wexp.items():
        cls = wpkg.class_name(e)
        pr = wprops[i]
        if cls == 'RouteShape':
            bg = (pr.get('Background') or {}).get('ref')
            if bg:
                try:
                    img = utexture.load_texture(uasset.load(paks, uasset.game_to_pak(bg)), max_size=2048)
                    img.save(os.path.join(OUT, 'icons', 'worldmap.png'), optimize=True)
                    worldmap['background'] = 'icons/worldmap.png'
                except Exception as ex:  # noqa: BLE001
                    log('  map background failed', ex)
        elif cls == 'RouteShapeLeg':
            ref, tint = icon_info(pr.get('Icon'))
            leg = {'x': pr.get('Position', [0, 0])[0], 'y': pr.get('Position', [0, 0])[1], 'size': pr.get('Size', 64.0),
                   'icon': save_icon(paks, ref, 'MAP_' + ref.rsplit('.', 1)[-1], icons) if ref else None,
                   'junction': loc.text(pr.get('JunctionID')), 'name': loc.text(pr.get('NameOverride')),
                   'type': loc.text(pr.get('DisplayTypeOverride')), 'zone': loc.text(pr.get('ZoneArea')),
                   'tags': [t for t in pr.get('Tags', []) if isinstance(t, str)],
                   'start': bool(pr.get('bIsStartingLevel')), 'byDefault': bool(pr.get('bDiscoveredByDefault'))}
            worldmap['legs'][e['name']] = leg
            for c in pr.get('Connections', []):
                ed = wprops.get(c.get('idx'), {})
                tgt = (ed.get('Target') or {}).get('idx', 0)
                if tgt > 0:
                    worldmap['edges'].append({'from': e['name'], 'to': wexp[tgt]['name'],
                                              'points': [{'p': pt.get('Position'), 'in': pt.get('InTangent'), 'out': pt.get('OutTangent')}
                                                         for pt in ed.get('Points', [])]})
    log('world map: %d legs, %d edges' % (len(worldmap['legs']), len(worldmap['edges'])))

    # route modifiers (RM_*) and what hazards/boons/events are called (via their logbook entries)
    modifiers = {}
    spawnables = {}
    for p in sorted(paks.list('PenDriverPro/Content/', '.uasset')):
        n = p.rsplit('/', 1)[1][:-7]
        gp = '/' + p[:-7].replace('PenDriverPro/Content/', 'Game/') + '.' + n
        if n.startswith('RM_'):
            try:
                pkg = uasset.load(paks, p[:-7])
                pr = pkg.export_props(pkg.main_export())[0]
            except Exception:  # noqa: BLE001
                continue
            ref, tint = icon_info(pr.get('Icon'))
            modifiers[gp] = {'id': n, 'name': loc.text(pr.get('Name')), 'desc': loc.text(pr.get('Description')),
                             'short': loc.text(pr.get('ShortDescription')),
                             'icon': save_icon(paks, ref, 'RM_' + n, icons) if ref and 'PLACEHOLDER' not in ref else None,
                             'tint': tint, 'state': '/JunctionState/' in p}
        elif n.startswith(('BP_Hazard_', 'BP_Boon_', 'GEV_', 'BP_Spawn_', 'PFX_Boon_')):
            d = bp_defaults(p[:-7])
            lb = (d.get('LogBookData') or {}).get('ref') if isinstance(d.get('LogBookData'), dict) else None
            if lb:
                spawnables[gp + '_C'] = lb
    log('route modifiers: %d, hazards/boons/events: %d' % (len(modifiers), len(spawnables)))

    # ---------------------------------------------------------- strings
    st = loc.st
    strings = {
        'container_trunk': st('ST_Containers', 'container_car_trunk'),
        'container_pack': st('ST_Containers', 'container_player_backpack'),
        'container_storage': st('ST_Containers', 'container_garage_storage'),
        'inventory': st('ST_UI', 'playermenu_category_inventory'),
        'anchor_energy': st('ST_UI', 'run_finished_success_stat_anchors_collected'),
        'fuel': st('ST_UI', 'item_info_stat_type_fuel'),
        'health': st('ST_UI', 'item_info_stat_type_health'),
        'battery': st('ST_UI', 'property_battery_name'),
        'total': st('ST_UI', 'crafting_ui_storage_total'),
        'preset': st('ST_MainMenu', 'setting_difficulty_newgame_title'),
        'quirks_title': st('ST_QuirkDetective', 'quirk_detective_quirks_title'),
    }
    _, ui_table = loc.table('/Game/StringTables/ST_UI.ST_UI')
    for k in ui_table:
        if k.startswith('run_finished_'):
            strings['ui.' + k] = st('ST_UI', k)
    for k in ('damage', 'carresource', 'crafting', 'environmnetalhazards', 'instabilitystorms', 'driving'):
        strings['summary_' + k] = st('ST_MainMenu', 'setting_difficulty_summaryicon_' + k)

    # ---------------------------------------------------------- fonts
    for f in ('Montserrat-Bold', 'Montserrat-ExtraBold', 'Inter-Regular', 'Inter-Bold', 'bedstead', 'PixelDriver'):
        p = 'PenDriverPro/Content/UI/Fonts/Faces/%s.ufont' % f
        if p in paks:
            data = paks.read(p)
            ext = 'otf' if data[:4] == b'OTTO' else 'ttf'
            with open(os.path.join(OUT, 'fonts', '%s.%s' % (f, ext)), 'wb') as fh:
                fh.write(data)

    car_slot_keys = {
        'Car.Equip.Body.DoorsFL': 'slot_frontleftdoor', 'Car.Equip.Body.DoorsFR': 'slot_frontrightdoor',
        'Car.Equip.Body.DoorsRL': 'slot_rearleftdoor', 'Car.Equip.Body.DoorsRR': 'slot_rearrightdoor',
        'Car.Equip.Body.DoorsTrunk': 'slot_trunk', 'Car.Equip.Body.PanelHood': 'slot_hood',
        'Car.Equip.Body.PanelFL': 'slot_panel_fl', 'Car.Equip.Body.PanelFR': 'slot_panel_fr',
        'Car.Equip.Body.PanelRL': 'slot_panel_rl', 'Car.Equip.Body.PanelRR': 'slot_panel_rr',
        'Car.Equip.Attachments.FrontGrill': 'slot_bumper_f', 'Car.Equip.Attachments.RearTow': 'slot_bumper_r',
        'Car.Equip.Attachments.HeadLightLeft': 'slot_leftheadlight', 'Car.Equip.Attachments.HeadLightRight': 'slot_rightheadlight',
        'Car.Equip.Attachments.BackSeatLeft': 'slot_essential_fueltank', 'Car.Equip.Attachments.BackSeatRight': 'slot_limbattery',
        'Car.Equip.Attachments.RoofFront': 'slot_topfront', 'Car.Equip.Attachments.RoofRear': 'slot_toprear',
        'Car.Equip.Attachments.LeftSideFront': 'slot_left_side_front_attachment',
        'Car.Equip.Attachments.LeftSideBack': 'slot_left_side_back_attachment',
        'Car.Equip.Attachments.RightSideFront': 'slot_right_side_front_attachment',
        'Car.Equip.Attachments.RightSideBack': 'slot_right_side_back_attachment',
        'Car.Equip.Essentials.Engine': 'slot_interior_engine', 'Car.Equip.Essentials.WheelFL': 'slot_interior_fl_wheel',
        'Car.Equip.Essentials.WheelFR': 'slot_interior_fr_wheel', 'Car.Equip.Essentials.WheelRL': 'slot_interior_rl_wheel',
        'Car.Equip.Essentials.WheelRR': 'slot_interior_rr_wheel', 'Car.Equip.Internal.GasCap': 'slot_essential_gascap',
        'Car.Equip.Internal.ChargePort': 'slot_essential_chargeport', 'Car.Equip.Internal.Computer': 'slot_internal_computer',
        'Car.Equip.Internal.Windshield': 'slot_windshield', 'Car.Equip.Internal.Soul': 'part_soul',
        'Car.Equip.Internal.SmallGadgetLeft': 'slot_interior_smallgadgetleft', 'Car.Equip.Internal.Gobbler': 'slot_internal_gobbler',
        'Car.Equip.Cosmetics.Antenna': 'slot_cosmetic_antenna', 'Car.Equip.Cosmetics.Bobblehead': 'slot_cosmetic_bobblehead',
        'Car.Equip.Cosmetics.Shifter': 'slot_cosmetic_gearboxshifter', 'Car.Equip.Cosmetics.HoodOrnament': 'slot_cosmetic_hoodornament',
        'Car.Equip.Cosmetics.LicensePlate': 'slot_cosmetic_licenseplate', 'Car.Equip.Cosmetics.SteeringWheel': 'slot_cosmetic_steeringwheel',
        'Car.Equip.Cosmetics.StickerL': 'slot_cosmetic_stickerl', 'Car.Equip.Cosmetics.StickerR': 'slot_cosmetic_stickerr',
        'Car.Equip.Cosmetics.Mirror': 'slot_mirror', 'Car.Equip.Internal.Handbrake': 'slot_handbrake',
        'Car.Equip.Internal.InventoryStorage': 'slot_trunkstorage', 'Car.Equip.Internal.Crafting': 'slot_trunkcrafting',
    }
    car_slot_keys.update({
        'Car.Equip.Attachments.LeftRearWindowBack': 'slot_left_side_back_attachment',
        'Car.Equip.Attachments.LeftRearWindowFront': 'slot_left_side_front_attachment',
        'Car.Equip.Attachments.RightRearWindowFront': 'slot_right_side_front_attachment',
        'Car.Equip.Attachments.RightRearWindowBack': 'slot_right_side_back_attachment',
        'Car.Equip.Attachments.RoofBack': 'slot_toprear', 'Car.Equip.Attachments.RoofFront': 'slot_topfront',
        'Car.Equip.Internal.Upgrade.RoofF': 'slot_internal_upgrade_roof_f', 'Car.Equip.Internal.Upgrade.RoofR': 'slot_internal_upgrade_roof_r',
        'Car.Equip.Internal.Upgrade.SideR': 'slot_internal_upgrade_side_r', 'Car.Equip.Internal.Upgrade.SideL': 'slot_internal_upgrade_side_l',
        'Car.Equip.Cosmetics.Sticker.L': 'slot_cosmetic_stickerl', 'Car.Equip.Cosmetics.Sticker.R': 'slot_cosmetic_stickerr',
        'Car.Equip.Attachments.FuelCan': 'slot_attachment_fuelcan',
    })
    car_slots = {tag: loc.st('ST_Car', key) for tag, key in car_slot_keys.items()}
    # mounting racks: '<place> · <rack name>'
    rack_names = {'Side': loc.st('ST_Car', 'slot_upgrade_rack_side_name'), 'Roof': loc.st('ST_Car', 'slot_upgrade_rack_roof_name'),
                  'BackSeat': loc.st('ST_Car', 'slot_upgrade_rack_backseat_name')}
    for tag in list(car_slots):
        if tag.startswith('Car.Equip.Attachments.'):
            base = car_slots[tag]
            kind = 'Roof' if 'Roof' in tag else 'BackSeat' if 'BackSeat' in tag else 'Side' if 'Window' in tag else None
            if kind:
                car_slots[tag + '_Rack'] = {l: '%s · %s' % (base.get(l, ''), rack_names[kind].get(l, '')) for l in base}

    for name, obj in (('items', items), ('currencies', currencies), ('containers', containers),
                      ('effects', effects), ('palettes', palettes), ('carslots', car_slots), ('graph', graph), ('logbook', logbook), ('quirks', quirks), ('packs', packs),
                      ('worldmap', worldmap), ('modifiers', modifiers), ('spawnables', spawnables),
                      ('presets', presets), ('settings', settings), ('strings', strings)):
        with open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=0, separators=(',', ':'))
    with open(os.path.join(OUT, 'langs.json'), 'w') as fh:
        json.dump([lk(l) for l in LANGS], fh)
    with open(os.path.join(OUT, 'meta.json'), 'w') as fh:
        gv, gb = game_version(paks)
        json.dump({'version': DATA_VERSION, 'game': os.path.abspath(game), 'gameVersion': gv, 'gameBuild': gb}, fh)
    log('done ->', os.path.abspath(OUT))


if __name__ == '__main__':
    main()
