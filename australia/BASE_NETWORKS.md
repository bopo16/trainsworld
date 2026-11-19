# Original Perth, Canberra and Sydney builds
For the revised Sydney CBD map, see [Sydney Central, City Circle and CBD Metro](SYDNEY_GEOMETRY.md).

This report records the three original Trainsworld 0.4 builds for 18 November 2026. See the [current save index](README.md) for downloads. These builds reuse the game's real-network, corridor, shared-track and save generators.

| Save | Network and deliberate simplifications |
| --- | --- |
| `perth.save` | Eight regular Transperth rail lines represented by six services: Yanchep–Mandurah and Fremantle–Midland run through the city. One representative stopping pattern per line; event-only and regional services omitted. See the [Perth approach revision](PERTH_APPROACH.md). |
| `canberra.save` | Route 1 light rail between Alinga Street and Gungahlin Place, all 14 stops. No planned extension. |
| `sydney.save` | Metro M1 to Bankstown, Sydney Trains T1–T9, and light rail L1–L4. Representative branches and stopping patterns, rather than all service variants; no intercity, future Metro lines, buses or ferries. T2, T3 and T8 services use one-way City Circle loops, then return along their originating branch. This models connectivity, not actual train block workings. |

Perth and Canberra use weekday GTFS stopping patterns and approximate frequencies, reduced to representative services. Sydney's official GTFS requires credentials and was unavailable: its lines and stops are derived from the pinned OpenStreetMap route relations in `sources/`. Sydney frequencies and travel times are **estimates from the game generator**, not official timetable observations. The game may display an internal comparison as “GTFS” even for these OSM-derived estimates. Geographic geometry is drawn from the game’s OSM-derived rail graph; it is simplified and is not a survey of individual tracks. One Sydney rail hop used a fallback geometry because the graph route did not pass the generator's detour check. All 55 Sydney light-rail and 13 Canberra light-rail hops matched the graph. Shared corridors are modelled with shared infrastructure where supported; separate parallel tracks, junctions and platforms remain approximations.

The game uses 20 m vehicle sections: Perth uses 140 m for Airport/Yanchep/Mandurah services and 100 m for the others; Canberra uses 40 m; Sydney uses 120 m for metro, 160 m for trains, and 40 m for light rail. These are broad capacity/platform approximations, not individual fleet or platform surveys. Relevant official references include the [PTA annual report](https://www.pta.wa.gov.au/Portals/15/annualreports/2024/Public%20Transport%20Authority%20Annual%20Report%202023-24.pdf) and [platform upgrade program](https://www.pta.wa.gov.au/projects/planned-projects/platform-and-signalling-upgrade-program-psup), and the [ACT light rail delivery report](https://www.parliament.act.gov.au/__data/assets/pdf_file/0009/1398258/City-to-Gungahlin-Light-Rail-Project-Delivery-Report%2C-dated-June-2019.pdf). The game’s section granularity accounts for the difference from the ACT's 33 m vehicles.

## Data and attribution

* [Transperth GTFS](https://www.transperth.wa.gov.au/TimetablePDFs/GoogleTransit/Production/google_transit.zip), retrieved 18 November 2026, SHA-256 `d236c301326d18466608f6a51579d6f66d021e92b45dc3ff8e04f94cb1294dbd`. Data available free of charge from www.transperth.wa.gov.au. See the [PTA spatial data terms](https://www.transperth.wa.gov.au/About/Spatial-Data-Access).
* [Transport Canberra light rail GTFS](https://www.transport.act.gov.au/googletransit/google_transit_lr.zip), retrieved 18 November 2026, SHA-256 `8bf96ab88671cbc9b7306cb8ffad2d30e0f9a2085570a62416668074468655e5`. The [developer page](https://www.transport.act.gov.au/contact-us/information-for-developers) marks this feed deprecated; check the current provider before updating. ACT data is licensed CC BY.
* Sydney route relations are © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). Compact snapshots and source relation IDs are checked in; `collect_sydney.py` converts downloaded relation/full XML files into those snapshots. The [Sydney Metro overview](https://www.sydneymetro.info/about) and [Sydney rail map](https://opendata.transport.nsw.gov.au/data/dataset/a1ebe80d-442e-43cc-9ea9-e075bba96eb5/resource/8e40e238-5575-4452-8e0a-8ce1c086d5f0/download/sydney-rail-network_1.pdf) provide context. OSM can lag actual operations; this is not a substitute for an authorised current NSW timetable.
* Game data release 18 November 2026: [Australian real-rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr), SHA-256 `5ed852b014bc36577188ec03be2fadee049851f0a3f18cfb07ae147ce6889d68`; [Perth pack](https://data.anita.garden/trainworld/2026-11-18/per.json), SHA-256 `f8d4ba43387966fcd1e50c3471cd5ae8fe6cb1ace9a52cd3d1ee1306d840aa17`; [Sydney pack](https://data.anita.garden/trainworld/2026-11-18/syd.json), SHA-256 `348ce36d3864846a5f71b9e902f190f466e00fbcbc8bb1632effcab12e712310`. The graph is processed OSM-derived game data; its exact OSM extraction date was not independently established. The generator loads local city crops and does not regenerate the worldwide graph. Canberra has no matching game city pack and uses a local geographic origin.

The download URLs are mutable. Exact rebuilding requires retaining the inputs matching the hashes above; the Sydney relation snapshots are included in the repository.

## Build and validate

Install Python 3, Rust/Cargo, and Python packages `numpy pandas scipy shapely>=2 matplotlib`. Run from the repository root, with these variables pointing to the pinned input files and fresh output directories:

```sh
export PYTHONHASHSEED=0
python australia/build.py per --gtfs "$PERTH_GTFS" --graph "$AU_GRAPH" --pack "$PERTH_PACK" --out "$PERTH_OUT"
python australia/build.py can --gtfs "$CANBERRA_GTFS" --graph "$AU_GRAPH" --out "$CANBERRA_OUT"
python australia/sydney.py --graph "$AU_GRAPH" --pack "$SYDNEY_PACK" --out "$SYDNEY_OUT"
python -m unittest discover -s australia -v
python australia/validate.py per "$PERTH_OUT/per_real.save"
python australia/validate.py can "$CANBERRA_OUT/can_real.save"
python australia/validate.py syd "$SYDNEY_OUT/syd_real.save"
```

The generators stage the supplied graph and city packs in the ignored `trainworld/data/packs` directory and refuse to overwrite different staged inputs. They extract only relevant GTFS routes and services, then invoke the existing Rust save builder and native validator. Remove or relocate conflicting staged files deliberately before changing inputs. A fresh output directory is required for each run.

The validator decompresses the actual save, loads its track payload using the game's native code, checks service connectivity, vehicle families, fleet allocation, key stations and City Circle/Perth through-running, and reports geometry warnings. The test suite also checks route coverage and through-service construction. A separate capacity diagnostic reported no modelled resources above 90% utilisation; that is not a guarantee against queues or congestion in actual play.

| Save | Native model result | Remaining geometry warnings | SHA-256 |
| --- | --- | --- | --- |
| Perth | 6 services running, 85 station names | 1 platform/junction outside the revised approach | `d660a23d27bc6cd3e2345ee9e43c0d0e39b52e0d6db7884a57b21588913d3da1` |
| Canberra | 1 service running, 14 station names | none | `b1a483c2acec052d3beadb2627dcca0c4b046c05e463163a2fa01ef5d30b0e53` |
| Sydney | 18 services running, 239 station/stop names | 1 platform joint, 1 platform/junction | `57151aabbb0ab3cbfc47e3b4c03b5518f33af7ea47a5caa5458da4beb0773e11` |

These checks do not replace loading and inspecting the saves in the game's graphical interface. In particular, Canberra's custom origin and city selection/camera have not been visually verified. Inspect dense Sydney interchanges and its reported platform warnings in-game. The Perth northeast approach was checked in Chromium as described in [the revision report](PERTH_APPROACH.md). A future NSW GTFS-backed build should replace the approximate frequencies and verify route patterns before adding intercity services.
