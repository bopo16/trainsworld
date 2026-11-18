# Melbourne metropolitan network: simpler layout

`melbourne-metro-simplified.save` is a separate, simplified alternative to `melbourne-metro.save`; the earlier save remains available. Load it using Trainsworld's **Load a file** flow. It preserves the timetable station coverage and the main metropolitan branches, City Loop and Metro Tunnel, while favouring an understandable network over every real stopping pattern.

## What changed

* Consolidates 39 input GTFS patterns into 18 pre-Tunnel patterns and then joins the Tunnel halves into **17 game services**, down from 38 in the earlier save. Frequencies from merged patterns are assigned to the retained pattern, so express and short-turn service rates become approximate all-stations or representative routes. Werribee's Altona/Laverton branch remains a separate service. Some services use a direct approach where the real timetable includes City Loop variations; the Loop is retained on other services. All 226 unique GTFS station keys represented in the earlier input remain covered somewhere; Flemington Racecourse is added from OSM as before.
* Uses **seven saved line groups**: Blue · Burnley, Red · Clifton Hill, Yellow · Northern, Green · Frankston, Pink · Cross-city, Light blue · Metro Tunnel and Special events. These are project-defined browsing groups, not official route-number designations. Line colours come from GTFS.
* Selects GTFS shapes only when stops appear in order and adjacent hops do not make unreasonable detours, instead of selecting a shape purely by proximity. The Cranbourne and Pakenham shapes are aligned along their shared Town Hall–Dandenong section before the shared-corridor builder runs. The Town Hall platform representations are merged for through-running, as in the prior version.
* The shared-corridor builder is tuned to favour shared track; it still places adjacent double-track pairs where its capacity and OSM geometry rules call for them (the game's quad-track representation). The generator reports seven two-pair pieces, and no pieces of three or more pairs, compared with 58 and seven respectively in the previous build. This is a readability trade-off, not a claim that every real track pair is represented. A capacity diagnostic reported one terminus resource over 90% at the high-demand level; the rest were below that threshold, so the busiest part of the network may still queue.
* Uses **single track for all nine Stony Point edges**, with no invented passing loop. Infrastructure Victoria describes the [Frankston–Stony Point line as single track](https://assets.infrastructurevictoria.com.au/assets/Resources/Raylink_Consulting_Frankston-Stony_Point_Rail_Corridor_Suitability_for_Container_Freight_to_the_Proposed_Ha.pdf). No additional one-way platforms or passing-loop upgrades are invented. As before, the graph-routed extension from Showgrounds to Flemington Racecourse has no service in the selected event timetable.

## Validation and limits

The game decoder and native simulation reload all **17 services as running**, checks each path is continuous and built, confirms the seven saved line groups, the Stony Point single-track edges, City Loop and both Metro Tunnel routes, and confirms sufficient fleet. **227 distinct station names** are present, including Flemington Racecourse. The model has **343 edges**, down from 517; six track-placement warnings remain (five platform/junction and one platform/joint) versus 25 in the previous build. Ordered shapes were found for all 18 pre-Tunnel patterns; one shared-corridor piece falls back from the OSM graph to a GTFS shape, down from 13. The track validator found no curve-radius errors in this build. Nine Python tests pass.

The geographic comparison was made against generated geometry, not a screenshot in the game. This save has not been visually tested in a WebGL2-capable browser. The Loop still uses bidirectional game services as an approximation; the selected GTFS day and event service are not exact real-life operating schedules. The native model's summed one-way journey times were about 16% shorter than the selected GTFS patterns, and the shared-corridor builder reduced seven high-demand frequencies by about 3.6% to fit junction constraints. Fleet, platform lengths, signals, shared-track capacity, levels and passing facilities remain simplified. See `METRO.md` for source provenance, length assumptions and the previous version's limitations.

## Rebuild

Use the dependencies and pinned input downloads documented in `METRO.md`. From the repository root:

```sh
python melbourne/metro_network.py --simplified --gtfs /path/to/gtfs.zip \
  --date 2026-11-18 --event-date 2026-11-21 --pack /path/to/mel.json \
  --graph /path/to/au.rgr --out /path/to/new-build-directory
python -m unittest discover -s melbourne -v
python melbourne/validate_metro.py /path/to/new-build-directory/mel_real.save
```

The official GTFS feed is rolling, so keep the exact input archive identified in `METRO.md` to reproduce the save. SHA-256 of this save: `0af7310a002b4e613560f0e4cdff753ba3412cc266ce30a19e7c2637ba95d9f5`.
