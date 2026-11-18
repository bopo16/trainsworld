#!/usr/bin/env python3
"""Apply the Northeast approach revision to the original Perth save."""

import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = "02da21fc6f242c4d994a16724b64475037c121aaa857001c8e98a325238fdbce"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.original.read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        parser.error("input must be the original Perth save from the Australian city maps branch")
    raw = gzip.decompress(original)
    payload_start = 8 + struct.unpack_from("<I", raw, 4)[0]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "original.twt2"
        target = Path(directory) / "revised.twt2"
        source.write_bytes(raw[payload_start:])
        subprocess.run(
            ["cargo", "run", "--locked", "--release", "--bin", "perth_approach", "--", source, target],
            cwd=ROOT / "trainworld" / "sim",
            check=True,
        )
        revised = gzip.compress(raw[:payload_start] + target.read_bytes(), mtime=0)
    args.output.write_bytes(revised)


if __name__ == "__main__":
    main()
