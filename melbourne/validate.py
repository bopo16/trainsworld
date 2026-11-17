#!/usr/bin/env python3
"""Check the game container, then load its track payload with the actual Rust game model."""
import argparse
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('save', type=Path)
a = p.parse_args()
raw = gzip.decompress(a.save.read_bytes())
if raw[:4] != b'TWG1' or len(raw) < 8: raise ValueError('Invalid game container')
n = struct.unpack_from('<I', raw, 4)[0]
if n == 0 or 8 + n >= len(raw): raise ValueError('Invalid header length')
h = json.loads(raw[8:8+n])
if h.get('game') != 'anitabuilder' or h.get('format') != 1 or h.get('fleet', 0) <= 0:
    raise ValueError('Invalid game header or empty fleet')
registry = json.loads((ROOT / 'trainworld/app/src/game/registry.json').read_text())
if h['city'] != registry['cities'][0]['id']: raise ValueError('Invalid world registry city')
with tempfile.TemporaryDirectory() as d:
    track = Path(d) / 'track.twt2'; track.write_bytes(raw[8+n:])
    subprocess.run(['cargo', 'run', '--release', '--features', 'demand', '--bin', 'melbourne_validate', '--', str(track), str(h['fleet'])], cwd=ROOT / 'trainworld/sim', check=True)
print(f'Valid game container; header fleet: {h["fleet"]} cars')
