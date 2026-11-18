#!/usr/bin/env python3
"""Create a metropolitan rail save with upstream realnet and shared-corridor builder."""
import argparse
import datetime as dt
import io
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TW = ROOT / 'trainworld'
sys.path.insert(0, str(TW / 'pipeline'))

# Melbourne does not use route-number badges: these are deliberately concise game labels.
SYMBOLS = {'Alamein':'ALM', 'Belgrave':'BEG', 'Cranbourne':'CBE', 'Craigieburn':'CGB',
           'Frankston':'FKN', 'Glen Waverley':'GWY', 'Hurstbridge':'HBE', 'Lilydale':'LIL',
           'Mernda':'MDD', 'Pakenham':'PKM', 'Flemington Racecourse':'RCE', 'Sandringham':'SHM',
           'Stony Point':'STY', 'Sunbury':'SUY', 'Upfield':'UFD', 'Werribee':'WER', 'Williamstown':'WIL'}

# Groups follow the route colours in the Victorian GTFS feed. IDs are stable.
GROUPS = {
    **{x: (1, 'Burnley Group', 'BLU') for x in ('Alamein','Belgrave','Glen Waverley','Lilydale')},
    **{x: (2, 'Clifton Hill Group', 'RED') for x in ('Hurstbridge','Mernda')},
    **{x: (3, 'Northern Group', 'YEL') for x in ('Craigieburn','Upfield')},
    **{x: (4, 'Caulfield Group', 'GRN') for x in ('Frankston','Stony Point')},
    **{x: (5, 'Cross-City Group', 'PNK') for x in ('Sandringham','Werribee','Williamstown')},
    **{x: (6, 'Metro Tunnel', 'TUN') for x in ('Cranbourne','Pakenham','Sunbury')},
    'Flemington Racecourse': (7, 'Special Events', 'EVT'),
}
TERMINALS = {name: ('East Pakenham' if name == 'Pakenham' else 'Showgrounds' if name == 'Flemington Racecourse' else name) for name in SYMBOLS}

def simplify_services(net, city_loops=False):
    """Choose a main pattern per route, add only variants needed for stop coverage.

    Frequencies of removed patterns are assigned to the kept pattern that shares
    the greatest fraction of stops, favouring its matching terminal. This is a
    deliberate approximation; it is not a recreation of express stopping.
    """
    from copy import deepcopy
    original = net['lines']; stations = net['stations']
    routes = defaultdict(list)
    for i, line in enumerate(original): routes[line['route']].append(i)
    def full_direct_stops(primary, ids):
        # Keep direct approaches legible, but restore observed intermediate stops
        # from a longer compatible pattern. Never invent an unobserved hop time.
        if primary['name'] not in {'Alamein', 'Glen Waverley', 'Mernda', 'Lilydale', 'Frankston'}:
            return None
        city = {'Southern Cross', 'Flagstaff', 'Melbourne Central', 'Parliament'}
        candidates = []
        for i in ids:
            route = [s for s in original[i]['stops'] if stations[s]['name'] not in city]
            at = iter(route)
            if all(any(s == v for s in at) for v in primary['stops']): candidates.append(route)
        if not candidates: return None
        target = max(candidates, key=len)
        if len(target) <= len(primary['stops']): return None
        from statistics import median
        samples = defaultdict(list)
        for i in ids:
            line = original[i]
            for k, (a, b) in enumerate(zip(line['stops'], line['stops'][1:])):
                for lv in range(3):
                    for pair, value in (((a,b), line['t0'][lv][k]), ((b,a), line['t1'][lv][k+1])):
                        if value > 0: samples[(pair, lv)].append(value)
        t0 = [[0.0]*len(target) for _ in range(3)]; t1 = [[0.0]*len(target) for _ in range(3)]
        for k,(a,b) in enumerate(zip(target,target[1:])):
            for lv in range(3):
                f = samples.get(((a,b),lv)) or samples.get(((b,a),lv))
                r = samples.get(((b,a),lv)) or f
                if not f or not r: return None
                t0[lv][k] = float(median(f)); t1[lv][k+1] = float(median(r))
        return target, t0, t1
    expanded = {i: full_direct_stops(line, routes[line['route']]) for i, line in enumerate(original)}
    def selected_stops(i):
        return expanded[i][0] if expanded[i] is not None else original[i]['stops']
    chosen = []
    for route, ids in routes.items():
        name = original[ids[0]]['name']; target = TERMINALS[name]
        eligible = [i for i in ids if any(stations[s]['name'] == target for s in original[i]['stops'])]
        eligible = eligible or ids
        # Keep a few direct city approaches to avoid piling every line onto the
        # same loop; the remaining patterns still represent the City Loop.
        direct_preferred = {'Alamein', 'Glen Waverley', 'Mernda', 'Lilydale', 'Upfield'}
        if name in direct_preferred:
            direct = [i for i in eligible if not any(stations[x]['name'] in ('Parliament', 'Melbourne Central', 'Flagstaff') for x in original[i]['stops'])]
            if direct: eligible = direct
        best = max(eligible, key=lambda i: (len(set(original[i]['stops'])), sum(original[i]['tph']), -i))
        chosen.append(best)
    all_stops = {s for line in original for s in line['stops']}
    served = {s for i in chosen for s in selected_stops(i)}
    while missing := all_stops - served:
        options = [i for i in range(len(original)) if i not in chosen and set(selected_stops(i)) & missing]
        if not options: raise ValueError('Cannot preserve all GTFS stations while consolidating')
        best = max(options, key=lambda i: (len(set(selected_stops(i)) & missing), sum(original[i]['tph']), -i))
        chosen.append(best); served.update(selected_stops(best))
    chosen.sort()
    assigned = {i: [] for i in chosen}
    for i, line in enumerate(original):
        options = [j for j in chosen if original[j]['route'] == line['route']]
        def similarity(j):
            common = len(set(line['stops']) & set(selected_stops(j)))
            # A short turn and a full-length pattern stay with the same branch when possible.
            return (common / len(set(line['stops'])), line['stops'][-1] == original[j]['stops'][-1], common, -j)
        assigned[i if i in assigned else max(options, key=similarity)].append(i)
    result = []
    for j in chosen:
        line = deepcopy(original[j]); sources = assigned[j]
        full = expanded[j]
        if full is not None:
            line['stops'], line['t0'], line['t1'] = full
        line['tph'] = [round(sum(original[i]['tph'][lv] for i in sources), 2) for lv in range(3)]
        line['trips_day'] = sum(original[i].get('trips_day', 0) for i in sources)
        line['merged_patterns'] = len(sources)
        result.append(line)
    if city_loops:
        # Temporary geometry guide: a low-frequency Frankston direct pattern is
        # removed after its city approach is used to close the Caulfield loop.
        direct = [i for i, l in enumerate(original) if l['name'] == 'Frankston' and not any(stations[x]['name'] in ('Parliament','Melbourne Central','Flagstaff') for x in l['stops']) and stations[l['stops'][-1]]['name'] == 'Frankston']
        if not direct: raise ValueError('Missing Frankston direct geometry guide')
        best = max(direct, key=lambda i:len(selected_stops(i)))
        guide = deepcopy(original[best])
        if expanded[best] is not None: guide['stops'], guide['t0'], guide['t1'] = expanded[best]
        guide['name'] = 'Frankston geometry guide'; guide['tph'] = [0.05,0.05,0.05]; guide['trips_day'] = 0
        result.append(guide)
    net['lines'] = result
    # Keep the upstream demand snapshot consistent with the selected network.
    d = {'st_xy':[v for st in stations for v in (st['x'],st['y'])], 'line_n':[], 'stops':[], 'times':[], 'tph':[], 'cars':[]}
    for line in result:
        d['line_n'].append(len(line['stops'])); d['stops'] += line['stops']
        for direction in (line['t0'], line['t1']):
            for level in direction: d['times'] += level
        d['tph'] += line['tph']; d['cars'].append(line['cars'])
    net['demand'] = d
    print(f'Consolidated {len(original)} patterns into {len(result)}, retaining {len(all_stops)} distinct GTFS station keys', flush=True)
    return net

def service_ids(calendar, dates, date):
    day = date.strftime('%Y%m%d')
    ids = set()
    if calendar is not None:
        mask = ((calendar.start_date <= day) & (calendar.end_date >= day) &
                (calendar[date.strftime('%A').lower()] == '1'))
        ids |= set(calendar.loc[mask, 'service_id'])
    if dates is not None:
        rows = dates[dates.date == day]
        ids |= set(rows.loc[rows.exception_type == '1', 'service_id'])
        ids -= set(rows.loc[rows.exception_type == '2', 'service_id'])
    return ids

def single_track_stony_point(out):
    """Use single track only for edges exclusively used by Stony Point."""
    net = json.loads((out / 'mel_real.json').read_text())
    path = out / 'mel_real_corridors.json'; doc = json.loads(path.read_text()); model = doc['model']
    uses = defaultdict(set)
    for line, service in zip(net['lines'], model['lines']):
        if service:
            for code in service['path']: uses[code >> 1].add(line['name'])
    stony = [service for line, service in zip(net['lines'], model['lines']) if line['name'] == 'Stony Point' and service]
    if len(stony) != 1: raise ValueError('Expected one Stony Point service')
    selected = {code >> 1 for code in stony[0]['path']}
    if any(uses[e] != {'Stony Point'} for e in selected):
        raise ValueError('Stony Point shares an edge with another line; cannot safely make it single')
    for e in selected: model['edges'][e]['tracks'] = 1
    path.write_text(json.dumps(doc))
    print(f'Set {len(selected)} Stony Point edges to single track', flush=True)

def ordered_shape(stations, candidates):
    """Best nearby shape visiting stations once in order, in either direction."""
    import numpy as np
    best = None
    for shape_id, shape in candidates:
        if shape is None or len(shape) < 2: continue
        distances = np.hypot(*(shape[:,None,:] - stations[None,:,:]).transpose(2,0,1))
        indexes = np.argmin(distances, axis=0)
        nearest = distances[indexes, np.arange(len(stations))]
        diff = np.diff(indexes)
        if max(nearest) > 400 or not (np.all(diff > 0) or np.all(diff < 0)): continue
        cum = np.r_[0, np.cumsum(np.hypot(*np.diff(shape,axis=0).T))]
        hops = np.abs(np.diff(cum[indexes])); direct = np.hypot(*np.diff(stations,axis=0).T)
        if np.any(hops > 1.8 * direct + 800): continue
        score = float(sum(nearest) + sum(np.maximum(0, hops - direct)))
        if best is None or score < best[0]: best = (score, shape, indexes)
    return best

def fit_ordered_shapes(out, feed, realnet):
    """Select GTFS shapes in stop order to avoid looped/doubled-back hops."""
    import numpy as np
    net = json.loads((out / 'mel_real.json').read_text())
    path = out / 'mel_real_geom.json'; geo = json.loads(path.read_text())
    shapes = pd.read_csv(feed / 'shapes.txt', dtype=str, keep_default_na=False)
    trips = pd.read_csv(feed / 'trips.txt', dtype=str, keep_default_na=False)
    shapes['seq'] = shapes.shape_pt_sequence.astype(float)
    shapes = shapes.sort_values(['shape_id', 'seq'])
    x, y = realnet.to_xy(shapes.shape_pt_lon.astype(float).to_numpy(), shapes.shape_pt_lat.astype(float).to_numpy(), realnet.origin('mel'))
    shapes['x'], shapes['y'] = x, y
    points = {sid: group[['x','y']].to_numpy() for sid, group in shapes.groupby('shape_id', sort=False)}
    route_shapes = {route: list(group.shape_id.unique()) for route, group in trips.groupby('route_id', sort=False)}
    chosen, fallback = 0, []
    for li, line in enumerate(net['lines']):
        st = np.array([[net['stations'][k]['x'], net['stations'][k]['y']] for k in line['stops']])
        best = ordered_shape(st, ((sid, points.get(sid)) for sid in route_shapes.get(line['route'], [])))
        if best is None:
            fallback.append(line['name']); continue
        _, shape, indexes = best
        hops = []
        for i, j in zip(indexes[:-1], indexes[1:]):
            piece = shape[min(i,j):max(i,j)+1]
            if j < i: piece = piece[::-1]
            piece = realnet.simplify(piece, 15.0)
            hops.append(piece[1:-1].round(1).tolist())
        geo['lines'][li] = {'nodes': shape[indexes].tolist(), 'hops': hops}
        chosen += 1
    # Frankston's combined all-stops/Loop pattern can lack one matching GTFS
    # shape. Compose its city portion and direct branch from observed shapes,
    # rather than allowing a closest-point match to double back around the Loop.
    by_name = {line['name']: i for i, line in enumerate(net['lines'])}
    if all(name in by_name for name in ('Frankston','Frankston geometry guide','Belgrave')):
        f,g,b = (by_name[name] for name in ('Frankston','Frankston geometry guide','Belgrave'))
        fs,gs,bs = (net['lines'][i]['stops'] for i in (f,g,b))
        n=0
        for x,y in zip(fs,bs):
            if x!=y: break
            n+=1
        if n<6: raise ValueError('Unexpected Frankston and Burnley City Loop stops')
        for k in range(n): geo['lines'][f]['nodes'][k]=geo['lines'][b]['nodes'][k]
        for k in range(n-1): geo['lines'][f]['hops'][k]=geo['lines'][b]['hops'][k]
        join=fs[n-1]
        if join not in gs: raise ValueError('Frankston geometry guide misses the loop junction')
        q=gs.index(join)
        for k in range(n-1,len(fs)):
            t=q+k-(n-1)
            if t>=len(gs) or fs[k]!=gs[t]: raise ValueError('Frankston geometry guide stops do not match')
            geo['lines'][f]['nodes'][k]=geo['lines'][g]['nodes'][t]
            if k+1<len(fs): geo['lines'][f]['hops'][k]=geo['lines'][g]['hops'][t]
        if 'Frankston' in fallback: fallback.remove('Frankston'); chosen += 1
        print(f'Composed Frankston Loop and branch geometry at {net["stations"][join]["name"]}',flush=True)
    # The two tunnel branches share precisely the same stops through Dandenong.
    # Feed shapes sometimes snap them to different platform ends, producing
    # unnecessary separate tracks and an artificial split at Town Hall.
    indexes = {line['name']: i for i, line in enumerate(net['lines'])}
    if 'Cranbourne' in indexes and 'Pakenham' in indexes:
        c, p = indexes['Cranbourne'], indexes['Pakenham']
        cs, ps = net['lines'][c]['stops'], net['lines'][p]['stops']
        common = 0
        for a, b in zip(cs, ps):
            if a != b: break
            common += 1
        if common < 2: raise ValueError('Metro Tunnel branches do not share expected stops')
        for k in range(common): geo['lines'][p]['nodes'][k] = geo['lines'][c]['nodes'][k]
        for k in range(common - 1): geo['lines'][p]['hops'][k] = geo['lines'][c]['hops'][k]
        print(f'Aligned tunnel branches over {common} shared stations', flush=True)
    levels, pairs, left = realnet.assign_levels(geo['lines'])
    for line, lv in zip(geo['lines'], levels): line['level'] = lv
    path.write_text(json.dumps(geo))
    print(f'Fit {chosen} ordered GTFS shapes, fallback for {fallback}; crossing pairs {pairs}, unresolved {left}', flush=True)

def add_flemington_infrastructure(out, realnet):
    """Extend Showgrounds to the OSM racecourse stop; no invented through service."""
    import numpy as np
    from realroute import Graph, length
    corr_path = out / 'mel_real_corridors.json'
    corr = json.loads(corr_path.read_text()); model = corr['model']
    found = [i for i, n in enumerate(model['nodes']) if n['station'] and n['station']['name'] == 'Showgrounds']
    if len(found) != 1: raise ValueError(f'Expected one Showgrounds station, got {len(found)}')
    station = json.loads((ROOT / 'melbourne/sources/flemington-osm-node.json').read_text())['elements'][0]
    if station['id'] != 8784348527: raise ValueError('Unexpected OSM station input')
    origin = realnet.origin('mel'); target = np.array(realnet.to_xy(station['lon'], station['lat'], origin))
    start = np.array(model['nodes'][found[0]]['xy']); xy = np.stack([start, target])
    box = (*(xy.min(0)-5000), *(xy.max(0)+5000))
    graph = Graph(str(Path(realnet.REALGRAPH) / 'au.rgr'), origin, box, realnet.R_EARTH)
    route = graph.route(start, target, 150, 0)
    if route is None or len(route[0]) < 2: raise ValueError('No OSM graph route from Showgrounds to Flemington Racecourse')
    points = route[0]; metres = length(points)
    if not 500 < metres < 2000: raise ValueError(f'Unexpected racecourse route length {metres:.0f}m')
    lead = min(60.0, metres / 4)
    a = realnet.along(points, lead); b = realnet.along(points[::-1], lead)
    segment = np.hypot(*np.diff(points, axis=0).T); cumulative = np.r_[0, np.cumsum(segment)]
    inner = [p.tolist() for p, d in zip(points, cumulative) if lead + 10 < d < metres - lead - 10]
    new = len(model['nodes'])
    model['nodes'].append({'xy': points[-1].tolist(), 'level': model['nodes'][found[0]]['level'],
                           'station': {'platform':140,'name':'Flemington Racecourse','key':'osm:8784348527'}})
    model['edges'].append({'a':found[0], 'b':new, 'lead_a':a.tolist(), 'lead_b':b.tolist(), 'line':inner, 'levels':[], 'flat':[0,0]})
    corr_path.write_text(json.dumps(corr))
    print(f'Added {metres:.0f} m graph-routed, unserved track to Flemington Racecourse', flush=True)

def join_tunnel(out):
    """Join the separate GTFS route halves at the two generated Town Hall nodes.

    The upstream builder represents each terminal as a different track node.
    Merge the two approximations of their common through platform.
    """
    net_path, corr_path, geo_path = (out / 'mel_real.json', out / 'mel_real_corridors.json', out / 'mel_real_geom.json')
    net = json.loads(net_path.read_text()); corr = json.loads(corr_path.read_text()); geo = json.loads(geo_path.read_text())
    lines, model = net['lines'], corr['model']
    def single(name):
        found = [i for i, line in enumerate(lines) if line['name'] == name]
        if len(found) != 1: raise ValueError(f'Expected one {name} tunnel pattern, got {len(found)}')
        return found[0]
    sun = single('Sunbury'); branches = [single('Cranbourne'), single('Pakenham')]
    sun_model = model['lines'][sun]
    if sun_model is None: raise ValueError('Sunbury has no model route')
    a = sun_model['stops'][0]
    b = model['lines'][branches[0]]['stops'][0]
    nodes = model['nodes']; sa, sb = nodes[a]['station'], nodes[b]['station']
    if not sa or not sb or sa['key'] != sb['key'] or 'Town Hall' not in sa['name']:
        raise ValueError('Metro Tunnel terminal nodes are not both Town Hall')
    if a == b or nodes[a]['level'] != nodes[b]['level']:
        raise ValueError('Unexpected Town Hall node configuration')
    import math
    distance = math.dist(nodes[a]['xy'], nodes[b]['xy'])
    if distance > 150: raise ValueError(f'Town Hall nodes too far apart: {distance:.1f} m')
    # The two terminal nodes represent the same Town Hall platform, 103 m apart
    # along the track. Merge them at their midpoint and preserve each lead vector.
    midpoint = [(x + y) / 2 for x, y in zip(nodes[a]['xy'], nodes[b]['xy'])]
    for ed in model['edges']:
        for side in ('a', 'b'):
            old = ed[side]
            if old not in (a, b): continue
            lead_key = 'lead_' + side
            if ed[lead_key] is not None:
                ed[lead_key] = [v + midpoint[i] - nodes[old]['xy'][i] for i, v in enumerate(ed[lead_key])]
            ed[side] = a
    nodes[a]['xy'] = midpoint
    nodes[b]['station'] = None
    # Align both platform approaches on the same axis, and leave a straight
    # lead beyond the platform so the curve fitter cannot enter it.
    incident = [(ed, 'a' if ed['a'] == a else 'b') for ed in model['edges'] if a in (ed['a'], ed['b'])]
    if len(incident) != 2: raise ValueError('Town Hall must have two tunnel approaches')
    v = [[ed['lead_' + side][i] - midpoint[i] for i in range(2)] for ed, side in incident]
    norm = [math.hypot(*x) for x in v]
    axis = [v[0][i] / norm[0] - v[1][i] / norm[1] for i in range(2)]
    axis_len = math.hypot(*axis)
    if axis_len < 1.5: raise ValueError('Town Hall approaches are not opposite')
    for k, (ed, side) in enumerate(incident):
        sign = 1 if k == 0 else -1
        ed['lead_' + side] = [midpoint[i] + sign * 150 * axis[i] / axis_len for i in range(2)]
        ed['line'] = [pt for pt in ed['line'] if math.dist(pt, midpoint) > 190.0]
    keep = [i for i in range(len(lines)) if i not in [sun, *branches]]
    new_lines = [lines[i] for i in keep]; new_model = [model['lines'][i] for i in keep]; new_geo = [geo['lines'][i] for i in keep]
    for idx in branches:
        branch, sm, bm = lines[idx], lines[sun], model['lines'][idx]
        if bm is None or bm['stops'][0] != b: raise ValueError('Tunnel branches do not share Town Hall')
        merged = dict(branch)
        merged['name'] = branch['name'] + ' – Sunbury'
        merged['stops'] = sm['stops'][::-1] + branch['stops'][1:]
        merged['t0'] = [sm['t1'][k][::-1][:-1] + branch['t0'][k] for k in range(3)]
        merged['t1'] = [sm['t0'][k][::-1] + branch['t1'][k][1:] for k in range(3)]
        combined = dict(bm)
        combined['stops'] = [a if v == b else v for v in sun_model['stops'][::-1]] + bm['stops'][1:]
        combined['path'] = [v ^ 1 for v in sun_model['path'][::-1]] + bm['path']
        new_lines.append(merged); new_model.append(combined); new_geo.append(geo['lines'][idx])
    net['lines'] = new_lines; model['lines'] = new_model; geo['lines'] = new_geo
    net_path.write_text(json.dumps(net)); corr_path.write_text(json.dumps(corr)); geo_path.write_text(json.dumps(geo))
    print(f'Joined Metro Tunnel route halves at Town Hall; merged platform nodes {distance:.1f} m apart', flush=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city-loops', action='store_true', help='prepare directional City Loop services')
    p.add_argument('--simplified', action='store_true', help='merge similar stopping patterns and add colour-based line groups')
    p.add_argument('--gtfs', required=True, type=Path)
    p.add_argument('--date', required=True, help='2026 service date, YYYY-MM-DD')
    p.add_argument('--event-date', default='2026-11-21', help='date for occasional Flemington Racecourse service')
    p.add_argument('--pack', required=True, type=Path)
    p.add_argument('--graph', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(); date = dt.date.fromisoformat(a.date)
    if a.city_loops and not a.simplified: p.error('--city-loops requires --simplified')
    if date.year != 2026: p.error('choose a service day in 2026')
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    if (out / 'mel_real.save').exists(): raise FileExistsError('Use a fresh output directory')
    feed = out / 'metro'; feed.mkdir(exist_ok=True)
    with zipfile.ZipFile(a.gtfs) as outer, zipfile.ZipFile(io.BytesIO(outer.read('2/google_transit.zip'))) as inner:
        for name in ('stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt', 'calendar.txt', 'calendar_dates.txt', 'shapes.txt'):
            if name in inner.namelist(): (feed / name).write_bytes(inner.read(name))
    read = lambda name: pd.read_csv(feed / name, dtype=str, keep_default_na=False) if (feed / name).exists() else None
    routes = read('routes.txt'); routes = routes[routes.route_short_name.isin(SYMBOLS)]
    if set(routes.route_short_name) != set(SYMBOLS): raise ValueError('Metro route names differ from expected list')
    trips = read('trips.txt'); trips = trips[trips.route_id.isin(routes.route_id)]
    calendar, calendar_dates = read('calendar.txt'), read('calendar_dates.txt')
    ids = service_ids(calendar, calendar_dates, date)
    event_date = dt.date.fromisoformat(a.event_date)
    if event_date.year != 2026: p.error('event date must be in 2026')
    event_ids = service_ids(calendar, calendar_dates, event_date)
    event_route = set(routes.loc[routes.route_short_name.eq('Flemington Racecourse'), 'route_id'])
    event = trips[trips.route_id.isin(event_route) & trips.service_id.isin(event_ids)]
    if event.empty: raise ValueError(f'No Flemington event trips on {event_date}')
    trips = pd.concat([trips[~trips.route_id.isin(event_route) & trips.service_id.isin(ids)], event]).drop_duplicates('trip_id')
    ids |= event_ids
    if not len(trips): raise ValueError('No metro trips active on selected date')
    stop_times = read('stop_times.txt'); stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    stops = read('stops.txt'); replacement = set(stops.loc[stops.platform_code.str.upper().eq('R-BUS'), 'stop_id'])
    bad = set(stop_times.loc[stop_times.stop_id.isin(replacement), 'trip_id'])
    trips = trips[~trips.trip_id.isin(bad)]
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    shapes = read('shapes.txt'); shapes = shapes[shapes.shape_id.isin(trips.shape_id)]
    for name, frame in [('routes.txt', routes), ('trips.txt', trips), ('stop_times.txt', stop_times), ('shapes.txt', shapes)]:
        frame.to_csv(feed / name, index=False)
    active = sorted(routes[routes.route_id.isin(trips.route_id)].route_short_name)
    print(f'{len(trips)} trips; active routes: {active}', flush=True)
    print('Routes with no trips:', sorted(set(SYMBOLS) - set(active)), flush=True)
    os.environ['REALNET_OUT'] = str(out)
    import realnet
    import realcorridors
    if a.simplified:
        # Prefer shared corridors and use adjacent pairs only on the busiest sections.
        import realshared
        realcorridors.PACK_LOAD_RAIL = 0.65
        realcorridors.WANT_LOAD = 0.8
        realcorridors.APART_LOAD = 1.05
        realshared.PLAT_LOAD = 1.0
        realshared.PAIR_GAP = 16.0
    packs = TW / 'data' / 'packs'; (packs / 'realgraph').mkdir(parents=True, exist_ok=True)
    for source, dest in ((a.pack, packs / 'mel.json'), (a.graph, packs / 'realgraph' / 'au.rgr')):
        if source.resolve() != dest.resolve():
            if dest.exists() and source.read_bytes() != dest.read_bytes(): raise FileExistsError(f'{dest} differs')
            if not dest.exists(): shutil.copyfile(source, dest)
    realnet.REALGRAPH = str(packs / 'realgraph'); realnet.REGION['mel'] = 'au'
    realnet.service_ids = lambda folder: (pd.Timestamp(date), ids)
    length = {'_': 143, **{r: 160 for r in routes.loc[routes.route_short_name.isin(['Cranbourne','Pakenham','Sunbury']), 'route_id']},
              **{r: 60 for r in routes.loc[routes.route_short_name.eq('Stony Point'), 'route_id']}}
    src = realnet.gtfs('metro', str(feed), 'https://opendata.transport.vic.gov.au/dataset/gtfs-schedule', .02, 2, length, 'commuter')
    realnet.CITIES['mel'] = {'pack':'mel', 'out': str(out / 'mel_real.json'), 'sources':[src], 'boundary':False, 'count_point':[144.99, -37.82]}
    original = realnet.ADAPTERS['gtfs']
    def load(source, inside):
        stations, journeys, names = original(source, inside)
        stations = {k: (re.sub(r' Railway Station(?: \([^)]*\))?$', '', name).removesuffix(' Station'), lon, lat) for k, (name, lon, lat) in stations.items()}
        return stations, journeys, names
    realnet.ADAPTERS['gtfs'] = load
    realnet.cmd_net('mel')
    net_path = out / 'mel_real.json'; net = json.loads(net_path.read_text())
    if a.simplified: simplify_services(net, a.city_loops)
    counts = Counter(line['name'] for line in net['lines'])
    labels = defaultdict(int)
    for line in net['lines']:
        name = line['name']; base_name = 'Frankston' if name == 'Frankston geometry guide' else name
        line['symbol'] = SYMBOLS.get(base_name, '')
        if a.simplified:
            group_id, group_name, group_symbol = GROUPS[base_name]
            line.update(group=group_id, group_name=group_name, group_symbol=group_symbol, group_colour=line.get('colour', ''))
        if name == 'Flemington Racecourse':
            line['name'] = 'Flemington Racecourse (Showgrounds events)'
        if counts[name] > 1:
            stops = [net['stations'][i]['name'] for i in line['stops']]
            city_loop = any(x in stops for x in ('Parliament', 'Melbourne Central', 'Flagstaff'))
            where = 'City Loop' if city_loop else 'direct'
            target = '' if stops[-1] == name else f' to {stops[-1]}'
            label = f'{name}{target} ({where})'
            labels[label] += 1
            line['name'] = label if labels[label] == 1 else f'{label} {labels[label]}'
        if a.simplified and name == 'Werribee' and any(net['stations'][i]['name'] == 'Altona' for i in line['stops']):
            line['name'] = 'Werribee via Altona (Laverton)'
    net_path.write_text(json.dumps(net))
    print('Generated', len(net['stations']), 'stations,', len(net['lines']), 'service patterns', flush=True)
    sys.argv = ['realnet.py', 'geom', 'mel']; realnet.cmd_geom()
    if a.simplified: fit_ordered_shapes(out, feed, realnet)
    realcorridors.build('mel', str(out))
    join_tunnel(out)
    if a.simplified: single_track_stony_point(out)
    add_flemington_infrastructure(out, realnet)
    if a.city_loops:
        import city_loop
        city_loop.build(out)
        import loop_geometry
        loop_geometry.align(out)
    subprocess.run(['cargo','run','--release','--features','demand','--bin','realsave','--','--city','mel','--out',str(out),'--shared','--left'], cwd=TW/'sim', check=True)
    sys.argv = ['realnet.py','gamesave','mel']; realnet.cmd_gamesave()
    subprocess.run([sys.executable, str(ROOT / 'melbourne/validate_metro.py'), str(out / 'mel_real.save')] + (['--city-loops'] if a.city_loops else []), check=True)

if __name__ == '__main__': main()
