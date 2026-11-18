#!/usr/bin/env python3
"""Validate a metro game save with the game's Rust decoder and service model."""
import argparse
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__); p.add_argument('save', type=Path); p.add_argument('--city-loops', action='store_true'); p.add_argument('--trams', action='store_true'); a = p.parse_args()
raw = gzip.decompress(a.save.read_bytes())
if len(raw) < 9 or raw[:4] != b'TWG1': raise ValueError('Invalid game container')
n = struct.unpack_from('<I', raw, 4)[0]
if not 0 < n < len(raw) - 8: raise ValueError('Invalid header length')
h = json.loads(raw[8:8+n])
registry = json.loads((ROOT / 'trainworld/app/src/game/registry.json').read_text())
if h.get('game') != 'anitabuilder' or h.get('format') != 1 or h.get('city') != registry['cities'][0]['id'] or h.get('fleet', 0) <= 0:
    raise ValueError('Invalid game header')
with tempfile.TemporaryDirectory() as tmp:
    payload = Path(tmp) / 'network.twt2'; payload.write_bytes(raw[8+n:])
    subprocess.run(['cargo','run','--release','--features','demand','--bin','melbourne_metro_validate','--',str(payload),str(h['fleet'])] + (['--city-loops'] if a.city_loops else []) + (['--trams',str(h['fleetTram'])] if a.trams else []), cwd=ROOT/'trainworld/sim', check=True)
