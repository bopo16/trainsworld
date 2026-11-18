#!/usr/bin/env python3
"""Revise the rail and tram geometry of the pinned v0.4 Melbourne save."""

import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "2f941474a9d55ea77cdcb83ead008304227147bc920c0a893039baa30b06543f"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.original.read_bytes()
    if hashlib.sha256(original).hexdigest() != BASE_SHA256:
        parser.error("input must match the Melbourne v0.4 base save")
    raw = gzip.decompress(original)
    payload_start = 8 + struct.unpack_from("<I", raw, 4)[0]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "original.twt2"
        target = Path(directory) / "revised.twt2"
        source.write_bytes(raw[payload_start:])
        subprocess.run(
            ["cargo", "run", "--locked", "--release", "--bin", "melbourne_geometry", "--", source, target],
            cwd=ROOT / "trainworld" / "sim",
            check=True,
        )
        result = gzip.compress(raw[:payload_start] + target.read_bytes(), mtime=0)
    args.output.write_bytes(result)


if __name__ == "__main__":
    main()
