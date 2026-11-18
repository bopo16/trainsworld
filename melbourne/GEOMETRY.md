# Melbourne metro: geometry cleanup

This report describes the earlier geometry save. The generator has since gained the additional rail and tram changes described in [TRAMS.md](TRAMS.md), so the command below now produces newer geometry rather than the original file's hash.

Import `melbourne-metro-geometry.save` using Trainsworld's **Load a file** flow. It is a separate revision of the save described in [CITY_LOOP.md](CITY_LOOP.md), which retains its original file.

The four City Loop group tracks between Parliament and Flagstaff are now fitted to spaced offsets of one common curve, instead of independently fitted paths. Each service stops once at Flagstaff, rather than twice at closely spaced copies. Eight unnecessary short joints within the four cloned Southern Cross platforms were removed. The generator also merges redundant parallel station paths when they have the same station key and connect the same pair of junctions: this affects Burnley, Blackburn and North Richmond. These station merges deliberately trade some separate platform capacity for a simpler layout; they do not alter one-way tracks. These changes are approximations to improve readability, not surveyed platform geometry.

The model reloads using the game load routine and native service model with **16 running services, 227 distinct station names, 409 edges and 1,223 cars**. All line routes are checked, including one-way Loop routing and through-running at Flinders Street. The generator checks that every Loop service has exactly one Flagstaff stop. Twelve Python tests pass, including tests for platform merging and joint removal. Two full builds produced identical save files. The capacity diagnostic reports no modelled resource above 90% at any of its three demand levels, although it still predicts holds. These are model checks, not proof of real-world capacity or a substitute for a longer in-game run.

The geometry validator reports **nine warnings**, down from 26: four platform/junction, four node-heading and one platform/joint. They are at Burnley, Southern Cross, North Melbourne, Newmarket and Laverton. The images provided by the user informed these changes and a plotted comparison of the generated geometry was inspected; the new save itself has not been visually verified in the game. Some track crossings and changing alignments remain, particularly on the approaches to Southern Cross, Flinders Street and Richmond and on multitrack sections outside the Parliament–Flagstaff segment. The northern Loop direction differs from the others, and tracks and platforms are intentionally schematic. Further work should inspect those areas in-game and adjust corridor-wide track ordering and junction geometry without losing connectivity or capacity.

Rebuild using the pinned inputs, dependencies and command in [CITY_LOOP.md](CITY_LOOP.md). The current `--simplified --city-loops` generator automatically applies this cleanup. To validate an existing output:

```sh
python -m unittest discover -s melbourne -v
python melbourne/validate_metro.py /path/to/build/mel_real.save --city-loops
```

Save SHA-256: `caddfe3b3ce2ef7513dc49346246ee5b1ae928c2b18a4218f1271bf76c665e70`.
