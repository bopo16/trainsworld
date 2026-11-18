#!/usr/bin/env python3
"""Build a local Perth or Canberra network from official GTFS and OSM graph data."""
import argparse
import copy
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; TW=ROOT/'trainworld'
sys.path[:0]=[str(ROOT/'melbourne'),str(TW/'pipeline')]
from metro_network import service_ids

CONFIG={
 'per':{'name':'Perth','names':['Airport Line','Armadale Line','Ellenbrook Line','Fremantle Line','Mandurah Line','Midland Line','Thornlie-Cockburn Line','Yanchep Line'],
        'symbols':{'Airport Line':'AIR','Armadale Line':'ARM','Ellenbrook Line':'ELL','Fremantle Line':'FRE','Mandurah Line':'MAN','Midland Line':'MID','Thornlie-Cockburn Line':'THO','Yanchep Line':'YAN'},'cars':5,'kind':'commuter','point':[115.86,-31.95]},
 'can':{'name':'Canberra','names':['1'],'symbols':{'1':'1'},'cars':2,'kind':'tram','point':[149.131,-35.28]},
}


def stage_feed(archive,folder,city,date):
    folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        def read(name):return pd.read_csv(z.open(name),dtype=str,keep_default_na=False,skipinitialspace=True)
        routes=read('routes.txt'); cal=read('calendar.txt'); exceptions=read('calendar_dates.txt');trips=read('trips.txt')
        if city=='per':routes=routes[(routes.agency_id=='WES-RAI') & routes.route_long_name.isin(CONFIG[city]['names'])]
        else:routes=routes[(routes.route_short_name=='1') & (routes.route_type=='0')]
        found=set(routes.route_long_name if city=='per' else routes.route_short_name)
        if found!=set(CONFIG[city]['names']):raise ValueError(f'Unexpected {city} routes {found}')
        active=service_ids(cal,exceptions,date)
        trips=trips[trips.route_id.isin(routes.route_id)&trips.service_id.isin(active)]
        times=read('stop_times.txt'); times=times[times.trip_id.isin(trips.trip_id)]
        trips=trips[trips.trip_id.isin(times.trip_id)]; shapes=read('shapes.txt');shapes=shapes[shapes.shape_id.isin(trips.shape_id)]
        stops=read('stops.txt'); wanted=set(times.stop_id)
        if 'parent_station' in stops:
            wanted.update(stops.loc[stops.stop_id.isin(wanted),'parent_station'])
        stops=stops[stops.stop_id.isin(wanted)]
        for name,frame in [('routes.txt',routes),('trips.txt',trips),('stop_times.txt',times),('shapes.txt',shapes),('stops.txt',stops),('calendar.txt',cal),('calendar_dates.txt',exceptions)]:frame.to_csv(folder/name,index=False)
    print(city, len(trips),'active trips',flush=True)
    return active


def simplify(net):
    """One representative longest observed stop pattern per named route."""
    groups=defaultdict(list)
    for line in net['lines']:groups[line['route']].append(line)
    chosen=[]
    for route,patterns in groups.items():
        best=max(patterns,key=lambda x:(len(set(x['stops'])),sum(x['tph'])))
        best['tph']=[round(sum(x['tph'][i] for x in patterns),2) for i in range(3)]
        chosen.append(best)
    net['lines']=chosen


def canberra_model(out,net,realnet,graph_path):
    import realshared, realroute
    from shapely.geometry import Point
    from shapely.ops import substring
    import math
    line=net['lines'][0]; stops=net['stations']; geo=json.loads((out/'can_real_geom.json').read_text())['lines'][0]
    coords=np.array([[s['x'],s['y']] for s in stops]); graph=realroute.Graph(str(graph_path),realnet.origin('can'),(*list(coords.min(0)-2000),*list(coords.max(0)+2000)),realnet.R_EARTH,kinds=(1,3))
    pieces=[];polys=[];path=[]; matched=0
    for k,(a,b) in enumerate(zip(line['stops'],line['stops'][1:])):
        p=np.array([stops[a]['x'],stops[a]['y']]);q=np.array([stops[b]['x'],stops[b]['y']]);result=graph.route(p,q,35,0,turn_max=math.radians(105))
        if result is not None and len(result[0])>=2 and realroute.length(result[0])<max(250,2.5*np.linalg.norm(q-p)+100):
            points=result[0][1:-1].tolist();matched+=1
        else:points=geo['hops'][k]
        pieces.append({'id':k,'pairs':1,'ends':[a,b]});polys.append(np.array([p.tolist()]+points+[q.tolist()]));path.append([k,1,0])
    realshared.PLAT_LOAD=1e6;realshared.LEAD_MAX=20;realshared.HEAD_M=20
    model=realshared.track_model({'pieces':pieces,'lines':[{'path':path,'stops':line['stops'],'tph':line['tph']}]},polys,net)
    if not model['lines'][0]:raise ValueError('Canberra line missing from shared model')
    for node in model['nodes']:
        node['level']=0
        if node['station']:node['station']['platform']=40
    for edge in model['edges']:edge.update(kind='tram',levels=[])
    (out/'can_real_corridors.json').write_text(json.dumps({'model':model}))
    print(f'Canberra: {matched}/{len(path)} OSM-routed hops',flush=True)


def join_perth_through(out):
    """Join the observed Yanchep and Mandurah route halves at Perth Underground."""
    files=[out/'per_real.json',out/'per_real_corridors.json',out/'per_real_geom.json']
    net,doc,geo=[json.loads(p.read_text()) for p in files];m=doc['model'];nodes=m['nodes'];edges=m['edges'];lines=net['lines'];services=m['lines']
    y=next(i for i,l in enumerate(lines) if l['name']=='Yanchep Line');q=next(i for i,l in enumerate(lines) if l['name']=='Mandurah Line')
    sy,sm=services[y],services[q]
    def stop_name(node):return (nodes[node]['station'] or {}).get('name')
    u=next(i for i,s in enumerate(sy['stops']) if stop_name(s)=='Perth Underground Stn')
    station=sy['stops'][u]
    if sm['stops'][-1]!=station:raise ValueError('Yanchep/Mandurah do not share Perth Underground')
    def ends(code):
        edge=edges[code>>1];return (edge['b'],edge['a']) if code&1 else (edge['a'],edge['b'])
    pos=next(i+1 for i,c in enumerate(sy['path']) if ends(c)[1]==station)
    path=sy['path'][:pos]+[c^1 for c in sm['path'][::-1]]
    if any(ends(a)[1]!=ends(b)[0] for a,b in zip(path,path[1:])):raise ValueError('Perth through path is disconnected')
    selected=copy.deepcopy(lines[y]);source=lines[y];other=lines[q]
    u2=next(i for i,s in enumerate(source['stops']) if net['stations'][s]['name']=='Perth Underground Stn')
    if other['stops'][-1]!=source['stops'][u2]:raise ValueError('Perth timetable stop mismatch')
    selected['name']='Yanchep – Mandurah';selected['symbol']='Y/M';selected['group_name']='Yanchep and Mandurah Lines';selected['group_symbol']='Y/M'
    selected['stops']=source['stops'][:u2+1]+other['stops'][-2::-1]
    selected['t0']=[source['t0'][k][:u2]+other['t1'][k][::-1] for k in range(3)]
    selected['t1']=[source['t1'][k][:u2+1]+other['t0'][k][:-1][::-1] for k in range(3)]
    selected['tph']=[min(source['tph'][k],other['tph'][k]) for k in range(3)]
    merged=copy.deepcopy(sy);merged.update(path=path,stops=sy['stops'][:u+1]+sm['stops'][-2::-1],tph=selected['tph'])
    keep=[i for i in range(len(lines)) if i not in (y,q)]
    net['lines']=[lines[i] for i in keep]+[selected];m['lines']=[services[i] for i in keep]+[merged];geo['lines']=[geo['lines'][i] for i in keep]+[geo['lines'][y]]
    for file,data in zip(files,(net,doc,geo)):file.write_text(json.dumps(data))
    print('Joined Yanchep and Mandurah through Perth Underground',flush=True)


def join_fremantle_midland(out):
    """Represent the continuous Fremantle–Midland corridor as one service."""
    files=[out/'per_real.json',out/'per_real_corridors.json',out/'per_real_geom.json']
    net,doc,geo=[json.loads(p.read_text()) for p in files];m=doc['model'];lines=net['lines'];services=m['lines']
    f=next(i for i,l in enumerate(lines) if l['name']=='Fremantle Line');q=next(i for i,l in enumerate(lines) if l['name']=='Midland Line')
    a,b=services[f],services[q];x,y=lines[f],lines[q]
    if a['stops'][-1]!=b['stops'][-1] or x['stops'][-1]!=y['stops'][-1]:raise ValueError('Fremantle/Midland do not share Perth station')
    line=copy.deepcopy(x);line.update(name='Fremantle – Midland',symbol='F/M',group_name='Fremantle and Midland Lines',group_symbol='F/M')
    line['stops']=x['stops']+y['stops'][-2::-1]
    line['t0']=[x['t0'][k][:-1]+y['t1'][k][::-1] for k in range(3)]
    line['t1']=[x['t1'][k]+y['t0'][k][:-1][::-1] for k in range(3)]
    line['tph']=[min(x['tph'][k],y['tph'][k]) for k in range(3)]
    service=copy.deepcopy(a);service.update(stops=a['stops']+b['stops'][-2::-1],path=a['path']+[p^1 for p in b['path'][::-1]],tph=line['tph'])
    keep=[i for i in range(len(lines)) if i not in (f,q)]
    net['lines']=[lines[i] for i in keep]+[line];m['lines']=[services[i] for i in keep]+[service];geo['lines']=[geo['lines'][i] for i in keep]+[geo['lines'][f]]
    for file,data in zip(files,(net,doc,geo)):file.write_text(json.dumps(data))
    print('Joined Fremantle and Midland through Perth',flush=True)


def wrap_tram(out,city):
    path=out/f'{city}_real.save';raw=gzip.decompress(path.read_bytes());n=struct.unpack_from('<I',raw,4)[0];head=json.loads(raw[8:8+n]);data=json.loads((out/f'{city}_real_track.json').read_text());head['fleetTram']=data['fleetTram'];b=json.dumps(head).encode();path.write_bytes(gzip.compress(b'TWG1'+struct.pack('<I',len(b))+b+raw[8+n:],mtime=0))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('city',choices=CONFIG);p.add_argument('--gtfs',required=True,type=Path);p.add_argument('--date',default='2026-11-18');p.add_argument('--graph',required=True,type=Path);p.add_argument('--pack',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    date=dt.date.fromisoformat(a.date);city=a.city;cfg=CONFIG[city];out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/f'{city}_real.save').exists():raise FileExistsError('Use a fresh output directory')
    active=stage_feed(a.gtfs,out/'feed',city,date)
    packs=TW/'data/packs';(packs/'realgraph').mkdir(parents=True,exist_ok=True)
    if city=='can':pack={'origin':{'lon':149.131,'lat':-35.28}}
    else:
        if a.pack is None:p.error('Perth requires --pack')
        pack=json.loads(a.pack.read_text())
    dest=packs/f'{city}.json';content=json.dumps(pack).encode()
    if dest.exists() and json.loads(dest.read_text())!=pack:raise FileExistsError(f'Pack differs: {dest}')
    if not dest.exists():dest.write_bytes(content)
    dest=packs/'realgraph/au-cities.rgr'
    if dest.exists() and dest.read_bytes()!=a.graph.read_bytes():raise FileExistsError('Staged graph differs')
    if not dest.exists():shutil.copyfile(a.graph,dest)
    os.environ['REALNET_OUT']=str(out)
    import realnet,realcorridors
    realnet.REALGRAPH=str(packs/'realgraph');realnet.REGION[city]='au-cities';realnet.service_ids=lambda folder:(pd.Timestamp(date),active)
    src=realnet.gtfs(city,str(out/'feed'),'official GTFS',.02,2,{'_':40 if city=='can' else 120},cfg['kind'])
    realnet.CITIES[city]={'pack':city,'out':str(out/f'{city}_real.json'),'sources':[src],'boundary':False,'count_point':cfg['point']}
    realnet.cmd_net(city);path=out/f'{city}_real.json';net=json.loads(path.read_text());simplify(net)
    for i,line in enumerate(net['lines']):
        name=line['name']; line.update(symbol=cfg['symbols'][name],group=i+1,group_name=name,group_symbol=cfg['symbols'][name],group_colour=line.get('colour',''),cars=cfg['cars'])
        if city=='per' and name in ('Airport Line','Yanchep Line','Mandurah Line'):line['cars']=7
        if city=='can':line['name']='Canberra Light Rail 1'
    if len(net['lines'])!=len(cfg['names']):raise ValueError(f'Expected {len(cfg["names"])} services, got {len(net["lines"])}')
    path.write_text(json.dumps(net));sys.argv=['realnet.py','geom',city];realnet.cmd_geom()
    if city=='can':canberra_model(out,net,realnet,a.graph)
    else:
        import realshared
        realshared.PLAT_LOAD=1e6
        realcorridors.build(city,str(out))
        join_perth_through(out)
        join_fremantle_midland(out)
    subprocess.run(['cargo','run','--release','--features','demand','--bin','realsave','--','--city',city,'--out',str(out),'--shared','--left'],cwd=TW/'sim',check=True)
    sys.argv=['realnet.py','gamesave',city];realnet.cmd_gamesave()
    if city=='can':wrap_tram(out,city)
    subprocess.run([sys.executable,str(ROOT/'australia/validate.py'),city,str(out/f'{city}_real.save')],check=True)

if __name__=='__main__':main()
