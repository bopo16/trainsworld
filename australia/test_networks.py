import json,tempfile,unittest
from pathlib import Path
from build import join_perth_through, join_fremantle_midland
from collect_sydney import collect,normalise
from sydney_circle import join as join_circle

class AustraliaTests(unittest.TestCase):
    def test_sydney_stop_names_normalised(self):
        self.assertEqual(normalise('Central Station, Platform 26'),'Central')
        self.assertEqual(normalise('Mount Colah, platfrom 2'),'Mount Colah')
        self.assertEqual(normalise('Gadigal 2'),'Gadigal')

    def test_sydney_relation_snapshots_include_all_lines_and_metro_endpoints(self):
        folder=Path(__file__).parent/'sources'
        refs=set()
        metro=None
        for mode in ('rail','light'):
            data=json.loads((folder/f'sydney-{mode}-osm.json').read_text());lookup={(e['type'],e['id']):e for e in data['elements']}
            for e in data['elements']:
                if e['type']=='relation' and e['tags'].get('type')=='route':
                    refs.add(e['tags']['ref'])
                    if e['tags']['ref']=='M1':metro=[lookup[(m['type'],m['ref'])]['tags']['name'] for m in e['members'] if m['role'].startswith('stop')]
        self.assertEqual(refs,{'M1','T1','T2','T3','T4','T5','T6','T7','T8','T9','L1','L2','L3','L4'})
        self.assertIn('Tallawong',metro);self.assertIn('Bankstown',metro)

    def test_perth_through_line_joins_at_shared_station(self):
        names=['Yanchep','Perth Underground Stn','Elizabeth Quay Stn','Mandurah'];stations=[{'name':n} for n in names]
        def source(name,ids):return {'name':name,'stops':ids,'tph':[3,2,1], 't0':[[1,1,0]]*3,'t1':[[0,1,1]]*3,'symbol':name}
        net={'stations':stations,'lines':[source('Yanchep Line',[0,1,2]),source('Mandurah Line',[3,2,1])]}
        model={'nodes':[{'station':{'name':n}} for n in names],'edges':[{'a':0,'b':1},{'a':1,'b':2},{'a':2,'b':3}],
               'lines':[{'stops':[0,1,2],'path':[0,2],'tph':[3,2,1]},{'stops':[3,2,1],'path':[5,3],'tph':[3,2,1]}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name,data in [('per_real.json',net),('per_real_corridors.json',{'model':model}),('per_real_geom.json',{'lines':[{},{}]})]:(p/name).write_text(json.dumps(data))
            join_perth_through(p)
            got=json.loads((p/'per_real_corridors.json').read_text())['model']['lines'][0]
            self.assertEqual(got['stops'],[0,1,2,3]);self.assertEqual(got['path'],[0,2,4])

    def test_perth_fremantle_midland_continue_through_perth(self):
        def line(name,stops):return {'name':name,'stops':stops,'tph':[3,2,1],'t0':[[1,1,0]]*3,'t1':[[0,1,1]]*3}
        net={'lines':[line('Fremantle Line',[0,1,2]),line('Midland Line',[4,3,2])]}
        model={'lines':[{'stops':[0,1,2],'path':[0,2]},{'stops':[4,3,2],'path':[5,7]}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name,data in [('per_real.json',net),('per_real_corridors.json',{'model':model}),('per_real_geom.json',{'lines':[{},{}]})]:(p/name).write_text(json.dumps(data))
            join_fremantle_midland(p)
            got=json.loads((p/'per_real_corridors.json').read_text())['model']['lines'][0]
            self.assertEqual(got['stops'],[0,1,2,3,4]);self.assertEqual(got['path'],[0,2,6,4])

    def test_city_circle_services_return_via_other_leg(self):
        names=['Museum','St James','Circular Quay','Wynyard','Town Hall',None,'Central','Parramatta','Green Square']
        nodes=[{'station':{'name':x} if x else None} for x in names]
        pairs=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(0,5),(6,8)]
        model={'nodes':nodes,'edges':[{'a':a,'b':b} for a,b in pairs],
          'lines':[{'path':[0,2,4,6,8,10,12],'stops':[0,1,2,3,4,6,7]},
                   {'path':[7,5,3,1,14,10,16],'stops':[4,3,2,1,0,6,8]}]}
        net={'lines':[{'symbol':'T2','name':'T2'},{'symbol':'T8','name':'T8'}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'syd_real.json').write_text(json.dumps(net));(p/'syd_real_corridors.json').write_text(json.dumps({'model':model}))
            join_circle(p)
            lines=json.loads((p/'syd_real.json').read_text())['lines'];built=json.loads((p/'syd_real_corridors.json').read_text())['model']['lines']
            self.assertTrue(all(l['one_way'] for l in lines))
            self.assertTrue(all(s['stops'][0]==s['stops'][-1] for s in built))
            self.assertTrue(all(0 in s['stops'] and 4 in s['stops'] for s in built))

if __name__=='__main__':unittest.main()
