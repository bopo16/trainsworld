//! Refine the Central approach and CBD Metro in the pinned Sydney save.
use std::{env, fs};
use trainworld_sim::track::{geom::Pi, net::Network, save, world::TrackWorld};

type Point = [f64; 2];
const ORIGIN: Point = [151.207, -33.884];

fn plane(net: &Network, p: Point) -> Point {
    let frame = net.frame();
    let (x, y) = frame.from_lonlat(ORIGIN[0], ORIGIN[1]);
    let (kx, ky) = frame.scale_at(ORIGIN[1]);
    [x + kx * p[0], y + ky * p[1]]
}

fn move_station(net: &mut Network, id: u32, p: Point) {
    let mut node = net.node_data(id).unwrap();
    [node.x, node.y] = plane(net, p);
    net.set_node(id, Some(node)).unwrap();
}

fn shape(net: &mut Network, id: u32, guides: &[(Point, i8)]) {
    let mut edge = net.edge_data(id).unwrap();
    edge.pis = guides
        .iter()
        .map(|&(p, level)| {
            let [x, y] = plane(net, p);
            Pi::new(x, y, 0.0, level)
        })
        .collect();
    net.set_edge(id, Some(edge)).unwrap();
}

fn metro(net: &mut Network) {
    // Midlines between the two OSM bores in the published Australian graph.
    // South of Central use 25012–25015; through Gadigal use 17313/17402
    // and 26199/26200; from Martin Place to Barangaroo use 25008/25009.
    move_station(net, 13, [147.0, 1123.0]);
    move_station(net, 14, [299.0, 1861.0]);
    move_station(net, 15, [-403.0, 2708.0]);
    let guides: &[(u32, &[Point])] = &[
        (
            23,
            &[
                [-77.0, -64.7],
                [-562.0, -802.0],
                [-637.0, -947.0],
                [-681.0, -1160.0],
                [-663.0, -1349.0],
                [-636.5, -1447.8],
            ],
        ),
        (
            24,
            &[
                [141.0, 1038.0],
                [129.0, 839.0],
                [166.0, 672.0],
                [185.0, 490.0],
                [168.0, 381.0],
                [122.0, 256.0],
                [10.9, 68.9],
            ],
        ),
        (
            25,
            &[
                [290.0, 1776.0],
                [273.0, 1670.0],
                [208.0, 1510.0],
                [164.0, 1379.0],
                [153.0, 1208.0],
            ],
        ),
        (
            26,
            &[
                [-398.0, 2625.0],
                [-383.0, 2495.0],
                [-330.0, 2405.0],
                [-238.0, 2332.0],
                [-127.0, 2314.0],
                [92.0, 2335.0],
                [181.0, 2315.0],
                [267.0, 2250.0],
                [311.0, 2172.0],
                [323.0, 2077.0],
                [308.0, 1946.0],
            ],
        ),
    ];
    for &(id, points) in guides {
        let points: Vec<_> = points.iter().copied().map(|p| (p, -3)).collect();
        shape(net, id, &points);
    }
    // Keep the northward tangent through the Barangaroo platform aligned
    // with the existing harbour bore.
    let mut edge = net.edge_data(27).unwrap();
    let last = edge.pis.last_mut().unwrap();
    [last.x, last.y] = plane(net, [-408.0, 2791.0]);
    net.set_edge(27, Some(edge)).unwrap();
}

fn central_and_circle(net: &mut Network) {
    // Use the existing leads and levels at the two Central platforms and
    // at the City Circle turnout. Match the west-leg bend to OSM 5516 and
    // 6892 rather than cutting diagonally across the bend.
    shape(
        net,
        65,
        &[
            ([-12.4, 1081.9], -1),
            ([-29.0, 953.0], -1),
            ([-15.0, 884.0], -1),
            ([38.0, 821.0], -1),
            ([113.0, 743.0], -2),
            ([163.0, 680.0], -2),
            ([176.5, 656.0], -2),
        ],
    );
    shape(
        net,
        66,
        &[
            ([-28.1, 1083.8], -3),
            ([-37.0, 956.0], -3),
            ([-20.0, 878.0], -3),
            ([32.0, 814.0], -3),
            ([104.0, 734.0], -2),
            ([158.0, 680.0], -2),
            ([176.5, 656.0], -2),
        ],
    );
    shape(
        net,
        69,
        &[
            ([-189.1, -231.0], 0),
            ([-112.0, -174.0], 0),
            ([-61.1, -97.8], 0),
        ],
    );
    shape(
        net,
        70,
        &[
            ([-172.0, -237.4], 0),
            ([-96.0, -181.0], 0),
            ([-46.4, -108.1], 0),
        ],
    );
    assert!(net.link(60, 61));
    assert!(net.link(12, 60));
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    assert_eq!(args.len(), 2, "sydney_geometry INPUT.twt2 OUTPUT.twt2");
    let raw = fs::read(&args[0]).unwrap();
    let mut net = save::decode(&raw).expect("decode Sydney save");
    assert_eq!((net.line_count(), net.edge_count()), (18, 310));
    metro(&mut net);
    central_and_circle(&mut net);
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
            "inactive route: {}",
            line.name
        );
    }
    fs::write(&args[1], save::encode(&world.net)).unwrap();
}
