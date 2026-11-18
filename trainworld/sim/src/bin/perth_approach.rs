//! Revise the track payload of the first Australian city maps Perth save.
use std::{env, fs};
use trainworld_sim::track::{net::Network, save, world::TrackWorld};

const CLONED_NODES: [u32; 7] = [56, 57, 58, 59, 60, 62, 63];

fn offset_edge(
    net: &mut Network,
    source: u32,
    target: u32,
    ends: [u32; 2],
    offset: [f64; 2],
    taper_from: Option<u32>,
) {
    let mut edge = net.edge_data(source).expect("original approach edge");
    [edge.a, edge.b] = ends;
    let anchor = taper_from.map(|id| net.node_data(id).unwrap());
    for pi in &mut edge.pis {
        let weight = anchor.as_ref().map_or(1.0, |p| {
            let t = ((pi.x - p.x).hypot(pi.y - p.y) / 260.0).min(1.0);
            1.0 - t * t * (3.0 - 2.0 * t)
        });
        pi.x += offset[0] * weight;
        pi.y += offset[1] * weight;
    }
    net.set_edge(target, Some(edge))
        .expect("place parallel edge");
}

// Keep the eased edges tangent to their adjoining track at the split.
fn align_lead(net: &mut Network, edge_id: u32, node: u32, adjoining: u32) {
    let joint = net.node_data(node).unwrap();
    let other_edge = net.edge_data(adjoining).unwrap();
    let (pi, other_node) = if other_edge.a == node {
        (other_edge.pis.first(), other_edge.b)
    } else {
        (other_edge.pis.last(), other_edge.a)
    };
    let other = net.node_data(other_node).unwrap();
    let (x, y) = pi.map_or((other.x, other.y), |p| (p.x, p.y));
    let (dx, dy) = (joint.x - x, joint.y - y);

    let mut edge = net.edge_data(edge_id).unwrap();
    let pi = if edge.a == node {
        edge.pis.first_mut()
    } else {
        edge.pis.last_mut()
    }
    .unwrap();
    let length = (pi.x - joint.x).hypot(pi.y - joint.y);
    let ratio = length / dx.hypot(dy);
    pi.x = joint.x + dx * ratio;
    pi.y = joint.y + dy * ratio;
    net.set_edge(edge_id, Some(edge)).unwrap();
}

fn main() {
    let args: Vec<_> = env::args_os().skip(1).collect();
    assert_eq!(args.len(), 2, "perth_approach INPUT.twt2 OUTPUT.twt2");
    let input = fs::read(&args[0]).expect("read original payload");
    let mut net = save::decode(&input).expect("decode Perth network");
    assert_eq!(net.line_count(), 6);
    assert_eq!(net.edge_count(), 114);
    for (id, a, b) in [
        (0, 58, 57),
        (1, 57, 59),
        (2, 61, 60),
        (3, 60, 62),
        (58, 55, 56),
        (59, 59, 62),
        (60, 59, 62),
        (61, 61, 63),
        (62, 63, 56),
        (63, 63, 56),
        (64, 64, 58),
        (98, 99, 100),
        (99, 100, 56),
        (100, 61, 63),
        (101, 58, 37),
        (107, 100, 99),
    ] {
        let edge = net.edge_data(id).expect("original Perth edge");
        assert_eq!((edge.a, edge.b, edge.tracks, edge.built), (a, b, 2, true));
    }

    // The real corridor runs east-northeast through the two suburban stations.
    // This offset keeps the northern pair beside the existing southern alignment.
    let scale = net.frame().scale_at(-31.95).0;
    let offset = [-5.5 * scale, 13.0 * scale];
    let first_node = net.node_count() as u32;
    let first_edge = net.edge_count() as u32;
    let split = |node| first_node + CLONED_NODES.iter().position(|&n| n == node).unwrap() as u32;
    for node in CLONED_NODES {
        let mut data = net.node_data(node).unwrap();
        data.x += offset[0];
        data.y += offset[1];
        net.set_node(split(node), Some(data)).unwrap();
    }
    for node in [57, 60] {
        let data = net.station_data(node).expect("shared station");
        net.set_station(split(node), Some(data)).unwrap();
        assert!(net.link(node, split(node)), "link the platform pairs");
    }
    for (id, a, b) in [(0, 58, 57), (1, 57, 59), (3, 60, 62)] {
        offset_edge(
            &mut net,
            id,
            first_edge + id,
            [split(a), split(b)],
            offset,
            None,
        );
    }
    offset_edge(&mut net, 60, 59, [split(59), split(62)], offset, None);
    offset_edge(&mut net, 100, 100, [split(60), split(63)], offset, None);
    offset_edge(&mut net, 63, 63, [split(63), split(56)], offset, None);

    // Continue the station leads through the old plain joints. This keeps the
    // platforms clear of joints without shortening them or moving the stops.
    let mut claisebrook = net.edge_data(61).unwrap();
    claisebrook.a = 60;
    net.set_edge(61, Some(claisebrook)).unwrap();
    let mut east_perth = net.edge_data(98).unwrap();
    east_perth.a = 98;
    net.set_edge(98, Some(east_perth)).unwrap();

    // Connect to the original Perth platform and East Perth approach.
    offset_edge(&mut net, 101, 101, [split(58), 37], offset, Some(58));
    offset_edge(&mut net, 99, 99, [100, split(56)], offset, Some(56));
    align_lead(&mut net, 101, split(58), first_edge);
    align_lead(&mut net, 99, split(56), 63);

    let mut revised = 0;
    for id in 0..net.line_count() as u32 {
        let mut line = net.line_data(id).unwrap();
        let north_side = match line.name.as_str() {
            "Airport Line" | "Ellenbrook Line" | "Fremantle – Midland" => true,
            "Armadale Line" | "Thornlie-Cockburn Line" => false,
            "Yanchep – Mandurah" => continue,
            name => panic!("unexpected Perth service {name}"),
        };
        line.path.retain(|code| !matches!(*code >> 1, 2 | 4));
        for code in &mut line.path {
            let (edge, rev) = (*code >> 1, *code & 1);
            let (replacement, rev) = match (north_side, edge) {
                (true, 0..=3) => (first_edge + edge, rev),
                (true, 60) => (59, rev),
                (true, 62) => (63, rev),
                (true, 107) => (98, rev ^ 1),
                (false, 63) => (62, rev),
                _ => (edge, rev),
            };
            *code = replacement << 1 | rev;
        }
        if north_side {
            for stop in &mut line.stops {
                if matches!(*stop, 57 | 60) {
                    *stop = split(*stop);
                }
            }
        }
        net.set_line(id, Some(line)).unwrap();
        revised += 1;
    }
    assert_eq!(revised, 5);
    for edge in [2, 4, 107] {
        net.set_edge(edge, None).unwrap();
    }
    for node in [61, 99] {
        net.set_node(node, None).unwrap();
    }

    let world = TrackWorld::new(net);
    for id in 0..world.net.line_count() as u32 {
        assert!(
            world.net.check_line(id).is_ok(),
            "invalid Perth service {id}"
        );
        assert!(
            world.svc.lines[id as usize].running,
            "inactive Perth service {id}"
        );
    }
    fs::write(&args[1], save::encode(&world.net)).expect("write revised payload");
}
