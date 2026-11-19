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
        line.stops.dedup();
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
        (369, 353, 349, 373, 303, 78.0),
        (370, 393, 389, 374, 320, 104.0),
        (371, 443, 420, 338, 326, 130.0),
        (372, 456, 452, 375, 354, 0.0),
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
    let p = lane(net, 26.0);
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
    let p = lane(net, 52.0);
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

fn northern_loop(net: &mut Network) {
    // Surveyed centre corridor approximated from OSM rail chains 218, 2586,
    // 2427 and 12115 in the 18 November Australian graph. Offset the same
    // vertices so all four tunnels keep their order and station tangents.
    let guide = [
        [-475.0, 462.0],
        [165.0, 695.0],
        [700.0, 890.0],
        [840.0, 884.0],
        [964.0, 806.0],
        [1018.0, 695.0],
        [1062.0, 568.0],
    ];
    for (flag, central, parliament, west, north, east, south, offset) in [
        (360, 365, 368, 373, 362, 361, 291, -6.0),
        (400, 405, 408, 374, 364, 363, 313, -18.0),
        (433, 428, 425, 331, 366, 365, 330, 18.0),
        (463, 468, 471, 375, 368, 367, 346, 6.0),
    ] {
        let p: Vec<_> = parallel(&guide, offset)
            .into_iter()
            .map(|q| plane(net, q))
            .collect();
        let old = point(net, flag);
        place(net, flag, p[0]);
        let westward = tangent(p[1], p[0]);
        if west == 331 {
            let scale = net.frame().scale_at(ORIGIN[1]).0;
            place(net, 434, plus(p[0], westward, 100.0 * scale));
            replace_shape(net, 331, &[], 0);
            place(net, 435, plane(net, [-676.0, 421.0]));
            place(net, 436, plane(net, [-838.0, 456.0]));
            let lead = plus(point(net, 434), westward, 40.0 * scale);
            replace_shape(net, 332, &[lead], 1);
            let q = plane(net, [-766.0, 434.0]);
            replace_shape(net, 333, &[q], 1);
            let q = [plane(net, [-1265.0, 654.0]), plane(net, [-989.0, 499.0])];
            replace_shape(net, 334, &q, 2);
        } else {
            retangent(net, west, flag, old, westward, 85.0);
        }
        place(net, central, p[1]);
        replace_shape(net, north, &[], 0);
        station_end(net, parliament, p[6], south, tangent(p[5], p[6]));
        replace_shape(net, east, &[p[5], p[4], p[3], p[2]], 2);
    }
}

fn flinders_east(net: &mut Network) {
    // Keep the river order for the first platform lead. The cross-city and
    // Frankston tracks then curve south; the Northern Loop turns north.
    let axis = unit([222.0, 61.0]);
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    for (station, joint, first, second, x, points) in [
        (
            452,
            479,
            354,
            355,
            918.0,
            &[[1040.0, -151.0], [1220.0, -244.0], [1490.0, -394.0]][..],
        ),
        (
            315,
            262,
            201,
            202,
            920.0,
            &[
                [1030.0, -125.0],
                [1210.0, -150.0],
                [1390.0, -261.0],
                [1570.0, -365.0],
            ][..],
        ),
        (
            349,
            380,
            303,
            304,
            835.0,
            &[
                [955.0, -74.0],
                [1080.0, -58.0],
                [1220.0, -69.0],
                [1440.0, -172.0],
            ][..],
        ),
        (
            389,
            415,
            320,
            321,
            819.0,
            &[[920.0, -47.0], [975.0, -46.0]][..],
        ),
        (
            420,
            421,
            326,
            327,
            850.0,
            &[[940.0, 5.0], [1015.0, 41.0]][..],
        ),
    ] {
        let start = point(net, station);
        let target = plane(net, [x, 0.0]);
        let end = plus(start, axis, (target[0] - start[0]) / axis[0]);
        place(net, joint, end);
        replace_shape(net, first, &[], 0);
        let mut guides = vec![plus(end, axis, 45.0 * scale)];
        guides.extend(points.iter().map(|&p| plane(net, p)));
        if net.edge_data(second).unwrap().a != joint {
            guides.reverse();
        }
        let split = guides.len() / 2;
        replace_shape(net, second, &guides, split);
    }
}

fn southern_cross_north(net: &mut Network) {
    // Spread the compact Flagstaff tubes into the same order as the river
    // bundle before they reach the platforms. End tangents follow the
    // adjoining tunnel and river alignments, respectively.
    let guide = [
        [-572.0, 445.0],
        [-747.0, 379.0],
        [-890.0, 303.0],
        [-948.0, 167.0],
        [-936.0, 55.0],
        [-829.0, -91.0],
        [-795.0, -211.0],
        [-767.0, -315.0],
    ];
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    let southward = unit([30.0, -111.0]);
    for (edge, flag, central, platform, offset) in [
        (375, 463, 468, 456, 0.0),
        (373, 360, 365, 353, 78.0),
        (374, 400, 405, 393, 104.0),
    ] {
        let start = point(net, flag);
        let end = point(net, platform);
        // The first two guide positions ease the expansion from 12 m
        // tunnel spacing without swapping the order of the lanes.
        let inner = parallel(&guide, offset);
        let mut points = vec![plus(
            start,
            tangent(point(net, central), start),
            85.0 * scale,
        )];
        points.extend((1..=5).map(|k| {
            let ease = [0.0, 0.45, 0.78, 1.0, 1.0, 1.0][k];
            plane(net, plus(guide[k], sub(inner[k], guide[k]), ease))
        }));
        points.push(plus(end, southward, -98.0 * scale));
        replace_shape(net, edge, &points, points.len());
        if edge == 375 {
            let mut data = net.edge_data(edge).unwrap();
            // Keep the crossing with the western surface pairs outside
            // the platform leads, in the underground approach.
            for pi in &mut data.pis[2..5] {
                pi.level = -2;
            }
            net.set_edge(edge, Some(data)).unwrap();
        }
    }
    // The Northern Group reaches Southern Cross from North Melbourne.
    // Keep it east of the new bundle through the immediate station throat.
    let station = point(net, 443);
    place(net, 445, plus(station, southward, -183.0 * scale));
    replace_shape(net, 338, &[], 0);
    // One curve through the cross-under instead of the short sideways dogleg
    // and its three joints. The through service still enters North Melbourne.
    let mut exit = net.edge_data(339).unwrap();
    exit.b = 449;
    net.set_edge(339, Some(exit)).unwrap();
    let q = [
        plus(point(net, 445), southward, -55.0 * scale),
        plane(net, [-771.0, 76.0]),
        plane(net, [-931.0, 285.0]),
        plane(net, [-1150.0, 437.0]),
        plane(net, [-1292.0, 566.0]),
    ];
    replace_shape(net, 339, &q, q.len());
    for name in ["Craigieburn", "Upfield"] {
        route(net, name, &[678, 680, 682, 685], &[678], None);
    }
    retire(net, &[340, 341, 342], &[446, 447, 448]);
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
    // The Burnley directions had identical control nodes on the east lead,
    // then swapped sides before East Richmond. Keep both lanes ordered
    // through both platforms and into the shared line beyond them.
    move_bundle(net, &[373, 374, 375, 376, 377, 378, 379], [8.0, 14.0]);
    move_bundle(
        net,
        &[381, 382, 383, 384, 385, 386, 387, 388],
        [-8.0, -14.0],
    );
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

fn tram_junctions(net: &mut Network) {
    // Route 64 had consecutive stops only 34 m apart on the Hawthorn Road
    // curve. Keep the named interchange beyond the turn and fit one curve.
    route(
        net,
        "Tram 64",
        &[965 * 2, 966 * 2],
        &[965 * 2],
        Some((1069, 1070)),
    );
    let mut tram = net.edge_data(965).unwrap();
    tram.b = 1070;
    place(net, 1070, plane(net, [5654.0, -5483.0]));
    let first = tram.pis[0];
    let [x, y] = plane(net, [5703.0, -5511.0]);
    tram.pis = vec![first, Pi::new(x, y, 26.0, 0)];
    net.set_edge(965, Some(tram)).unwrap();
    let points = [plane(net, [5636.5, -5473.0]), plane(net, [5523.2, -5417.5])];
    replace_shape(net, 967, &points, 2);
    retire(net, &[966], &[1069]);

    // Leave the Nicholson turnout on its existing tangent, then stay
    // near the road centre before the straight Barrow Street platform lead.
    let a = point(net, 811);
    let mut edge = net.edge_data(1033).unwrap();
    let first = edge.pis[0];
    let last = *edge.pis.last().unwrap();
    let u = unit(sub([first.x, first.y], a));
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    let mut corner = pi(plus(a, u, 31.0 * scale), 0);
    corner.radius = 24.0;
    edge.pis = vec![corner, pi(plane(net, [1080.0, 6657.0]), 0), last];
    net.set_edge(1033, Some(edge)).unwrap();
}

fn swanston_trams(net: &mut Network) {
    // The previous save intentionally doubled these tracks for capacity.
    // Route the services onto the shared street pair, retaining the branch
    // junctions used by routes 58, 72, and 1.
    let stops = [
        (707, 706),
        (710, 709),
        (712, 711),
        (715, 713),
        (718, 716),
        (720, 719),
        (722, 721),
        (725, 723),
        (727, 726),
        (729, 728),
        (731, 730),
        (733, 732),
        (735, 734),
        (737, 736),
        (739, 738),
        (741, 740),
    ];
    let paths: &[(u32, &[u32])] = &[
        (622, &[623 * 2, 420 * 2 + 1]),
        (625, &[624 * 2]),
        (627, &[626 * 2]),
        (629, &[628 * 2, 421 * 2 + 1]),
        (631, &[630 * 2]),
        (633, &[422 * 2 + 1, 632 * 2]),
        (635, &[634 * 2]),
        (637, &[636 * 2, 423 * 2 + 1]),
        (639, &[638 * 2]),
        (641, &[640 * 2]),
        (643, &[642 * 2]),
        (645, &[644 * 2]),
        (647, &[646 * 2]),
        (649, &[648 * 2]),
        (651, &[650 * 2]),
        (653, &[652 * 2]),
    ];
    let mut lead = net.edge_data(420).unwrap();
    lead.a = 706;
    net.set_edge(420, Some(lead)).unwrap();

    let mut centres = Vec::new();
    for (duplicate, keep) in stops {
        let orig = point(net, keep);
        let shift = sub(point(net, duplicate), orig);
        centres.push((keep, plus(orig, shift, 0.5)));
    }
    for &(node, xy) in &centres {
        place(net, node, xy);
    }
    // South of RMIT the city-grid track is one straight line, aligned
    // to OSM rails 9522–9533 and 10385–10397. The 9511–9514/9534–9536
    // bundle turns northeast out of the grid towards Melbourne Uni.
    let frame = net.frame();
    let (origin_x, origin_y) = frame.from_lonlat(ORIGIN[0], ORIGIN[1]);
    let scale = frame.scale_at(ORIGIN[1]).0;
    let nodes = [726, 728, 730, 732, 734, 736, 738, 740];
    for node in nodes {
        let y = (point(net, node)[1] - origin_y) / scale;
        let x = if node <= 734 {
            507.0 - 0.362 * y
        } else {
            23.9 + 0.139 * y
        };
        place(net, node, [origin_x + x * scale, origin_y + y * scale]);
    }
    for edge in [640, 642, 644, 646, 650, 652] {
        replace_shape(net, edge, &[], 0);
    }
    let [x, y] = plane(net, [148.0, 992.0]);
    let mut turn = net.edge_data(648).unwrap();
    turn.pis = vec![Pi::new(x, y, 78.0, 0)];
    net.set_edge(648, Some(turn)).unwrap();
    let north = point(net, 726);
    let scale = net.frame().scale_at(ORIGIN[1]).0;
    let lead = plus(north, unit([0.362, -1.0]), 35.0 * scale);
    replace_shape(net, 638, &[lead], 1);
    for id in 0..net.line_count() as u32 {
        let mut line = net.line_data(id).unwrap();
        let mut changed = false;
        let mut new_path = Vec::with_capacity(line.path.len());
        for &code in &line.path {
            if let Some((_, replacement)) = paths.iter().find(|(e, _)| *e == code >> 1) {
                if code & 1 == 0 {
                    new_path.extend(replacement.iter().copied());
                } else {
                    new_path.extend(replacement.iter().rev().map(|p| p ^ 1));
                }
                changed = true;
            } else {
                new_path.push(code);
            }
        }
        if changed {
            line.path = new_path;
            for stop in &mut line.stops {
                if let Some((_, keep)) = stops.iter().find(|(drop, _)| *drop == *stop) {
                    *stop = *keep;
                }
            }
            net.set_line(id, Some(line)).unwrap();
        }
    }
    let edges: Vec<_> = paths.iter().map(|(edge, _)| *edge).collect();
    let nodes: Vec<_> = stops.iter().map(|(drop, _)| *drop).collect();
    retire(net, &edges, &nodes);
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
    northern_loop(&mut net);
    flinders_east(&mut net);
    southern_cross_north(&mut net);
    approaches(&mut net);
    plaza(&mut net);
    street_stops(&mut net);
    swanston_trams(&mut net);
    tram_junctions(&mut net);
    net.touch_all();
    derive(&mut net);
    for edge in [462, 509, 726, 965, 1033, 1040, 1200, 1281] {
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
        if line.name == "Tram 64" {
            assert!(world.net.path_reversals(&line.path).is_empty());
        }
        assert!(
            world.svc.lines[id as usize].running,
            "inactive service: {}",
            line.name
        );
    }
    fs::write(&args[1], save::encode(&world.net)).unwrap();
}
