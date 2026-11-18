#!/usr/bin/env python3
"""Compact public OpenStreetMap relation/full XML snapshots into route-stop inputs."""
import argparse,json,re,xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROUTES=['M1','T1','T2','T3','T4','T5','T6','T7','T8','T9','L1','L2','L3','L4']
ROLES={'stop','stop_entry_only','stop_exit_only','platform','platform_entry_only','platform_exit_only'}

def normalise(name):
    name=re.sub(r'\s*[,–-]?\s*(?:station\s*,?\s*)?(?:platf?orm|platfrom|platforms)\s*\d+.*$', '',name,flags=re.I)
    name=re.sub(r'(?<=\D)\s+\d+$','',name)
    return re.sub(r'\s+station$', '',name,flags=re.I).strip(' ,')

def collect(folder):
    elements={};routes={};byref=defaultdict(list)
    for file in sorted(Path(folder).glob('*.osm')):
        id=int(file.stem);root=ET.parse(file).getroot();rel=next((v for v in root.findall('relation') if int(v.get('id'))==id),None)
        if rel is None:raise ValueError(f'missing relation {id}')
        tags={v.get('k'):v.get('v') for v in rel.findall('tag')};ref=tags.get('ref')
        if ref not in ROUTES or tags.get('type')!='route':continue
        raw={(v.tag,int(v.get('id'))):v for v in root if v.tag in ('node','way')}
        members=[]
        for member in rel.findall('member'):
            role=member.get('role','');key=(member.get('type'),int(member.get('ref')))
            if role not in ROLES:continue
            node=raw.get(key)
            if node is None:continue
            ntags={v.get('k'):v.get('v') for v in node.findall('tag')};name=normalise(ntags.get('name',''))
            if not name or name.isdigit():continue
            ntags['name']=name;obj={'type':key[0],'id':key[1],'tags':ntags}
            if key[0]=='node':obj.update(lat=float(node.get('lat')),lon=float(node.get('lon')))
            else:
                pts=[raw.get(('node',int(x.get('ref')))) for x in node.findall('nd')];pts=[x for x in pts if x is not None]
                if not pts:continue
                obj['center']={'lat':sum(float(x.get('lat')) for x in pts)/len(pts),'lon':sum(float(x.get('lon')) for x in pts)/len(pts)}
            elements[key]=obj;members.append({'type':key[0],'ref':key[1],'role':role})
        if len(members)<2:raise ValueError(f'{ref} relation {id} has too few named stops')
        routes[id]={'type':'relation','id':id,'tags':tags,'members':members};byref[ref].append(id)
    missing=set(ROUTES)-set(byref)
    if missing:raise ValueError(f'missing route relations {sorted(missing)}')
    result={}
    for mode in ('rail','light'):
        refs=[r for r in ROUTES if (r.startswith('L'))==(mode=='light')];selected=[r for ref in refs for r in byref[ref]]
        members={(m['type'],m['ref']) for i in selected for m in routes[i]['members']}
        masters=[{'type':'relation','id':-1000-i,'tags':{'type':'route_master','ref':ref},'members':[{'type':'relation','ref':id,'role':''} for id in byref[ref]]} for i,ref in enumerate(refs)]
        result[mode]={'elements':[elements[k] for k in sorted(members)]+[routes[i] for i in selected]+masters}
    return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('out',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 for mode,data in collect(a.folder).items():
  path=a.out/f'sydney-{mode}-osm.json';path.write_text(json.dumps(data,sort_keys=True,separators=(',',':')));print(path,len(data['elements']))
