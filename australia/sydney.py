#!/usr/bin/env python3
"""Build an approximate Sydney game save from pinned OSM route relations."""
import argparse,json,math,os,shutil,subprocess,sys
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parents[1];TW=ROOT/'trainworld';sys.path[:0]=[str(TW/'pipeline'),str(ROOT/'australia')]
from build import wrap_tram
COLOURS={'M1':'168388','T1':'F99D1C','T2':'0098CD','T3':'F36F21','T4':'005AA3','T5':'C064A3','T6':'A35B29','T7':'717F84','T8':'00954C','T9':'D11F2F','L1':'D71920','L2':'ED1C24','L3':'E31B23','L4':'B34E98'}
LABELS={'M1':'Metro North West & Bankstown','T1':'North Shore & Western','T2':'Leppington & Inner West','T3':'Liverpool & Inner West','T4':'Eastern Suburbs & Illawarra','T5':'Cumberland','T6':'Lidcombe & Bankstown','T7':'Olympic Park','T8':'Airport & South','T9':'Northern','L1':'Dulwich Hill','L2':'Randwick','L3':'Kingsford','L4':'Parramatta'}


def configure(net,light=False):
    counts=defaultdict(int)
    for l in net['lines']:counts[l['name']]+=1
    for line in net['lines']:
        code=line['name'];st=[net['stations'][i]['name'] for i in line['stops']]
        line.update(symbol=code,group=list(COLOURS).index(code)+1,group_name=code+' '+LABELS[code],group_symbol=code,group_colour=COLOURS[code],colour=COLOURS[code],cars=2 if light else (6 if code=='M1' else 8))
        line['name']=code+' '+LABELS[code]+(f' ({st[0]} – {st[-1]})' if counts[code]>1 else '')


def light_model(net,graph_path,realnet):
    import realroute,realshared
    stations=net['stations'];xy=np.array([[s['x'],s['y']] for s in stations]);graph=realroute.Graph(str(graph_path),realnet.origin('syd'),(*list(xy.min(0)-2000),*list(xy.max(0)+2000)),realnet.R_EARTH,kinds=(1,3))
    if not graph.pts:raise ValueError('No Sydney light rail in graph')
    pieces=[];polys=[];used={};services=[];routed=0;fallback=[]
    for line in net['lines']:
        path=[]
        for a,b in zip(line['stops'],line['stops'][1:]):
            key=tuple(sorted((a,b)))
            if key not in used:
                p=xy[a];q=xy[b];match=graph.route(p,q,35,0,turn_max=math.radians(105));points=[]
                if match is not None and len(match[0])>=2 and realroute.length(match[0]) <= max(200,2.5*np.linalg.norm(q-p)+120):
                    points=match[0][1:-1].tolist();routed+=1
                else:fallback.append((stations[a]['name'],stations[b]['name']))
                idx=len(pieces);used[key]=(idx,a,b);pieces.append({'id':idx,'pairs':1,'ends':[a,b]});polys.append(np.array([p.tolist()]+points+[q.tolist()]))
            i,u,v=used[key];path.append([i,1 if (u,v)==(a,b) else -1,0])
        services.append({'path':path,'stops':line['stops'],'tph':line['tph']})
    realshared.PLAT_LOAD=1e6;realshared.LEAD_MAX=20;realshared.HEAD_M=20;realshared.BRANCH_CLEAR=10
    model=realshared.track_model({'pieces':pieces,'lines':services},polys,net)
    if any(not l for l in model['lines']):raise ValueError('missing light-rail service')
    for node in model['nodes']:
        node['level']=0
        if node['station']:node['station']['platform']=40
    for e in model['edges']:e.update(kind='tram',levels=[])
    print('Sydney light rail:',routed,'/',len(pieces),'OSM-routed hops; fallbacks:',fallback,flush=True)
    return model


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--graph',required=True,type=Path);p.add_argument('--pack',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'syd_real.save').exists():raise FileExistsError('Use a fresh output directory')
    packs=TW/'data/packs';(packs/'realgraph').mkdir(parents=True,exist_ok=True)
    for src,dest in [(a.pack,packs/'syd.json'),(a.graph,packs/'realgraph/au-cities.rgr')]:
        if dest.exists() and dest.read_bytes()!=src.read_bytes():raise FileExistsError(f'{dest} differs')
        if not dest.exists():shutil.copyfile(src,dest)
    os.environ['REALNET_OUT']=str(out)
    import realnet,realcorridors,realshared
    realnet.REALGRAPH=str(packs/'realgraph');realnet.REGION['syd']='au-cities';realnet.REGION['sydlight']='au-cities'
    def config(mode,city):
        src={'name':mode,'adapter':'osm','file':str(ROOT/f'australia/sources/sydney-{mode}-osm.json'),'min_share':.01,'min_trips':1,'split_tph':True}
        realnet.CITIES[city]={'pack':'syd','out':str(out/f'{city}_real.json'),'sources':[src],'boundary':False,'count_point':[151.21,-33.88]}
    config('rail','syd');realnet.cmd_net('syd');pnet=out/'syd_real.json';net=json.loads(pnet.read_text());configure(net);pnet.write_text(json.dumps(net))
    sys.argv=['realnet.py','geom','syd'];realnet.cmd_geom()
    realshared.PLAT_LOAD=1e6;realshared.PAIR_GAP=18
    realcorridors.PACK_LOAD_RAIL=.75;realcorridors.WANT_LOAD=.85;realcorridors.APART_LOAD=1.1
    realcorridors.build('syd',str(out))
    # T6 and T7 use the same Lidcombe terminus; use the game's platform
    # upgrade rather than inventing a second station to carry their turns.
    corrpath=out/'syd_real_corridors.json';doc=json.loads(corrpath.read_text());rail=doc['model'];railnet=json.loads(pnet.read_text())
    ends=[]
    for symbol in ('T6','T7'):
        i=next(i for i,l in enumerate(railnet['lines']) if l['symbol']==symbol)
        ends.append({v for v in (rail['lines'][i]['stops'][0],rail['lines'][i]['stops'][-1]) if rail['nodes'][v]['station']['name']=='Lidcombe'})
    shared=ends[0]&ends[1]
    if len(shared)!=1:raise ValueError('Expected a shared T6/T7 Lidcombe terminus')
    rail['nodes'][shared.pop()]['station']['upgrades']=9;corrpath.write_text(json.dumps(doc))
    import sydney_circle
    sydney_circle.join(out)
    config('light','sydlight');realnet.cmd_net('sydlight');light=json.loads((out/'sydlight_real.json').read_text());configure(light,True);model=light_model(light,a.graph,realnet)
    net=json.loads(pnet.read_text());corrpath=out/'syd_real_corridors.json';corr=json.loads(corrpath.read_text());m=corr['model'];geo_path=out/'syd_real_geom.json';geo=json.loads(geo_path.read_text())
    no,eo,so=len(m['nodes']),len(m['edges']),len(net['stations']);m['nodes'].extend(model['nodes'])
    for e in model['edges']:e['a']+=no;e['b']+=no
    m['edges'].extend(model['edges'])
    for l in model['lines']:l['stops']=[x+no for x in l['stops']];l['path']=[((c>>1)+eo)<<1|c&1 for c in l['path']]
    m['lines'].extend(model['lines'])
    for l in light['lines']:l['stops']=[x+so for x in l['stops']]
    net['stations'].extend(light['stations']);net['lines'].extend(light['lines']);geo['lines'].extend([{} for _ in light['lines']])
    for file,data in [(pnet,net),(corrpath,corr),(geo_path,geo)]:file.write_text(json.dumps(data))
    subprocess.run(['cargo','run','--release','--features','demand','--bin','realsave','--','--city','syd','--out',str(out),'--shared','--left'],cwd=TW/'sim',check=True)
    sys.argv=['realnet.py','gamesave','syd'];realnet.cmd_gamesave();wrap_tram(out,'syd')
    subprocess.run([sys.executable,str(ROOT/'australia/validate.py'),'syd',str(out/'syd_real.save')],check=True)

if __name__=='__main__':main()
