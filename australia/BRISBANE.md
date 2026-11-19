# Brisbane and South East Queensland

Load the [Brisbane save](saves/brisbane.save). It runs nine rail services and the Gold Coast G:link.

| Service | Modelled path |
| --- | --- |
| Beenleigh – Ferny Grove | Local stops via the Merivale Bridge and Brisbane CBD |
| Cleveland – Shorncliffe | Via Park Road, the CBD and Northgate |
| Ipswich – Caboolture | Inner-west local stops, then express between Northgate and Petrie |
| Springfield Central – Kippa-Ring | Local stops via Darra, the CBD and Petrie |
| Brisbane Airport – Gold Coast | Through to Varsity Lakes, with an express pattern between Park Road and Beenleigh |
| Doomben | From Roma Street via Eagle Junction |
| Rosewood | Shuttle from Ipswich |
| Sunshine Coast | Representative Nambour and Gympie North services from Roma Street |
| G:link | Helensvale to Broadbeach South, with a linked transfer to heavy rail |

Parallel tracks through Roma Street, Central, Fortitude Valley and Bowen Hills keep the western and southern groups apart. Shared tracks continue to the Merivale Bridge and to the turnouts at Darra, Petrie, Eagle Junction and toward Ferny Grove. The save models the CBD tunnels and the Merivale Bridge level changes. The express patterns share some suburban infrastructure, and yard tracks and crossovers are simplified.

## Sources

- Queensland Department of Transport and Main Roads, Translink static GTFS for 10 March 2021, recovered from the [Hermes project snapshot](https://github.com/DECO3801-Segfault-Coredump/hermes/blob/8338d01347417da7a9e228a6d35f75412879c9ad/assets/hermes/gtfs.zip). The source ZIP has SHA-256 `d616cd7e7fe4bfdffce9b36481b7713475a8154e435de2b0888479c9025260b1`.
- November 2026 OpenStreetMap railway and stop mapping for geometry and newer station locations, including Pimpama and Hope Island. The [Australian rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr) has SHA-256 `5ed852b014bc36577188ec03be2fadee049851f0a3f18cfb07ae147ce6889d68`. [OpenStreetMap contributors, ODbL](https://www.openstreetmap.org/copyright)

The timetable and headways are representative. Coverage ends at Rosewood, Gympie North, Varsity Lakes and Broadbeach South. The build excludes busways, long-distance services and the Cross River Rail network.

## Build and verify

With Python 3, NumPy and Rust/Cargo on PATH, set `AU_GRAPH` to the downloaded Australian rail graph.

```sh
python australia/build_regional.py brisbane --graph "$AU_GRAPH" --output australia/saves/brisbane.save
python australia/validate.py bri australia/saves/brisbane.save
```

The build derives track guides from the pinned graph and the [checked-in corridors](sources/brisbane-corridors.json). The native validator confirms route endpoints, shared tracks, fleet and left-hand running. The browser check covers the CBD, Roma Street and the Gold Coast light rail over OpenFreeMap.

The checked save has **10 running services**, 173 distinct station names and 187 track pieces. The engine reports 24 geometry and placement warnings, principally small heading mismatches and simplified station junctions. Peak-hour passenger demand remains unverified. Save SHA-256 `91dc12f549cff34f4a2cfaa34bfa46c3d61bc090e074e84cadfcf66ee102a34b`.
