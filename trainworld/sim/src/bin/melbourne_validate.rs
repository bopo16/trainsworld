//! Validate the extracted network payload using the game's own decoder and service model.
use trainworld_sim::track::{save, world::TrackWorld};
fn main() {
    let file = std::env::args().nth(1).expect("usage: melbourne_validate TRACK_BYTES");
    let fleet: u32 = std::env::args().nth(2).expect("fleet required").parse().expect("invalid fleet");
    let bytes = std::fs::read(file).expect("read track payload");
    let net = save::decode(&bytes).expect("game decoder rejected track payload");
    assert!(!net.right_hand, "expected left-hand running");
    let w = TrackWorld::new(net);
    assert_eq!(w.net.line_count(), 1, "expected one line");
    let line = w.net.line_data(0).expect("missing line");
    let wanted = ["Flinders Street", "Richmond", "South Yarra", "Hawksburn", "Toorak", "Armadale", "Malvern", "Caulfield"];
    let names: Vec<String> = line.stops.iter().map(|&id| w.net.station_data(id).expect("missing station").name).collect();
    let mut reversed = wanted; reversed.reverse();
    assert!(names.iter().map(String::as_str).eq(wanted) || names.iter().map(String::as_str).eq(reversed), "unexpected stations: {names:?}");
    assert_eq!(line.path.len(), wanted.len() - 1);
    for (idx, &p) in line.path.iter().enumerate() {
        let edge = w.net.edge_data(p >> 1).expect("missing path edge");
        assert!(edge.built && edge.tracks == 2, "edge not built as a track pair");
        let (from, to) = if p & 1 == 0 { (edge.a, edge.b) } else { (edge.b, edge.a) };
        assert_eq!((from, to), (line.stops[idx], line.stops[idx+1]), "disconnected path");
    }
    let svc = &w.svc.lines[0];
    assert!(svc.running, "service does not run after load");
    assert!(svc.trains.iter().any(|&n| n > 0), "no allocated trains");
    assert!(fleet >= svc.trains.iter().max().unwrap() * line.cars as u32, "header fleet cannot support allocated trains");
    assert!(line.tph.iter().any(|&x| x > 0.0));
    println!("decoded: {} stations, {} built double-track edges, running service, trains {:?}, tph {:?}, cars {}", names.len(), line.path.len(), svc.trains, line.tph, line.cars);
}
