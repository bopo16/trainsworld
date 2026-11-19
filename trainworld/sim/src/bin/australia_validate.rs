//! Validate generated Australian networks with the same loader and service model as the game.
use std::collections::{BTreeMap, BTreeSet};
use trainworld_sim::track::{save,world::TrackWorld,wasm::TrackApi,net::LoopKind};
fn main() {
    let mut a=std::env::args().skip(1);
    let city=a.next().expect("city");
    let file=a.next().expect("payload");
    let fleet:u64=a.next().expect("fleet").parse().unwrap();
    let trams:u64=a.next().expect("tram fleet").parse().unwrap();
    let expanded = a.any(|arg| arg == "--expanded");
    let bytes=std::fs::read(file).unwrap();
    let mut api=TrackApi::new(0.0,0.0,false);
    assert!(api.load(&bytes),"game load failed");
    let world=TrackWorld::new(save::decode(&api.save()).unwrap());let n=&world.net;
    assert!(!n.right_hand,"expected left-hand running");
    let mut line_ids = BTreeMap::new();
    let mut names=BTreeSet::new();let mut symbols=BTreeSet::new();let mut stations=BTreeSet::new();let mut need=0u64;let mut tram_need=0u64;
    for v in 0..n.node_count() as u32 {if let Some(s)=n.station_data(v){if s.built {stations.insert(s.name);}}}
    for i in 0..n.line_count() as u32 {
        let l=n.line_data(i).unwrap();let svc=&world.svc.lines[i as usize];
        assert!(n.check_line(i).is_ok(),"invalid route {}: {:?}",l.name,n.check_line(i));
        assert!(svc.running && svc.trains.iter().any(|&x|x>0),"{} not running",l.name);
        assert!(!l.symbol.is_empty() && l.stops.len()>=2 && !l.path.is_empty(),"bad line {}",l.name);
        let tram = match city.as_str() {
            "can" => true,
            "syd" => l.symbol.starts_with('L'),
            "bri" => l.symbol == "GLK",
            "ade" => matches!(l.symbol.as_str(), "GL" | "BT"),
            _ => false,
        };
        assert_eq!(n.line_tram(i),tram,"wrong track type {}",l.name);
        if city=="syd" && ["T2","T3","T8"].contains(&l.symbol.as_str()) {
            assert_eq!(n.line_loop(i),LoopKind::Balloon,"{} is not a City Circle balloon",l.name);
            assert!(l.one_way,"{} is not a directional service",l.name);
            for st in ["Central","Town Hall","Wynyard","Circular Quay","St James","Museum"] {
                assert!(l.stops.iter().any(|&v|n.station_data(v).is_some_and(|s|s.name==st)),"{} lacks {st}",l.name);
            }
        }
        if city=="syd" && l.symbol=="M1" {
            for st in ["Tallawong","Bankstown","Sydenham","Chatswood"] {
                assert!(l.stops.iter().any(|&v|n.station_data(v).is_some_and(|s|s.name==st)),"M1 lacks {st}");
            }
        }
        if l.name=="Yanchep – Mandurah" {
            let stop=*l.stops.iter().find(|&&v|n.station_data(v).is_some_and(|s|s.name=="Perth Underground Stn")).expect("missing Perth Underground");
            let at=(1..l.path.len()).find(|&k|n.path_nodes(l.path[k-1]).1==stop).expect("Perth Underground not inside path");
            assert!(!n.turns_back(l.path[at-1],l.path[at]),"reversal at Perth Underground");
        }
        if l.name=="Fremantle – Midland" {
            let stop=*l.stops.iter().find(|&&v|n.station_data(v).is_some_and(|s|s.name=="Perth Stn")).expect("missing Perth");
            let at=(1..l.path.len()).find(|&k|n.path_nodes(l.path[k-1]).1==stop).expect("Perth not inside path");
            assert!(!n.turns_back(l.path[at-1],l.path[at]),"reversal at Perth");
        }
        for &edge in &l.path {let d=n.edge_data(edge>>1).unwrap();assert!(d.built);assert_eq!(d.kind.spec().family==1,tram);}
        if tram {for &stop in &l.stops {assert!(n.station_data(stop).unwrap().platform<=80);}}
        let cars=u64::from(*svc.trains.iter().max().unwrap())*u64::from(l.cars);
        if tram {tram_need+=cars;} else {need+=cars;}
        line_ids.insert(l.symbol.clone(), i);
        symbols.insert(l.symbol);
        names.insert(l.name);
    }
    match city.as_str(){
      "per"=>{for expected in ["Airport Line","Armadale Line","Ellenbrook Line","Fremantle – Midland","Thornlie-Cockburn Line","Yanchep – Mandurah"] {assert!(names.contains(expected),"missing {expected}");}assert_eq!(names.len(),6);assert!(stations.len()>=70);assert!(fleet>=need);},
      "can"=>{assert!(names.contains("Canberra Light Rail 1"));assert_eq!(names.len(),1);for name in ["Gungahlin Place","Alinga Street"] {assert!(stations.contains(name),"missing {name}");}assert!(stations.len()>=14);assert!(trams>=tram_need);},
      "syd"=>{for code in ["M1","T1","T2","T3","T4","T5","T6","T7","T8","T9","L1","L2","L3","L4"] {assert!(symbols.contains(code),"missing {code}");}for name in ["Tallawong","Bankstown","Central"] {assert!(stations.contains(name),"missing {name}");}let lidcombe=(0..n.node_count() as u32).filter_map(|i|n.station_data(i)).any(|s|s.name=="Lidcombe" && s.upgrades&9==9);assert!(lidcombe,"Lidcombe missing terminus upgrades");assert!(stations.len()>=180);assert!(fleet>=need && trams>=tram_need);},
      "bri" | "ade" => {
          let (routes, links, minimum_stations): (&[(&str, &str, &str)], &[(&str, &str, usize)], usize) =
              if city == "bri" {
                  (&[
                      ("BN–FG", "Beenleigh", "Ferny Grove"), ("IP–CA", "Ipswich", "Caboolture"),
                      ("SP–RP", "Springfield Central", "Kippa-Ring"), ("CL–SH", "Cleveland", "Shorncliffe"),
                      ("AIR–GC", "Domestic Airport", "Varsity Lakes"), ("DB", "Roma Street", "Doomben"),
                      ("RW", "Ipswich", "Rosewood"), ("NA", "Roma Street", "Nambour"),
                      ("GY", "Roma Street", "Gympie North"), ("GLK", "Helensvale", "Broadbeach South"),
                  ], &[("IP–CA", "SP–RP", 12), ("BN–FG", "AIR–GC", 20), ("NA", "GY", 15)], 160)
              } else {
                  (&[
                      ("GAW", "Adelaide", "Gawler Central"), ("OH", "Adelaide", "Outer Harbor"),
                      ("GR", "Adelaide", "Grange"), ("PD", "Adelaide", "Port Dock"),
                      ("SEA", "Adelaide", "Seaford"), ("FL", "Adelaide", "Flinders"),
                      ("BEL", "Adelaide", "Belair"), ("GL", "Royal Adelaide Hospital", "Moseley Square"),
                      ("BT", "Botanic Gardens", "Entertainment Centre"),
                  ], &[("SEA", "FL", 7), ("OH", "PD", 9), ("GL", "BT", 3)], 115)
              };
          assert_eq!(n.line_count(), routes.len());
          assert!(stations.len() >= minimum_stations);
          assert!(fleet >= need && trams >= tram_need);
          for &(symbol, first, last) in routes {
              let line = n.line_data(line_ids[symbol]).unwrap();
              let name = |id| n.station_data(id).unwrap().name;
              assert_eq!(name(line.stops[0]), first, "{symbol} origin");
              assert_eq!(name(*line.stops.last().unwrap()), last, "{symbol} destination");
          }
          for &(a, b, count) in links {
              let edges = |symbol| {
                  n.line_data(line_ids[symbol]).unwrap().path.into_iter()
                      .map(|code| code >> 1).collect::<BTreeSet<_>>()
              };
              assert!(edges(a).intersection(&edges(b)).count() >= count, "{a} and {b} lack shared track");
          }
      },
      _=>panic!("unknown city")
    }
    if city == "syd" && expanded {
        let stop = |name: &str, id| n.station_data(id).is_some_and(|station| station.name == name);
        let mut surface_central = BTreeSet::new();
        for id in 0..n.line_count() as u32 {
            let line = n.line_data(id).unwrap();
            match line.symbol.as_str() {
                "T1" | "T2" | "T3" | "T8" | "T9" => {
                    surface_central.extend(line.stops.iter().copied().filter(|&node| {
                        stop("Central", node) && n.node_data(node).unwrap().level == 0
                    }));
                }
                "T4" => {
                    for name in ["Redfern", "Central", "Town Hall"] {
                        let node = *line.stops.iter().find(|&&node| stop(name, node)).expect("T4 CBD stop");
                        assert!(n.node_data(node).unwrap().level < 0, "T4 must serve underground {name}");
                        for other in [1, 2, 3, 4, 5, 11, 12, 13] {
                            assert!(!n.line_data(other).unwrap().stops.contains(&node), "T4 shares {name} with a surface line");
                        }
                    }
                }
                "BMT" | "BTH" | "CCN" | "SCO" => {
                    let terminal = line.stops[0];
                    assert!(stop("Central", terminal));
                    assert_eq!(n.built_ports(terminal), 1, "{} Central track is not a terminus", line.name);
                    assert_ne!(n.station_data(terminal).unwrap().upgrades & 1, 0);
                    assert!(!line.stops.iter().any(|&node| stop("Museum", node)), "regional train uses the City Circle");
                }
                "L5" | "HUN" => assert!(line.stops.iter().any(|&node| stop("Newcastle Interchange", node))),
                _ => {}
            }
        }
        assert_eq!(surface_central.len(), 4, "expected four surface suburban platforms");
        for code in ["BMT", "BTH", "CCN", "SCO", "SHL", "HUN", "L5"] {
            assert!(symbols.contains(code), "missing {code}");
        }
        assert_eq!(n.line_count(), 28);
    }
    let issues=n.validate(&(0..n.edge_count() as u32).collect::<Vec<_>>(),&(0..n.node_count() as u32).collect::<Vec<_>>(),&[]);
    for issue in &issues {eprintln!("track validation: {issue:?}");}
    println!("{city}: {} lines running, {} distinct station names, {} edges, fleet need {} rail / {} tram; {} geometry/placement warnings",n.line_count(),stations.len(),n.edge_count(),need,tram_need,issues.len());
}
