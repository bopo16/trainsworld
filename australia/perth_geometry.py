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
APPROACH_SHA256 = "59fa645f007bf89217d65ab03d999ef9e2e544f705fe225460e8055a04401ff3"
ORIGINAL_SHA256 = "02da21fc6f242c4d994a16724b64475037c121aaa857001c8e98a325238fdbce"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bayswater", action="store_true", help="revise Bayswater on the northeast approach save")
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.original.read_bytes()
    expected = APPROACH_SHA256 if args.bayswater else ORIGINAL_SHA256
    if hashlib.sha256(original).hexdigest() != expected:
        parser.error("input does not match the base save for this revision")
    tool = "perth_bayswater" if args.bayswater else "perth_approach"
    raw = gzip.decompress(original)
    payload_start = 8 + struct.unpack_from("<I", raw, 4)[0]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "original.twt2"
        target = Path(directory) / "revised.twt2"
        source.write_bytes(raw[payload_start:])
        subprocess.run(
            ["cargo", "run", "--locked", "--release", "--bin", tool, "--", source, target],
            cwd=ROOT / "trainworld" / "sim",
            check=True,
        )
        revised = gzip.compress(raw[:payload_start] + target.read_bytes(), mtime=0)
    args.output.write_bytes(revised)


if __name__ == "__main__":
    main()
