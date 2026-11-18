# Melbourne metro: directional City Loop

This report describes the earlier `melbourne-metro-city-loop.save`. The generator now also applies the geometry cleanup described in [GEOMETRY.md](GEOMETRY.md), so the rebuild command below produces the newer geometry save instead of the hash at the end of this document.

Import `melbourne-metro-city-loop.save` with Trainsworld's **Load a file** command. This is an alternative to the earlier saves. It prioritises legibility and through-running over a complete timetable or a surveyed track layout.

## Network and operations

The four City Loop groups have separate, spaced, one-way tracks and separate through platforms at Flinders Street. Nine representative services use the game's one-way balloon routes: they approach the Loop from their suburban branch, pass through Flinders Street without reversing, and return to the same branch. Frankston uses the Caulfield Group Loop, including Richmond, Parliament, Melbourne Central, Flagstaff, Southern Cross and Flinders Street. Other branch services within each group share that group's track. These simple balloons do **not** reproduce all actual train workings, changes of destination, direction changes or timetables.

The two cross-city services are Werribee–Sandringham and Williamstown–Sandringham, continuing through Flinders Street; the Altona/Laverton branch remains a separate short-turn. The two Metro Tunnel services continue to link Sunbury with Cranbourne and Pakenham. Service patterns and frequencies are aggregated; cross-city frequencies are scaled to fit the selected Sandringham service. Stony Point remains single track. Showgrounds–Flemington Racecourse infrastructure remains present, but the selected event service terminates at Showgrounds. V/Line and trams are not modelled.

Saved groups are Burnley Group, Clifton Hill Group, Northern Group, Caulfield Group, Cross-City Group, Metro Tunnel and Special Events. The first four reflect the traditional Loop group names; the others are practical browsing labels, not claims of formal PTV group names. Line letters are project-defined game symbols. The builder uses 31 two-pair and two three-or-more-pair corridor pieces before the separate Loop tracks are added. Track counts and offsets are chosen for the game and are not an audit of actual infrastructure.

Victoria's Big Build states that [Frankston trains returned to the City Loop in February 2026](https://bigbuild.vic.gov.au/projects/metro-tunnel/about/overview), and its [passenger guide](https://bigbuild.vic.gov.au/library/metro-tunnel/get-ready-to-ride) describes Frankston's Loop route. The [Metro training material](https://ds12k1658w1f2.cloudfront.net/wp-content/uploads/2025/02/TFPC-3.2-Participant-Workbook-Renewal-v6.0.pdf) describes the four named Loop groups. In the input GTFS, consecutive trips with the same vehicle block include examples of Werribee/Williamstown–Sandringham, Mernda–Hurstbridge and Craigieburn–Upfield workings. These examples indicate trains can continue as a different line; they do not establish that every train does so. The Loop balloons here intentionally return to their own branches rather than simulating those interlinings.

## Validation and limitations

The game load routine, decoder and native service model reload all **16 services as running**, with **227 distinct station names**, 447 edges and 1,223 fleet cars. The validator checks every path is built and continuous, every service has trains, the four Loop groups use distinct directional track and Flinders platforms, the nine Loop services do not reverse at Flinders, and Frankston's Loop stop order. It also checks the cross-city through services and Metro Tunnel. The capacity diagnostic found no modelled resource above 90% utilisation at any of its three demand levels; it nevertheless predicts some holds. Nine Python tests pass and two independent builds produced identical save hashes.

The game geometry validator reports **26 placement warnings**: 17 platform joints, five platform junctions and four node-heading warnings. These do not prevent the native model from running, but could affect appearance or operation and need inspection in the game. This version has not been visually checked in a WebGL2-capable browser. Inferred tracks and junctions are approximations, one shared-corridor piece uses GTFS geometry when OSM routing fails, and cloned tunnel levels are simplified for game geometry; Flinders Street may be shown underground even though its real platforms are at surface level. Frequencies, platforms, signals, train lengths and stopping patterns are approximations, and the capacity diagnostic is not a real-world signalling simulation. See [METRO.md](METRO.md) for data provenance, train and platform length assumptions, and further limitations.

The next stage is to inspect the Loop and warned junctions in-game, refine platform levels and spacing, then investigate modelling the observed cross-branch vehicle workings without compromising legibility. Station-by-station platform lengths and operating patterns also need verification before adding trams or regional services.

## Rebuild

Use the dependencies and pinned GTFS, Melbourne pack and Australian OSM graph inputs documented in [METRO.md](METRO.md). The GTFS archive is a rolling feed; the exact archive identified there is needed for reproduction. From the repository root:

```sh
python melbourne/metro_network.py --simplified --city-loops --gtfs /path/to/gtfs.zip \
  --date 2026-11-18 --event-date 2026-11-21 --pack /path/to/mel.json \
  --graph /path/to/au.rgr --out /path/to/new-build-directory
python -m unittest discover -s melbourne -v
python melbourne/validate_metro.py /path/to/new-build-directory/mel_real.save --city-loops
```

The generator validates the output automatically and refuses to overwrite an existing save. No worldwide data regeneration is needed. Save SHA-256: `24fe9656ac63bea0700a1e9b331604019666fcdc6ab0f607f15d1a8352c49b63`.
