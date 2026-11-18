//! Geometry revision for the pinned v0.4 Melbourne rail and tram save.
use std::{env, fs};
use trainworld_sim::track::{
    geom::{self, Pi},
    net::{Issue, Network},
    save,
    world::TrackWorld,
};

type Point = [f64; 2];
const ORIGIN: Point = [144.961, -37.816];

fn sub(a: Point, b: Point) -> Point {
    [a[0] - b[0], a[1] - b[1]]
}
fn plus(a: Point, b: Point, scale: f64) -> Point {
    [a[0] + b[0] * scale, a[1] + b[1] * scale]
}
fn length(a: Point) -> f64 {
    a[0].hypot(a[1])
}
fn unit(a: Point) -> Point {
    plus([0.0; 2], a, 1.0 / length(a))
}
fn point(net: &Network, id: u32) -> Point {
    let n = net.node_data(id).unwrap();
    [n.x, n.y]
}
fn place(net: &mut Network, id: u32, xy: Point) {
    let mut n = net.node_data(id).unwrap();
    [n.x, n.y] = xy;
    net.set_node(id, Some(n)).unwrap();
}
fn plane(net: &Network, p: Point) -> Point {
    let frame = net.frame();
    let (x, y) = frame.from_lonlat(ORIGIN[0], ORIGIN[1]);
    plus([x, y], p, frame.scale_at(ORIGIN[1]).0)
}
fn pi(p: Point, level: i8) -> Pi {
    Pi::new(p[0], p[1], 0.0, level)
}
fn replace_shape(net: &mut Network, id: u32, points: &[Point], split: usize) {
    let mut edge = net.edge_data(id).unwrap();
    let a = net.node_data(edge.a).unwrap().level;
    let b = net.node_data(edge.b).unwrap().level;
    edge.pis = points
        .iter()
        .enumerate()
        .map(|(i, &p)| pi(p, if i < split { a } else { b }))
        .collect();
    net.set_edge(id, Some(edge)).unwrap();
}

// Ease the old shape into the new endpoint and make the platform lead
// collinear with the track on the other side.
fn retangent(net: &mut Network, id: u32, node: u32, old: Point, direction: Point, lead: f64) {
    let new = point(net, node);
    let shift = sub(new, old);
    let mut edge = net.edge_data(id).unwrap();
    assert!(edge.a == node || edge.b == node);
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    let near_a = edge.a == node;
    if !near_a {
        edge.pis.reverse();
    }
    for p in &mut edge.pis {
        let weight = (1.0 - length(sub([p.x, p.y], old)) / (320.0 * scale)).clamp(0.0, 1.0);
        [p.x, p.y] = plus([p.x, p.y], shift, weight);
    }
    edge.pis
        .retain(|p| length(sub([p.x, p.y], new)) > (lead + 16.0) * scale);
    edge.pis.insert(
        0,
        pi(
            plus(new, direction, lead * scale),
            net.node_level[node as usize],
        ),
    );
    if !near_a {
        edge.pis.reverse();
    }
    net.set_edge(id, Some(edge)).unwrap();
}

fn station_end(net: &mut Network, node: u32, xy: Point, approach: u32, outward: Point) {
    let old = point(net, node);
    place(net, node, xy);
    retangent(net, approach, node, old, outward, 92.0);
}

fn tangent(a: Point, b: Point) -> Point {
    unit(sub(b, a))
}

fn parallel(points: &[Point], offset: f64) -> Vec<Point> {
    let left = |a: Point, b: Point| {
        let [dx, dy] = tangent(a, b);
        [-dy, dx]
    };
    (0..points.len())
        .map(|i| {
            let before = left(points[i.saturating_sub(1)], points[i.max(1)]);
            let after = if i + 1 < points.len() {
                left(points[i], points[i + 1])
            } else {
                before
            };
            let denominator = 1.0 + before[0] * after[0] + before[1] * after[1];
            plus(points[i], plus(before, after, 1.0), offset / denominator)
        })
        .collect()
}

fn route(net: &mut Network, name: &str, old: &[u32], new: &[u32], stop: Option<(u32, u32)>) {
    let id = (0..net.line_count() as u32)
        .find(|&i| net.line_data(i).unwrap().name == name)
        .unwrap();
    let mut line = net.line_data(id).unwrap();
    let start = line
        .path
        .windows(old.len())
        .position(|window| window == old)
        .expect(name);
    line.path
        .splice(start..start + old.len(), new.iter().copied());
    if let Some((from, to)) = stop {
        let at = line.stops.iter().position(|&id| id == from).expect(name);
        line.stops[at] = to;
    }
    net.set_line(id, Some(line)).unwrap();
}

fn retire(net: &mut Network, edges: &[u32], nodes: &[u32]) {
    for id in 0..net.line_count() as u32 {
        assert!(net
            .line_data(id)
            .unwrap()
            .path
            .iter()
            .all(|code| !edges.contains(&(code >> 1))));
    }
    for &e in edges {
        net.set_edge(e, None).unwrap();
    }
    for &n in nodes {
        if net.is_station(n) {
            net.set_station(n, None).unwrap();
        }
        net.set_node(n, None).unwrap();
    }
}

fn river(net: &mut Network) {
    // Road and viaduct corridor used for the schematic. Consecutive lanes
    // keep their order from Southern Cross platforms around the turn and
    // along the river to the Flinders Street platforms.
    let w = [-767.0, -315.0];
    let e = [508.0, -290.0];
    let guide = [
        w,
        [-737.0, -426.0],
        [-697.0, -544.0],
        [-557.0, -605.0],
        [-405.0, -589.0],
        [-148.0, -468.0],
        [95.0, -401.0],
        [286.0, -351.0],
        e,
    ];
    let west = tangent(guide[1], w);
    let east = tangent(guide[guide.len() - 2], e);
    let lane = |net: &Network, m| {
        parallel(&guide, m)
            .into_iter()
            .map(|p| plane(net, p))
            .collect::<Vec<_>>()
    };
    for (id, sx, fss, incoming, outgoing, offset) in [
        (369, 353, 349, 373, 303, 60.0),
        (370, 393, 389, 374, 320, 89.0),
        (371, 443, 420, 338, 326, 118.0),
        (372, 456, 452, 375, 354, 147.0),
    ] {
        let p = lane(net, offset);
        station_end(net, sx, p[0], incoming, west);
        station_end(net, fss, p[8], outgoing, east);
        replace_shape(net, id, &p[1..8], 7);
    }

    // The Altona short service and two cross-city services use the same
    // Southern Cross and viaduct infrastructure.
    route(
        net,
        "Williamstown – Sandringham",
        &[29 * 2 + 1],
        &[30 * 2 + 1],
        None,
    );
    route(
        net,
        "Werribee via Altona (Laverton)",
        &[62, 3, 1, 549, 64, 394],
        &[256 * 2, 257 * 2],
        Some((43, 316)),
    );
    let p = lane(net, 0.0);
    station_end(net, 316, p[0], 257, west);
    station_end(net, 315, p[8], 201, east);
    place(net, 40, p[1]);
    place(net, 39, p[7]);
    replace_shape(net, 256, &[], 0);
    replace_shape(net, 30, &[p[6], p[5], p[4], p[3], p[2]], 2);
    replace_shape(net, 255, &[], 0);

    // The event route has its own double track beside the cross-city pair.
    let event = "Flemington Racecourse (Showgrounds events)";
    route(net, event, &[384 * 2, 377 * 2 + 1], &[384 * 2], None);
    route(net, event, &[376 * 2 + 1, 385 * 2], &[385 * 2], None);
    let p = lane(net, 30.0);
    let old = point(net, 488);
    place(net, 488, p[0]);
    place(net, 485, p[8]);
    place(net, 487, p[1]);
    place(net, 486, p[7]);
    for (id, a, b) in [(384, 487, 488), (385, 488, 491)] {
        let mut edge = net.edge_data(id).unwrap();
        [edge.a, edge.b] = [a, b];
        net.set_edge(id, Some(edge)).unwrap();
    }
    retangent(net, 385, 488, old, west, 92.0);
    replace_shape(net, 384, &[], 0);
    replace_shape(net, 383, &[p[6], p[5], p[4], p[3], p[2]], 2);
    replace_shape(net, 382, &[], 0);
    retire(
        net,
        &[29, 31, 1, 0, 274, 32, 197, 377, 376],
        &[43, 44, 45, 47, 48, 489, 490],
    );
}

fn move_bundle(net: &mut Network, nodes: &[u32], offset: Point) {
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    for &id in nodes {
        place(net, id, plus(point(net, id), offset, scale));
    }
    for id in 0..net.edge_count() as u32 {
        let Some(mut e) = net.edge_data(id) else {
            continue;
        };
        let [a, b] = [nodes.contains(&e.a), nodes.contains(&e.b)];
        if !a && !b {
            continue;
        }
        let p = point(net, e.a);
        let q = point(net, e.b);
        for pi in &mut e.pis {
            let d = length(sub([pi.x, pi.y], p));
            let f = length(sub([pi.x, pi.y], q));
            let weight = (f * f64::from(a) + d * f64::from(b)) / (d + f);
            [pi.x, pi.y] = plus([pi.x, pi.y], offset, weight * scale);
        }
        net.set_edge(id, Some(e)).unwrap();
    }
}

fn approaches(net: &mut Network) {
    // Keep the duplicate directional platform center lines apart. The
    // two ends still join the same routes outside each platform throat.
    move_bundle(net, &[439, 438], [9.0, 3.0]);
    move_bundle(net, &[451, 450], [-9.0, -3.0]);
    move_bundle(net, &[478, 477], [4.0, 10.0]);
    move_bundle(net, &[484, 483], [-4.0, -10.0]);
    move_bundle(net, &[413, 412], [0.0, 8.0]);
    move_bundle(net, &[418, 417], [0.0, -8.0]);
    for (edge, node, other, lead) in [(337, 439, 438, 58.0), (345, 451, 450, 58.0)] {
        let p = point(net, node);
        retangent(net, edge, node, p, tangent(point(net, other), p), lead);
    }
}

fn add_like(net: &mut Network, source: u32, id: u32, a: u32, b: u32) {
    let mut e = net.edge_data(source).unwrap();
    [e.a, e.b] = [a, b];
    e.pis.clear();
    net.set_edge(id, Some(e)).unwrap();
}

fn plaza(net: &mut Network) {
    // Routes 11, 12 and 109 share the southwest turnout and its stop.
    // Route 30 keeps its separate west-facing terminus on Victoria Parade.
    let joint = net.node_count() as u32;
    let lead = net.edge_count() as u32;
    let mut n = net.node_data(531).unwrap();
    [n.x, n.y] = plane(net, [1375.0, 861.0]);
    net.set_node(joint, Some(n)).unwrap();
    add_like(net, 463, lead, 531, joint);
    let phi = tangent(point(net, 531), point(net, joint));
    let p = point(net, 531);
    retangent(net, 462, 531, p, plus([0.0; 2], phi, -1.0), 20.0);

    let mut east = net.edge_data(463).unwrap();
    east.a = joint;
    east.pis.remove(0);
    net.set_edge(463, Some(east)).unwrap();

    let mut north = net.edge_data(509).unwrap();
    north.a = joint;
    north.pis.remove(0);
    net.set_edge(509, Some(north)).unwrap();
    for name in ["Tram 12", "Tram 109"] {
        route(net, name, &[463 * 2], &[lead * 2, 463 * 2], None);
    }
    // Route 11 can be encoded in either direction by the timetable importer.
    let line = (0..net.line_count() as u32)
        .map(|i| net.line_data(i).unwrap())
        .find(|l| l.name == "Tram 11")
        .unwrap();
    if line.path.windows(2).any(|w| w == [508 * 2, 509 * 2]) {
        route(
            net,
            "Tram 11",
            &[508 * 2, 509 * 2],
            &[462 * 2, lead * 2, 509 * 2],
            Some((579, 531)),
        );
    } else {
        route(
            net,
            "Tram 11",
            &[509 * 2 + 1, 508 * 2 + 1],
            &[509 * 2 + 1, lead * 2 + 1, 462 * 2 + 1],
            Some((579, 531)),
        );
    }
    retire(net, &[508], &[579]);

    // The west-facing terminal has its own stop short of the turnout.
    let old_terminal = point(net, 831);
    place(net, 831, plane(net, [1297.0, 866.0]));
    let west = tangent(point(net, 531), point(net, 831));
    retangent(net, 734, 831, old_terminal, west, 20.0);
    assert!(net.link(831, 531));
}

fn street_stops(net: &mut Network) {
    // Put the two Errol Street platforms on tangent track. The bends remain
    // on the Victoria and Queensberry street alignments between stops.
    let victoria = plane(net, [-985.0, 1199.4]);
    let errol = plane(net, [-1007.7, 1370.0]);
    place(net, 908, victoria);
    place(net, 909, errol);
    let q = |net: &Network, p| plane(net, p);
    let points = [q(net, [-776.1, 1168.5]), q(net, [-965.2, 1196.7])];
    replace_shape(net, 809, &points, 2);
    let corner = q(net, [-1032.6, 1205.9]);
    replace_shape(net, 810, &[corner], 1);
    let mut victoria_corner = net.edge_data(810).unwrap();
    victoria_corner.pis[0].radius = 24.0;
    net.set_edge(810, Some(victoria_corner)).unwrap();
    let points = [
        q(net, [-1001.5, 1410.9]),
        q(net, [-1005.9, 1435.4]),
        q(net, [-1031.0, 1441.1]),
        q(net, [-1090.3, 1449.4]),
    ];
    replace_shape(net, 811, &points, 4);

    // Give the Elizabeth Street terminus room before the Flinders Street
    // cross street, preserving its original terminal upgrades.
    let end = point(net, 778);
    let inbound = unit(sub(point(net, 777), end));
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    place(net, 778, plus(end, inbound, 19.0 * scale));
    retangent(net, 687, 778, end, inbound, 21.0);

    // Follow the Bourke Street turnout tangent into one curve before
    // continuing along Spencer Street to Lonsdale.
    let corner = [q(net, [-685.5, -120.6]), q(net, [-750.4, 57.5])];
    replace_shape(net, 1281, &corner, 2);
}

fn tidy_headings(net: &mut Network) {
    let nodes: Vec<_> = (0..net.node_count() as u32)
        .filter(|&n| net.node_ok(n))
        .collect();
    for _ in 0..4 {
        let warnings = net.validate(&[], &nodes, &[]);
        let mut improved = false;
        for issue in warnings {
            let Issue::NodeHeading { node, edge: id } = issue else {
                continue;
            };
            if node == 832 {
                continue;
            } // Waterfront terminal uses a folded loop layout.
            let old = net.edge_data(id).unwrap();
            let a = old.a == node;
            let p = point(net, node);
            let other = point(net, if a { old.b } else { old.a });
            let side = net.port_side(id, u32::from(!a)).unwrap();
            let h = net.node_heading[node as usize];
            let ray = plus(
                [0.0; 2],
                [h.cos(), h.sin()],
                if side == 1 { 1.0 } else { -1.0 },
            );
            let before = net.validate(&[id], &[old.a, old.b], &[]);
            let mut e = old.clone();
            if !a {
                e.pis.reverse();
            }
            let ground = net.frame().scale_at(ORIGIN[1]).0;
            let lead = if let Some(pi) = e.pis.first() {
                length(sub([pi.x, pi.y], p))
            } else {
                (length(sub(other, p)) * 0.25).min(38.0 * ground)
            };
            let end = plus(p, ray, lead);
            if let Some(pi) = e.pis.first_mut() {
                if length(sub([pi.x, pi.y], end)) > 38.0 * ground {
                    continue;
                }
                [pi.x, pi.y] = end;
            } else {
                e.pis.push(pi(end, net.node_level[node as usize]));
            }
            if !a {
                e.pis.reverse();
            }
            net.set_edge(id, Some(e)).unwrap();
            derive(net);
            let after = net.validate(&[id], &[old.a, old.b], &[]);
            if after.len() < before.len() {
                improved = true;
            } else {
                net.set_edge(id, Some(old)).unwrap();
                derive(net);
            }
        }
        if !improved {
            break;
        }
    }
}

fn edge_samples(net: &Network, id: u32) -> Vec<Point> {
    let pieces = net.edge_pieces(id);
    let n = (net.edge_len[id as usize] / 5.0).ceil() as usize;
    (0..=n)
        .map(|i| {
            let (x, y, _) = geom::pos_at(pieces, net.edge_len[id as usize] * i as f64 / n as f64);
            [x, y]
        })
        .collect()
}

fn deviation(a: &[Point], b: &[Point]) -> f64 {
    a.iter()
        .map(|&p| {
            b.iter()
                .map(|&q| length(sub(p, q)))
                .fold(f64::INFINITY, f64::min)
        })
        .fold(0.0, f64::max)
}

fn derive(net: &mut Network) {
    let touch = net.take_touch();
    net.derive(&touch);
}

// Keep the stop and turnout leads. Remove an interior PI only when it
// removes a local warning and keeps the street trace within tolerance.
fn tidy_tram_curve(net: &mut Network, id: u32) {
    let base = edge_samples(net, id);
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    loop {
        let edge = net.edge_data(id).unwrap();
        let ends = [edge.a, edge.b];
        let old = net.validate(&[id], &ends, &[]);
        if old.is_empty() || edge.pis.len() < 3 {
            return;
        }
        let mut improved = false;
        for i in 1..edge.pis.len() - 1 {
            let mut candidate = edge.clone();
            candidate.pis.remove(i);
            net.set_edge(id, Some(candidate)).unwrap();
            derive(net);
            let current = net.validate(&[id], &ends, &[]);
            let samples = edge_samples(net, id);
            if current.len() < old.len()
                && current.iter().all(|issue| {
                    old.iter()
                        .any(|old| format!("{old:?}") == format!("{issue:?}"))
                })
                && deviation(&samples, &base).max(deviation(&base, &samples)) <= 15.0 * scale
            {
                improved = true;
                break;
            }
            net.set_edge(id, Some(edge.clone())).unwrap();
            derive(net);
        }
        if !improved {
            return;
        }
    }
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    assert_eq!(args.len(), 2, "melbourne_geometry INPUT.twt2 OUTPUT.twt2");
    let input = fs::read(&args[0]).unwrap();
    let mut net = save::decode(&input).expect("decode Melbourne save");
    assert_eq!((net.line_count(), net.edge_count()), (40, 1307));
    river(&mut net);
    approaches(&mut net);
    plaza(&mut net);
    street_stops(&mut net);
    net.touch_all();
    derive(&mut net);
    for edge in [462, 509, 726, 966, 1033, 1040, 1200, 1281] {
        tidy_tram_curve(&mut net, edge);
    }
    tidy_headings(&mut net);
    let world = TrackWorld::new(net);
    for id in 0..world.net.line_count() as u32 {
        let line = world.net.line_data(id).unwrap();
        assert!(
            world.net.check_line(id).is_ok(),
            "invalid route: {}",
            line.name
        );
        assert!(
            world.svc.lines[id as usize].running,
            "inactive service: {}",
            line.name
        );
    }
    fs::write(&args[1], save::encode(&world.net)).unwrap();
}
