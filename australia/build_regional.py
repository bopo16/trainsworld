#!/usr/bin/env python3
"""Build one of the Australian rail networks from shared corridors and the game rail graph."""

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from edit_save import ROOT

sys.path.insert(0, str(ROOT / "trainworld/pipeline"))
from realroute import Graph, length

EARTH_RADIUS = 6371008.8
GRAPH_SHA256 = "5ed852b014bc36577188ec03be2fadee049851f0a3f18cfb07ae147ce6889d68"
RAIL_KINDS = (0,)
TRAM_KINDS = (1, 3)


def reverse(path):
    return [code ^ 1 for code in reversed(path)]


def source_name(key):
    return key.split("@", 1)[0]


class Network:
    def __init__(self, spec, graph):
        self.spec = spec
        self.origin = np.asarray(spec["origin"])
        self.scale = EARTH_RADIUS * np.pi / 180 * np.array([math.cos(math.radians(self.origin[1])), 1])
        self.stations = spec["stations"]
        self.nodes, self.edges = [], []
        self.keys, self.paths = {}, {}
        boundary = np.array([self.to_xy(s["at"]) for s in self.stations.values()])
        box = (*tuple(boundary.min(axis=0) - 6000), *tuple(boundary.max(axis=0) + 6000))
        self.rail = Graph(graph, self.origin, box, EARTH_RADIUS, kinds=RAIL_KINDS)
        self.tram = Graph(graph, self.origin, box, EARTH_RADIUS, kinds=TRAM_KINDS)
        self.penalties = {
            tram: {i: 1.12 for i, flags in enumerate(graph.flags) if not flags & 1}
            for tram, graph in ((False, self.rail), (True, self.tram))
        }
        self.terminal = {k for c in spec["services"] for k in c.get("terminal", [])}
        self.matched = 0
        self.manual = 0
        self.rail_cache = {}
        self.track_bearings = defaultdict(list)

    def to_xy(self, lonlat):
        return (np.asarray(lonlat) - self.origin) * self.scale

    def to_lonlat(self, xy):
        return np.round(np.asarray(xy) / self.scale + self.origin, 8).tolist()

    def make_node(self, key, tram):
        if key in self.keys:
            return self.keys[key]
        source = self.stations[key]
        node = dict(id=len(self.nodes), at=source["at"], level=source.get("level", 0))
        if not key.startswith("_"):
            node.update(name=source.get("name", source_name(key)),
                        platform=source.get("platform", 60 if tram else 160),
                        terminal=key in self.terminal, passing=source.get("passing", False))
        self.nodes.append(node)
        self.keys[key] = node["id"]
        return node["id"]

    def match_hop(self, first, second, tram):
        a, b = [self.to_xy(self.stations[key]["at"]) for key in (first, second)]
        if not tram:
            # Parallel platforms through the same corridor use a shared
            # guide, shifted by each platform's position at either end.
            f, s = [source_name(key) for key in (first, second)]
            if f in self.stations and s in self.stations and (f, s) in self.rail_cache:
                baseline = self.rail_cache[f, s]
                portion = np.r_[0., np.cumsum(np.hypot(*np.diff(baseline, axis=0).T))]
                portion = (portion / portion[-1])[:, None]
                return baseline + (1 - portion) * (a - self.to_xy(self.stations[f]["at"])) \
                    + portion * (b - self.to_xy(self.stations[s]["at"]))

        g = self.tram if tram else self.rail
        radius = 45 if tram else 95
        # Prefer mapped passenger alignments over sidings when both connect.
        match = g.route(a, b, radius, 0, extra=self.penalties[tram],
                        turn_max=math.radians(105 if tram else 60))
        if match is None or length(match[0]) > 1.9 * np.linalg.norm(b - a) + (160 if tram else 350):
            raise ValueError(f"no plausible OSM route from {first} to {second}")
        self.matched += 1
        if not tram:
            self.rail_cache[first, second] = match[0]
            self.rail_cache[second, first] = match[0][::-1]
        return match[0]

    def add_corridor(self, corridor):
        tram = corridor.get("tram", False)
        tracks = corridor.get("tracks", 2)
        name = corridor["id"]
        keys = corridor["stops"]
        ids = [self.make_node(key, tram) for key in keys]
        codes = []
        for i, (first, second) in enumerate(zip(keys, keys[1:])):
            custom = corridor.get("guides", {}).get(first)
            if custom is None:
                path = self.match_hop(first, second, tram)
            else:
                path = np.array([self.to_xy(p) for p in custom])
                self.manual += 1
            a, b = [self.to_xy(self.stations[key]["at"]) for key in (first, second)]
            lead = corridor.get("lead", 10 if tram else 25)
            usable = [p for p in path if np.linalg.norm(p - a) > lead and np.linalg.norm(p - b) > lead]
            edge_id = len(self.edges)
            edge = dict(id=edge_id, a=ids[i], b=ids[i + 1], tracks=tracks, tram=tram,
                        guides=[self.to_lonlat(p) for p in usable])
            self.edges.append(edge)
            road = np.vstack((a, path, b))
            reach = min(25 if tram else 72, length(road) / 5)
            for end, node in enumerate((ids[i], ids[i + 1])):
                outward = road if end == 0 else road[::-1]
                distance = np.cumsum(np.hypot(*np.diff(outward, axis=0).T))
                vector = outward[np.searchsorted(distance, reach) + 1] - outward[0]
                self.track_bearings[node].append((edge_id, end, vector / np.linalg.norm(vector), reach))
            codes.append(edge_id * 2)
        self.paths[name] = keys, codes

    def align_through_tracks(self):
        for node, ports in self.track_bearings.items():
            if len(ports) != 2:
                continue
            (_, _, a, _), (_, _, b, _) = ports
            if np.dot(a, b) > -0.96:
                continue
            heading = (a - b) / np.linalg.norm(a - b)
            at = self.to_xy(self.nodes[node]["at"])
            for sign, (edge, end, _, reach) in zip((1, -1), ports):
                self.edges[edge].setdefault("leads", [None, None])[end] = self.to_lonlat(
                    at + sign * heading * reach)

    def service(self, service):
        path, stops = [], []
        for name in service["via"]:
            backward = name.startswith("-")
            keys, codes = self.paths[name[1:] if backward else name]
            if backward:
                keys, codes = list(reversed(keys)), reverse(codes)
            if stops:
                assert stops[-1] == keys[0], (service["symbol"], stops[-1], keys[0])
                stops.extend(keys[1:])
            else:
                stops.extend(keys)
            path.extend(codes)
        if "calls" in service:
            calls = set(service["calls"])
            assert calls <= {source_name(k) for k in stops}
            stops = [k for k in stops if source_name(k) in calls]
        else:
            skip = set(service.get("skip", []))
            stops = [k for k in stops if not k.startswith("_") and source_name(k) not in skip]
        assert self.keys[stops[0]] == self.ends(path[0])[0], service["name"]
        assert self.keys[stops[-1]] == self.ends(path[-1])[1], service["name"]
        assert len(set(stops)) == len(stops), service["name"]
        return dict(name=service["name"], symbol=service["symbol"], colour=int(service["colour"], 16),
                    tph=service["tph"], cars=service["cars"], path=path, stops=[self.keys[k] for k in stops])

    def ends(self, code):
        edge = self.edges[code // 2]
        pair = edge["a"], edge["b"]
        return pair[::-1] if code & 1 else pair

    def recipe(self):
        for corridor in self.spec["corridors"]:
            self.add_corridor(corridor)
        self.align_through_tracks()
        for key, peer in self.spec.get("links", []):
            self.nodes[self.keys[key]]["link"] = self.keys[peer]
        lines = [self.service(line) for line in self.spec["services"]]
        print(f"Routed {self.matched} hops on OSM, reused or fitted {len(self.edges) - self.matched - self.manual}, "
              f"used {self.manual} hand guides")
        return dict(origin=self.spec["origin"], nodes=self.nodes, edges=self.edges, routes=lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("city", choices=["brisbane", "adelaide"])
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.graph.read_bytes()).hexdigest() != GRAPH_SHA256:
        parser.error("use the Australian graph pinned in the city report")
    path = Path(__file__).parent / "sources" / f"{args.city}-corridors.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    recipe = Network(spec, args.graph).recipe()
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "recipe.json"
        target = Path(directory) / "network.twt2"
        source.write_text(json.dumps(recipe), encoding="utf-8")
        rail, tram = map(int, subprocess.check_output(
            ["cargo", "run", "--locked", "--release", "--features", "demand", "--bin", "edit_real_save",
             "--", "--new", target, source],
            cwd=ROOT / "trainworld/sim", text=True).split())
        header = json.dumps(dict(game="anitabuilder", format=1, city="nyc", home=spec["home"],
                                 clock=111600, cash=6000, fleet=rail, fleetTram=tram,
                                 fares=dict(base=1.5, perKm=0.1), ledger=[]),
                            separators=(",", ":")).encode()
        args.output.write_bytes(gzip.compress(b"TWG1" + struct.pack("<I", len(header)) + header
                                              + target.read_bytes(), mtime=0))


if __name__ == "__main__":
    main()
