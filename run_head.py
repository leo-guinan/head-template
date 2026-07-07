#!/usr/bin/env python3
"""CLI wrapper for build_spine."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_spine import write_spine  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a head's spine.")
    ap.add_argument("head", nargs="?", default="head.json",
                    help="path to head.json")
    ap.add_argument("--seed", nargs="*", default=None,
                    help="extra seed queries")
    args = ap.parse_args()
    out = write_spine(args.head, args.seed)
    print(f"spine written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
