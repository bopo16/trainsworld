//! Apply a geometry and service recipe to an existing real-world game save.
use std::{env, fs};
use trainworld_sim::track::{save, world::TrackWorld};

fn blueprint(raw: &[u8]) -> (Vec<u8>, f64) {
    let mut net = save::decode(raw).expect("decode network");
    for id in 0..net.line_count() as u32 {
        if net.line_ok(id) {
            net.set_line(id, None).expect("remove service");
        }
    }
    for id in 0..net.edge_count() as u32 {
        if let Some(mut edge) = net.edge_data(id) {
            edge.built = false;
            edge.off = false;
            edge.day = 0;
            net.set_edge(id, Some(edge))
                .expect("convert track to blueprint");
        }
    }
    for id in 0..net.node_count() as u32 {
        if let Some(mut station) = net.station_data(id) {
            station.built = false;
            station.off = false;
            station.day = 0;
            net.set_station(id, Some(station))
                .expect("convert station to blueprint");
        }
    }
    let world = TrackWorld::new(net);
    let encoded = save::encode(&world.net);
    let check = save::decode(&encoded).expect("reload blueprint");
    assert!((0..check.line_count() as u32).all(|id| !check.line_ok(id)));
    assert!((0..check.edge_count() as u32)
        .filter_map(|id| check.edge_data(id))
        .all(|e| !e.built && !e.off));
    assert!((0..check.node_count() as u32)
        .filter_map(|id| check.station_data(id))
        .all(|s| !s.built && !s.off));
    let quote = world
        .net
        .blueprint_cost_items()
        .chunks_exact(7)
        .map(|row| row[6])
        .sum();
    (encoded, quote)
}

#[cfg(feature = "demand")]
mod recipe {
    use serde::Deserialize;
    use std::collections::{BTreeMap, BTreeSet};
    use trainworld_sim::track::{
        frame::FrameKind,
        geom::{self, Pi},
        net::{EdgeData, GroupLook, LineData, Network, NodeData, StationData, DAY_UNKNOWN},
        params::{TrackKind, R_CAP},
        save, trace, upgrades,
        world::TrackWorld,
    };

    #[derive(Deserialize)]
    struct Node {
        id: u32,
        at: [f64; 2],
        level: i8,
        #[serde(default)]
        name: String,
        #[serde(default)]
        platform: u16,
        #[serde(default)]
        terminal: bool,
        #[serde(default)]
        passing: bool,
        link: Option<u32>,
    }

    #[derive(Deserialize)]
    struct Edge {
        id: u32,
        a: u32,
        b: u32,
        #[serde(default)]
        guides: Vec<[f64; 2]>,
        #[serde(default)]
        levels: Vec<i8>,
        #[serde(default)]
        leads: [Option<[f64; 2]>; 2],
        #[serde(default)]
        tram: bool,
        #[serde(default = "track_pair")]
        tracks: u8,
    }

    fn track_pair() -> u8 {
        2
    }

    #[derive(Deserialize)]
    struct Route {
        existing: Option<u32>,
        #[serde(default)]
        name: String,
        #[serde(default)]
        symbol: String,
        #[serde(default)]
        colour: u32,
        #[serde(default)]
        group: String,
        #[serde(default = "frequency")]
        tph: [f32; 3],
        #[serde(default)]
        cars: u8,
        #[serde(default)]
        path: Vec<u32>,
        #[serde(default)]
        stops: Vec<u32>,
    }

    fn frequency() -> [f32; 3] {
        [2.0, 1.0, 1.0]
    }

    #[derive(Deserialize)]
    struct Recipe {
        origin: Option<[f64; 2]>,
        nodes: Vec<Node>,
        edges: Vec<Edge>,
        routes: Vec<Route>,
        #[serde(default)]
        retire: Vec<u32>,
    }

    fn add_edge(net: &mut Network, edge: Edge) {
        let a = net.node_data(edge.a).expect("edge start");
        let b = net.node_data(edge.b).expect("edge end");
        let kind = if edge.tram {
            TrackKind::StreetTram
        } else {
            TrackKind::Regular
        };
        let frame = net.frame();
        let guides: Vec<_> = edge
            .guides
            .into_iter()
            .map(|[lon, lat]| frame.from_lonlat(lon, lat))
            .collect();
        let mut pis = if edge.levels.is_empty() {
            let mut polyline = vec![(a.x, a.y)];
            polyline.extend(guides);
            polyline.push((b.x, b.y));
            let (tol, cap) = if edge.tram {
                (3.5, 180.0)
            } else {
                (7.0, R_CAP)
            };
            trace::trace(
                &polyline,
                frame.scaled(),
                tol,
                kind.spec().min_radius,
                cap,
                a.level,
            )
            .unwrap_or_else(|| panic!("could not fit edge {}", edge.id))
            .pis
        } else {
            assert_eq!(edge.levels.len(), guides.len());
            guides
                .into_iter()
                .zip(edge.levels)
                .map(|((x, y), level)| Pi::new(x, y, 0.0, level))
                .collect()
        };
        for (end, lead) in edge.leads.into_iter().enumerate() {
            let Some([lon, lat]) = lead else { continue };
            let (x, y) = frame.from_lonlat(lon, lat);
            let node = if end == 0 { &a } else { &b };
            let reach = (x - node.x).hypot(y - node.y);
            let mut proposal: Vec<_> = pis
                .iter()
                .copied()
                .filter(|pi| (pi.x - node.x).hypot(pi.y - node.y) > reach * 1.30)
                .collect();
            let insert = if end == 0 { 0 } else { proposal.len() };
            proposal.insert(insert, Pi::new(x, y, 0.0, node.level));
            let mut vertices = vec![Pi::new(a.x, a.y, 0.0, a.level)];
            vertices.extend(proposal.iter().copied());
            vertices.push(Pi::new(b.x, b.y, 0.0, b.level));
            if geom::fit_min(&vertices, frame.scaled(), R_CAP, kind.spec().min_radius)
                .issues
                .is_empty()
            {
                pis = proposal;
            }
        }
        let old = net.edge_data(edge.id);
        net.set_edge(
            edge.id,
            Some(EdgeData {
                a: edge.a,
                b: edge.b,
                tracks: edge.tracks,
                pis,
                built: true,
                off: false,
                thru: vec![],
                crossover: false,
                kind,
                sep: !edge.tram,
                day: DAY_UNKNOWN,
                oneway: old.as_ref().map_or(0, |e| e.oneway),
                join: old.as_ref().map_or([0; 2], |e| e.join),
                limit: old.as_ref().map_or(0, |e| e.limit),
            }),
        )
        .unwrap_or_else(|issue| panic!("edge {}: {issue:?}", edge.id));
    }

    pub fn apply(raw: Option<&[u8]>, recipe: &str) -> (Vec<u8>, u64, u64) {
        let recipe: Recipe = serde_json::from_str(recipe).expect("parse recipe");
        let mut net = match raw {
            Some(bytes) => save::decode(bytes).expect("decode network"),
            None => {
                let [lon, lat] = recipe.origin.expect("new network origin");
                Network::new_in(FrameKind::Merc, lon, lat, false)
            }
        };
        for node in &recipe.nodes {
            let (x, y) = net.frame().from_lonlat(node.at[0], node.at[1]);
            let flying = net.node_data(node.id).is_some_and(|n| n.flying);
            net.set_node(
                node.id,
                Some(NodeData {
                    x,
                    y,
                    level: node.level,
                    flying,
                }),
            )
            .expect("place node");
            if node.platform > 0 {
                net.set_station(
                    node.id,
                    Some(StationData {
                        platform: node.platform,
                        name: node.name.clone(),
                        named: true,
                        built: true,
                        off: false,
                        upgrades: (u8::from(node.terminal) * upgrades::TERMINAL)
                            | (u8::from(node.passing) * upgrades::PASSING),
                        berth: None,
                        day: DAY_UNKNOWN,
                        one: 0,
                    }),
                )
                .expect("place station");
            }
        }
        for node in recipe.nodes {
            if let Some(peer) = node.link {
                assert!(net.link(node.id, peer), "link {} to {peer}", node.id);
            }
        }
        for edge in recipe.edges {
            add_edge(&mut net, edge);
        }
        let mut next_group = (0..net.line_count() as u32)
            .filter_map(|id| net.line_data(id))
            .map(|line| line.group)
            .max()
            .unwrap_or(0)
            + 1;
        let mut groups = BTreeMap::new();
        for route in recipe.routes {
            let (id, mut line) = if let Some(id) = route.existing {
                (id, net.line_data(id).expect("existing line"))
            } else {
                let mut line = LineData {
                    name: route.name,
                    symbol: route.symbol,
                    colour: route.colour,
                    stops: vec![],
                    path: vec![],
                    tph: route.tph,
                    trains: None,
                    auto: None,
                    dwell_s: 35.0,
                    turnaround_s: 240.0,
                    cars: route.cars,
                    fast: false,
                    bus: None,
                    ferry: None,
                    group: 0,
                    group_name: route.group,
                    group_look: GroupLook::default(),
                    day: DAY_UNKNOWN,
                    hand: true,
                    one_way: false,
                    limit: 0,
                    twin: Default::default(),
                    weekend: Default::default(),
                };
                if !line.group_name.is_empty() {
                    line.group = *groups.entry(line.group_name.clone()).or_insert_with(|| {
                        let group = next_group;
                        next_group += 1;
                        group
                    });
                    line.group_look = GroupLook {
                        symbol: line.group_name.clone(),
                        colour: Some(line.colour),
                    };
                }
                (net.line_count() as u32, line)
            };
            line.path = route.path;
            line.stops = route.stops;
            net.set_line(id, Some(line))
                .unwrap_or_else(|issue| panic!("line {id}: {issue:?}"));
        }
        let used: BTreeSet<_> = (0..net.line_count() as u32)
            .filter_map(|id| net.line_data(id))
            .flat_map(|line| line.path.into_iter().map(|code| code >> 1))
            .collect();
        for id in recipe.retire {
            if !used.contains(&id) {
                net.set_edge(id, None).expect("retire bypassed track");
            }
        }
        let mut world = TrackWorld::new(net);
        world.allocate_unallocated();
        let mut fleet = [0u64; 2];
        for id in (0..world.net.line_count() as u32).filter(|&id| world.net.line_ok(id)) {
            let line = world.net.line_data(id).unwrap();
            let svc = &world.svc.lines[id as usize];
            if let Err(issue) = world.net.check_line(id) {
                let bad_turns: Vec<_> = line
                    .path
                    .windows(2)
                    .filter(|pair| {
                        world.net.path_nodes(pair[0]).1 != world.net.path_nodes(pair[1]).0
                            || !world.net.move_ok(pair[0], pair[1])
                    })
                    .map(|pair| {
                        (
                            pair[0],
                            pair[1],
                            world.net.path_nodes(pair[0]),
                            world.net.path_nodes(pair[1]),
                        )
                    })
                    .collect();
                panic!(
                    "{}: {issue:?}; discontinuities or reversals: {bad_turns:?}",
                    line.name
                );
            }
            assert!(svc.running, "{} is inactive", line.name);
            fleet[usize::from(world.net.line_tram(id))] +=
                u64::from(*svc.trains.iter().max().unwrap()) * u64::from(line.cars);
        }
        (save::encode(&world.net), fleet[0], fleet[1])
    }
}

fn main() {
    let mut args = env::args_os().skip(1);
    let input = args.next().expect("input or --new");
    let input = (input != "--new").then(|| fs::read(input).expect("read input"));
    let output = args.next().expect("output");
    let recipe = args.next().expect("recipe or --blueprint");
    if recipe == "--blueprint" {
        let (result, cost) = blueprint(input.as_deref().expect("blueprint input"));
        fs::write(output, result).expect("write blueprint");
        println!("{cost}");
        return;
    }
    #[cfg(feature = "demand")]
    {
        let (result, rail, tram) = recipe::apply(
            input.as_deref(),
            &fs::read_to_string(recipe).expect("read recipe"),
        );
        fs::write(output, result).expect("write network");
        println!("{rail} {tram}");
    }
    #[cfg(not(feature = "demand"))]
    panic!("build with --features demand to apply a recipe");
}
