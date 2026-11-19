#!/usr/bin/env python3
"""Apply a real-network recipe or make a construction-only copy of a game save."""

import argparse
import gzip
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recipe", type=Path)
    mode.add_argument("--blueprint", action="store_true")
    parser.add_argument("--home", help="map zone to open on import (for example mel or syd)")
    args = parser.parse_args()
    original = args.input.read_bytes()
    if args.recipe:
        expected = json.loads(args.recipe.read_text(encoding="utf-8"))["base_sha256"]
        if hashlib.sha256(original).hexdigest() != expected:
            parser.error("the input save does not match this recipe's base revision")
    raw = gzip.decompress(original)
    if raw[:4] != b"TWG1":
        parser.error("input must be a Trainworld save")
    size = struct.unpack_from("<I", raw, 4)[0]
    header = json.loads(raw[8:8 + size])
    if args.home:
        header["home"] = args.home

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "input.twt2"
        target = Path(directory) / "output.twt2"
        source.write_bytes(raw[8 + size:])
        recipe = "--blueprint" if args.blueprint else args.recipe.resolve()
        amounts = subprocess.check_output(
            ["cargo", "run", "--locked", "--release", "--features", "demand",
             "--bin", "edit_real_save", "--", source, target, recipe],
            cwd=ROOT / "trainworld/sim",
            text=True,
        )
        if args.blueprint:
            # Keep a construction budget with room for player edits.
            header["cash"] += float(amounts) * 1.20
        else:
            rail, tram = map(int, amounts.split())
            header["fleet"] = max(header.get("fleet", 0), rail)
            header["fleetTram"] = max(header.get("fleetTram", 0), tram)
        encoded = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode()
        args.output.write_bytes(gzip.compress(b"TWG1" + struct.pack("<I", len(encoded)) + encoded
                                            + target.read_bytes(), mtime=0))


if __name__ == "__main__":
    main()
