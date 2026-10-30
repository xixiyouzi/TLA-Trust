#!/usr/bin/env python3
"""Compare run_bench.py results.json against benchmark/manifest.csv."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    manifest = ROOT / "benchmark" / "manifest.csv"
    results = ROOT / "benchmark_results.json"
    l4_results = ROOT / "l4_results.json"

    expected = {}
    with manifest.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            expected[f'{row["task"]}{row["candidate"]}'] = (
                int(row["expected_L1"]),
                int(row["expected_L3"]),
                int(row["expected_L4"]),
            )

    got13 = {r["spec"]: (int(r["L1"]), int(r["L3"])) for r in json.loads(results.read_text(encoding="utf-8"))}
    got4 = {r["spec"]: int(r["L4"]) for r in json.loads(l4_results.read_text(encoding="utf-8"))}

    ok = True
    print(f'{"spec":<20} {"exp_L1/L3/L4":<14} {"got_L1/L3/L4":<14} {"match"}')
    print("-" * 64)
    for name in sorted(expected):
        e1, e3, e4 = expected[name]
        if name not in got13 or name not in got4:
            print(f"{name:<20} MISSING")
            ok = False
            continue
        g1, g3 = got13[name]
        g4 = got4[name]
        match = (e1 == g1) and (e3 == g3) and (e4 == g4)
        ok = ok and match
        print(f"{name:<20} ({e1},{e3},{e4})     ({g1},{g3},{g4})     {'PASS' if match else 'FAIL'}")

    print("-" * 64)
    total = len(expected)
    matched = sum(
        1
        for k in expected
        if k in got13
        and k in got4
        and expected[k] == (got13[k][0], got13[k][1], got4[k])
    )
    print(f"Matched {matched}/{total} candidates on L1/L3/L4")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
