#!/usr/bin/env python3
"""L4 mutation-sensitivity harness.

For every candidate that parses (L1=1) and is not single-state (L3>1), inject
the task's canonical transition-system defect and check whether the
candidate's invariant rejects it.  C1 (syntax error) and C2 (single-state
deadlock) are scored L4 = -1 (not applicable).

Canonical defect per task (reconstructed from the original *Mutant.toolbox*):
  Counter         Init == x = -5             (corrupted initial value)
  Mutex           drop ~p1_in_cs guard       (dropped mutex guard)
  Buffer          Len(buffer) < 100          (corrupted capacity bound)
  TwoPhaseCommit  Decide THEN -> commit,abort (inconsistent decision)
  MajorityVote    Vote1 allows "maybe"       (out-of-domain vote)
  AlternatingBit  Send data' = 2             (out-of-domain message)

L4 mapping over kill ratio r:
  r >= 0.8 -> 5,  r >= 0.5 -> 4,  r >= 0.25 -> 3,  r > 0 -> 2,  r == 0 -> 1.
With one canonical mutant per task: gold invariant -> 5 (killed),
TRUE invariant -> 1 (survives).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_bench import run_tlc  # noqa: E402


MUTATIONS = {
    "Counter": [("Init == x = 0", "Init == x = -5")],
    "Mutex": [
        ("P0Enter == ~p1_in_cs /\\ p0_in_cs' = TRUE", "P0Enter == p0_in_cs' = TRUE")
    ],
    "Buffer": [("Len(buffer) < N", "Len(buffer) < 100")],
    "TwoPhaseCommit": [
        (
            "p1_state' = \"commit\" /\\ p2_state' = \"commit\"",
            "p1_state' = \"commit\" /\\ p2_state' = \"abort\"",
        )
    ],
    "MajorityVote": [
        ("v1' \\in {\"yes\", \"no\"}", "v1' \\in {\"yes\", \"no\", \"maybe\"}")
    ],
    "AlternatingBit": [("data' = sbit", "data' = 2")],
}


def l4_from_kill_ratio(r: float) -> int:
    if r >= 0.8:
        return 5
    if r >= 0.5:
        return 4
    if r >= 0.25:
        return 3
    if r > 0:
        return 2
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", required=True)
    ap.add_argument("--specs", required=True)
    ap.add_argument("--results", required=True, help="benchmark_results.json")
    ap.add_argument("--out", default="l4_results.json")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    specs_dir = Path(args.specs)
    manifest = specs_dir.parent / "manifest.csv"

    task_by_stem = {}
    with manifest.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            task_by_stem[f'{row["task"]}{row["candidate"]}'] = row["task"]

    results = {
        r["spec"]: r for r in json.loads(Path(args.results).read_text(encoding="utf-8"))
    }

    rows = []
    for stem in sorted(task_by_stem):
        task = task_by_stem[stem]
        rec = results.get(stem)
        if rec is None:
            print(f"{stem}: missing from {args.results}", flush=True)
            continue
        l1, l3 = int(rec["L1"]), int(rec["L3"])

        if l1 == 0 or l3 <= 1:
            l4, killed, total = -1, 0, 0
        else:
            tla = specs_dir / f"{stem}.tla"
            cfg = specs_dir / f"{stem}.cfg"
            text = tla.read_text(encoding="utf-8")
            killed = 0
            total = 0
            for search, repl in MUTATIONS[task]:
                if search not in text:
                    print(f"  WARN {stem}: mutation not found: {search!r}", flush=True)
                    continue
                total += 1
                mutant = text.replace(search, repl, 1)
                with tempfile.TemporaryDirectory(prefix="l4_mut_") as td:
                    # TLC requires the file name to match the top-level module
                    # name, so keep the original stem here.
                    mt = Path(td) / f"{stem}.tla"
                    mc = Path(td) / f"{stem}.cfg"
                    mt.write_text(mutant, encoding="utf-8")
                    mc.write_text(cfg.read_text(encoding="utf-8"), encoding="utf-8")
                    res = run_tlc(args.jar, mt, mc, args.timeout)
                    if "is violated" in res["out"]:
                        killed += 1
            ratio = killed / total if total else 0.0
            l4 = l4_from_kill_ratio(ratio)

        rows.append(
            {
                "spec": stem,
                "task": task,
                "L1": l1,
                "L3": l3,
                "L4": l4,
                "mutants_killed": killed,
                "mutants_total": total,
            }
        )
        print(
            f"{stem:<20} L1={l1} L3={l3} -> L4={l4} (killed {killed}/{total})",
            flush=True,
        )

    Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {args.out} ({len(rows)} candidates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
