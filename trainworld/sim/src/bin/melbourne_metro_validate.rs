//! Reload a generated Melbourne network using the game's decoder and service model.
use std::collections::BTreeSet;
use trainworld_sim::track::{save, world::TrackWorld, net::LoopKind, wasm::TrackApi};
fn main() {
    let mut args = std::env::args().skip(1);
    let file = args.next().expect("usage: melbourne_metro_validate TRACK FLEET");
    let fleet: u64 = args.next().expect("fleet required").parse().expect("invalid fleet");
    let options: Vec<String> = args.collect();
    let expect_city_loops = options.iter().any(|x| x == "--city-loops");
    let tram_fleet: Option<u64> = options.iter().position(|x| x == "--trams").map(|i| options[i+1].parse().expect("invalid tram fleet"));
    let bytes = std::fs::read(file).expect("read track payload");
    let mut api = TrackApi::new(0.0, 0.0, false);
    assert!(api.load(&bytes), "game load routine rejected payload");
    let net = save::decode(&api.save()).expect("decode re-saved game network");
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
    let mut tram_needed = 0u64;
    let mut tram_count = 0;
    let mut tram_symbols = BTreeSet::new();
    let mut tram_edge_use = std::collections::BTreeMap::<u32, u32>::new();
    let mut event_edges = BTreeSet::new();
    let mut cross_city_edges = BTreeSet::new();
    let mut city_loop = false;
    let grouped = n.line_group.iter().any(|&g| g != 0);
    let mut groups = std::collections::BTreeMap::new();
    let has_loop_services = (0..n.line_count() as u32).any(|i| n.line_data(i).is_some_and(|l| l.one_way));
    assert!(!expect_city_loops || has_loop_services, "missing directional City Loop services");
    let mut loop_platforms = std::collections::BTreeMap::new();
    let mut tunnel_edges: std::collections::BTreeMap<u32, BTreeSet<u32>> = std::collections::BTreeMap::new();
    for i in 0..n.line_count() as u32 {
        let l = n.line_data(i).expect("missing line");
        if grouped {
            assert!(l.group > 0 && !l.group_name.is_empty() && !l.group_look.symbol.is_empty(), "{} missing line group metadata", l.name);
            if let Some(previous) = groups.insert(l.group, l.group_name.clone()) { assert_eq!(previous, l.group_name, "inconsistent group name"); }
            if l.name == "Stony Point" {
                for &edge in &l.path { assert_eq!(n.edge_data(edge >> 1).unwrap().tracks, 1, "Stony Point is not single-track"); }
            }
        }
        let stop_names: Vec<String> = l.stops.iter().map(|&id| n.station_data(id).expect("line stop is not a station").name).collect();
        if ["Flinders Street", "Southern Cross", "Flagstaff", "Melbourne Central", "Parliament"].iter().all(|s| stop_names.iter().any(|x| x == s)) { city_loop = true; }
        if l.name == "Cranbourne – Sunbury" || l.name == "Pakenham – Sunbury" {
            for station in ["Sunbury", "Arden", "Parkville", "State Library", "Town Hall", "Anzac", "Caulfield"] {
                assert!(stop_names.iter().any(|x| x == station), "{} does not stop at {station}", l.name);
            }
        }
        let svc = &world.svc.lines[i as usize];
        if l.name.starts_with("Flemington Racecourse") { event_edges.extend(l.path.iter().map(|p| p >> 1)); }
        if l.name.contains("Werribee") || l.name.contains("Williamstown") { cross_city_edges.extend(l.path.iter().map(|p| p >> 1)); }
        if has_loop_services && (l.name == "Werribee – Sandringham" || l.name == "Williamstown – Sandringham") {
            let fss: Vec<u32> = l.stops.iter().copied().filter(|&id| n.station_data(id).is_some_and(|st| st.name == "Flinders Street")).collect();
            assert_eq!(fss.len(), 1, "{} does not pass Flinders Street once", l.name);
            assert_eq!(n.built_ports(fss[0]), 2, "{} terminates at Flinders Street", l.name);
            let at = (1..l.path.len()).find(|&k| n.path_nodes(l.path[k-1]).1 == fss[0]).expect("Flinders not inside cross-city path");
            assert!(!n.turns_back(l.path[at-1], l.path[at]), "{} reverses at Flinders Street", l.name);
        }
        assert!(n.check_line(i).is_ok(), "{} has an invalid game route: {:?}", l.name, n.check_line(i));
        if has_loop_services && ["Alamein", "Belgrave", "Craigieburn", "Frankston", "Glen Waverley", "Hurstbridge", "Lilydale", "Mernda", "Upfield"].contains(&l.name.as_str()) {
            assert_eq!(n.line_loop(i), LoopKind::Balloon, "{} is not a balloon", l.name);
            assert!(l.one_way && svc.one_way, "{} is not one-way", l.name);
            let fss: Vec<u32> = l.stops.iter().copied().filter(|&id| n.station_data(id).is_some_and(|st| st.name == "Flinders Street")).collect();
            assert_eq!(fss.len(), 1, "{} should pass Flinders Street once per circuit", l.name);
            assert_eq!(n.built_ports(fss[0]), 2, "{} terminates at Flinders Street", l.name);
            assert_eq!(n.station_data(fss[0]).unwrap().upgrades & trainworld_sim::track::upgrades::TERMINAL, 0, "{} has a terminal at Flinders Street", l.name);
            let at = (1..l.path.len()).find(|&k| n.path_nodes(l.path[k-1]).1 == fss[0]).expect("Flinders not inside path");
            assert!(!n.turns_back(l.path[at-1], l.path[at]), "{} reverses at Flinders Street", l.name);
            let one_way: BTreeSet<u32> = l.path.iter().map(|p| p >> 1).filter(|&e| n.edge_data(e).is_some_and(|d| d.tracks == 1 && d.oneway != 0)).collect();
            assert!(!one_way.is_empty(), "{} has no directional loop track", l.name);
            tunnel_edges.entry(l.group).or_default().extend(one_way);
            for station in ["Parliament", "Melbourne Central", "Flagstaff", "Southern Cross"] {
                assert!(stop_names.iter().any(|x| x == station), "{} missing loop station {station}", l.name);
            }
            if l.name == "Frankston" {
                let expected = ["Richmond", "Parliament", "Melbourne Central", "Flagstaff", "Southern Cross", "Flinders Street", "Richmond"];
                let mut next = 0;
                for station in &stop_names {
                    if next < expected.len() && station == expected[next] { next += 1; }
                }
                assert_eq!(next, expected.len(), "Frankston does not traverse the Loop in the expected order: {stop_names:?}");
            }
            if let Some(old) = loop_platforms.insert(l.group, fss[0]) { assert_eq!(old, fss[0], "group has inconsistent Flinders platform"); }
        }
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
        let cars_needed = u64::from(*svc.trains.iter().max().unwrap()) * u64::from(l.cars);
        if n.line_tram(i) {
            tram_count += 1;
            tram_symbols.insert(l.symbol.clone());
            tram_needed += cars_needed;
            if l.name == "Tram 35" {
                assert!(l.one_way && n.line_loop(i) != LoopKind::None, "City Circle is not a loop");
            }
            assert_eq!(l.group_name, "Yarra Trams");
            assert_eq!(l.colour, 0x009b3a, "tram is not green");
            assert!(l.cars <= 4, "tram exceeds four sections");
            for &stop in &l.stops {
                assert!(n.station_data(stop).unwrap().platform <= 80, "tram platform too long");
            }
            for &edge in &l.path {
                assert!(n.edge_data(edge >> 1).unwrap().kind.spec().family == 1, "tram uses rail track");
                *tram_edge_use.entry(edge >> 1).or_default() += 1;
            }
        } else { needed += cars_needed; }
        names.insert(l.name);
    }
    for expected in ["Alamein", "Belgrave", "Cranbourne", "Craigieburn", "Flemington Racecourse", "Frankston", "Glen Waverley", "Hurstbridge", "Lilydale", "Mernda", "Pakenham", "Sandringham", "Stony Point", "Sunbury", "Upfield", "Werribee", "Williamstown"] {
        assert!(names.iter().any(|name| name.contains(expected)), "missing line {expected}");
    }
    if grouped {
        assert_eq!(groups.len(), if tram_fleet.is_some() { 8 } else { 7 }, "unexpected line groups");
        for name in ["Burnley Group", "Clifton Hill Group", "Northern Group", "Caulfield Group", "Cross-City Group", "Metro Tunnel", "Special Events"] {
            assert!(groups.values().any(|x| x == name), "missing group {name}");
        }
    }
    if has_loop_services {
        assert_eq!(loop_platforms.len(), 4, "expected four loop groups");
        assert_eq!(loop_platforms.values().copied().collect::<BTreeSet<_>>().len(), 4, "loop groups share a Flinders platform");
        let sets: Vec<_> = tunnel_edges.values().collect();
        for i in 0..sets.len() { for j in i+1..sets.len() { assert!(sets[i].is_disjoint(sets[j]), "different loop groups share directional tunnel track"); } }
        assert!(names.contains("Werribee – Sandringham") && names.contains("Williamstown – Sandringham"), "missing cross-city through services");
    }
    assert!(city_loop, "no route serves all City Loop stations");
    assert!(names.contains("Cranbourne – Sunbury") && names.contains("Pakenham – Sunbury"), "Metro Tunnel through services missing");
    assert!(fleet >= needed, "header fleet {fleet} is less than {needed} cars needed");
    if let Some(fleet) = tram_fleet {
        assert_eq!(tram_count, 24, "expected all 24 tram routes");
        let expected: BTreeSet<String> = ["1","3","5","6","11","12","16","19","30","35","48","57","58","59","64","67","70","72","75","78","82","86","96","109"].iter().map(|s| s.to_string()).collect();
        assert_eq!(tram_symbols, expected, "unexpected numbered tram routes");
        assert!(tram_edge_use.values().any(|&users| users > 1), "tram routes do not share track");
        assert!(event_edges.is_disjoint(&cross_city_edges), "event and cross-city services overlap on an edge");
        if options.iter().any(|x| x == "--tram-upgrades") {
            for stop in ["Flinders Street Station/Elizabeth St #1", "Waterfront City/Docklands Dr #D11"] {
                let upgraded = (0..n.node_count() as u32).filter_map(|i| n.station_data(i)).any(|st| st.name == stop && st.upgrades & 9 == 9);
                assert!(upgraded, "{stop} missing its tram terminal/passing upgrade");
            }
        }
        assert!(fleet >= tram_needed, "header tram fleet {fleet} is less than {tram_needed} sections needed");
    } else { assert_eq!(tram_count, 0, "tram validation flag missing"); }
    let issues = n.validate(&(0..n.edge_count() as u32).collect::<Vec<_>>(), &(0..n.node_count() as u32).collect::<Vec<_>>(), &[]);
    for issue in &issues { eprintln!("track validation: {issue:?}"); }
    println!("Reloaded: {} lines running ({} tram), {} distinct station names, {} edges, fleet {} cars (need {}), {} tram sections needed; {} track geometry/placement warnings", n.line_count(), tram_count, stations.len(), n.edge_count(), fleet, needed, tram_needed, issues.len());
}
