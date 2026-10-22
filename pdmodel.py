"""Game-aware editing operations (inventory grids, storage, currencies, settings).

Rules observed in real saves:
  * A tile container (Layout = ItemTileLayout) holds ItemTileSlot objects.
    Location {X, Y} is the item's centre in half-tile units:
        left = (X - w) / 2, top = (Y - h) / 2   (w, h already swapped when bRotated)
    Zones with (Attributes & 1) are blocked cells.
  * A list container (Layout = ItemListLayout, garage storage) holds ItemListSlot
    objects ordered by Index, one stack per slot.
  * One ItemInstance object per item; minimal form is {Archetype}.
  * Stack limit = ItemStackSizes[NewStackSize] from DefaultGame.ini.
"""
import copy
import json
import os
import re
import uuid

import pdsave
import pdtools

HERE = os.path.dirname(os.path.abspath(__file__))
GAMEDATA = os.path.join(HERE, 'gamedata')

INV = '/Script/PenDriverInventory.'
ARCH_CLASS = INV + 'ItemArchetype'


class EditError(Exception):
    pass


def load_gamedata():
    gd = {}
    for name in ('items', 'containers', 'currencies', 'presets', 'settings', 'strings', 'langs',
                 'effects', 'palettes', 'carslots', 'graph', 'logbook', 'quirks'):
        p = os.path.join(GAMEDATA, name + '.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                gd[name] = json.load(f)
        else:
            gd[name] = {} if name not in ('settings', 'langs') else []
    return gd


def asset_of(ref):
    """'*/Game/X.X|/Script/..' -> '/Game/X.X'"""
    return ref[1:].split('|')[0] if ref else None


def guid_of(ref):
    return ref[1:33] if ref and ref.startswith('@') else None


class Model:
    def __init__(self, path, gd=None):
        self.gd = gd or load_gamedata()
        self.save = pdtools.Save(path)
        self.path = path
        self.dirty = False
        self._index()

    # ------------------------------------------------------------ indexes
    def _index(self):
        self.tables = pdtools.object_tables(self.save)
        self.obj = {}            # guid -> (table, object)
        for t in self.tables:
            for k, o in t.items():
                if isinstance(o, dict):
                    self.obj[k.split('|')[0]] = (t, o)
        self.taken = set(self.obj)
        self._names = {}
        self._ext = None

    def get(self, guid):
        try:
            return self.obj[guid][1]
        except KeyError:
            raise EditError('object %s not found' % guid)

    def item_info(self, arche):
        return self.gd['items'].get(arche) or {'id': arche.rsplit('.', 1)[-1], 'name': {}, 'size': [2, 2],
                                                'stack': 1, 'icon': None, 'category': ''}

    def new_guid(self):
        while True:
            g = uuid.uuid4().hex.upper()
            if g not in self.taken:
                self.taken.add(g)
                return g

    def new_name(self, prefix):
        if prefix not in self._names:
            lowest = 2147483647
            for _, o in self.obj.values():
                n = o.get('_name|N', '')
                if n.startswith(prefix + '_') and n[len(prefix) + 1:].isdigit():
                    lowest = min(lowest, int(n[len(prefix) + 1:]))
            self._names[prefix] = lowest
        self._names[prefix] -= 1
        return '%s_%d' % (prefix, self._names[prefix])

    def add_object(self, table, guid, o):
        table[guid + '|>'] = o
        self.obj[guid] = (table, o)

    def remove_object(self, guid):
        t, o = self.obj.pop(guid)
        del t[guid + '|>']
        # sub-objects owned by it
        for g, (t2, o2) in list(self.obj.items()):
            if guid_of(o2.get('_outer|$')) == guid:
                self.remove_object(g)

    def external_refs(self, guid):
        """How many references to @guid exist outside slot Items arrays and _outer links."""
        if self._ext is None:
            cnt = {}

            def rec(v, skip):
                if isinstance(v, dict):
                    for k, x in v.items():
                        rec(x, k in ('Items|A$', '_outer|$'))
                elif isinstance(v, list):
                    for x in v:
                        rec(x, skip)
                elif not skip and isinstance(v, str) and v[:1] == '@' and len(v) > 33:
                    cnt[v[1:33]] = cnt.get(v[1:33], 0) + 1
            rec(self.save.root('GAME'), False)
            self._ext = cnt
        return self._ext.get(guid, 0)

    # ------------------------------------------------------------ items
    def new_item(self, arche, table, template=None):
        """Create an ItemInstance. Copies a same-archetype template's data if given."""
        g = self.new_guid()
        data = {'Archetype|$': '*%s|%s' % (arche, ARCH_CLASS)}
        if template is not None:
            t = self.get(template)
            if not any(guid_of(o.get('_outer|$')) == template for _, o in self.obj.values()):
                data = copy.deepcopy(t.get('_data|*', data))
        o = {'_class|^': INV + 'ItemInstance', '_name|N': self.new_name('ItemInstance'),
             '_outer|$': '*/Engine/Transient|/Script/CoreUObject.Package', '_data|*': data}
        self.add_object(table, g, o)
        return '@%s|%sItemInstance' % (g, INV)

    def slot_items(self, slot_guid):
        return self.get(slot_guid).setdefault('_data|*', {}).setdefault('Items|A$', [])

    def set_slot_count(self, slot_guid, count, force=False):
        slot = self.get(slot_guid)
        data = slot.setdefault('_data|*', {})
        items = data.setdefault('Items|A$', [])
        arche = asset_of(data.get('FilterItemType|$')) or (
            asset_of(self.get(guid_of(items[0]))['_data|*']['Archetype|$']) if items else None)
        if arche is None:
            raise EditError('slot has no item type')
        stack = self.item_info(arche)['stack']
        if count < 1:
            raise EditError('count must be at least 1 (delete the slot instead)')
        if count > stack and not force:
            raise EditError('stack limit for this item is %d' % stack)
        table = self.obj[slot_guid][0]
        while len(items) < count:
            tmpl = guid_of(items[-1]) if items else None
            items.append(self.new_item(arche, table, tmpl))
        while len(items) > count:
            g = guid_of(items[-1])
            if self.external_refs(g):
                raise EditError('item %s is referenced elsewhere (hotbar/quest), remove it in game' % g)
            items.pop()
            self.remove_object(g)
        self.dirty = True

    # ------------------------------------------------------------ containers
    def container_layout(self, cont):
        lay = asset_of(cont.get('_data|*', {}).get('Layout|$'))
        L = self.gd['containers'].get(lay) or self.gd['containers'].get((lay or '').lower())
        return lay, L

    def blocked_cells(self, L):
        W, H = L['w'], L['h']
        cells = [[0] * W for _ in range(H)]
        for z in L.get('zones', []):
            if z['attr'] & 1:
                for y in range(max(0, z['y']), min(H, z['y'] + z['h'])):
                    for x in range(max(0, z['x']), min(W, z['x'] + z['w'])):
                        cells[y][x] = 1
        return cells

    @staticmethod
    def tile_rect(slot_data, size):
        w, h = size
        if slot_data.get('bRotated|B'):
            w, h = h, w
        X, Y = slot_data['Location|:']['X|I'], slot_data['Location|:']['Y|I']
        return (X - w) // 2, (Y - h) // 2, w, h

    def check_fit(self, cont_guid, x, y, w, h, ignore_slot=None):
        cont = self.get(cont_guid)
        _, L = self.container_layout(cont)
        if not L or not L.get('w'):
            raise EditError('not a grid container')
        if x < 0 or y < 0 or x + w > L['w'] or y + h > L['h']:
            raise EditError('does not fit inside the container')
        blocked = self.blocked_cells(L)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if blocked[yy][xx]:
                    raise EditError('cell %d,%d is not usable' % (xx, yy))
        for r in cont['_data|*'].get('Slots|A$', []):
            sg = guid_of(r)
            if sg == ignore_slot:
                continue
            sd = self.get(sg).get('_data|*', {})
            if 'Location|:' not in sd:
                continue
            ox, oy, ow, oh = self.tile_rect(sd, self.item_info(asset_of(sd.get('FilterItemType|$')))['size'])
            if x < ox + ow and ox < x + w and y < oy + oh and oy < y + h:
                raise EditError('overlaps another item')

    def place_item(self, cont_guid, arche, x, y, rotated=False, count=1, force=False):
        info = self.item_info(arche)
        w, h = info['size']
        if rotated:
            w, h = h, w
        self.check_fit(cont_guid, x, y, w, h)
        if count > info['stack'] and not force:
            raise EditError('stack limit for this item is %d' % info['stack'])
        cont = self.get(cont_guid)
        table = self.obj[cont_guid][0]
        sg = self.new_guid()
        data = {'Location|:': {'X|I': 2 * x + w, 'Y|I': 2 * y + h}}
        if rotated:
            data['bRotated|B'] = True
        data['Items|A$'] = []
        data['FilterItemType|$'] = '*%s|%s' % (arche, ARCH_CLASS)
        slot = {'_class|^': INV + 'ItemTileSlot', '_name|N': self.new_name('ItemTileSlot'),
                '_outer|$': '@%s|%s' % (cont_guid, cont['_class|^']), '_data|*': data}
        self.add_object(table, sg, slot)
        cont['_data|*'].setdefault('Slots|A$', []).append('@%s|%sItemTileSlot' % (sg, INV))
        tmpl = self.find_template(arche)
        for _ in range(count):
            data['Items|A$'].append(self.new_item(arche, table, tmpl))
        self.dirty = True
        return sg

    def find_template(self, arche):
        """A pristine existing instance of the same archetype (keeps default properties)."""
        best = None
        for g, (_, o) in list(self.obj.items()):
            d = o.get('_data|*') if isinstance(o, dict) else None
            if d and o.get('_class|^') == INV + 'ItemInstance' and asset_of(d.get('Archetype|$')) == arche:
                if 'Properties|*' not in d and 'ActiveEffects|A$' not in d:
                    return g
        return best

    def move_slot(self, cont_guid, slot_guid, x, y, rotated):
        sd = self.get(slot_guid)['_data|*']
        info = self.item_info(asset_of(sd.get('FilterItemType|$')))
        w, h = info['size']
        if rotated:
            w, h = h, w
        self.check_fit(cont_guid, x, y, w, h, ignore_slot=slot_guid)
        sd['Location|:'] = {'X|I': 2 * x + w, 'Y|I': 2 * y + h}
        if rotated:
            sd['bRotated|B'] = True
        else:
            sd.pop('bRotated|B', None)
        # keep key order stable: Location, bRotated, Items, FilterItemType
        order = ['Location|:', 'bRotated|B', 'Items|A$', 'FilterItemType|$']
        rest = {k: v for k, v in sd.items() if k not in order}
        new = {k: sd[k] for k in order if k in sd}
        new.update(rest)
        sd.clear()
        sd.update(new)
        self.dirty = True

    def delete_slot(self, cont_guid, slot_guid):
        cont = self.get(cont_guid)
        items = list(self.slot_items(slot_guid))
        for r in items:
            if self.external_refs(guid_of(r)):
                raise EditError('an item in this slot is referenced elsewhere (hotbar/quest); remove it in game')
        for r in items:
            self.remove_object(guid_of(r))
        slots = cont['_data|*']['Slots|A$']
        slots[:] = [r for r in slots if guid_of(r) != slot_guid]
        self.remove_object(slot_guid)
        self.dirty = True

    # ------------------------------------------------------------ list containers (storage)
    def list_totals(self, cont_guid):
        cont = self.get(cont_guid)
        out = {}
        for r in cont['_data|*'].get('Slots|A$', []):
            sd = self.get(guid_of(r)).get('_data|*', {})
            a = asset_of(sd.get('FilterItemType|$'))
            out.setdefault(a, []).append(guid_of(r))
        return out

    def set_list_total(self, cont_guid, arche, total):
        if total < 0:
            raise EditError('total must be >= 0')
        cont = self.get(cont_guid)
        table = self.obj[cont_guid][0]
        stack = max(1, self.item_info(arche)['stack'])
        slots = self.list_totals(cont_guid).get(arche, [])
        current = sum(len(self.slot_items(s)) for s in slots)
        tmpl = self.find_template(arche)
        if total > current:
            need = total - current
            for s in slots:
                items = self.slot_items(s)
                while need and len(items) < stack:
                    items.append(self.new_item(arche, table, tmpl))
                    need -= 1
            all_slots = [self.get(guid_of(r)) for r in cont['_data|*'].get('Slots|A$', [])]
            next_index = max([o.get('_data|*', {}).get('Index|I', 0) for o in all_slots] + [0]) + 1
            while need:
                sg = self.new_guid()
                n = min(need, stack)
                data = {'Items|A$': [self.new_item(arche, table, tmpl) for _ in range(n)],
                        'FilterItemType|$': '*%s|%s' % (arche, ARCH_CLASS), 'Index|I': next_index}
                next_index += 1
                self.add_object(table, sg, {'_class|^': INV + 'ItemListSlot', '_name|N': self.new_name('ItemListSlot'),
                                            '_outer|$': '@%s|%s' % (cont_guid, cont['_class|^']), '_data|*': data})
                cont['_data|*'].setdefault('Slots|A$', []).append('@%s|%sItemListSlot' % (sg, INV))
                need -= n
        elif total < current:
            drop = current - total
            for s in reversed(slots):
                items = self.slot_items(s)
                while drop and items:
                    g = guid_of(items[-1])
                    if self.external_refs(g):
                        raise EditError('an item is referenced elsewhere; remove it in game')
                    items.pop()
                    self.remove_object(g)
                    drop -= 1
                if not items:
                    cont['_data|*']['Slots|A$'] = [r for r in cont['_data|*']['Slots|A$'] if guid_of(r) != s]
                    self.remove_object(s)
        self.dirty = True

    # ------------------------------------------------------------ item instances
    # (property block, field, kind, max key in items.json)
    PROPS = [
        ('IP_Durability|:', 'Durability|I', 'int', 'maxDurability'),
        ('IP_Health|:', 'Health|F', 'float', 'maxHealth'),
        ('IP_Fatigue|:', 'Fatigue|F', 'float', None),
        ('IP_Fuelable|:', 'Fuel|F', 'float', 'maxFuel'),
        ('IP_Battery|:', 'BATTERY|F', 'float', 'maxBattery'),
        ('IP_GarageCharger|:', 'CurrentCharge|F', 'float', None),
        ('IP_Locked|:', 'LockStrength|I', 'int', None),
    ]

    def instance_view(self, guid):
        o = self.get(guid)
        d = o.get('_data|*', {})
        arche = asset_of(d.get('Archetype|$'))
        info = self.item_info(arche)
        props = d.get('Properties|*', {})
        fields = []
        for ip, field, kind, maxkey in self.PROPS:
            block = props.get(ip)
            mx = info.get(maxkey) if maxkey else None
            if ip == 'IP_Fatigue|:':
                if block is None and not info.get('fatigueBase'):
                    continue
                mx = (block or {}).get('MaxFatigueThreshold|F') or info.get('fatigueBase')
            elif block is None and mx is None:
                continue
            cur = (block or {}).get(field)
            if cur is None and block is not None and ip == 'IP_Battery|:':
                cur = block.get('Battery|F')
            fields.append({'ip': ip, 'field': field, 'kind': kind, 'value': cur, 'max': mx,
                           'stored': cur is not None})
        tint = props.get('IP_Tintable|:') or {}
        effects = []
        for r in d.get('ActiveEffects|A$', []):
            eg = guid_of(r)
            if eg not in self.obj:
                continue
            eo = self.get(eg)
            cls = eo.get('_class|^')
            effects.append({'guid': eg, 'cls': cls, 'data': eo.get('_data|*', {})})
        return {'guid': guid, 'arche': arche, 'fields': fields, 'effects': effects,
                'paint': tint.get('PaintPalette|^'), 'decal': tint.get('DecalPalette|^'),
                'tintable': info.get('tintable'), 'context': d.get('CreateContext|N')}

    def _props(self, guid):
        """The instance's Properties block, created in the game's key order if missing."""
        d = self.get(guid).setdefault('_data|*', {})
        if 'Properties|*' not in d:
            rebuilt = {k: d[k] for k in ('Archetype|$', 'CreateContext|N') if k in d}
            rebuilt['Properties|*'] = {}
            rebuilt.update({k: v for k, v in d.items() if k not in rebuilt})
            d.clear()
            d.update(rebuilt)
        return d['Properties|*']

    def set_instance_prop(self, guid, ip, field, value):
        spec = next((x for x in self.PROPS if x[0] == ip and x[1] == field), None)
        if not spec:
            raise EditError('property %s.%s is not editable' % (ip, field))
        block = self._props(guid).setdefault(ip, {})
        if ip == 'IP_Battery|:' and 'Battery|F' in block and 'BATTERY|F' not in block:
            field = 'Battery|F'
        block[field] = int(value) if spec[2] == 'int' else float(value)
        self.dirty = True

    def repair_instance(self, guid):
        """Full durability / health / fuel, no fatigue, no breaking effects."""
        v = self.instance_view(guid)
        for f in v['fields']:
            if f['ip'] == 'IP_Fatigue|:' and f['stored']:
                self.set_instance_prop(guid, f['ip'], f['field'], 0)
            elif f['ip'] in ('IP_Durability|:', 'IP_Health|:', 'IP_Fuelable|:', 'IP_Battery|:') and f['max']:
                self.set_instance_prop(guid, f['ip'], f['field'], f['max'])
        breaking = set(self.item_info(v['arche']).get('breakEffects') or []) | {
            '/Game/Gameplay/StatusEffects/StatusEffects/Breaking/SE_Breaking.SE_Breaking_C'}
        for e in v['effects']:
            if e['cls'] in breaking:
                self.remove_effect(guid, e['guid'])
        self.dirty = True

    def remove_effect(self, item_guid, effect_guid):
        d = self.get(item_guid)['_data|*']
        effs = d.get('ActiveEffects|A$', [])
        effs[:] = [r for r in effs if guid_of(r) != effect_guid]
        if not effs:
            d.pop('ActiveEffects|A$', None)
        if effect_guid in self.obj:
            self.remove_object(effect_guid)
        self.dirty = True

    def add_effect(self, item_guid, cls):
        info = self.gd.get('effects', {}).get(cls)
        if not info or info.get('upgrade'):
            raise EditError('unknown effect %s' % cls)
        table = self.obj[item_guid][0]
        eg = self.new_guid()
        short = cls.rsplit('.', 1)[-1]
        self.add_object(table, eg, {'_class|^': cls, '_name|N': self.new_name(short),
                                    '_outer|$': '@%s|%sItemInstance' % (item_guid, INV), '_data|*': {}})
        self.get(item_guid)['_data|*'].setdefault('ActiveEffects|A$', []).append('@%s|%s' % (eg, cls))
        self.dirty = True

    def set_tint(self, guid, kind, palette):
        block = self._props(guid).setdefault('IP_Tintable|:', {})
        key = 'PaintPalette|^' if kind == 'paint' else 'DecalPalette|^'
        if palette:
            block[key] = palette
        else:
            block.pop(key, None)
        self.dirty = True

    def slot_info(self, slot_guid):
        return [self.instance_view(guid_of(r)) for r in self.slot_items(slot_guid)]

    # ------------------------------------------------------------ car
    def car_container(self):
        inv = pdtools.inventory_manager(self.save)
        ref = inv.get('Inventory_CarEquipped|$')
        return guid_of(ref)

    def car_state(self):
        cg = self.car_container()
        if not cg:
            return None
        c = self.get(cg)['_data|*']
        slots = []
        for tag, ref in c.get('Slots|MN$', []):
            sg = guid_of(ref)
            if sg not in self.obj:
                continue
            items = self.get(sg).get('_data|*', {}).get('Items|A$', [])
            inst = self.instance_view(guid_of(items[0])) if items and guid_of(items[0]) in self.obj else None
            slots.append({'tag': tag, 'slot': sg, 'item': inst})
        return {'guid': cg, 'slots': slots}

    def compatible_parts(self, tag):
        return [a for a, it in self.gd['items'].items() if tag in (it.get('slots') or [])]

    def set_car_part(self, slot_guid, arche):
        """Swap the part in a car slot. The existing item object is converted in place
        (same GUID, so quest/arrival references stay valid); an empty slot gets a new item."""
        tag = next((t for t, r in self.get(self.car_container())['_data|*'].get('Slots|MN$', [])
                    if guid_of(r) == slot_guid), None)
        if tag is None:
            raise EditError('not a car slot')
        if tag not in (self.item_info(arche).get('slots') or []):
            raise EditError('this part does not fit %s' % tag)
        items = self.slot_items(slot_guid)
        if not items:
            items.append(self.new_item(arche, self.obj[slot_guid][0]))
        else:
            g = guid_of(items[0])
            d = self.get(g)['_data|*']
            for r in list(d.get('ActiveEffects|A$', [])):
                self.remove_effect(g, guid_of(r))
            for k in list(d):
                if k not in ('Archetype|$', 'CreateContext|N'):
                    d.pop(k)
            d['Archetype|$'] = '*%s|%s' % (arche, ARCH_CLASS)
        self.dirty = True

    def repair_car(self):
        st = self.car_state()
        for s in st['slots']:
            if s['item']:
                self.repair_instance(s['item']['guid'])

    # ------------------------------------------------------------ all containers
    def _owner(self, o):
        og = guid_of(o.get('_outer|$'))
        if not og or og not in self.obj:
            return None, None
        oo = self.get(og)
        if oo.get('_class|^', '').endswith('.ItemInstance'):
            return og, oo
        return og, oo

    def containers_view(self):
        """Every editable container, classified the way the game groups them."""
        named = {g: n for n, g in pdtools.containers(self.save)}
        car_items = set()
        car = self.car_container()
        if car:
            for _, r in self.get(car)['_data|*'].get('Slots|MN$', []):
                sg = guid_of(r)
                if sg in self.obj:
                    car_items.update(guid_of(x) for x in self.slot_items(sg))
        out = []
        for g, (t, o) in list(self.obj.items()):
            cls = o.get('_class|^', '') if isinstance(o, dict) else ''
            if not (cls.endswith('.ItemContainer') or cls.endswith('.NamedItemContainer')) or g == car:
                continue
            d = o.get('_data|*', {})
            og, owner = self._owner(o)
            ocls = (owner or {}).get('_class|^', '')
            if ocls.endswith('BP_ProgressionManager_C'):
                continue          # level/world state, not player storage
            lay, L = self.container_layout(o)
            lid = (L or {}).get('id', '')
            if 'Lootable' in lid:
                continue
            owner_arche = asset_of((owner or {}).get('_data|*', {}).get('Archetype|$')) if ocls.endswith('.ItemInstance') else None
            owner_id = self.item_info(owner_arche)['id'] if owner_arche else ''
            if owner_id.startswith('IA_Template'):
                continue          # abandoned cars in the world
            station = ((owner or {}).get('_data|*', {}).get('Properties|*', {}).get('IP_Station|:', {}) or {}).get('StationTag|T')
            key = named.get(g, '')
            if key.startswith('Inventories_Garage['):
                station = key[len('Inventories_Garage['):-1]
            # group
            if key in ('Inventory_Trunk', 'Inventory_Player', 'Inventory_PlayerHand') or 'Trunk_Storage' in ocls:
                group = 'player'
            elif og in car_items:
                group = 'car'
            elif 'InventoryParts' in owner_id or 'Parts_Transfer' in lid:
                group = 'parts'
            elif key in ('Inventory_Tubes_In', 'Inventory_Tubes_Out', 'Inventory_GarageTransfer'):
                group = 'tubes'
            elif station and 'Mount' in station:
                group = 'mounts'
            elif station and '.Inventory.' in station:
                group = 'storage'
            elif key in ('Inventory_GarageStations', 'Inventory_AnchorStorage', 'Inventory_CarEquipped', 'ShoppingList'):
                continue
            else:
                group = 'garage'
            c = {'guid': g, 'key': key, 'layout': lid, 'group': group, 'station': station, 'owner': owner_id}
            if cls.endswith('NamedItemContainer'):
                c['kind'] = 'named'
                c['slots'] = []
                for tag, r in d.get('Slots|MN$', []):
                    sg = guid_of(r)
                    if sg not in self.obj:
                        continue
                    sd = self.get(sg).get('_data|*', {})
                    its = sd.get('Items|A$', [])
                    arche = asset_of(self.get(guid_of(its[0]))['_data|*'].get('Archetype|$')) if its else None
                    c['slots'].append({'guid': sg, 'tag': tag, 'arche': arche, 'count': len(its),
                                       'cap': sd.get('Capacity|I', 1)})
            elif L and L['class'] == 'ItemTileLayout' and L.get('w'):
                c['kind'] = 'grid'
                c['w'], c['h'] = L['w'], L['h']
                c['blocked'] = self.blocked_cells(L)
                c['slots'] = []
                for r in d.get('Slots|A$', []):
                    sg = guid_of(r)
                    if sg not in self.obj:
                        continue
                    sd = self.get(sg).get('_data|*', {})
                    if 'Location|:' not in sd:
                        continue
                    arche = asset_of(sd.get('FilterItemType|$'))
                    x, y, w, h = self.tile_rect(sd, self.item_info(arche)['size'])
                    c['slots'].append({'guid': sg, 'arche': arche, 'x': x, 'y': y, 'w': w, 'h': h,
                                       'rot': bool(sd.get('bRotated|B')), 'count': len(sd.get('Items|A$', []))})
            elif L and L['class'] == 'ItemListLayout':
                c['kind'] = 'list'
                c['totals'] = {a: sum(len(self.slot_items(x)) for x in ss) for a, ss in self.list_totals(g).items()}
                c['slotsCount'] = len(d.get('Slots|A$', []))
            else:
                continue
            out.append(c)
        order = {'player': 0, 'car': 1, 'storage': 2, 'parts': 3, 'tubes': 4, 'garage': 5, 'mounts': 6}
        out.sort(key=lambda c: (order[c['group']], c['key'] or c['station'] or c['layout']))
        return out

    def named_set(self, slot_guid, arche, count=1):
        """Put `count` items of `arche` into a named/plain ItemSlot (None empties it)."""
        items = self.slot_items(slot_guid)
        for r in list(items):
            g = guid_of(r)
            if self.external_refs(g):
                raise EditError('the item in this slot is referenced elsewhere; change it in game')
        for r in list(items):
            items.remove(r)
            self.remove_object(guid_of(r))
        if arche:
            table = self.obj[slot_guid][0]
            tmpl = self.find_template(arche)
            for _ in range(max(1, count)):
                items.append(self.new_item(arche, table, tmpl))
        self.dirty = True

    # ------------------------------------------------------------ research / upgrades
    GRAPH_PATH = '/Game/Gameplay/Inventory/Items/RecipeResearchGraph.RecipeResearchGraph'

    def unlock_state(self):
        inv = pdtools.inventory_manager(self.save)
        return self.get(guid_of(inv['UnlockState|$']))['_data|*']

    def node_ref(self, node_id):
        n = self.gd['graph']['nodes'][node_id]
        cls = 'GenericGraphRecipeNode' if n['kind'] == 'recipe' else 'GenericGraphUpgradeNode'
        return '*%s:%s|/Script/PenDriverPro.%s' % (self.GRAPH_PATH, node_id, cls)

    def installed_upgrades(self):
        """upgrade class -> host station item guid"""
        out = {}
        for g, (_, o) in self.obj.items():
            c = o.get('_class|^', '') if isinstance(o, dict) else ''
            if '/UP_Garage' in c:
                out.setdefault(c, guid_of(o.get('_outer|$')))
        return out

    def research_view(self):
        u = self.unlock_state()
        node_of = lambda r: r.split(':')[-1].split('|')[0]
        inst = self.installed_upgrades()
        installed = [n for n, v in self.gd['graph']['nodes'].items() if v.get('upgrade') in inst]
        installed += self._car_upgrades_installed()
        return {'unlocked': [node_of(r) for r in u.get('UnlockedNodes|A$', [])],
                'purchased': [node_of(r) for r in u.get('PurchasedNodes|A$', [])],
                'installed': installed}

    def _car_upgrades_installed(self):
        """IU_* car upgrades are 'in use' when their rack / trunk tier item sits in a car slot."""
        car = self.car_state()
        if not car:
            return []
        filled = {s['tag'] for s in car['slots'] if s['item'] and not self.item_info(s['item']['arche'])['id'].endswith('_Empty')}
        racks = lambda word: sum(1 for t in filled if t.endswith('_Rack') and word in t)
        counts = {'Side': racks('Window'), 'Top': racks('Roof'), 'Backseat': racks('BackSeat')}
        ordinal = {'': 1, '_2nd': 2, '_3rd': 3, '_4th': 4}
        out = []
        for n, v in self.gd['graph']['nodes'].items():
            up = re.sub(r'_C$', '', (v.get('upgrade') or '').rsplit('.', 1)[-1])
            if up.startswith('IU_CarUpgrade_'):
                rest = up[len('IU_CarUpgrade_'):]
                kind, _, suffix = rest.partition('_')
                if counts.get(kind, 0) >= ordinal.get('_' + suffix if suffix else '', 99):
                    out.append(n)
            elif up == 'IU_Trunk_Storage_Tier2' and filled & {'Car.Equip.Internal.InventoryStorageTierTwo', 'Car.Equip.Internal.InventoryStorageTierThree'}:
                out.append(n)
            elif up == 'IU_Trunk_Storage_Tier3' and 'Car.Equip.Internal.InventoryStorageTierThree' in filled:
                out.append(n)
            elif up == 'IU_Trunk_Crafting_Tier2' and 'Car.Equip.Internal.Crafting_TierTwo' in filled:
                out.append(n)
        return out

    def set_research(self, node_id, state):
        """state: 'locked' | 'available' | 'researched'"""
        if node_id not in self.gd['graph']['nodes']:
            raise EditError('unknown node %s' % node_id)
        u = self.unlock_state()
        ref = self.node_ref(node_id)
        un = u.setdefault('UnlockedNodes|A$', [])
        pu = u.setdefault('PurchasedNodes|A$', [])
        node_of = lambda r: r.split(':')[-1].split('|')[0]
        un[:] = [r for r in un if node_of(r) != node_id]
        pu[:] = [r for r in pu if node_of(r) != node_id]
        if state in ('available', 'researched'):
            un.append(ref)
        if state == 'researched':
            pu.append(ref)
        self.dirty = True

    @staticmethod
    def upgrade_family(ucls):
        """'.../UP_Garage_InventoryExpansion_Tier2_2nd.X_C' -> ('inventoryexpansion', '_2nd')"""
        import re
        n = ucls.rsplit('.', 1)[-1]
        n = re.sub(r'_C$', '', n).replace('UP_Garage_', '')
        m = re.search(r'_(2nd|3rd|4th)$', n)
        ordinal = m.group(0) if m else ''
        n = n[:len(n) - len(ordinal)]
        n = re.sub(r'(_Install|_Tier\d+|_T\d+_Install|_T\d+)$', '', n)
        n = re.sub(r'_Install$', '', n)
        return n.lower(), ordinal

    def upgrade_host(self, ucls):
        """Station item an upgrade effect belongs on, or None when it cannot be decided safely."""
        fam, ordn = self.upgrade_family(ucls)
        same = lambda f: f == fam or f.startswith(fam) or fam.startswith(f)
        by_item = {}
        for c, g in self.installed_upgrades().items():
            by_item.setdefault(g, []).append(self.upgrade_family(c))
        exact = [g for g, fams in by_item.items() if any(same(f) and o == ordn for f, o in fams)]
        if len(exact) == 1:
            return exact[0]
        # station archetypes that carry this family somewhere
        family_arches = {asset_of(self.get(g)['_data|*'].get('Archetype|$'))
                         for g, fams in by_item.items() if any(same(f) for f, _ in fams)}
        stations = []
        for g, (_, o) in self.obj.items():
            d = o.get('_data|*') if isinstance(o, dict) else None
            if not d or o.get('_class|^') != INV + 'ItemInstance':
                continue
            a = asset_of(d.get('Archetype|$'))
            iid = self.item_info(a)['id'].lower()
            if not iid.startswith('ia_garage_'):
                continue
            if a in family_arches or fam in iid.replace('_', ''):
                if not any(same(f) for f, _ in by_item.get(g, [])):
                    stations.append(g)
        return stations[0] if len(stations) == 1 else None

    def set_installed(self, node_id, on):
        n = self.gd['graph']['nodes'].get(node_id)
        if not n or n['kind'] != 'upgrade' or '/UP_Garage' not in n['upgrade']:
            raise EditError('only garage station upgrades can be installed here')
        ucls = n['upgrade']
        inst = self.installed_upgrades()
        if on:
            if ucls in inst:
                return
            host = self.upgrade_host(ucls)
            if not host:
                raise EditError('cannot tell which garage station this upgrade belongs to (not built yet, or several candidates); build it in the game first')
            table = self.obj[host][0]
            eg = self.new_guid()
            self.add_object(table, eg, {'_class|^': ucls, '_name|N': self.new_name(ucls.rsplit('.', 1)[-1]),
                                        '_outer|$': '@%s|%sItemInstance' % (host, INV), '_data|*': {}})
            self.get(host)['_data|*'].setdefault('ActiveEffects|A$', []).append('@%s|%s' % (eg, ucls))
            self.set_research(node_id, 'researched')
        else:
            for g, (_, o) in list(self.obj.items()):
                if isinstance(o, dict) and o.get('_class|^') == ucls:
                    self.remove_effect(guid_of(o['_outer|$']), g)
        self.dirty = True

    # ------------------------------------------------------------ logbook (codex) and whiteboard
    def logbook_guid(self):
        for g, (_, o) in self.obj.items():
            if isinstance(o, dict) and o.get('_class|^') == INV + 'LogBook':
                return g
        return None

    def whiteboard(self):
        """The progression whiteboard: map gameplay tag -> float (stats, scans, world state)."""
        best = None
        for g, (_, o) in self.obj.items():
            if isinstance(o, dict) and o.get('_class|^', '').endswith('.Whiteboard'):
                ow = self.obj.get(guid_of(o.get('_outer|$')), (0, {}))[1]
                if ow.get('_class|^', '').endswith('BP_ProgressionManager_C'):
                    e = o.setdefault('_data|*', {}).setdefault('Entries|MTF', [])
                    if best is None or len(e) > len(best):
                        best = e
        return best

    def logbook_entries(self):
        lg = self.logbook_guid()
        if not lg:
            return {}
        out = {}
        for r in self.get(lg)['_data|*'].get('Entries|A$', []):
            g = guid_of(r)
            if g not in self.obj:
                continue
            d = self.get(g)['_data|*']
            out[asset_of(d.get('DataObject|$'))] = g
        return out

    def logbook_view(self):
        out = []
        for path, g in self.logbook_entries().items():
            d = self.get(g)['_data|*']
            out.append({'path': path, 'ts': d.get('Timestamp|D'), 'ack': bool(d.get('Acknowledged|B')),
                        'img': 'CompressedImageData|#' in d})
        return out

    def _wb_set(self, tag, value):
        wb = self.whiteboard()
        if wb is None or not tag:
            return
        for pair in wb:
            if pair[0] == tag:
                if value is None:
                    wb.remove(pair)
                else:
                    pair[1] = float(value)
                return
        if value is not None:
            wb.append([tag, float(value)])

    # whiteboard statistics duplicated in META (the load-menu preview)
    META_MIRROR = {'WB.Statistics.TotalRuns': ('RunCount|I', int), 'WB.Statistics.CarDriveMileage': ('MilesDriven|F', float)}

    def set_whiteboard(self, tag, value):
        self._wb_set(tag, value)
        mirror = self.META_MIRROR.get(tag)
        if mirror and value is not None and self.save.docs.get('META'):
            meta = self.save.root('META').get('_data|:', {})
            if mirror[0] in meta:
                meta[mirror[0]] = mirror[1](value)
        self.dirty = True

    def set_log(self, path, on):
        info = self.gd.get('logbook', {}).get('entries', {}).get(path)
        if not info:
            raise EditError('unknown logbook entry %s' % path)
        lg = self.logbook_guid()
        if not lg:
            raise EditError('this save has no logbook yet')
        existing = self.logbook_entries()
        if on and path not in existing:
            import datetime
            now = datetime.datetime.now()
            ts = '%04d.%02d.%02d-%02d.%02d.%02d.%07d' % (now.year, now.month, now.day, now.hour, now.minute,
                                                       now.second, now.microsecond * 10)
            g = self.new_guid()
            self.add_object(self.obj[lg][0], g, {
                '_class|^': INV + 'LogBookEntry', '_name|N': self.new_name('LogBookEntry'),
                '_outer|$': '@%s|%sLogBook' % (lg, INV),
                '_data|*': {'DataObject|$': '*%s|%s' % (path, info['cls']), 'Timestamp|D': ts, 'Acknowledged|B': False}})
            self.get(lg)['_data|*'].setdefault('Entries|A$', []).append('@%s|%sLogBookEntry' % (g, INV))
            if info.get('unlockTag'):
                wb = dict((k, v) for k, v in (self.whiteboard() or []))
                if not wb.get(info['unlockTag']):
                    self._wb_set(info['unlockTag'], 1)
        elif not on and path in existing:
            g = existing[path]
            ents = self.get(lg)['_data|*']['Entries|A$']
            ents[:] = [r for r in ents if guid_of(r) != g]
            self.remove_object(g)
            if info.get('unlockTag'):
                self._wb_set(info['unlockTag'], None)
        self.dirty = True

    def set_log_ack(self, path, on):
        g = self.logbook_entries().get(path)
        if not g:
            raise EditError('entry is not unlocked')
        self.get(g)['_data|*']['Acknowledged|B'] = bool(on)
        self.dirty = True

    def set_log_many(self, paths, on):
        for p in paths:
            self.set_log(p, on)

    # ------------------------------------------------------------ car quirks
    QUIRK_SE = '/Game/Gameplay/StatusEffects/Quirks/SE_Quirk_MixAndMatch.SE_Quirk_MixAndMatch_C'
    FIX_MECH = '/Game/Gameplay/Inventory/Items/Tools/FixStatusEffect/FixMechanical/IA_Tool_Target_FixMechanical.IA_Tool_Target_FixMechanical'
    FIX_ELEC = '/Game/Gameplay/Inventory/Items/Tools/FixStatusEffect/FixElectronic/IA_Tool_Target_FixElectronics.IA_Tool_Target_FixElectronics'

    def se_manager(self):
        for g, o in pdtools.objects_of_class(self.save, 'BP_StatusEffectManager_C'):
            return o.setdefault('_data|*', {})
        raise EditError('status effect manager not found')

    def chassis(self):
        car = self.car_state()
        for s in (car or {}).get('slots', []):
            if s['tag'] == 'Car.Equip.Internal.Soul' and s['item']:
                return s['item']['guid']
        raise EditError('car chassis (Soul) not found')

    def quirks_view(self):
        try:
            mgr = self.se_manager()
        except EditError:
            return None
        active = []
        for r in mgr.get('CarQuirks|A$', []):
            g = guid_of(r)
            if g not in self.obj:
                continue
            d = self.get(g).get('_data|*', {})
            qc = self.obj.get(guid_of(d.get('QuirkCondition|$')), (0, {}))[1]
            qb = self.obj.get(guid_of(d.get('QuirkBehavior|$')), (0, {}))[1]
            active.append({'guid': g, 'condition': qc.get('_class|^'), 'behavior': qb.get('_class|^'),
                           'invocations': d.get('Invocations|F', 0), 'diagnosed': bool(d.get('Diagnosed|B')),
                           'cure': [[asset_of(k), v] for k, v in d.get('CureIngredients|M$I', [])]})
        grave = [{'condition': k.get('Condition|^'), 'behavior': k.get('Behavior|^'), 'invocations': v.get('Invocations|F', 0),
                  'revivals': v.get('Revivals|I', 0)} for k, v in mgr.get('GraveyardQuirks|M::', [])]
        flags = {k.split('|')[0]: v for k, v in mgr.items() if k.endswith('|B')}
        return {'active': active, 'graveyard': grave, 'flags': flags}

    def _quirk_stats(self, d_active=0, d_cured=0):
        wb = dict((k, v) for k, v in (self.whiteboard() or []))
        if d_active:
            self._wb_set('WB.Statistics.Quirks.QuirksActive', max(0, wb.get('WB.Statistics.Quirks.QuirksActive', 0) + d_active))
        if d_cured:
            self._wb_set('WB.Statistics.Quirks.QuirksCured', max(0, wb.get('WB.Statistics.Quirks.QuirksCured', 0) + d_cured))

    def quirk_diagnose(self, se_guid, on):
        d = self.get(se_guid)['_data|*']
        if on:
            d['Diagnosed|B'] = True
            d['InvocationsWhenDiagnosed|F'] = float(d.get('Invocations|F', 0))
            known = [[1, True], [2, True]]
            for key in ('QuirkCondition|$', 'QuirkBehavior|$'):
                sub = self.obj.get(guid_of(d.get(key)), (0, None))[1]
                if sub is not None:
                    sd = sub.setdefault('_data|*', {})
                    sd['PartKnownCategories|MIB'] = [list(x) for x in known]
                    sd['TypeKnownCategories|MIB'] = [list(x) for x in known]
        else:
            d.pop('Diagnosed|B', None)
            d.pop('InvocationsWhenDiagnosed|F', None)
        self.dirty = True

    def quirk_cure(self, se_guid):
        mgr = self.se_manager()
        d = self.get(se_guid)['_data|*']
        qc = self.obj.get(guid_of(d.get('QuirkCondition|$')), (0, {}))[1].get('_class|^')
        qb = self.obj.get(guid_of(d.get('QuirkBehavior|$')), (0, {}))[1].get('_class|^')
        mgr['CarQuirks|A$'] = [r for r in mgr.get('CarQuirks|A$', []) if guid_of(r) != se_guid]
        host = guid_of(self.get(se_guid).get('_outer|$'))
        if host in self.obj:
            self.remove_effect(host, se_guid)
        elif se_guid in self.obj:
            self.remove_object(se_guid)
        if qc and qb:
            grave = mgr.setdefault('GraveyardQuirks|M::', [])
            entry = next((e for e in grave if e[0].get('Condition|^') == qc and e[0].get('Behavior|^') == qb), None)
            if entry:
                entry[1]['Invocations|F'] = float(entry[1].get('Invocations|F', 0)) + float(d.get('Invocations|F', 0))
            else:
                grave.append([{'Condition|^': qc, 'Behavior|^': qb},
                              {'Cycled|B': False, 'Invocations|F': float(d.get('Invocations|F', 0)), 'Revivals|I': 0}])
        self._quirk_stats(-1, +1)
        self.dirty = True

    def quirk_set_cure(self, se_guid, cure):
        d = self.get(se_guid)['_data|*']
        d['CureIngredients|M$I'] = [['*%s|%s' % (a, ARCH_CLASS), int(n)] for a, n in cure if int(n) > 0]
        self.dirty = True

    def quirk_add(self, qc_cls, qb_cls, diagnosed=False):
        q = self.gd.get('quirks', {})
        if qc_cls not in q.get('conditions', {}) or qb_cls not in q.get('behaviors', {}):
            raise EditError('unknown quirk condition/behavior')
        soul = self.chassis()
        table = self.obj[soul][0]
        se, cg, bg = self.new_guid(), self.new_guid(), self.new_guid()
        se_ref = '@%s|%s' % (se, self.QUIRK_SE)
        elec = any(w in (q['behaviors'][qb_cls].get('part') or '') + (q['conditions'][qc_cls].get('part') or '')
                   for w in ('Radio', 'Headlights', 'Dash', 'Battery', 'InteriorLights', 'Wipers', 'Horn', 'Ability'))
        data = {'QuirkCondition|$': '@%s|%s' % (cg, qc_cls), 'QuirkBehavior|$': '@%s|%s' % (bg, qb_cls),
                'CureIngredients|M$I': [['*%s|%s' % (self.FIX_ELEC if elec else self.FIX_MECH, ARCH_CLASS), 1]]}
        self.add_object(table, se, {'_class|^': self.QUIRK_SE, '_name|N': self.new_name('SE_Quirk_MixAndMatch_C'),
                                    '_outer|$': '@%s|%sItemInstance' % (soul, INV), '_data|*': data})
        self.add_object(table, cg, {'_class|^': qc_cls, '_name|N': self.new_name(qc_cls.rsplit('.', 1)[-1]),
                                    '_outer|$': se_ref, '_data|*': {'QuirkOwner|$': se_ref}})
        self.add_object(table, bg, {'_class|^': qb_cls, '_name|N': self.new_name(qb_cls.rsplit('.', 1)[-1]),
                                    '_outer|$': se_ref, '_data|*': {}})
        self.get(soul)['_data|*'].setdefault('ActiveEffects|A$', []).append(se_ref)
        self.se_manager().setdefault('CarQuirks|A$', []).append(se_ref)
        if diagnosed:
            self.quirk_diagnose(se, True)
        self._quirk_stats(+1, 0)
        self.dirty = True

    def quirk_grave_remove(self, qc_cls, qb_cls):
        mgr = self.se_manager()
        grave = mgr.get('GraveyardQuirks|M::', [])
        grave[:] = [e for e in grave if not (e[0].get('Condition|^') == qc_cls and e[0].get('Behavior|^') == qb_cls)]
        self.dirty = True

    def quirk_flag(self, name, on):
        self.se_manager()[name + '|B'] = bool(on)
        self.dirty = True

    # ------------------------------------------------------------ simple values
    def set_currency(self, arche, value):
        for pair in pdtools.currencies(self.save):
            if asset_of(pair[0]) == arche:
                pair[1] = int(value)
                self.dirty = True
                return
        pdtools.currencies(self.save).append(['*%s|%sCurrencyArchetype' % (arche, INV), int(value)])
        self.dirty = True

    def set_resource(self, name, value):
        for pair in pdtools.resources(self.save):
            if pair[0] == name:
                pair[1] = float(value)
                self.dirty = True
                return
        raise EditError('unknown resource %s' % name)

    def opts_data(self):
        o = self.save.root('OPTS')['_objects|*']
        return next(iter(o.values()))['_data|*']

    def set_settings(self, preset, overrides):
        d = self.opts_data()
        if preset is not None:
            d['ActiveGamePresetName|S'] = preset
        if overrides is not None:
            name = d['ActiveGamePresetName|S']
            us = d.setdefault('UserSettings|MS:', [])
            entry = next((e for e in us if e[0] == name), None)
            if not overrides:
                if entry:
                    us.remove(entry)
            else:
                if entry is None:
                    entry = [name, {'Settings|MN:': []}]
                    us.append(entry)
                entry[1]['Settings|MN:'] = [[k, {'ValueString|S': str(v)}] for k, v in overrides.items()]
        self.dirty = True

    # ------------------------------------------------------------ state for the UI
    def state(self):
        gd = self.gd
        meta = {}
        if self.save.docs.get('META'):
            m = self.save.root('META').get('_data|:', {})
            meta = {'lastPlayed': m.get('LastPlayed|D'), 'playtime': m.get('Playtime|I'), 'level': m.get('Level|S'),
                    'runs': m.get('RunCount|I'), 'miles': m.get('MilesDriven|F'),
                    'mission': pdtools.short_asset(m.get('ActiveMission|$')),
                    'build': (m.get('BuildHistory|AS') or [None])[-1]}
        cur = [{'arche': asset_of(k), 'value': v} for k, v in pdtools.currencies(self.save)]
        res = [{'name': k, 'value': v} for k, v in pdtools.resources(self.save)]
        conts = []
        for label, g in pdtools.containers(self.save):
            cont = self.get(g)
            lay, L = self.container_layout(cont)
            if not L:
                continue
            c = {'guid': g, 'key': label, 'layout': L['id'], 'kind': None}
            if L['class'] == 'ItemTileLayout' and L.get('w'):
                c['kind'] = 'grid'
                c['w'], c['h'] = L['w'], L['h']
                c['blocked'] = self.blocked_cells(L)
                c['slots'] = []
                for r in cont['_data|*'].get('Slots|A$', []):
                    sg = guid_of(r)
                    sd = self.get(sg).get('_data|*', {})
                    if 'Location|:' not in sd:
                        continue
                    arche = asset_of(sd.get('FilterItemType|$'))
                    x, y, w, h = self.tile_rect(sd, self.item_info(arche)['size'])
                    c['slots'].append({'guid': sg, 'arche': arche, 'x': x, 'y': y, 'w': w, 'h': h,
                                       'rot': bool(sd.get('bRotated|B')), 'count': len(sd.get('Items|A$', []))})
            elif L['class'] == 'ItemListLayout':
                c['kind'] = 'list'
                c['totals'] = {a: sum(len(self.slot_items(s)) for s in ss) for a, ss in self.list_totals(g).items()}
                c['slotsCount'] = len(cont['_data|*'].get('Slots|A$', []))
            else:
                continue
            conts.append(c)
        settings = {}
        if self.save.docs.get('OPTS'):
            d = self.opts_data()
            name = d.get('ActiveGamePresetName|S')
            ov = {}
            for pn, st in d.get('UserSettings|MS:', []):
                if pn == name:
                    ov = {k: v.get('ValueString|S') for k, v in st.get('Settings|MN:', [])}
            settings = {'preset': name, 'overrides': ov}
        return {'path': self.path, 'dirty': self.dirty, 'meta': meta, 'currencies': cur, 'resources': res,
                'containers': conts, 'settings': settings, 'car': self.car_state(),
                'allContainers': self.containers_view(), 'research': self.research_view(),
                'logbook': self.logbook_view(), 'whiteboard': dict((k, v) for k, v in (self.whiteboard() or [])),
                'quirks': self.quirks_view()}

    def write(self):
        bak = self.save.save()
        self.dirty = False
        return bak
