"""Codec tests on synthetic data (no game files or real saves needed)."""
import base64
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pdsave  # noqa: E402
import pdtools  # noqa: E402

TEXT_STRINGTABLE = base64.b64encode(
    struct.pack('<Ib', 0, 11) + b'\x06\x00\x00\x00ST_UI\x00' + b'\x04\x00\x00\x00key\x00').decode()


def sample_doc():
    return {'header': [6, 3], 'type': '*', 'root': {
        'flag|B': True,
        'count|I': -42,
        'big|E': 1 << 40,
        'speed|F': 1.5,
        'name|S': 'Привет, Zone',       # forces UTF-16 FString
        'tag|T': 'WB.Statistics.TotalRuns',
        'fname|N': 'ITEMCONTEXT1',
        'when|D': '2026.10.21-19.43.42.6350000',
        'guid|G': '58E30CF0488513545EE62D9C03A4F69B',
        'rot|R': [0.0, 180.0, 0.0],
        'color|L': [1.0, 0.5, 0.25, 1.0],
        'fcolor|C': [1, 2, 3, 255],
        'xf|Z': {'rot': [0.0, 0.0, 0.0, 1.0], 'loc': [1.0, 2.0, 3.0], 'scale': [1.0, 1.0, 1.0]},
        'text|X': TEXT_STRINGTABLE,
        'blob|#': base64.b64encode(b'\xff\xd8 jpeg').decode(),
        'cls|^': '/Game/X.X_C',
        'soft|@': '/Game/Mesh.Mesh',
        'softc|~': '/Game/Cls.Cls_C',
        'null|$': None,
        'obj|$': '@58E30CF0488513545EE62D9C03A4F69B|/Script/PenDriverInventory.ItemInstance',
        'named|$': '$__GAMEINSTANCE__|/Script/PenDriverPro.DrivingGameInstance',
        'asset|$': '*/Game/Items/IA_X.IA_X|/Script/PenDriverInventory.ItemArchetype',
        'arr|AI': [1, 2, 3],
        'map|MNF': [['Fuel', 75.0], ['CarHealth', 794.5]],
        'nested|:': {'X|I': 1, 'Y|I': 2},
        '_objects|*': {'58E30CF0488513545EE62D9C03A4F69B|>': {
            '_class|^': '/Script/PenDriverInventory.ItemInstance', '_name|N': 'ItemInstance_1',
            '_outer|$': None, '_data|*': {'Archetype|$': '*/Game/Items/IA_X.IA_X|/Script/PenDriverInventory.ItemArchetype'}}},
    }}


class CodecTest(unittest.TestCase):
    def test_payload_roundtrip(self):
        doc = sample_doc()
        data = pdsave.encode_payload(doc)
        back = pdsave.decode_payload(data)
        self.assertEqual(back, doc)
        self.assertEqual(pdsave.encode_payload(back), data)

    def test_lz4_roundtrip(self):
        rnd = random.Random(1)
        for blob in (b'', b'a', b'abc' * 5000, bytes(rnd.getrandbits(8) for _ in range(20000)),
                     pdsave.encode_payload(sample_doc()) * 20):
            packed = pdsave.lz4_compress(blob)
            self.assertEqual(pdsave.lz4_decompress(packed, len(blob)), blob)

    def test_container_formats(self):
        payload = pdsave.encode_payload(sample_doc())
        for fmt in (pdsave.FMT_BINARY, pdsave.FMT_LZ4):
            sf = pdsave.SaveFile()
            sf.sections = [pdsave.Section('OPTS', pdsave.FMT_BINARY, payload),
                           pdsave.Section('GAME', fmt, payload), pdsave.Section('CHKP', pdsave.FMT_BINARY, b'')]
            raw = sf.build()
            self.assertEqual(raw[:4], b'SAVC')
            again = pdsave.SaveFile.parse(raw)
            self.assertEqual([s.tag for s in again.sections], ['OPTS', 'GAME', 'CHKP'])
            self.assertEqual(again.section('GAME').fmt, fmt)
            self.assertEqual(again.section('GAME').data, payload)
            # untouched sections are written back byte-identically
            self.assertEqual(again.build(), raw)

    def test_datetime(self):
        for s in ('0001.01.01-00.00.00.0000000', '2024.05.25-14.57.31.4100000', '2026.10.21-19.43.42.6350000'):
            self.assertEqual(pdsave.ticks_to_str(pdsave.str_to_ticks(s)), s)

    def test_paths_and_set(self):
        sf = pdsave.SaveFile()
        sf.sections = [pdsave.Section('GAME', pdsave.FMT_LZ4, pdsave.encode_payload(sample_doc()))]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tmp_test.sav')
        try:
            with open(path, 'wb') as f:
                f.write(sf.build())
            s = pdtools.Save(path)
            old, new, t = pdtools.set_value(s, 'GAME/map/#0', '60')
            self.assertEqual((old, new, t), (75.0, 60.0, 'F'))
            pdtools.set_value(s, 'GAME/nested/X', '5')
            bak = s.save(backup=True)
            self.assertTrue(bak and os.path.exists(bak))
            s2 = pdtools.Save(path)
            self.assertEqual(s2.root('GAME')['map|MNF'][0][1], 60.0)
            self.assertEqual(s2.root('GAME')['nested|:']['X|I'], 5)
            hits = pdtools.find(s2, 'TotalRuns')
            self.assertTrue(any(p.endswith('/tag') for p, _, _ in hits))
        finally:
            for p in [path] + [os.path.join(os.path.dirname(path), x) for x in os.listdir(os.path.dirname(path))
                               if x.startswith('_tmp_test.sav')]:
                if os.path.exists(p):
                    os.remove(p)


if __name__ == '__main__':
    unittest.main()
