# Melbourne Loop and tram geometry revision

Import [melbourne-v040-loop-and-trams.save](melbourne-v040-loop-and-trams.save) with **Load file**. This revision starts from the [v0.4 rail and tram save](V040.md) and keeps its 16 rail services and 24 tram routes.

## City Loop and approaches

The four directional City Loop tracks and two double-track surface alignments run side by side around a common bend between Southern Cross and Flinders Street. The Frankston alignment takes the outside slot and the Flinders Street leads continue east on the platform axes. The six river alignments keep their order through the bend. In the Flinders Street platform and immediate lead area, the six modelled alignments had five centre-line crossings in the previous revision and have none in this one. The Altona, Werribee–Sandringham and Williamstown–Sandringham services use the same cross-city tracks and Southern Cross platform where their approaches coincide. The Flemington event tracks keep their separate pair.

The directional platforms at North Melbourne, the Frankston approaches at Richmond and the Clifton Hill approaches at Jolimont have more separation. The Loop services still run through Flinders Street. Native validation checks that Frankston runs through Richmond, Parliament, Melbourne Central, Flagstaff, Southern Cross and Flinders Street before returning to Richmond. The Victorian transport site was blocked during this revision, so the save retains the v0.4 service pattern.

The four northern tubes follow one guide traced from OSM chains 218, 2586, 2427 and 12115, at 12 m centre spacing through Flagstaff, Melbourne Central and Parliament. The Flagstaff approaches fan out in order before Southern Cross. Projected crossings remain on both outer approaches, where the groups fan out to North Melbourne, Jolimont and Richmond. The geometry is diagrammatic. Signals, crossover assignments and track levels require separate infrastructure evidence.

## Trams

Routes 11, 12 and 109 now share the southwest approach and one through platform at St Vincents Plaza before their Victoria Parade and Brunswick Street branches separate. Route 30 keeps a distinct west-facing terminus a short walk away. The two platforms are linked for transfers.

The Errol Street stops sit on straighter sections of Victoria Street and Errol Street. The curves follow the street junctions shown in the published OSM-derived rail graph. The Elizabeth Street terminus has more clearance from the Flinders Street cross street. Tight turns were simplified at several other junctions, including the Bourke–Spencer turnout, the route 70 turn towards Richmond, the Docklands approach and a route 82 turn in Maribyrnong. Swanston Street and the adjoining St Kilda Road corridor now use one shared double-track pair. Sixteen duplicate platform nodes are merged, and the branch paths at Commercial Road, Toorak Road and Sturt Street are retained. The closely spaced Hawthorn Road stops on route 64 were consolidated and the Moreland Road turn on route 6 was refitted. The validator confirms all tram routes run. Peak-hour queuing on the shared pair has not been measured.

## Validate and reproduce

The native validator reloads the save and checks all 40 services, the four Loop groups, Metro Tunnel through-running, tram routes and fleet. Browser inspection used the live OpenFreeMap basemap and the game's geometry view with demand disabled for the visual pass. The published Australian [OSM rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr) is credited in [the v0.4 report](V040.md).

From the repository root with Rust and Cargo on PATH:

```sh
python melbourne/geometry_revision.py melbourne/melbourne-v040-rail-and-trams.save /tmp/melbourne-revised.save
python melbourne/validate_metro.py /tmp/melbourne-revised.save --city-loops --trams --tram-upgrades
```

The revision takes the pinned base save as input. The complete GTFS rebuild and its source requirements are documented in [V040.md](V040.md).

All 40 services run with the existing 1,223 rail-car and 696 tram-section fleet. The native validator reports 16 geometry and placement warnings, compared with 15 in the previous revision and 22 in the base save. The two previous tight-radius warnings on routes 6 and 64 are gone. Remaining warnings include headings on the northern rail approaches and at tram junctions.

Revised save SHA-256: `67c3d0e80fd2c9f9e083f096bcbf7c2965fb1c61bbfdbf1dd2f35f18159dcc8f`.
