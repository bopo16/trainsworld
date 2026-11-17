#!/usr/bin/env python3
"""Build a deliberately limited Frankston corridor using upstream realnet and realsave."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TW = ROOT / 'trainworld'
sys.path.insert(0, str(TW / 'pipeline'))
import pandas as pd

STATIONS = ('Flinders Street', 'Richmond', 'South Yarra', 'Hawksburn', 'Toorak', 'Armadale', 'Malvern', 'Caulfield')

def station_name(s):
    return s.removesuffix(' Railway Station').removesuffix(' Station').strip()

def select_corridor(stations, trips, route_names):
    routes = {r for r, name in route_names.items() if name.strip().lower() in ('frankston', 'frankston line')}
    if len(routes) != 1:
        raise ValueError(f'Expected one non-replacement Frankston route; found {routes}')
    selected = []
    wanted = set(STATIONS)
    for route, direction, keys, times in trips:
        if route not in routes:
            continue
        # Keep either the complete direct corridor, or the inbound Caulfield–Richmond
        # part of a trip that continues around the Loop. Never skip intermediate stops.
        labels = [station_name(stations[k][0]) for k in keys]
        for pattern in (STATIONS, STATIONS[::-1], STATIONS[:0:-1]):
            for i in range(len(labels) - len(pattern) + 1):
                if tuple(labels[i:i + len(pattern)]) == pattern:
                    selected.append((route, direction, keys[i:i + len(pattern)], times[i:i + len(pattern)]))
                    break
            else:
                continue
            break
    patterns = {tuple(station_name(stations[k][0]) for k in t[2]) for t in selected}
    if STATIONS not in patterns or not (STATIONS[::-1] in patterns or STATIONS[:0:-1] in patterns):
        raise ValueError('No complete outbound and inbound corridor trips on the chosen day')
    return selected

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gtfs', type=Path, required=True, help='Transport Victoria outer GTFS zip')
    p.add_argument('--date', required=True, help='service date YYYY-MM-DD (must be a Wednesday in 2026)')
    p.add_argument('--pack', type=Path, required=True, help='published mel.json')
    p.add_argument('--graph', type=Path, required=True, help='published realgraph/au.rgr')
    p.add_argument('--out', type=Path, required=True, help='scratch/output directory')
    a = p.parse_args()
    date = dt.date.fromisoformat(a.date)
    if date.year != 2026 or date.weekday() != 2:
        p.error('choose a Wednesday in 2026 covered by the supplied feed')
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    if (out / 'mel_real.save').exists():
        raise FileExistsError('Output save already exists; use a fresh output directory')
    feed = out / 'metro'; feed.mkdir(exist_ok=True)
    with zipfile.ZipFile(a.gtfs) as outer:
        import io
        with zipfile.ZipFile(io.BytesIO(outer.read('2/google_transit.zip'))) as inner:
            for name in ('stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt', 'calendar.txt', 'calendar_dates.txt', 'shapes.txt'):
                if name in inner.namelist():
                    (feed / name).write_bytes(inner.read(name))
    # Trim to Frankston before invoking upstream; replacement buses have a distinct route id.
    routes = pd.read_csv(feed / 'routes.txt', dtype=str, keep_default_na=False)
    routes = routes[routes.route_short_name.str.strip().str.lower() == 'frankston']
    if len(routes) != 1:
        raise ValueError('Expected exactly one Frankston rail route')
    trips = pd.read_csv(feed / 'trips.txt', dtype=str, keep_default_na=False)
    trips = trips[trips.route_id.isin(routes.route_id)]
    stop_times = pd.read_csv(feed / 'stop_times.txt', dtype=str, keep_default_na=False)
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    stops = pd.read_csv(feed / 'stops.txt', dtype=str, keep_default_na=False)
    replacements = set(stops.loc[stops.platform_code.str.upper().eq('R-BUS'), 'stop_id'])
    bad = set(stop_times.loc[stop_times.stop_id.isin(replacements), 'trip_id'])
    trips = trips[~trips.trip_id.isin(bad)]
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
    for name, df in [('routes.txt', routes), ('trips.txt', trips), ('stop_times.txt', stop_times)]:
        df.to_csv(feed / name, index=False)
    shapes = pd.read_csv(feed / 'shapes.txt', dtype=str, keep_default_na=False)
    shapes[shapes.shape_id.isin(trips.shape_id)].to_csv(feed / 'shapes.txt', index=False)
    os.environ['REALNET_OUT'] = str(out)
    import realnet
    # The upstream binary requires this exact local pack path; these files are ignored by git.
    packs = TW / 'data' / 'packs'; (packs / 'realgraph').mkdir(parents=True, exist_ok=True)
    for src, dest in ((a.pack, packs / 'mel.json'), (a.graph, packs / 'realgraph' / 'au.rgr')):
        if src.resolve() != dest.resolve():
            if dest.exists() and dest.read_bytes() != src.read_bytes():
                raise FileExistsError(f'{dest} already exists with different content; do not overwrite')
            if not dest.exists(): shutil.copyfile(src, dest)
    realnet.REALGRAPH = str(packs / 'realgraph')
    realnet.REGION['mel'] = 'au'
    src = realnet.gtfs('metro', str(feed), 'https://opendata.transport.vic.gov.au/dataset/gtfs-schedule', .05, 4, {'_': 140}, 'commuter')
    realnet.CITIES['mel'] = {'pack':'mel', 'out': str(out / 'mel_real.json'), 'sources':[src], 'boundary':False, 'count_point':[144.99, -37.82]}
    day = date.strftime('%Y%m%d')
    def service_ids(folder):
        cal = realnet.read(folder, 'calendar.txt'); cd = realnet.read(folder, 'calendar_dates.txt')
        ids = set()
        if cal is not None:
            mask = (cal.start_date <= day) & (cal.end_date >= day) & (cal[date.strftime('%A').lower()] == '1')
            ids |= set(cal.loc[mask, 'service_id'])
        if cd is not None:
            rows = cd[cd.date == day]
            ids |= set(rows.loc[rows.exception_type == '1', 'service_id'])
            ids -= set(rows.loc[rows.exception_type == '2', 'service_id'])
        active = ids & set(trips.service_id)
        if not active: raise ValueError(f'No Frankston services active on {day}')
        return pd.Timestamp(date), ids
    realnet.service_ids = service_ids
    original = realnet.ADAPTERS['gtfs']
    outbound_directions = set()
    def corridor(source, inside):
        stations, journeys, names = original(source, inside)
        journeys = select_corridor(stations, journeys, names)
        outbound_directions.update(t[1] for t in journeys if tuple(station_name(stations[k][0]) for k in t[2]) == STATIONS)
        if len(outbound_directions) != 1: raise ValueError('Ambiguous outbound GTFS directions')
        print(f'{len(journeys)} corridor trips selected')
        stations = {k: (station_name(name), lon, lat) for k, (name, lon, lat) in stations.items()}
        return stations, journeys, names
    realnet.ADAPTERS['gtfs'] = corridor
    realnet.cmd_net('mel')
    # The upstream pattern grouping can split directions; refuse anything except one full path.
    network = json.loads((out / 'mel_real.json').read_text())
    if len(network['lines']) != 1 or len(network['lines'][0]['stops']) != len(STATIONS):
        raise ValueError('Upstream did not produce exactly one full corridor line')
    # Shape choice must use the outbound trips: inbound travels through the City Loop.
    trips[trips.direction_id.isin(outbound_directions)].to_csv(feed / 'trips.txt', index=False)
    try:
        sys.argv = ['realnet.py', 'geom', 'mel']; realnet.cmd_geom()
    finally:
        trips.to_csv(feed / 'trips.txt', index=False)
    sys.argv = ['realnet.py', 'route', 'mel']; realnet.cmd_route()
    routed = json.loads((out / 'mel_real_route.json').read_text())['lines'][0]
    if any(h is None for h in routed['hops']):
        raise ValueError('OSM graph routing failed for one or more hops; refusing straight-line fallback')
    subprocess.run(['cargo', 'run', '--release', '--features', 'demand', '--bin', 'realsave', '--', '--city', 'mel', '--out', str(out), '--left'], cwd=TW / 'sim', check=True)
    sys.argv = ['realnet.py', 'gamesave', 'mel']; realnet.cmd_gamesave()
    subprocess.run([sys.executable, str(ROOT / 'melbourne/validate.py'), str(out / 'mel_real.save')], check=True)
    print('Created and validated', out / 'mel_real.save')

if __name__ == '__main__': main()
