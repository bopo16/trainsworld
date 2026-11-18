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
    p.add_argument('--gtfs', required=True, type=Path)
    p.add_argument('--date', required=True, help='2026 service date, YYYY-MM-DD')
    p.add_argument('--event-date', default='2026-11-21', help='date for occasional Flemington Racecourse service')
    p.add_argument('--pack', required=True, type=Path)
    p.add_argument('--graph', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(); date = dt.date.fromisoformat(a.date)
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
    counts = Counter(line['name'] for line in net['lines'])
    labels = defaultdict(int)
    for line in net['lines']:
        name = line['name']; line['symbol'] = SYMBOLS.get(name, '')
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
    net_path.write_text(json.dumps(net))
    print('Generated', len(net['stations']), 'stations,', len(net['lines']), 'service patterns', flush=True)
    sys.argv = ['realnet.py', 'geom', 'mel']; realnet.cmd_geom()
    realcorridors.build('mel', str(out))
    join_tunnel(out)
    add_flemington_infrastructure(out, realnet)
    subprocess.run(['cargo','run','--release','--features','demand','--bin','realsave','--','--city','mel','--out',str(out),'--shared','--left'], cwd=TW/'sim', check=True)
    sys.argv = ['realnet.py','gamesave','mel']; realnet.cmd_gamesave()
    subprocess.run([sys.executable, str(ROOT / 'melbourne/validate_metro.py'), str(out / 'mel_real.save')], check=True)

if __name__ == '__main__': main()
