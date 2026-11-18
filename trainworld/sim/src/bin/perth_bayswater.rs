//! Move the Bayswater Airport pair to the south side of the rail corridor.
use std::{env, fs};
use trainworld_sim::track::{net::Network, save, world::TrackWorld};

fn offset_edge(
    net: &mut Network,
    source: u32,
    target: u32,
    ends: [u32; 2],
    offset: [f64; 2],
    taper_at: Option<u32>,
) {
    let mut edge = net.edge_data(source).unwrap();
    let anchor = taper_at.map(|id| net.node_data(id).unwrap());
    [edge.a, edge.b] = ends;
    let keep = taper_at.map(|id| {
        if id == edge.a {
            0
        } else {
            edge.pis.len().saturating_sub(1)
        }
    });
    for (index, pi) in edge.pis.iter_mut().enumerate() {
        let factor = anchor.as_ref().map_or(1.0, |node| {
            if keep == Some(index) {
                return 0.0;
            }
            let t = ((pi.x - node.x).hypot(pi.y - node.y) / 270.0).min(1.0);
            t * t * (3.0 - 2.0 * t)
        });
        pi.x += offset[0] * factor;
        pi.y += offset[1] * factor;
    }
    net.set_edge(target, Some(edge)).unwrap();
}

// Fit a single turn between the two existing tangents east of the platform.
fn smooth_departure(net: &mut Network) {
    let mut edge = net.edge_data(90).unwrap();
    let a = net.node_data(edge.a).unwrap();
    let b = net.node_data(edge.b).unwrap();
    let (first, last) = (edge.pis.first().unwrap(), edge.pis.last().unwrap());
    let u = [first.x - a.x, first.y - a.y];
    let v = [last.x - b.x, last.y - b.y];
    let cross = |p: [f64; 2], q: [f64; 2]| p[0] * q[1] - p[1] * q[0];
    let distance = cross([b.x - a.x, b.y - a.y], v) / cross(u, v);
    assert!(distance > 0.0);
    let mut corner = *first;
    corner.x = a.x + distance * u[0];
    corner.y = a.y + distance * u[1];
    edge.pis = vec![corner];
    net.set_edge(90, Some(edge)).unwrap();
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    assert_eq!(args.len(), 2, "perth_bayswater INPUT.twt2 OUTPUT.twt2");
    let input = fs::read(&args[0]).unwrap();
    let mut net = save::decode(&input).expect("decode revised Perth save");
    for (id, a, b) in [
        (88, 89, 90),
        (89, 90, 91),
        (90, 91, 92),
        (91, 93, 92),
        (101, 89, 101),
        (103, 91, 102),
        (104, 102, 93),
    ] {
        let edge = net.edge_data(id).unwrap();
        assert_eq!((edge.a, edge.b, edge.tracks), (a, b, 2));
    }
    let main = net.node_data(92).unwrap();
    let airport = net.node_data(102).unwrap();
    let offset = [main.x - airport.x, main.y - airport.y];
    let next = net.node_count() as u32;
    for (from, to) in [(89, next), (90, next + 1), (91, next + 2), (92, 102)] {
        let mut data = net.node_data(from).unwrap();
        data.x += offset[0];
        data.y += offset[1];
        net.set_node(to, Some(data)).unwrap();
    }

    smooth_departure(&mut net);
    let first = net.edge_count() as u32;
    offset_edge(&mut net, 88, first, [next, next + 1], offset, None);
    offset_edge(&mut net, 89, first + 1, [next + 1, next + 2], offset, None);
    offset_edge(&mut net, 90, 103, [next + 2, 102], offset, None);
    // Keep the route direction from the Airport to Perth. The template is
    // oriented the opposite way between the western junction and Bayswater.
    offset_edge(&mut net, 91, 104, [93, 102], offset, Some(93));
    let mut west = net.edge_data(104).unwrap();
    west.pis.reverse();
    [west.a, west.b] = [102, 93];
    net.set_edge(104, Some(west)).unwrap();
    offset_edge(&mut net, 101, 101, [next, 101], offset, Some(101));

    let id = (0..net.line_count() as u32)
        .find(|&id| net.line_data(id).unwrap().name == "Airport Line")
        .unwrap();
    let mut airport = net.line_data(id).unwrap();
    let section = [88 << 1, 89 << 1];
    let at = airport.path.windows(2).position(|w| w == section).unwrap();
    airport.path[at..at + 2].copy_from_slice(&[first << 1, (first + 1) << 1]);
    net.set_line(id, Some(airport)).unwrap();
    assert!(net.link(92, 102), "link Bayswater platform pairs");

    let world = TrackWorld::new(net);
    for id in 0..world.net.line_count() as u32 {
        assert!(world.net.check_line(id).is_ok());
        assert!(world.svc.lines[id as usize].running);
    }
    fs::write(&args[1], save::encode(&world.net)).unwrap();
}
