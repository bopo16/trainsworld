//! Reload a generated Melbourne network using the game's decoder and service model.
use std::collections::BTreeSet;
use trainworld_sim::track::{save, world::TrackWorld};
fn main() {
    let mut args = std::env::args().skip(1);
    let file = args.next().expect("usage: melbourne_metro_validate TRACK FLEET");
    let fleet: u64 = args.next().expect("fleet required").parse().expect("invalid fleet");
    let net = save::decode(&std::fs::read(file).expect("read track payload")).expect("decode game network");
    assert!(!net.right_hand, "network must keep left");
    let world = TrackWorld::new(net);
    let n = &world.net;
    let mut stations = BTreeSet::new();
    for i in 0..n.node_count() as u32 {
        if let Some(st) = n.station_data(i) { if st.built { stations.insert(st.name); } }
    }
    for st in ["Flinders Street", "Richmond", "Parliament", "Melbourne Central", "Flagstaff", "Southern Cross", "Town Hall", "State Library", "Parkville", "Arden", "Anzac", "Caulfield", "Sunbury", "Cranbourne", "East Pakenham", "Lilydale", "Belgrave", "Stony Point", "Flemington Racecourse"] {
        assert!(stations.contains(st), "missing {st}");
    }
    assert!(stations.len() >= 220, "too few distinct stations: {}", stations.len());
    let mut names = BTreeSet::new();
    let mut needed = 0u64;
    let mut city_loop = false;
    for i in 0..n.line_count() as u32 {
        let l = n.line_data(i).expect("missing line");
        let stop_names: Vec<String> = l.stops.iter().map(|&id| n.station_data(id).expect("line stop is not a station").name).collect();
        if ["Flinders Street", "Southern Cross", "Flagstaff", "Melbourne Central", "Parliament"].iter().all(|s| stop_names.iter().any(|x| x == s)) { city_loop = true; }
        if l.name == "Cranbourne – Sunbury" || l.name == "Pakenham – Sunbury" {
            for station in ["Sunbury", "Arden", "Parkville", "State Library", "Town Hall", "Anzac", "Caulfield"] {
                assert!(stop_names.iter().any(|x| x == station), "{} does not stop at {station}", l.name);
            }
        }
        let svc = &world.svc.lines[i as usize];
        assert!(svc.running, "{} is not running", l.name);
        assert!(!l.symbol.is_empty(), "{} missing symbol", l.name);
        assert!(l.stops.len() >= 2 && !l.path.is_empty(), "{} missing stops/path", l.name);
        assert!(svc.trains.iter().any(|&x| x > 0), "{} has no trains", l.name);
        let mut last = None;
        for p in &l.path {
            let edge = n.edge_data(p >> 1).expect("missing path edge");
            assert!(edge.built, "{} uses an unbuilt edge", l.name);
            let (from, to) = if p & 1 == 0 { (edge.a,edge.b) } else { (edge.b,edge.a) };
            if let Some(previous) = last { assert_eq!(previous,from,"{} has a disconnected path",l.name); }
            last = Some(to);
        }
        needed += u64::from(*svc.trains.iter().max().unwrap()) * u64::from(l.cars);
        names.insert(l.name);
    }
    for expected in ["Alamein", "Belgrave", "Cranbourne", "Craigieburn", "Flemington Racecourse", "Frankston", "Glen Waverley", "Hurstbridge", "Lilydale", "Mernda", "Pakenham", "Sandringham", "Stony Point", "Sunbury", "Upfield", "Werribee", "Williamstown"] {
        assert!(names.iter().any(|name| name.contains(expected)), "missing line {expected}");
    }
    assert!(city_loop, "no route serves all City Loop stations");
    assert!(names.contains("Cranbourne – Sunbury") && names.contains("Pakenham – Sunbury"), "Metro Tunnel through services missing");
    assert!(fleet >= needed, "header fleet {fleet} is less than {needed} cars needed");
    let issues = n.validate(&(0..n.edge_count() as u32).collect::<Vec<_>>(), &(0..n.node_count() as u32).collect::<Vec<_>>(), &[]);
    for issue in &issues { eprintln!("track validation: {issue:?}"); }
    println!("Reloaded: {} lines running, {} distinct station names, {} edges, fleet {} cars (need {}); {} track geometry/placement warnings", n.line_count(), stations.len(), n.edge_count(), fleet, needed, issues.len());
}
