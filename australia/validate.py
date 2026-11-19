#!/usr/bin/env python3
"""Load an Australian city save with the native game engine and check its services."""
import argparse,gzip,json,struct,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('city',choices=('per','can','syd','bri','ade'));p.add_argument('save',type=Path);p.add_argument('--expanded',action='store_true');a=p.parse_args()
raw=gzip.decompress(a.save.read_bytes())
if raw[:4]!=b'TWG1':raise ValueError('not a game save')
n=struct.unpack_from('<I',raw,4)[0]
if n<=0 or n>=len(raw)-8:raise ValueError('invalid save header')
h=json.loads(raw[8:8+n])
if h.get('game')!='anitabuilder' or h.get('format')!=1:raise ValueError('invalid game header')
with tempfile.TemporaryDirectory() as d:
 path=Path(d)/'network.twt2';path.write_bytes(raw[8+n:])
 subprocess.run(['cargo','run','--release','--features','demand','--bin','australia_validate','--',a.city,str(path),str(h.get('fleet',0)),str(h.get('fleetTram',0))]+(['--expanded'] if a.expanded else []),cwd=root/'trainworld/sim',check=True)
