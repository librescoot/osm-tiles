#!/usr/bin/env python3
"""Parity test for build_places.normalize().

Runs every case in normalize_cases.txt through normalize() and asserts the
output matches. The same fixtures are referenced from scootui-qt's matching
C++ implementation — keep them in sync.

Run:
    python3 tests/test_normalize.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_places import normalize


def parse_cases(path):
    cases = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip("\n")
        if not line or line.lstrip().startswith("#"):
            continue
        if "\t" not in line:
            sys.exit(f"{path}:{lineno}: missing tab separator: {line!r}")
        inp, expected = line.split("\t", 1)
        cases.append((lineno, inp, expected))
    return cases


def main():
    fixtures = Path(__file__).resolve().parent / "normalize_cases.txt"
    cases = parse_cases(fixtures)
    fails = []
    for lineno, inp, expected in cases:
        got = normalize(inp)
        if got != expected:
            fails.append((lineno, inp, expected, got))
    if fails:
        for lineno, inp, expected, got in fails:
            print(f"FAIL line {lineno}: normalize({inp!r}) = {got!r}, expected {expected!r}")
        sys.exit(1)
    print(f"OK: {len(cases)} cases passed")


if __name__ == "__main__":
    main()
