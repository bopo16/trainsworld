# Perth Station northeast approach

Import [perth.save](saves/perth.save) through **Load file**. Airport, Ellenbrook, and Fremantle–Midland use the northern pair through McIver and Claisebrook. Armadale and Thornlie–Cockburn use the southern pair. The two platform pairs are linked at McIver and Claisebrook for passenger transfers.

The original save merged those services onto one pair through the stations, then placed several separate game edges on nearly the same geometry. This revision separates the approaches from Perth to the east side of Claisebrook and removes an overlapping duplicate toward East Perth. It also extends the track carrying the Claisebrook and East Perth platforms past the old joints. The grouping represents the parallel corridor in the game and leaves the detailed real-world crossover and platform assignments open.

The comparison used the [18 November 2026 Australian rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr), SHA-256 `5ed852b014bc36577188ec03be2fadee049851f0a3f18cfb07ae147ce6889d68`. It is derived from [OpenStreetMap](https://www.openstreetmap.org/copyright) under ODbL. The nearest distance between the modelled Armadale and Fremantle–Midland approach centre lines increased from zero to about 13.6 m. This is spacing between double-track pairs in the game. The graph establishes geographic alignment and visible rail connections. Signal diagrams or infrastructure plans would be needed to verify operational crossovers and precise platform assignments. The PTA and Track and Signal sites were blocked by the cloud proxy during this check.

The game import and geometry were checked in Chromium with the live OpenFreeMap basemap and published Perth city data. Chromium rejected the managed proxy certificate. The browser check relayed only OpenFreeMap requests through Node 24 with `NODE_USE_ENV_PROXY=1`, using the environment's trusted CA and preserving TLS verification. The game intentionally hides OpenFreeMap's railway layers, so the published rail graph was also plotted separately for comparison.

All six services pass the native validator with 85 distinct station names and the same 430-car fleet requirement. One existing platform/junction warning remains outside the edited approach. The previous save had three warnings.

## Reproduce

From the repository root, with Rust and Cargo on PATH:

```sh
git show a8dadf55d3a1813550fc15c8d29c3ca99fd810ba:australia/perth.save > /tmp/perth-original.save
python australia/perth_geometry.py /tmp/perth-original.save /tmp/perth-revised.save
python australia/validate.py per /tmp/perth-revised.save
```

The revision script operates on the pinned original save, preserving its game header. The full GTFS-based builder remains the workflow for regenerating the original network. The revised save SHA-256 is `59fa645f007bf89217d65ab03d999ef9e2e544f705fe225460e8055a04401ff3`.

## Bayswater Airport approach

The Airport line now uses the southern Bayswater platform pair and stays south through the junctions where the Ellenbrook and Midland routes turn away. The two Bayswater platform pairs are linked. The Airport line rejoins the other services west of Bayswater and keeps its original stops and left-hand running. All six services run with the same fleet requirement, and the native validator still reports one unrelated platform/junction warning.
The departure east of Bayswater follows a single curve fitted to the original two tangents, removing the short S-bend from both track pairs.

To reproduce the current Perth save, apply the Bayswater revision to the approach save made above:

```sh
python australia/perth_geometry.py --bayswater /tmp/perth-revised.save /tmp/perth-bayswater.save
python australia/validate.py per /tmp/perth-bayswater.save
```

The current save SHA-256 is `d660a23d27bc6cd3e2345ee9e43c0d0e39b52e0d6db7884a57b21588913d3da1`.
