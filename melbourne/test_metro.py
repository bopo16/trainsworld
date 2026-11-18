import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from metro_network import join_tunnel, service_ids, simplify_services, ordered_shape, single_track_stony_point
from loop_geometry import merge_redundant_platforms, remove_short_station_joints, separate_event_tracks, merge_identical_edges

class MetroTests(unittest.TestCase):
    def test_identical_edges_are_shared_without_changing_direction(self):
        model={'edges':[{'a':0,'b':1,'line':[]}, {'a':0,'b':1,'line':[]}, {'a':0,'b':1,'line':[[5,2]]}],
               'lines':[{'path':[0]}, {'path':[3]}, {'path':[4]}]}
        merge_identical_edges(model)
        self.assertEqual([s['path'] for s in model['lines']],[[0],[1],[4]])

    def test_tram_graph_filters_rail_and_allows_street_corner(self):
        import numpy as np
        import realroute
        data={'lon':np.array([0,0,0,.001,0,.001]), 'lat':np.array([0,.001,.001,.001,0,.001]),
              'off':np.array([0,2,4,6]), 'a':np.array([0,1,0]), 'b':np.array([1,2,2]),
              'kind':np.array([3,3,0]), 'flags':np.array([0,0,0])}
        with patch.object(realroute, 'read', return_value=data):
            graph=realroute.Graph('unused',(0,0),(-10,-10,200,200),6371000,kinds=(3,))
        self.assertEqual(len(graph.pts),2)
        start,end=graph.pts[0][0],graph.pts[1][-1]
        self.assertIsNone(graph.route(start,end,1,0))
        self.assertIsNotNone(graph.route(start,end,1,0,turn_max=np.deg2rad(105)))

    def test_event_track_separation_preserves_racecourse_extension(self):
        def node(name, xy): return {'xy':xy, 'station':{'name':name} if name else None}
        def edge(a,b): return {'a':a,'b':b,'lead_a':None,'lead_b':None,'line':[]}
        model={'nodes':[node('Flinders Street',[0,0]),node('Showgrounds',[100,0]),node('Flemington Racecourse',[200,0])],
               'edges':[edge(0,1),edge(1,2)],
               'lines':[{'path':[0], 'stops':[0,1]},{'path':[0], 'stops':[0,1]}]}
        separate_event_tracks(model, {'lines':[{'name':'Flemington Racecourse events'},{'name':'Other'}]})
        event,other=model['lines']
        self.assertNotEqual(event['path'][0]>>1,other['path'][0]>>1)
        self.assertEqual(model['edges'][1]['a'],event['stops'][-1])
        self.assertEqual(model['edges'][other['path'][0]>>1]['b'],1)

    def test_short_station_joint_preserves_service_path(self):
        nodes = [{'xy':[0,0], 'level':0, 'station':{'name':'Southern Cross'}},
                 {'xy':[40,0], 'level':0, 'station':None},
                 {'xy':[300,0], 'level':0, 'station':None}]
        edges = [{'a':0,'b':1,'tracks':1,'oneway':1,'lead_a':[10,0],'lead_b':[30,0],'line':[]},
                 {'a':2,'b':1,'tracks':1,'oneway':2,'lead_a':[280,0],'lead_b':[60,0],'line':[]}]
        model = {'nodes':nodes,'edges':edges,'lines':[{'path':[0,3], 'stops':[0]}]}
        remove_short_station_joints(model)
        self.assertEqual(model['lines'][0]['path'], [3])
        self.assertEqual(edges[1]['b'], 0)

    def test_redundant_platforms_keep_paths_connected(self):
        station = {'name':'Example', 'key':'example'}
        nodes = [{'xy':[0,0], 'station':None}, {'xy':[10,0], 'station':station},
                 {'xy':[10,8], 'station':station.copy()}, {'xy':[20,0], 'station':None}]
        edges = [{'a':0,'b':1}, {'a':1,'b':3}, {'a':2,'b':0}, {'a':3,'b':2}]
        model = {'nodes':nodes, 'edges':edges,
                 'lines':[{'path':[0,2], 'stops':[1]}, {'path':[5,7], 'stops':[2]}]}
        self.assertEqual(merge_redundant_platforms(model), {2,3})
        self.assertEqual(model['lines'][1]['path'], [0,2])
        self.assertEqual(model['lines'][1]['stops'], [1])
        self.assertIsNone(nodes[2]['station'])

    def test_directional_platforms_are_not_merged(self):
        nodes = [{'xy':[0,0], 'station':None}, {'xy':[10,0], 'station':{'name':'Example','key':'x'}},
                 {'xy':[10,8], 'station':{'name':'Example','key':'x'}}, {'xy':[20,0], 'station':None}]
        edges = [{'a':0,'b':1}, {'a':1,'b':3}, {'a':0,'b':2,'oneway':1}, {'a':2,'b':3}]
        self.assertEqual(merge_redundant_platforms({'nodes':nodes,'edges':edges,'lines':[]}), set())

    def test_calendar_additions_and_removals(self):
        cal = pd.DataFrame([{'service_id':'a','wednesday':'1','start_date':'20261101','end_date':'20261130'},
                            {'service_id':'b','wednesday':'1','start_date':'20261101','end_date':'20261130'}])
        exceptions = pd.DataFrame([{'service_id':'a','date':'20261118','exception_type':'2'},
                                   {'service_id':'c','date':'20261118','exception_type':'1'}])
        self.assertEqual(service_ids(cal, exceptions, dt.date(2026,11,18)), {'b','c'})

    def test_shape_selection_rejects_wrong_station_order(self):
        import numpy as np
        stations = np.array([[0.,0.],[1000.,0.],[2000.,0.]])
        bad = np.array([[0.,0.],[2000.,0.],[1000.,0.]])
        good = np.array([[0.,1.],[1000.,1.],[2000.,1.]])
        result = ordered_shape(stations, [('bad',bad),('good',good)])
        self.assertTrue(np.array_equal(result[1], good))
        self.assertIsNone(ordered_shape(stations, [('bad',bad)]))

    def test_consolidation_preserves_stations_and_frequency(self):
        names = ['Flinders Street','Newport','Laverton','Altona','Werribee']
        stations = [{'name':n,'x':i,'y':0} for i,n in enumerate(names)]
        def pattern(stops, rate):
            length = len(stops)
            return {'name':'Werribee','route':'wer','stops':stops,'tph':[rate,rate,rate], 'cars':7,
                    't0':[[1]*(length-1)+[0] for _ in range(3)],
                    't1':[[0]+[1]*(length-1) for _ in range(3)]}
        original = [pattern([0,1,2,4],2), pattern([0,1,3,2],3), pattern([0,1,2,4],1)]
        net = simplify_services({'stations':stations,'lines':original})
        self.assertEqual(len(net['lines']),2)
        self.assertEqual({s for l in net['lines'] for s in l['stops']}, set(range(5)))
        self.assertEqual(sum(l['tph'][0] for l in net['lines']),6)
        self.assertTrue(all(sum(l['tph']) > 0 for l in net['lines']))

    def test_single_track_only_for_exclusive_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); (d/'mel_real.json').write_text(json.dumps({'lines':[{'name':'Stony Point'},{'name':'Other'}]}))
            model={'edges':[{},{}], 'lines':[{'path':[0,2]},{'path':[]} ]}
            (d/'mel_real_corridors.json').write_text(json.dumps({'model':model}))
            single_track_stony_point(d)
            got=json.loads((d/'mel_real_corridors.json').read_text())['model']
            self.assertEqual([e['tracks'] for e in got['edges']],[1,1])
            model['lines'][1]['path']=[2]
            (d/'mel_real_corridors.json').write_text(json.dumps({'model':model}))
            with self.assertRaises(ValueError): single_track_stony_point(d)

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
