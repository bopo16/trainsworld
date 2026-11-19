# Adelaide rail and trams

Load the [Adelaide save](saves/adelaide.save). It has seven suburban rail services to Gawler Central, Outer Harbor, Grange, Port Dock, Seaford, Flinders and Belair, plus two tram services between Royal Adelaide Hospital and Glenelg, and Botanic Gardens and Entertainment Centre.

Adelaide Railway Station has separate, connected platforms for the northern, Port Adelaide, Seaford and Belair corridors. Outer Harbor and Port Dock share the approach through Alberton, with the fork placed beyond the platform. Grange branches at Woodville. Flinders and Seaford share tracks past Woodlands Park. Belair runs on a separate single track. Tram lines share North Terrace, and the Glenelg route follows the mapped curve onto King William Street. The Goodwood tram bridge passes above both rail alignments.

## Sources

- The Department for Infrastructure and Transport, Government of South Australia, Adelaide Metro GTFS. The [archived weekday feed](https://github.com/gtfsdata/adelaidemetro-gtfs/tree/d2ae39b41d50132865614350d46e288b2cb3b5ad/gtfs) gives the established stopping patterns and tram routes.
- The [November 2026 Adelaide Metro stop extract](https://github.com/cjmuldoon/plotlay-adelaide-frequent-transit/blob/83b8411840eec8d6374406a29630c1d7c893feec/data/tables/stops.csv), SHA-256 `c7fec938ff4d07c533ec6af896be1c8c855e6293efa300a2521364021133cf0e`, supplies station positions and coverage including Port Dock, Flinders and Gawler Central. [Government of South Australia GTFS, CC BY 4.0](https://data.sa.gov.au/data/dataset/4e191c1e-b971-441f-83f7-45e266c41b99)
- Track shapes come from the [Australian rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr), SHA-256 `5ed852b014bc36577188ec03be2fadee049851f0a3f18cfb07ae147ce6889d68`. The short North Terrace tram curve was fitted from its mapped rails. [OpenStreetMap contributors, ODbL](https://www.openstreetmap.org/copyright)

The save uses representative all-stop services and headways. Detailed terminal turnouts and passing arrangements are simplified.

## Build and verify

With Python 3, NumPy and Rust/Cargo on PATH, set `AU_GRAPH` to the downloaded Australian rail graph.

```sh
python australia/build_regional.py adelaide --graph "$AU_GRAPH" --output australia/saves/adelaide.save
python australia/validate.py ade australia/saves/adelaide.save
```

The build uses the [checked-in corridors](sources/adelaide-corridors.json). The native validator checks route endpoints, shared approaches, fleet and left-hand running. The browser check covers the terminal, Port Dock, Goodwood and the North Terrace tram junction over OpenFreeMap.

The checked save has **9 running services**, 120 distinct station names and 130 track pieces. The engine reports eight geometry and placement warnings. Peak-hour passenger demand remains unverified. Save SHA-256 `b1342b6cb41bd46ef2cf437798737e1c364f7077a47afbe981aaa6e4698e3f0e`.
