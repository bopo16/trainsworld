# Sydney Central, City Circle and CBD Metro

Import [sydney-cbd.save](sydney-cbd.save) with **Load file**. This is a geometry revision of the original [Sydney save](sydney.save).

The two suburban Central platforms retain their service assignments and are linked with the Metro platform for transfers. Their southern leads use a simpler alignment through the existing junctions. Both western City Circle approaches follow the bend into the turnout south of Town Hall, as shown by OSM chains 5516 and 6892. The existing eastern leg via Museum, St James and Circular Quay and the route directions through the Circle are preserved.

The downloaded [Australian rail graph](https://data.anita.garden/trainworld/2026-11-18/realgraph/au.rgr) provides the two Metro bores. The model's double-track centre line follows their midpoint through the CBD, including Gadigal, Martin Place and Barangaroo. The Central–Waterloo segment also uses a smoother approximation of the two parallel bores. Actual flyover levels and interlocking remain schematic. Regional and Newcastle services were outside the verified geometry pass. Track data credits and its pinned checksum are in [the Australian city saves report](README.md).

The save was imported in Chromium over live OpenFreeMap tiles. Native validation confirms all 18 services, 239 station names and 310 edges, plus the existing 1,178 rail-car and 90 tram-section fleet. The two pre-existing platform warnings at nodes 70 and 94 remain.

```sh
python australia/sydney_geometry.py australia/sydney.save /tmp/sydney-cbd.save
python australia/validate.py syd /tmp/sydney-cbd.save
```

Revised save SHA-256: `44dad625191ff8599a3b2de96505a8b3e4a5f6f76b5ae51098813aa04ccc87bc`.
