"""Connect representative Sydney City Circle routes into one-way balloon services."""
import json
from pathlib import Path


def join(out):
    files=[out/'syd_real.json',out/'syd_real_corridors.json'];net,doc=[json.loads(p.read_text()) for p in files]
    model=doc['model'];nodes=model['nodes'];edges=model['edges'];services=model['lines'];lines=net['lines']
    def walk(path):
        def ends(c):
            e=edges[c>>1];return (e['b'],e['a']) if c&1 else (e['a'],e['b'])
        out=[ends(path[0])[0]]+[ends(c)[1] for c in path]
        if any(ends(a)[1]!=ends(b)[0] for a,b in zip(path,path[1:])):raise ValueError('Disconnected City Circle')
        return out
    def name(v):return (nodes[v]['station'] or {}).get('name')
    def at(ids,station):return next(i for i,v in enumerate(ids) if name(v)==station)
    iy=next(i for i,l in enumerate(lines) if l['symbol']=='T2');airport=next(i for i,l in enumerate(lines) if l['symbol']=='T8' and any(name(x)=='Green Square' for x in services[i]['stops']))
    ref=services[iy]['path'];refnodes=walk(ref);c=at(refnodes,'Central');m=at(refnodes,'Museum')
    if m!=0 or c<1:raise ValueError('Unexpected T2 City Circle approach')
    inner=ref[:c]
    ap=services[airport]['path'];apnodes=walk(ap);am,ac=at(apnodes,'Museum'),at(apnodes,'Central');other=ap[am:ac]
    if walk(other)[-1]!=walk(inner)[-1]:raise ValueError('City Circle approaches use different Central platforms')
    city={'Central','Town Hall','Wynyard','Circular Quay','St James','Museum'}
    for i,l in enumerate(lines):
        code=l['symbol']
        if code not in ('T2','T3','T8'):continue
        p=services[i]['path'];ids=walk(p);central=at(ids,'Central');tail=p[central:]
        if not tail:raise ValueError('City Circle service has no suburban branch')
        if code in ('T2','T3'):
            museum=at(ids,'Museum');prefix=p[museum:central]
            if walk(prefix)[-1]!=walk(other)[-1]:raise ValueError(f'{l["name"]} has a different Central platform')
            cycle=[v^1 for v in prefix[::-1]]+other
        else:
            museum=at(ids,'Museum');prefix=p[museum:central]
            # The two Central station nodes use the same city-side junction.
            target=walk(prefix)[-1];before=walk(prefix)[-2]
            if walk(inner)[-2]!=before:raise ValueError(f'{l["name"]} has a different City Circle junction')
            cycle=[v^1 for v in prefix[::-1]]+inner[:-1]+[prefix[-1]]
            if walk(cycle)[-1]!=target:raise ValueError('Wrong Central platform after cycle')
        path=[v^1 for v in tail[::-1]]+cycle+tail
        wanted={name(v) for v in services[i]['stops']}|city
        stops=[v for v in walk(path) if name(v) in wanted]
        stops=[v for j,v in enumerate(stops) if j==0 or v!=stops[j-1]]
        if len(stops)<3 or stops[0]!=stops[-1]:raise ValueError('City Circle must return to its suburban terminus')
        services[i]['path']=path;services[i]['stops']=stops;l['one_way']=True
        print('Joined Sydney City Circle:',l['name'],flush=True)
    for p,data in zip(files,(net,doc)):p.write_text(json.dumps(data))
