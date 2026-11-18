"""Construct one-way City Loop balloons and cross-city services in the shared-track model."""
import copy
import heapq
import json
import math


def build(out):
    files = [out/'mel_real.json', out/'mel_real_corridors.json', out/'mel_real_geom.json']
    net, doc, geo = [json.loads(p.read_text()) for p in files]
    model = doc['model']; nodes = model['nodes']; edges = model['edges']; lines = net['lines']; services = model['lines']
    first_clone = len(nodes)

    def walk(path):
        ends = []
        for code in path:
            edge = edges[code >> 1]
            ends.append((edge['a'], edge['b']) if not code & 1 else (edge['b'], edge['a']))
        if not ends or any(a[1] != b[0] for a, b in zip(ends, ends[1:])):
            raise ValueError('Disconnected input path')
        return [ends[0][0]] + [x[1] for x in ends]

    def lookup(name):
        ids = [i for i, line in enumerate(lines) if line['name'] == name]
        if len(ids) != 1: raise ValueError(f'Expected one {name}: {ids}')
        return ids[0]

    def stop_list(path, allowed_keys):
        stops = [node for node in walk(path) if nodes[node]['station'] and nodes[node]['station']['key'] in allowed_keys]
        stops = [s for i,s in enumerate(stops) if not i or s != stops[i-1]]
        if len(stops) < 3 or stops[0] != stops[-1]: raise ValueError('Balloon must end at its starting terminus')
        return stops

    anchors = []; cloned_stations = []; loops = {}
    def make(name, helper, anchor, shift):
        i,j = lookup(name),lookup(helper); target, guide = services[i],services[j]
        pa,pb = target['path'],guide['path']; na,nb = walk(pa),walk(pb)
        at = next(k for k,v in enumerate(na) if (nodes[v]['station'] or {}).get('name') == anchor)
        possible = [(k,nb.index(v),v) for k,v in enumerate(na) if k >= at and v in nb and nodes[v]['station'] is None]
        if not possible: raise ValueError(f'{name} has no suitable junction with {helper}')
        k,h,join = possible[0]; anchors.append(join)
        first = copy.deepcopy(nodes[na[0]]); first['xy'] = [v+d for v,d in zip(first['xy'],shift)]
        fss = len(nodes); nodes.append(first); cloned_stations.append(fss)
        def clone(path, ids):
            remap = {ids[0]:fss, join:join}
            for old in ids[1:-1]:
                if old not in remap:
                    node = copy.deepcopy(nodes[old]); node['xy'] = [v+d for v,d in zip(node['xy'],shift)]
                    remap[old] = len(nodes); nodes.append(node)
            result = []
            for code in path:
                edge = copy.deepcopy(edges[code >> 1]); olda = nodes[edge['a']]['xy']; oldb = nodes[edge['b']]['xy']
                edge['a'],edge['b'] = remap[edge['a']],remap[edge['b']]
                da = [x-y for x,y in zip(nodes[edge['a']]['xy'],olda)]; db = [x-y for x,y in zip(nodes[edge['b']]['xy'],oldb)]
                if edge['lead_a'] is not None:
                    edge['lead_a'] = [x+y for x,y in zip(edge['lead_a'],da)]
                    edge['lead_b'] = [x+y for x,y in zip(edge['lead_b'],db)]
                    count = len(edge['line'])
                    edge['line'] = [[v+(da[z]*(count-t)+db[z]*(t+1))/(count+1) for z,v in enumerate(pt)] for t,pt in enumerate(edge['line'])]
                result.append(len(edges) << 1 | code & 1); edges.append(edge)
            return result
        loop = clone(pa[:k],na[:k+1]); direct = clone(pb[:h],nb[:h+1]); tail = pa[k:]
        for code in loop:
            edge = edges[code >> 1]; edge['tracks'] = 1; edge['oneway'] = 1 if (code ^ 1) & 1 == 0 else 2
        for code in direct:
            edge = edges[code >> 1]; edge['tracks'] = 1; edge['oneway'] = 1 if code & 1 == 0 else 2
        allowed = {nodes[s]['station']['key'] for s in target['stops']}
        allowed |= {n['station']['key'] for n in nodes if n['station'] and n['station']['name'] in ('Flinders Street','Southern Cross','Flagstaff','Melbourne Central','Parliament')}
        path = [p^1 for p in tail[::-1]] + [p^1 for p in loop[::-1]] + direct + tail
        target['stops'] = stop_list(path,allowed); target['path'] = path; lines[i]['one_way'] = True
        loops[name] = (loop,direct,join,allowed)
        print(f'{name}: through Flinders Street via one-way loop, join node {join}', flush=True)

    for args in [('Belgrave','Alamein','Richmond',[35,55]),
                 ('Hurstbridge','Mernda','Jolimont-MCG',[0,0]),
                 ('Craigieburn','Upfield','North Melbourne',[70,70]),
                 ('Frankston','Frankston geometry guide','Richmond',[-35,-55])]:
        make(*args)

    def add_branch(name, template):
        i = lookup(name); service = services[i]; loop,direct,join,city_keys = loops[template]
        seq = walk(service['path'])
        if join not in seq: raise ValueError(f'{name} cannot reach its {template} loop junction')
        k = seq.index(join); tail = service['path'][k:]
        allowed = {nodes[s]['station']['key'] for s in service['stops']} | city_keys
        path = [p^1 for p in tail[::-1]] + [p^1 for p in loop[::-1]] + direct + tail
        service['stops'] = stop_list(path,allowed); service['path'] = path; lines[i]['one_way'] = True
        print(f'{name}: shares {template} City Loop track', flush=True)

    for name, template in [('Alamein','Belgrave'),('Lilydale','Belgrave'),('Glen Waverley','Belgrave'),
                           ('Mernda','Hurstbridge'),('Upfield','Craigieburn')]:
        add_branch(name,template)

    # Discard the Frankston geometry guide and edges that no remaining service uses.
    keep = [i for i,l in enumerate(lines) if l['name'] != 'Frankston geometry guide']
    net['lines'] = [lines[i] for i in keep]; model['lines'] = [services[i] for i in keep]; geo['lines'] = [geo['lines'][i] for i in keep]
    used = {v >> 1 for line in model['lines'] if line for v in line['path']}
    for i,e in enumerate(edges):
        if any((nodes[v]['station'] or {}).get('name') == 'Flemington Racecourse' for v in (e['a'],e['b'])): used.add(i)
    ids = sorted(used); remap = {v:i for i,v in enumerate(ids)}; model['edges'] = [edges[i] for i in ids]; edges = model['edges']
    for line in model['lines']:
        if line: line['path'] = [remap[v >> 1] << 1 | v & 1 for v in line['path']]
    active = {v for e in edges for v in (e['a'],e['b'])}
    for i,node in enumerate(nodes):
        if i not in active: node['station'] = None

    # Keep each new tunnel on one level; transition near its branch junction.
    # Levels are a deliberately simplified game geometry, not a survey.
    for node in nodes[first_clone:]: node['level'] = -1
    adj = {}
    for e in edges:
        a,b = e['a'],e['b']
        if max(a,b) < first_clone: continue
        e['levels'] = []
        length = math.dist(nodes[a]['xy'],nodes[b]['xy'])
        adj.setdefault(a,[]).append((b,length)); adj.setdefault(b,[]).append((a,length))
    for root in anchors:
        q=[(0,root)]; seen=set()
        while q:
            distance,u=heapq.heappop(q)
            if distance > 1800 or u in seen: continue
            seen.add(u)
            if u >= first_clone: nodes[u]['level']=nodes[root]['level']
            for v,d in adj.get(u,[]):
                if v >= first_clone and v not in seen: heapq.heappush(q,(distance+d,v))
    # Propagate levels along short clone edges until every requested height
    # change has enough straight-line room for the game's maximum grade.
    queue=[(0,root) for root in anchors]; heapq.heapify(queue); nearest={}
    while queue:
        distance,u=heapq.heappop(queue)
        if u in nearest: continue
        nearest[u]=distance
        for v,length in adj.get(u,[]):
            if v >= first_clone and v not in nearest: heapq.heappush(queue,(distance+length,v))
    for _ in range(len(nodes)):
        changed=0
        for edge in edges:
            a,b=edge['a'],edge['b']
            if max(a,b)<first_clone or a not in nearest or b not in nearest: continue
            diff=abs(nodes[a]['level']-nodes[b]['level'])
            if diff and math.dist(nodes[a]['xy'],nodes[b]['xy']) < 200*diff+100:
                near,far=(a,b) if nearest[a]<nearest[b] else (b,a)
                if far >= first_clone:
                    nodes[far]['level']=nodes[near]['level']; changed+=1
        if not changed: break
    else:
        raise ValueError('Could not settle cloned loop levels')

    # Align the two approaches at each through Flinders Street platform.
    for i in cloned_stations:
        incident=[(e,'a' if e['a']==i else 'b') for e in edges if i in (e['a'],e['b'])]
        if len(incident)!=2: raise ValueError('A loop platform must have two through approaches')
        xy=nodes[i]['xy']; vectors=[]
        for e,side in incident:
            lead=e['lead_'+side] or nodes[e['b' if side=='a' else 'a']]['xy']
            vectors.append([lead[k]-xy[k] for k in range(2)])
        norm=[math.hypot(*v) for v in vectors]
        axis=[vectors[0][k]/norm[0]-vectors[1][k]/norm[1] for k in range(2)]; size=math.hypot(*axis)
        if size < 1: raise ValueError('Flinders Street approaches face the same way')
        for k,(e,side) in enumerate(incident):
            sign=1 if k==0 else -1
            e['lead_'+side]=[xy[j]+sign*100*axis[j]/size for j in range(2)]
            e['line']=[pt for pt in e['line'] if math.dist(pt,xy)>140]

    # Werribee and Williamstown through-run with Sandringham via Flinders Street.
    lines,services=net['lines'],model['lines']
    w,v,s = lookup('Werribee (direct)'),lookup('Williamstown'),lookup('Sandringham')
    a,b=services[w]['stops'][0],services[s]['stops'][0]
    if any(services[i]['stops'][0] != a for i in (w,v)) or any(sum(x in (e['a'],e['b']) for e in edges)!=1 for x in (a,b)):
        raise ValueError('Unexpected cross-city Flinders Street layout')
    mid=[(x+y)/2 for x,y in zip(nodes[a]['xy'],nodes[b]['xy'])]
    for e in edges:
        for side in ('a','b'):
            old=e[side]
            if old not in (a,b): continue
            lead='lead_'+side
            if e[lead] is not None: e[lead]=[v+mid[i]-nodes[old]['xy'][i] for i,v in enumerate(e[lead])]
            e[side]=a
    nodes[a]['xy']=mid;nodes[a]['level']=0;nodes[b]['station']=None
    for line in services:
        if line: line['stops']=[a if x==b else x for x in line['stops']]
    incident=[(e,'a' if e['a']==a else 'b') for e in edges if a in (e['a'],e['b'])]
    vec=[[e['lead_'+side][i]-mid[i] for i in range(2)] for e,side in incident]; norm=[math.hypot(*x) for x in vec]
    axis=[vec[0][i]/norm[0]-vec[1][i]/norm[1] for i in range(2)]; mag=math.hypot(*axis)
    for k,(e,side) in enumerate(incident):
        sign=1 if k==0 else -1;e['lead_'+side]=[mid[i]+sign*150*axis[i]/mag for i in range(2)]
        e['line']=[x for x in e['line'] if math.dist(x,mid)>190]
    keep=[i for i in range(len(lines)) if i not in (w,v,s)]
    newlines=[lines[i] for i in keep];newservices=[services[i] for i in keep];newgeo=[geo['lines'][i] for i in keep]
    for i in (w,v):
        x,y=lines[i],lines[s];xm,ym=services[i],services[s];line=copy.deepcopy(x)
        line['name']=('Werribee' if i==w else 'Williamstown')+' – Sandringham'
        line['stops']=x['stops'][::-1]+y['stops'][1:]
        line['t0']=[x['t1'][k][::-1][:-1]+y['t0'][k] for k in range(3)]
        line['t1']=[x['t0'][k][::-1]+y['t1'][k][1:] for k in range(3)]
        # Avoid assigning more trains to Sandringham than its selected timetable.
        rates=[]
        for k in range(3):
            total=lines[w]['tph'][k]+lines[v]['tph'][k]
            rates.append(x['tph'][k]*min(1,y['tph'][k]/total) if total else 0)
        line['tph']=rates; service=copy.deepcopy(xm)
        service['stops']=xm['stops'][::-1]+ym['stops'][1:]
        service['path']=[p^1 for p in xm['path'][::-1]]+ym['path'];service['tph']=rates
        newlines.append(line);newservices.append(service);newgeo.append(geo['lines'][i])
    net['lines']=newlines;model['lines']=newservices;geo['lines']=newgeo
    for path,data in zip(files,(net,doc,geo)): path.write_text(json.dumps(data))
