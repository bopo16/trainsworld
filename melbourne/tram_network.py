"""Append a compact GTFS tram network to a generated Melbourne shared-track model."""
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import substring

GREEN = '009B3A'


def build(out, archive, date, realnet, tram_graph):
    """Build one representative full-length pattern per active numbered route.

    Prefer OSM tram/light-rail geometry, falling back to GTFS shapes. Hops with
    the same stop endpoints are shared, so routes can run on common track.
    """
    from metro_network import service_ids
    import realshared
    folder = out / 'tram'; folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as outer, zipfile.ZipFile(io.BytesIO(outer.read('3/google_transit.zip'))) as feed:
        for f in ('routes.txt','stops.txt','trips.txt','stop_times.txt','shapes.txt','calendar.txt','calendar_dates.txt'):
            (folder/f).write_bytes(feed.read(f))
    def read(f): return pd.read_csv(folder/f, dtype=str, keep_default_na=False)
    routes=read('routes.txt'); trips=read('trips.txt'); stops=read('stops.txt')
    active=service_ids(read('calendar.txt'),read('calendar_dates.txt'),date)
    trips=trips[trips.service_id.isin(active) & trips.route_id.isin(routes.route_id)]
    if not len(trips): raise ValueError('No active tram trips')
    candidates=trips.groupby(['route_id','direction_id','shape_id'],sort=True).first().reset_index()
    ids=set(candidates.trip_id); active_ids=set(trips.trip_id)
    samples=[]; departures=[]
    for chunk in pd.read_csv(folder/'stop_times.txt',dtype=str,keep_default_na=False,chunksize=300000):
        chunk=chunk[chunk.trip_id.isin(active_ids)]
        samples.append(chunk[chunk.trip_id.isin(ids)])
        departures.append(chunk[chunk.stop_sequence.eq('1')][['trip_id','departure_time']])
    samples=pd.concat(samples); departures=pd.concat(departures).drop_duplicates('trip_id')
    counts=samples.groupby('trip_id').size()
    candidates['count']=candidates.trip_id.map(counts).fillna(0)
    # Prefer a direction with the most stops; a missing route or bad pattern is an error.
    chosen=candidates.sort_values(['route_id','count','direction_id'],ascending=[True,False,True]).drop_duplicates('route_id')
    if len(chosen) != len(routes) or (chosen['count']<3).any(): raise ValueError('Incomplete tram route selection')
    times=trips[['route_id','direction_id','trip_id']].merge(departures,on='trip_id')
    times['hour']=times.departure_time.str.split(':').str[0].astype(int)
    rate={}
    for route,group in times.groupby('route_id'):
        directions=max(1,group.direction_id.nunique())
        rate[route]=[len(group[group.hour.isin(hours)])/(directions*len(hours)) for hours in ([7,8,17,18],list(range(10,17)),list(range(0,6)))]
    by_id=stops.set_index('stop_id'); origin=realnet.origin('mel')
    # Opposite platforms often use separate stop IDs but the same official name.
    # Canonicalise only stops with that exact name, and reject widely separated names.
    stop_ids=set(samples[samples.trip_id.isin(set(chosen.trip_id))].stop_id)
    relevant=stops[stops.stop_id.isin(stop_ids)].copy()
    relevant['x'], relevant['y']=realnet.to_xy(relevant.stop_lon.astype(float).to_numpy(),relevant.stop_lat.astype(float).to_numpy(),origin)
    import realroute
    xs,ys=relevant['x'].to_numpy(),relevant['y'].to_numpy()
    graph=realroute.Graph(str(tram_graph),origin,(xs.min()-2000,ys.min()-2000,xs.max()+2000,ys.max()+2000),realnet.R_EARTH,kinds=(1,3))
    if not graph.pts: raise ValueError('The supplied realgraph contains no Melbourne tram/light rail')
    stations=[]; station_of={}
    for nm,group in relevant.groupby('stop_name',sort=True):
        points=group[['x','y']].to_numpy(); center=points.mean(axis=0)
        if np.max(np.linalg.norm(points-center,axis=1)) > 100: raise ValueError(f'Ambiguous tram stop {nm}')
        ix=len(stations); stations.append({'name':nm,'key':'tram:'+nm,'x':float(center[0]),'y':float(center[1])})
        for id in group.stop_id: station_of[id]=ix
    shape_ids=set(chosen.shape_id); shape_chunks=[]
    for chunk in pd.read_csv(folder/'shapes.txt',dtype=str,keep_default_na=False,chunksize=200000):
        shape_chunks.append(chunk[chunk.shape_id.isin(shape_ids)])
    shapes=pd.concat(shape_chunks); shapes['seq']=shapes.shape_pt_sequence.astype(int)
    shape_by={}
    for sid,g in shapes.groupby('shape_id'):
        g=g.sort_values('seq'); x,y=realnet.to_xy(g.shape_pt_lon.astype(float).to_numpy(),g.shape_pt_lat.astype(float).to_numpy(),origin)
        shape_by[sid]=LineString(np.column_stack((x,y)))
    route_by=routes.set_index('route_id'); lines=[]; clines=[]; pieces=[]; polys=[]; hops={}; straight_hops=0; osm_hops=0; final_straight=0
    for r in chosen.itertuples():
        seq=samples[samples.trip_id.eq(r.trip_id)].copy(); seq['seq']=seq.stop_sequence.astype(int); seq=seq.sort_values('seq')
        def seconds(value):
            h,m,s = map(int,value.split(':')); return 3600*h+60*m+s
        visits=[]
        for row in seq.itertuples():
            stop=station_of[row.stop_id]
            if not visits or stop != visits[-1][0]: visits.append((stop,seconds(row.departure_time)))
        stops_seq=[x for x,_ in visits]
        code=route_by.loc[r.route_id,'route_short_name']
        if len(set(stops_seq)) != len(stops_seq) and code != '35':
            raise ValueError(f'Tram {code} repeats a stop in its representative pattern')
        shape=shape_by[r.shape_id]; path=[]
        for a,b in zip(stops_seq,stops_seq[1:]):
            key=tuple(sorted((a,b)))
            if key not in hops:
                p,q=Point(stations[a]['x'],stations[a]['y']),Point(stations[b]['x'],stations[b]['y'])
                da,db=shape.project(p),shape.project(q)
                sub=substring(shape,da,db).simplify(4)
                line=list(sub.coords) if sub.geom_type=='LineString' else []
                straight=False; osm=False
                if len(line)<2 or sub.length > max(700,4*p.distance(q)):
                    line=[list(p.coords[0]),list(q.coords[0])]; straight_hops+=1; straight=True
                match=graph.route(np.array(p.coords[0]),np.array(q.coords[0]),20,0,turn_max=math.radians(105))
                if match is not None and len(match[0]) >= 2:
                    routed=match[0]
                    if realroute.length(routed) <= max(150,2.5*p.distance(q)+120) and (straight or realroute.far_from(routed,np.asarray(line)) <= 90):
                        line=routed.tolist(); osm_hops+=1; osm=True
                if not osm:
                    print(f"Tram {code}: {'straight' if straight else 'GTFS'} fallback from {stations[a]['name']} to {stations[b]['name']}",flush=True)
                if straight and not osm: final_straight+=1
                poly=np.array([list(p.coords[0])]+line[1:-1]+[list(q.coords[0])])
                index=len(pieces); hops[key]=(index,a,b); pieces.append({'id':index,'pairs':1,'ends':[a,b]});polys.append(poly)
            index,u,v=hops[key]; path.append([index,1 if (a,b)==(u,v) else -1,0])
        n=len(stops_seq)
        tph=[round(v,2) for v in rate[r.route_id]]
        hop_times=[max(1,b[1]-a[1]) for a,b in zip(visits,visits[1:])]
        line={'feed':'tram','name':'Tram '+code,'symbol':code,'route':r.route_id,'colour':GREEN,'group':8,'group_name':'Yarra Trams','group_symbol':'TRAM','group_colour':GREEN,'cars':2,'stops':stops_seq,'tph':tph,'t0':[hop_times+[0] for _ in range(3)],'t1':[[0]+hop_times for _ in range(3)]}
        if code == '35': line['one_way'] = True
        lines.append(line);clines.append({'path':path,'stops':stops_seq,'tph':tph})
        print(f'Tram {code}: {n} stops, {r.count} selected-trip stops, {tph} tph',flush=True)
    # The game's section capacity is lower than the aggregate Swanston Street
    # timetable. Give its heavily used common pieces a second pair, keeping
    # the same route assignment throughout the trunk.
    cohorts = ({'1','3','5','6'}, {'16','64','67','72'})
    users=defaultdict(set)
    for i,l in enumerate(clines):
        for piece,_,_ in l['path']: users[piece].add(i)
    split=set()
    for piece, indices in users.items():
        codes={lines[i]['symbol'] for i in indices}
        if codes & cohorts[0] and codes & cohorts[1] and sum(max(lines[i]['tph'][:2]) for i in indices) > 25:
            pieces[piece]['pairs']=2; split.add(piece)
    for i,l in enumerate(clines):
        l['path']=[[piece,direction, (1 if lines[i]['symbol'] in cohorts[1] else 0) if piece in split else 0]
                   for piece,direction,_ in l['path']]
    print(f'Tram capacity: {len(split)} busy pieces use two pairs',flush=True)
    # A double-track tram stop handles both directions; don't split platforms
    # merely because several routes use it. Distinct track pairs remain distinct.
    realshared.PLAT_LOAD=1e6
    realshared.LEAD_MAX=20.0
    realshared.HEAD_M=20.0
    realshared.BRANCH_CLEAR=10.0
    model=realshared.track_model({'pieces':pieces,'lines':clines},polys,{'stations':stations,'lines':lines});stats=model['stats']
    if any(x is None for x in model['lines']): raise ValueError(f'Tram tracks missing routes: {stats}')
    # Route 35 starts and ends at Waterfront City, but separate approaches
    # initially create two nearby copies of that terminal. Join them so its
    # selected journey is a continuous one-way loop.
    circle=model['lines'][next(i for i,l in enumerate(lines) if l['symbol']=='35')]
    start,end=circle['stops'][0],circle['stops'][-1]
    if start != end:
        a,b=model['nodes'][start],model['nodes'][end]
        if a['station']['key'] != b['station']['key'] or np.linalg.norm(np.array(a['xy'])-b['xy']) > 40:
            raise ValueError('City Circle endpoints do not match')
        delta=np.array(a['xy'])-np.array(b['xy'])
        for edge in model['edges']:
            for side in ('a','b'):
                if edge[side] == end:
                    edge[side] = start
                    if edge['lead_'+side] is not None: edge['lead_'+side]=(np.array(edge['lead_'+side])+delta).tolist()
        for line in model['lines']: line['stops']=[start if s==end else s for s in line['stops']]
        b['station']=None
    stop_counts=Counter(node['station']['key'] for node in model['nodes'] if node['station'])
    if any(count > 2 for count in stop_counts.values()):
        raise ValueError('A tram stop has more than two separate station nodes')
    for node in model['nodes']:
        node['level']=0
        if node['station']:
            node['station']['platform']=40
            # Two unusually busy shared termini use v0.4's tram terminal and
            # passing-track upgrades instead of separate station nodes.
            if node['station']['name'] in ('Flinders Street Station/Elizabeth St #1','Waterfront City/Docklands Dr #D11'):
                node['station']['upgrades']=9
    for edge in model['edges']: edge.update(kind='tram',levels=[])
    net_path=out/'mel_real.json'; corr_path=out/'mel_real_corridors.json'; geom_path=out/'mel_real_geom.json'
    net=json.loads(net_path.read_text()); corr=json.loads(corr_path.read_text()); geom=json.loads(geom_path.read_text());m=corr['model']
    no,eo,so=len(m['nodes']),len(m['edges']),len(net['stations'])
    m['nodes'].extend(model['nodes'])
    for e in model['edges']: e['a']+=no;e['b']+=no
    m['edges'].extend(model['edges'])
    for l in model['lines']:
        l['stops']=[x+no for x in l['stops']];l['path']=[((c>>1)+eo)<<1 | c&1 for c in l['path']]
    m['lines'].extend(model['lines'])
    for l in lines: l['stops']=[x+so for x in l['stops']]
    net['stations'].extend(stations);net['lines'].extend(lines);geom['lines'].extend([{} for _ in lines])
    for p,data in ((net_path,net),(corr_path,corr),(geom_path,geom)):p.write_text(json.dumps(data))
    print(f'Tram model: {len(lines)} routes, {len(stations)} named stops, {len(model["edges"])} edges; {osm_hops}/{len(pieces)} OSM-routed hops, {final_straight} final straight fallbacks ({straight_hops} before OSM matching); {dict(stats)}',flush=True)
