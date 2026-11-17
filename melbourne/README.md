# Melbourne corridor proof of concept

This is a deliberately limited experiment, not a complete or operationally accurate 2026 network. It builds an importable Trainsworld game container containing the Frankston stopping pattern from Flinders Street to Caulfield via Richmond, South Yarra, Hawksburn, Toorak, Armadale and Malvern. The generated file is `melbourne-corridor.save`.

## Sources and reproducibility

* [Transport Victoria GTFS Schedule](https://opendata.transport.vic.gov.au/dataset/gtfs-schedule), CC BY 4.0, Department of Transport and Planning, Victoria. The build used the outer zip dated 12 November 2026, SHA-256 `424be6c94c328b22ca25b5ce90273acd945dcfd3dec562bb13dfd2ade2b40990`, and Wednesday 18 November 2026. It extracts only branch `2/google_transit.zip` (metropolitan trains), excludes replacement-bus routes and trips with R-Bus stops, and requires consecutive stops. The feed is a rolling release; the same URL will change. Keep this exact input archive for byte-for-byte reproduction. The feed's coverage and exceptions must include the requested date.
* The 13 November 2026 game data release provides [Melbourne's city pack](https://data.anita.garden/trainworld/2026-11-13/mel.json), SHA-256 `7bf3622945cc3e381bf077c9a806df14637204669757243dc6e9b7104d9089c2`, and the [Australian real-rail graph](https://data.anita.garden/trainworld/2026-11-13/realgraph/au.rgr), SHA-256 `a6110b317b28a198d9deda78eec83f7ab4fbd31bcf00743b3a7b82f922aee28a`. The graph is the game's processed noritetsu/OpenStreetMap rail data, not a fresh survey. © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). Its exact underlying OSM extraction date and completeness were not independently established.
* [Victoria's Big Build](https://bigbuild.vic.gov.au/projects/metro-tunnel/about/benefits) confirms the February 2026 Metro Tunnel configuration: Cranbourne, Pakenham and Sunbury services use the tunnel; they are not assigned to the Richmond corridor in this prototype.

Requires Python 3.10+, `numpy`, `pandas`, `scipy`, `shapely` 2+, Rust/Cargo and network access for Cargo dependencies. Tested with Python 3.12, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0, Shapely 2.2.0 and Rust 1.100.0. No WASM build or worldwide data download is required. The published GTFS outer archive is roughly 296 MB; only metropolitan rail is extracted. The Australian graph is ~743 KB.

From the repository root, download the GTFS zip from the official page and the two pinned game data files linked above, then run:

```sh
python -m pip install numpy pandas scipy 'shapely>=2'
python melbourne/generate.py --gtfs /path/to/gtfs.zip --date 2026-11-18 \
  --pack /path/to/mel.json --graph /path/to/au.rgr --out /path/to/new-empty-build
python -m unittest discover -s melbourne -v
python melbourne/validate.py /path/to/new-empty-build/mel_real.save
```

The generator stages the specified pack and graph under ignored `trainworld/data/packs/`; it refuses to overwrite different existing inputs. It refuses to overwrite an existing output save, to use a non-Wednesday or non-2026 date, to bridge omitted stations, to run with no matching service in either direction, or to fall back to a straight/GTFS-only hop when graph routing fails. It temporarily filters GTFS shape candidates to the outbound direction, avoiding accidentally routing the first hop along the inbound City Loop. The upstream generator may still trace a graph route approximately and snap station nodes onto track. `--out` retains intermediates for inspection. Keep the licensed source archive separately; it is not included in this repository.

## How the existing generator works

`pipeline/realnet.py` parses GTFS parent stations, service calendars and stop times; groups stopping patterns, computes high/medium/low trains per hour and hop times; matches shapes; and routes each hop on the OSM-derived graph. `sim/src/bin/realsave.rs` makes station nodes and constructed double-track edges, traces the routes, creates a service, derives whole train allocations and writes the native track payload. `realnet.py gamesave` wraps that payload with the gzip `TWG1` game header, funds and fleet. This prototype reuses all three rather than writing a save encoder. `realcorridors.py` plus `realsave --shared` is the better starting point for multiple lines, shared pairs, junctions and OSM levels, but was not used for this one-line test. The non-shared builder gives each line a separate pair and marks imported crossings separated; those are assumptions, not a representation of Melbourne's actual junctions.

## Validation results and limitations

Two independent runs with the pinned inputs generated the same SHA-256 save `426d3512acbb8c94992fa2ec367b487920eaf0b356dfbed92adb047f6667a0f6`. The selected feed has 218 complete or clipped all-stations trips, including inbound trips clipped at Richmond. All 7 of 7 hops routed over the published graph; the upstream tracer reported all 7 traced, worst fit 4.0 m. Station nodes are 7.8–21.2 m from their GTFS parent-station coordinates. Its track validator reported no issues; it set 8 station nodes, 7 constructed double-track edges and 1 running line.

`validate.py` checks the gzip container, header, world ID and fleet, then uses the game's actual Rust decoder and `TrackWorld` to check left-hand running, the eight named stops, connected built edges, a running service and sufficient fleet. It reloaded 5/4/1 trains at the three demand levels, with 35 cars in the header. Four selection tests pass. This establishes native-model loading and service derivation, **not a verified browser import or visual play test**: the available cloud browser reported no WebGL2. Load the save through the game's Load a file flow on a WebGL2-capable browser to verify UI compatibility.

Material compromises:

* The game line runs in both directions between artificial terminals. On the selected day, most inbound Frankston trains go Richmond → Parliament → Melbourne Central → Flagstaff → Southern Cross → Flinders Street. The prototype omits that Loop and therefore **incorrectly returns directly from Richmond to Flinders Street**; the upstream converter mirrors the outbound hop time. This is a known operational approximation, not a real inbound service. Caulfield is also an artificial turnback. Adding the Loop and modelling directional services is the highest-priority next step.
* Only the selected all-stations pattern is counted; express/short-turn and replacement-bus trips are excluded, and other lines, track pairs, junctions, crossovers and platforms are absent. The game line is one double-track pair, not a survey of all physical tracks. Station locations are snapped to the selected track. All edges use one generated level; no verified grade separation or track assignment is implied.
* GTFS has no reliable consist allocation in this pipeline. The code uses **seven 20 m game cars (140 m)** as an explicit unverified approximation, not a claim about individual real train formations. The model uses aggregate directional frequencies, not an actual timetable. Requested high/medium/low rates were 7.5/6/0.83 trains per hour per direction; whole-train allocation and the short artificial turnback settle to approximately 9.06/7.25/1.81. Upstream reports 18.0 minutes GTFS vs 13.56 minutes simulated outbound (about 25% faster). These operational discrepancies require calibration.
* GTFS data can include disruptions and is only valid for its stated calendar; no claim is made that this snapshot represents every day in 2026. The pack, graph, train length and service choices need review before broader use.

## Next stage

Add the complete City Loop and directional Frankston services, using the current feed's calendar, platform/parent relationships and route shapes. Verify the actual track pairs, crossover and turnback connections against OSM and authoritative rail infrastructure data. Run `realcorridors.py`/`realsave --shared`, inspect off-graph hops, station snaps, levels and dropped services, then add Metro Tunnel and interchange services as a separate connected stage. Validate each direction's path, frequencies, platform and fleet assumptions, followed by a real browser import and an unpaused simulation test before expanding line by line across metropolitan Melbourne.
