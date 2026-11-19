# Melbourne V/Line and construction blueprint

Load [melbourne-v040-vline.save](melbourne-v040-vline.save) to play or [melbourne-v040-blueprint.save](melbourne-v040-blueprint.save) to edit the full network as a construction plan. The blueprint keeps the track, junctions, stations and transfers with no service lines. It includes the engine's construction quote plus extra cash for edits.

This revision starts with the [Melbourne Loop and tram update](LOOP_AND_TRAMS.md) and adds representative V/Line services to Geelong and Waurn Ponds, Warrnambool, Ballarat and Wendouree, Ararat, Bendigo, Echuca, Swan Hill, Seymour, Shepparton, Albury and Bairnsdale. All V/Line services terminate at Southern Cross and avoid the City Loop. Gippsland serves Flinders Street and Richmond on the surface and joins the eastern suburban route at Caulfield. Geelong and Ballarat services share the Regional Rail Link to Deer Park. Warrnambool and Ararat reuse the corresponding trunk routes.

Routes, stops and geometry use a weekday snapshot of the published Transport Victoria V/Line GTFS, selected for 20 November 2024. The save uses representative frequencies and platform approaches. Track layouts beyond the metropolitan approaches are simplified. [V/Line timetable source](https://github.com/vnen0001/Melbourne-GTFS/tree/3b976ae50372ba66ed647691860bef8221973ce5) · [Track and data credits](V040.md)

## Reproduce and verify

```sh
python australia/edit_save.py melbourne/melbourne-v040-loop-and-trams.save melbourne/melbourne-v040-vline.save --recipe melbourne/vline-recipe.json
python melbourne/validate_metro.py melbourne/melbourne-v040-vline.save --city-loops --trams --tram-upgrades --vline
python australia/edit_save.py melbourne/melbourne-v040-vline.save melbourne/melbourne-v040-blueprint.save --blueprint
```

The native game loader checks 51 running services, including all 24 tram routes and 11 V/Line routes. It also checks that V/Line avoids the City Loop. The validator reports 87 placement warnings, mostly small heading mismatches at stations. Chromium inspection used OpenFreeMap in the geometry view. The game engine reloaded the blueprint and constructed the complete plan with the supplied budget.

- Playable save SHA-256 `6a427cafe871f91e57e3a9a7efc601d97d09b85c5c4c08377ca81dba07510e60`
- Blueprint SHA-256 `5c97ec45b50a7b5a328ed110383d2bb80b71335e8d291d36d79da81510764962`
