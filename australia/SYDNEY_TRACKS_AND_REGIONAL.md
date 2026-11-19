# Sydney track pairs and regional services

Load [Sydney playable save](saves/sydney.save) to play. Load [Sydney blueprint](blueprints/sydney.save) to edit the same tracks, junctions and station platforms as a construction plan. The blueprint has no service lines and includes the engine's construction quote plus a cash buffer. Keep both files if you want to edit one and compare it with the running network.

## What the track data shows

The track study uses a July 2026 OpenStreetMap rail export with named running roads, platforms and tunnel flags, alongside the 18 November 2026 Transport for NSW timetable extract. The track counts below are cross-sections of named running tracks. Counts change within junctions, and goods tracks and yards are outside the passenger counts. See the [reference track model and source notes](https://github.com/mmuschalik/sydney-rail-sim/tree/094ffd3ef501bec896fc98819151733cfb978b9a) and the [Sydney service map](https://github.com/earlybean4/Map-Tube-Sydney/blob/master/maps/Sydney-Rail.png).

| Reference cross-section | Passenger running tracks | Save treatment |
| --- | --- | --- |
| Macdonaldtown–Newtown, Stanmore–Petersham, Ashfield–Croydon and the west side of Strathfield | 6. Up/Down Main, Suburban and Local | Adds the Main for Blue Mountains and Central Coast trains alongside the suburban and local alignments. |
| Homebush–Flemington and Flemington–Lidcombe | 4. Main and Suburban | The Main joins the existing western running pair. The two inner-west pairs continue along this section. Goods roads are omitted. |
| Lidcombe–Auburn and Harris Park–Parramatta | 4. Main and Suburban. A single relief road appears near Clyde | The main and suburban lanes continue towards Parramatta. The relief road is omitted. |
| Westmead–Wentworthville, Doonside–Rooty Hill and the east side of St Marys | 4. Main and Suburban | Separate western paths to St Marys, with the terminal approaches simplified. |
| St Marys–Werrington and Kingswood–Penrith | 2. Up/Down Main | The regional service and T1 share the pair on these sections. |
| Tempe–Wolli Creek, Arncliffe–Banksia and Allawah–Hurstville | 4. Illawarra Main and Local | Separate T4 and South Coast alignments share one pair on the south side of Hurstville. |
| Bardwell Park–Bexley North, Narwee–Riverwood and Padstow–Revesby | 4. East Hills Main and Local | The via-Sydenham T8 variant uses a separate express pair. The Airport variant serves the local platforms. |
| West side of Revesby towards Panania | 2 after the junction | Both T8 variants use the same pair towards East Hills. |

The timetable places T1 and T9 on Central 16 and 18 in normal through running. T2, T3 and T8 use the other surface platform groups in varying directions. The save models four distinct surface suburban platform pairs with simplified connections to the City Circle. T4 serves Sydenham 5–6, drops below the surface on the Illawarra approach, and uses Redfern 11–12, Central 24–25 and Town Hall 4–5. The older CBD Metro and the City Circle service directions are retained. TrainLink's terminal-side platforms at Central are linked for transfers. Some of the game paths join at a platform node where the real turnout is in the station throat.

## Services

- Blue Mountains Line to Lithgow and the Bathurst Bullet to Bathurst.
- South Coast Line to Kiama and Southern Highlands services from Campbelltown to Moss Vale and Goulburn.
- Central Coast & Newcastle Line from Sydney Central to Newcastle Interchange.
- Hunter trains from Newcastle Interchange to Telarah, Dungog and Scone, and six Newcastle Light Rail stops between the interchange and Newcastle Beach.

Intercity stopping patterns and headways are representative. The Newcastle light rail stop locations were snapped to the mapped street tracks. Rail geometry outside the reference simulator's track coverage uses the published Australian game rail graph. The save covers the listed services. Long-distance NSW TrainLink trains beyond these corridors, additional yards, relief tracks and detailed signalling remain outside this revision. [Australian OSM-derived rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr) · [OpenStreetMap attribution and ODbL](https://www.openstreetmap.org/copyright)

## Reproduce and verify

The recipe pins the [CBD geometry save](SYDNEY_GEOMETRY.md) and contains the fitted corridor guides and route choices used by the fork.

```sh
python australia/edit_save.py australia/archive/sydney/sydney-cbd.save australia/saves/sydney.save --recipe australia/sources/sydney-track-and-service-recipe.json
python australia/validate.py syd australia/saves/sydney.save --expanded
python australia/edit_save.py australia/saves/sydney.save australia/blueprints/sydney.save --blueprint --home syd
```

The native game loader checks 28 running services, 367 distinct station names and 461 track pieces. It confirms the four surface suburban Central platforms, the separate T4 underground platforms and the regional turnbacks. The geometry validator reports 167 placement warnings, mostly small heading mismatches at stations. Chromium confirmed the expanded network over the OpenFreeMap basemap in the geometry view. The game engine also reloaded the blueprint and constructed the complete plan with the supplied budget.

- Playable save SHA-256 `cf92eb73dcd5891e4bbde4bea4c39aa3fd434c112f22703a6aa337d8d9ff2ca7`
- Blueprint SHA-256 `a52d1e76151af51ab0e0c26a0cc5f16df8ac75898b5c20a5f9971154a11dc0b4`
