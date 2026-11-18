"""Align the common underground Loop segment on parallel, directional tracks."""
import copy
import json
import math
from collections import defaultdict
from shapely.geometry import LineString
from shapely.ops import substring


def merge_redundant_platforms(model):
    """Collapse parallel station paths with the same two junctions and station key."""
    nodes, edges = model['nodes'], model['edges']
    incident = defaultdict(list)
    for i,e in enumerate(edges):
        incident[e['a']].append((i,e['b']))
        incident[e['b']].append((i,e['a']))
    groups = defaultdict(list)
    for i,node in enumerate(nodes):
        st = node['station']
        if st and len(incident[i]) == 2:
            groups[(st['key'], tuple(sorted(other for _,other in incident[i])))].append(i)
    replacements = {}; stop_map = {}
    for group in groups.values():
        if len(group) != 2: continue
        keep, drop = group
        if math.dist(nodes[keep]['xy'], nodes[drop]['xy']) > 40: continue
        # Only merge ordinary double tracks, not directional or differently upgraded edges.
        pairs = []
        for old,other in incident[drop]:
            new = next(i for i,v in incident[keep] if v == other)
            if any(edges[x].get('tracks', 2) != 2 or edges[x].get('oneway', 0) for x in (old,new)):
                break
            pairs.append((old,new,other))
        if len(pairs) != 2: continue
        for old,new,other in pairs:
            # Preserve traversal direction, taking the kept platform as the dropped one.
            flip = (edges[old]['a'] == other) != (edges[new]['a'] == other)
            replacements[old] = (new, flip)
        stop_map[drop] = keep
        nodes[drop]['station'] = None
        print(f"Merged redundant platforms at {nodes[keep]['station']['name']}", flush=True)
    for service in model['lines']:
        if not service: continue
        path=[]
        for code in service['path']:
            edge,flip = replacements.get(code >> 1, (code >> 1, False))
            path.append(edge << 1 | ((code & 1) ^ flip))
        service['path'] = path
        service['stops'] = [stop_map.get(s,s) for s in service['stops']]
    return set(replacements)


def remove_short_station_joints(model):
    """Remove degree-two joints within a platform, without changing route connectivity."""
    nodes, edges = model['nodes'], model['edges']
    removed = set()
    for station, node in enumerate(nodes):
        if not node['station'] or node['station']['name'] != 'Southern Cross': continue
        for short, edge in list(enumerate(edges)):
            if short in removed or station not in (edge['a'],edge['b']): continue
            joint = edge['b'] if edge['a'] == station else edge['a']
            if nodes[joint]['station'] or math.dist(node['xy'],nodes[joint]['xy']) >= 80: continue
            incident = [i for i,e in enumerate(edges) if i not in removed and joint in (e['a'],e['b'])]
            if len(incident) != 2: continue
            other = next(i for i in incident if i != short)
            outer = edges[other]
            if (edge.get('tracks',2), bool(edge.get('oneway',0))) != (outer.get('tracks',2), bool(outer.get('oneway',0))): continue
            if nodes[station]['level'] != nodes[joint]['level']: continue
            # Every use must also traverse the connecting edge, not terminate at the joint.
            if any(any((c >> 1) == short and not ((k and (s['path'][k-1] >> 1) == other) or
                       (k+1 < len(s['path']) and (s['path'][k+1] >> 1) == other))
                       for k,c in enumerate(s['path'])) for s in model['lines'] if s): continue
            side = 'a' if outer['a'] == joint else 'b'
            outer[side] = station
            delta = [node['xy'][j]-nodes[joint]['xy'][j] for j in (0,1)]
            if outer['lead_'+side] is not None:
                outer['lead_'+side] = [outer['lead_'+side][j]+delta[j] for j in (0,1)]
            outer['line'] = [p for p in outer['line'] if math.dist(p,node['xy']) > 100]
            for service in model['lines']:
                if service: service['path'] = [c for c in service['path'] if c >> 1 != short]
            removed.add(short)
    print(f'Removed {len(removed)} short Southern Cross platform joints',flush=True)


def separate_event_tracks(model, net):
    """Space the event route away from the cross-city tracks in the diagram."""
    nodes, edges, services = model['nodes'], model['edges'], model['lines']
    index = next(i for i,l in enumerate(net['lines']) if l['name'].startswith('Flemington Racecourse'))
    service = services[index]
    old_edges = {c >> 1 for c in service['path']}
    old_nodes = {v for i in old_edges for v in (edges[i]['a'],edges[i]['b'])}
    shift = (40.0,40.0)
    node_map = {}
    for old in sorted(old_nodes):
        node=copy.deepcopy(nodes[old]); node['xy']=[node['xy'][j]+shift[j] for j in (0,1)]
        node_map[old]=len(nodes); nodes.append(node)
    edge_map={}
    for old in sorted(old_edges):
        edge=copy.deepcopy(edges[old]); edge['a']=node_map[edge['a']];edge['b']=node_map[edge['b']]
        for side in ('a','b'):
            if edge['lead_'+side] is not None: edge['lead_'+side]=[edge['lead_'+side][j]+shift[j] for j in (0,1)]
        edge['line']=[[p[j]+shift[j] for j in (0,1)] for p in edge['line']]
        edge_map[old]=len(edges);edges.append(edge)
    service['path']=[edge_map[c>>1]<<1 | c&1 for c in service['path']]
    service['stops']=[node_map[v] for v in service['stops']]
    # The unserved extension must still connect to the moved Showgrounds stop.
    for edge in edges:
        ends=(edge['a'],edge['b'])
        if not any((nodes[v]['station'] or {}).get('name')=='Flemington Racecourse' for v in ends): continue
        for side in ('a','b'):
            if edge[side] in node_map:
                edge[side]=node_map[edge[side]]
                if edge['lead_'+side] is not None: edge['lead_'+side]=[edge['lead_'+side][j]+shift[j] for j in (0,1)]
    print('Separated event route from cross-city track for readability',flush=True)


def merge_identical_edges(model):
    """Use one edge when generated railway edges are exactly identical."""
    seen={}; remap={}
    for i,edge in enumerate(model['edges']):
        key=json.dumps(edge,sort_keys=True,separators=(',',':'))
        if key in seen: remap[i]=seen[key]
        else: seen[key]=i
    for service in model['lines']:
        if service: service['path']=[remap.get(c>>1,c>>1)<<1 | c&1 for c in service['path']]
    print(f'Merged {len(remap)} exactly coincident rail edges',flush=True)


def align(out):
    files = [out / 'mel_real.json', out / 'mel_real_corridors.json']
    net, doc = [json.loads(p.read_text()) for p in files]
    m = doc['model']; nodes = m['nodes']; edges = m['edges']; services = m['lines']
    def walk(path):
        def ends(c):
            e = edges[c >> 1]
            return (e['b'], e['a']) if c & 1 else (e['a'], e['b'])
        return [ends(path[0])[0]] + [ends(c)[1] for c in path]
    def name(i): return (nodes[i]['station'] or {}).get('name')
    def line(name): return next(i for i,l in enumerate(net['lines']) if l['name'] == name)
    def section(i):
        ids = walk(services[i]['path'])
        p = next(k for k,x in enumerate(ids) if name(x) == 'Parliament')
        flags = [k for k,x in enumerate(ids) if name(x) == 'Flagstaff']
        f = max(flags) if p < flags[0] else min(flags)
        return ids, p, f
    ids,p,f = section(line('Belgrave'))
    spine = LineString([nodes[x]['xy'] for x in ids[p:f+1]]).simplify(12)
    mid = next(x for x in ids[p:f+1] if name(x) == 'Melbourne Central')
    from shapely.geometry import Point
    fraction = spine.project(Point(nodes[mid]['xy'])) / spine.length
    # The order remains fixed around curves; each is a separate one-way track.
    aligned_stations = []
    for primary, members, offset in [
        ('Belgrave', ['Belgrave','Alamein','Lilydale','Glen Waverley'], -90),
        ('Hurstbridge', ['Hurstbridge','Mernda'], -30),
        ('Craigieburn', ['Craigieburn','Upfield'], 30),
        ('Frankston', ['Frankston'], 90),
    ]:
        i = line(primary); ids,p,f = section(i); lo,hi=sorted((p,f))
        old = services[i]['path'][lo:hi]
        pm = ids[p]; fm = ids[f]
        mm = next(x for x in ids[lo:hi+1] if name(x) == 'Melbourne Central')
        aligned_stations.extend((pm, mm, fm))
        other_flags = [x for x in ids[lo:hi+1] if name(x) == 'Flagstaff' and x != fm]
        curve = spine.offset_curve(offset)
        if curve.geom_type != 'LineString' or curve.length < spine.length * .8:
            raise ValueError('Cannot offset City Loop spine')
        # Shapely retains the direction of the original line.
        cuts = [0, fraction * curve.length, curve.length]
        for node,dist in zip((pm,mm,fm),cuts):
            xy = list(curve.interpolate(dist).coords[0]); delta = [xy[j]-nodes[node]['xy'][j] for j in (0,1)]
            for e in edges:
                for side in ('a','b'):
                    if e[side] == node and e['lead_'+side] is not None:
                        e['lead_'+side] = [e['lead_'+side][j] + delta[j] for j in (0,1)]
            nodes[node]['xy'] = xy
        new=[]
        for a,b,start,end in zip((pm,mm),(mm,fm),cuts,cuts[1:]):
            segment=substring(curve,start,end)
            length=end-start
            lead=min(80,length/4)
            la=list(curve.interpolate(start+lead).coords[0]); lb=list(curve.interpolate(end-lead).coords[0])
            inner=substring(curve,start+lead,end-lead)
            pts=list(inner.coords)[1:-1] if inner.geom_type == 'LineString' else []
            e=copy.deepcopy(edges[old[0]>>1]); e.update(a=a,b=b,lead_a=la,lead_b=lb,line=pts,tracks=1,oneway=1 if p<f else 2,levels=[])
            new.append(len(edges)<<1);edges.append(e)
        replacement = new if p<f else [c^1 for c in new[::-1]]
        for member in members:
            j=line(member); path=services[j]['path']
            matches=[k for k in range(len(path)-len(old)+1) if path[k:k+len(old)] == old]
            if len(matches)!=1: raise ValueError(f'{member}: shared Loop segment not found')
            k=matches[0]; services[j]['path']=path[:k]+replacement+path[k+len(old):]
            services[j]['stops']=[x for x in services[j]['stops'] if x not in other_flags]
        print(f'Aligned {primary} Loop segment; removed {len(other_flags)} duplicate Flagstaff stops',flush=True)
    # Give the four groups the same ordering on the Southern Cross–Flinders Street
    # curve as on the underground section. Their stations may be moved to fit.
    def river_section(i):
        ids=walk(services[i]['path'])
        a=next(k for k,x in enumerate(ids) if name(x)=='Southern Cross')
        b=next(k for k,x in enumerate(ids) if name(x)=='Flinders Street')
        return ids,a,b
    ids,a,b=river_section(line('Belgrave'))
    river=LineString([nodes[x]['xy'] for x in ids[a:b+1]]).simplify(12)
    for primary,members,offset in [
        ('Belgrave',['Belgrave','Alamein','Lilydale','Glen Waverley'],-90),
        ('Hurstbridge',['Hurstbridge','Mernda'],-30),
        ('Craigieburn',['Craigieburn','Upfield'],30),
        ('Frankston',['Frankston'],90),
    ]:
        i=line(primary); ids,a,b=river_section(i); lo,hi=sorted((a,b)); old=services[i]['path'][lo:hi]
        start,end=ids[a],ids[b]; curve=river.offset_curve(offset)
        if curve.geom_type != 'LineString' or curve.length < river.length * .8: raise ValueError('Cannot offset river Loop curve')
        for node,distance in ((start,0),(end,curve.length)):
            xy=list(curve.interpolate(distance).coords[0]); delta=[xy[j]-nodes[node]['xy'][j] for j in (0,1)]
            for e in edges:
                for side in ('a','b'):
                    if e[side]==node and e['lead_'+side] is not None:
                        e['lead_'+side]=[e['lead_'+side][j]+delta[j] for j in (0,1)]
            nodes[node]['xy']=xy
        aligned_stations.extend((start,end))
        lead=min(80,curve.length/4)
        mid=substring(curve,lead,curve.length-lead)
        e=copy.deepcopy(edges[old[0]>>1]); e.update(a=start,b=end,lead_a=list(curve.interpolate(lead).coords[0]),lead_b=list(curve.interpolate(curve.length-lead).coords[0]),line=list(mid.coords)[1:-1],tracks=1,oneway=1 if a<b else 2,levels=[])
        new=len(edges)<<1;edges.append(e);replacement=[new if a<b else new^1]
        for member in members:
            path=services[line(member)]['path']; matches=[k for k in range(len(path)-len(old)+1) if path[k:k+len(old)]==old]
            if len(matches)!=1: raise ValueError(f'{member}: river Loop segment not found')
            k=matches[0];services[line(member)]['path']=path[:k]+replacement+path[k+len(old):]
        print(f'Aligned {primary} Southern Cross–Flinders Street track',flush=True)
    # Three groups travel from Flagstaff to Southern Cross. Derive their
    # intermediate curves from a common spine; the Northern group instead
    # enters via North Melbourne, so it does not use this part of the loop.
    def western_section(i):
        ids=walk(services[i]['path'])
        a=next(k for k,x in enumerate(ids) if name(x)=='Flagstaff')
        b=next(k for k,x in enumerate(ids) if name(x)=='Southern Cross')
        if a>=b: raise ValueError('Unexpected western Loop order')
        return ids,a,b
    ids,a,b=western_section(line('Belgrave'))
    western=LineString([nodes[x]['xy'] for x in ids[a:b+1]]).simplify(8)
    for primary,members,offset in [
        ('Belgrave',['Belgrave','Alamein','Lilydale','Glen Waverley'],0),
        ('Hurstbridge',['Hurstbridge','Mernda'],60),
        ('Frankston',['Frankston'],120),
    ]:
        ids,a,b=western_section(line(primary));old=services[line(primary)]['path'][a:b]
        start,end=ids[a],ids[b];curve=western.offset_curve(offset)
        if curve.geom_type != 'LineString' or curve.length < western.length*.7: raise ValueError('Cannot offset western Loop curve')
        lead=min(80,curve.length/4); c0=list(curve.coords[0]); c1=list(curve.coords[-1]); start_xy=nodes[start]['xy'];end_xy=nodes[end]['xy']
        va=list(curve.interpolate(lead).coords[0]);vb=list(curve.interpolate(curve.length-lead).coords[0])
        middle=substring(curve,lead,curve.length-lead)
        e=copy.deepcopy(edges[old[0]>>1]);e.update(a=start,b=end,
            lead_a=[start_xy[j]+va[j]-c0[j] for j in (0,1)],lead_b=[end_xy[j]+vb[j]-c1[j] for j in (0,1)],
            line=list(middle.coords)[1:-1],tracks=1,oneway=1,levels=[])
        new=len(edges)<<1;edges.append(e)
        for member in members:
            path=services[line(member)]['path']; matches=[k for k in range(len(path)-len(old)+1) if path[k:k+len(old)]==old]
            if len(matches)!=1: raise ValueError(f'{member}: western Loop segment not found')
            k=matches[0];services[line(member)]['path']=path[:k]+[new]+path[k+len(old):]
        print(f'Aligned {primary} Flagstaff–Southern Cross track',flush=True)
    # Keep the Flinders Street platforms level, placing the simplified
    # Clifton Hill transition further out on the approach to Jolimont.
    ids=walk(services[line('Hurstbridge')]['path'])
    start=next(i for i,v in enumerate(ids) if name(v)=='Flinders Street')
    end=next(i for i,v in enumerate(ids[start+1:],start+1) if name(v)=='Jolimont-MCG')
    for v in ids[start:end]: nodes[v]['level']=nodes[ids[start-1]]['level']
    merge_redundant_platforms(m)
    remove_short_station_joints(m)
    separate_event_tracks(m,net)
    merge_identical_edges(m)
    used={c>>1 for s in services if s for c in s['path']}
    # Preserve deliberately unserved Flemington infrastructure.
    used.update(i for i,e in enumerate(edges) if any(name(v)=='Flemington Racecourse' for v in (e['a'],e['b'])))
    indices=sorted(used); remap={old:i for i,old in enumerate(indices)}
    m['edges']=[edges[i] for i in indices]
    for s in services:
        if s: s['path']=[remap[c>>1]<<1 | c&1 for c in s['path']]
    active={v for e in m['edges'] for v in (e['a'],e['b'])}
    for i,n in enumerate(nodes):
        if i not in active: n['station']=None
    # Stations need opposite, collinear approaches in the game's track model.
    for node in aligned_stations:
        xy = nodes[node]['xy']
        incident = [(e, 'a' if e['a'] == node else 'b') for e in m['edges'] if node in (e['a'], e['b'])]
        if len(incident) != 2: raise ValueError(f'Unexpected Loop station degree at {name(node)}')
        vectors = [[e['lead_'+side][j] - xy[j] for j in (0,1)] for e,side in incident]
        lengths = [math.hypot(*v) for v in vectors]
        axis = [vectors[0][j]/lengths[0] - vectors[1][j]/lengths[1] for j in (0,1)]
        length = math.hypot(*axis)
        if length < 0.1: raise ValueError(f'Unexpected Loop station heading at {name(node)}')
        for k,(e,side) in enumerate(incident):
            other = nodes[e['b' if side == 'a' else 'a']]['xy']
            lead = min(80, math.dist(xy, other) / 4)
            e['lead_'+side] = [xy[j] + (1 if k == 0 else -1)*lead*axis[j]/length for j in (0,1)]
            e['line'] = [p for p in e['line'] if math.dist(p,xy) > lead + 20]
    for primary in ('Belgrave', 'Alamein', 'Lilydale', 'Glen Waverley', 'Hurstbridge', 'Mernda', 'Craigieburn', 'Upfield', 'Frankston'):
        stops = services[line(primary)]['stops']
        if sum(name(s) == 'Flagstaff' for s in stops) != 1:
            raise ValueError(f'{primary}: expected exactly one Flagstaff stop')
    for path,data in zip(files,(net,doc)): path.write_text(json.dumps(data))
