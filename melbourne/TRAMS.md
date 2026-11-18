# Melbourne metropolitan rail and trams

This describes the earlier save. For the 0.4.0 update and revised OSM tram geometry, see [V040.md](V040.md); the current generator requires an additional `--tram-graph` input and produces the newer save instead of the hash below.

Import `melbourne-rail-and-trams.save` using Trainsworld's **Load a file** command. The previous rail-only saves remain available. This revision includes the 16 simplified metropolitan rail services and all 24 numbered tram routes active on 18 November 2026: 1, 3, 5, 6, 11, 12, 16, 19, 30, 35, 48, 57, 58, 59, 64, 67, 70, 72, 75, 78, 82, 86, 96 and 109.

## Rail geometry

The four directional City Loop groups now use spaced, parallel curves between Southern Cross and Flinders Street as well as between Flagstaff and Parliament. Their platforms have been moved to suit the diagram. The Flemington event service previously shared several actual *game edges* with the Werribee and Williamstown services, accounting for the superimposed colours in the supplied screenshots. It now has separate, offset track for readability, including a connection from Showgrounds to the unserved Flemington Racecourse extension. This is a diagrammatic capacity and layout approximation, not a claim that the real event route has its own full-length tracks. Werribee and Williamstown services still share track where their modelled paths coincide.

Some crossings and alignment changes remain, notably on approaches to the CBD and Richmond, and additional work is needed to make all multitrack corridors parallel. The new save has been checked against plotted model geometry and the user's screenshots, but has not been visually inspected in the game itself. See [GEOMETRY.md](GEOMETRY.md) and [CITY_LOOP.md](CITY_LOOP.md) for the previous revisions and their assumptions.

## Tram data and modelling

The tram inputs come from the metropolitan tram part (`3/google_transit.zip`) of the same pinned [Transport Victoria GTFS archive](https://opendata.transport.vic.gov.au/dataset/gtfs-schedule) described in [METRO.md](METRO.md). Service calendars, stops, route numbers, representative trips and GTFS shapes are taken from the selected weekday. One long representative trip is used per route; short turns and other variants are merged into approximate hourly rates. Opposite-direction platforms with the same GTFS stop name are represented as one location. The City Circle is modelled as a one-way continuous loop; the selected feed has one direction of service that day. Its selected weekday timetable has no trips in the model's high-demand time windows, so it does not run at the save's initial 07:00 clock time, but it has daytime service.

Track follows GTFS shape geometry and shared stop-to-stop hops are combined between routes; it has **not** been snapped to a road network or independently audited against OSM tram tracks. Nine hops whose shapes could not be used have straight-line geometry. There are 830 distinct named tram stops in the input model. All trams use the game's dedicated off-street **tram** track type, green `#009B3A`, a Yarra Trams group, two 20 m game sections and 40 m platforms. These lengths are a uniform approximation, not a fleet-by-fleet survey; the cars are game sections rather than literal real-world carriages. Actual street-running versus reserved track, signals, infrastructure, stop locations, exact schedules and vehicle allocations need further research.

To accommodate the modelled frequencies, 17 heavily used Swanston Street corridor pieces use two track pairs and a fixed assignment of route groups. This is an intentional game-capacity approximation and should not be read as a survey of actual street tracks. Other routes still share track where their selected stop sequences match. Two directions' frequencies are averaged; reverse running times are approximated from the selected trip. The game derives its own operating times and allocates whole trains; it does not reproduce individual GTFS departures. V/Line and buses are not added.

## Validation and remaining issues

The game's native loader, decoder and service model reload **40 services as running**, including all 24 expected tram numbers. Checks cover connected built paths, tram track family and green colour, a continuous City Circle loop, platform and vehicle lengths, separate tram and rail fleet allocations, shared tram edges, separation of the Flemington event path from cross-city paths, City Loop through-running and Metro Tunnel services. The save has **1,057 distinct station/stop names**, 1,365 edges, 1,223 rail cars and 680 tram sections. Thirteen Python tests pass; two builds with the pinned data produced identical output.

The game's placement validator reports **28 warnings**: 11 small-radius geometry warnings, five node headings, one one-sided node, seven platform joints, two platform junctions and two platform/station warnings. Some are on the City Circle's shared Docklands terminal and some on tram street corners; the remainder include previously identified rail junctions. All services run in the native model, but the warnings and actual appearance need in-game inspection. The capacity diagnostic has **one terminus over 90%** in high and medium demand, at Waterfront City where routes 35, 70 and 86 meet. The model predicts holds there and elsewhere; its results do not establish real-world capacity or guarantee a problem-free long simulation.

## Rebuild

Use the exact GTFS archive, Melbourne pack and Australian graph inputs and dependencies documented in [METRO.md](METRO.md). No worldwide data regeneration is needed. The tram feed's full stop-times file is temporarily extracted into the build directory, which needs sufficient disk space.

```sh
python melbourne/metro_network.py --simplified --city-loops --trams \
  --gtfs /path/to/gtfs.zip --date 2026-11-18 --event-date 2026-11-21 \
  --pack /path/to/mel.json --graph /path/to/au.rgr --out /path/to/new-build-directory
python -m unittest discover -s melbourne -v
python melbourne/validate_metro.py /path/to/new-build-directory/mel_real.save --city-loops --trams
```

The generator validates its save before returning success. Save SHA-256: `c03f7254921cdb125c495a93f85ad7ec3529dae4d6efde6b206aad49e53596d5`.
