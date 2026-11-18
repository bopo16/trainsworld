# Melbourne Loop and tram geometry revision

Import [melbourne-v040-loop-and-trams.save](melbourne-v040-loop-and-trams.save) with **Load file**. This revision starts from the [v0.4 rail and tram save](V040.md) and keeps its 16 rail services and 24 tram routes.

## City Loop and approaches

The four directional City Loop tracks and two double-track surface alignments run side by side around a common bend between Southern Cross and Flinders Street. All six alignments keep their order through the bend and the platform groups. Their centre lines intersected in four pairs in the base save and in zero pairs in the revision. The Altona, Werribee–Sandringham and Williamstown–Sandringham services use the same cross-city tracks and Southern Cross platform where their approaches coincide. The Flemington event tracks keep their separate pair.

The directional platforms at North Melbourne, the Frankston approaches at Richmond and the Clifton Hill approaches at Jolimont have more separation. The Loop services still run through Flinders Street. Native validation checks that Frankston runs through Richmond, Parliament, Melbourne Central, Flagstaff, Southern Cross and Flinders Street before returning to Richmond. The Victorian transport site was blocked during this revision, so the save retains the v0.4 service pattern.

Two visible intersections remain where the Northern Group approach crosses the Burnley and Clifton Hill alignments north of Southern Cross. The river section is diagrammatic. Signals, crossover assignments and track levels require separate infrastructure evidence.

## Trams

Routes 11, 12 and 109 now share the southwest approach and one through platform at St Vincents Plaza before their Victoria Parade and Brunswick Street branches separate. Route 30 keeps a distinct west-facing terminus a short walk away. The two platforms are linked for transfers.

The Errol Street stops sit on straighter sections of Victoria Street and Errol Street. The curves follow the street junctions shown in the published OSM-derived rail graph. The Elizabeth Street terminus has more clearance from the Flinders Street cross street. Tight turns were simplified at several other junctions, including the Bourke–Spencer turnout, the route 70 turn towards Richmond, the Docklands approach and a route 82 turn in Maribyrnong. The existing St Kilda Road pairs retain shared tracks within each pair and preserve the branch towards Sturt Street.

## Validate and reproduce

The native validator reloads the save and checks all 40 services, the four Loop groups, Metro Tunnel through-running, tram routes and fleet. Browser inspection used the live OpenFreeMap basemap and the game's geometry view with demand disabled for the visual pass. The published Australian [OSM rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr) is credited in [the v0.4 report](V040.md).

From the repository root with Rust and Cargo on PATH:

```sh
python melbourne/geometry_revision.py melbourne/melbourne-v040-rail-and-trams.save /tmp/melbourne-revised.save
python melbourne/validate_metro.py /tmp/melbourne-revised.save --city-loops --trams --tram-upgrades
```

The revision takes the pinned base save as input. The complete GTFS rebuild and its source requirements are documented in [V040.md](V040.md).

All 40 services run with the existing 1,223 rail-car and 696 tram-section fleet. The native validator reports 15 geometry and placement warnings, down from 22 in the base save. Remaining warnings include approaches around North Melbourne and Southern Cross, a St Vincents Plaza turnout heading, and tight turns on routes 6 and 64.

Revised save SHA-256: `2dd199fb8a9b660e4a91025a65ca1761f50e529aaba4d786a90eedd9b90885a2`.
