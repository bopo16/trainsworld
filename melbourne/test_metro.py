import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from metro_network import join_tunnel, service_ids

class MetroTests(unittest.TestCase):
    def test_calendar_additions_and_removals(self):
        cal = pd.DataFrame([{'service_id':'a','wednesday':'1','start_date':'20261101','end_date':'20261130'},
                            {'service_id':'b','wednesday':'1','start_date':'20261101','end_date':'20261130'}])
        exceptions = pd.DataFrame([{'service_id':'a','date':'20261118','exception_type':'2'},
                                   {'service_id':'c','date':'20261118','exception_type':'1'}])
        self.assertEqual(service_ids(cal, exceptions, dt.date(2026,11,18)), {'b','c'})

    def test_tunnel_join_connects_both_routes_and_keeps_one_platform(self):
        def station(name): return {'name':name,'platform':160,'key':'town' if name == 'Town Hall' else name}
        nodes = [{'xy':[0,0],'level':-3,'station':station('Town Hall')},
                 {'xy':[0,-1000],'level':-3,'station':station('Sunbury')},
                 {'xy':[0,100],'level':-3,'station':station('Town Hall')},
                 {'xy':[0,1000],'level':-3,'station':station('Cranbourne')}]
        edges = [{'a':0,'b':1,'lead_a':[0,-80],'lead_b':[0,-920],'line':[]},
                 {'a':2,'b':3,'lead_a':[0,180],'lead_b':[0,920],'line':[]}]
        def service(name): return {'name':name,'stops':[0,1], 't0':[[10,0] for _ in range(3)], 't1':[[0,10] for _ in range(3)], 'tph':[2,2,1]}
        net = {'lines':[service('Sunbury'),service('Cranbourne'),service('Pakenham')]}
        model = {'nodes':nodes,'edges':edges,'lines':[{'stops':[0,1], 'path':[0]}, {'stops':[2,3], 'path':[2]}, {'stops':[2,3], 'path':[2]}]}
        geo = {'lines':[{}, {}, {}]}
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name, data in [('mel_real.json',net),('mel_real_corridors.json',{'model':model}),('mel_real_geom.json',geo)]:
                (d/name).write_text(json.dumps(data))
            join_tunnel(d)
            n=json.loads((d/'mel_real.json').read_text()); m=json.loads((d/'mel_real_corridors.json').read_text())['model']
            self.assertEqual([l['name'] for l in n['lines']], ['Cranbourne – Sunbury','Pakenham – Sunbury'])
            self.assertEqual(m['lines'][0]['path'], [1,2])
            self.assertEqual(m['edges'][1]['a'],0)
            self.assertEqual(m['lines'][0]['stops'],[1,0,3])
            self.assertIsNone(m['nodes'][2]['station'])
            self.assertEqual(len(m['edges']),2)

if __name__ == '__main__': unittest.main()
