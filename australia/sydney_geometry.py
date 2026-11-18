#!/usr/bin/env python3
"""Revise the Central and Metro geometry of the pinned Sydney save."""

import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "57151aabbb0ab3cbfc47e3b4c03b5518f33af7ea47a5caa5458da4beb0773e11"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.original.read_bytes()
    if hashlib.sha256(original).hexdigest() != BASE_SHA256:
        parser.error("input must match the Sydney base save")
    raw = gzip.decompress(original)
    payload_start = 8 + struct.unpack_from("<I", raw, 4)[0]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "original.twt2"
        target = Path(directory) / "revised.twt2"
        source.write_bytes(raw[payload_start:])
        subprocess.run(
            ["cargo", "run", "--locked", "--release", "--bin", "sydney_geometry", "--", source, target],
            cwd=ROOT / "trainworld" / "sim",
            check=True,
        )
        result = gzip.compress(raw[:payload_start] + target.read_bytes(), mtime=0)
    args.output.write_bytes(result)


if __name__ == "__main__":
    main()
