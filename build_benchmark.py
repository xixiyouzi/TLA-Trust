#!/usr/bin/env python3
"""Build the canonical 24-spec TLA-Trust sanity-check benchmark.

Six tasks x four defect classes:
  C1 = syntax error (undefined operator)
  C2 = over-constrained next-state relation (single-state deadlock)
  C3 = tautological invariant (TRUE)
  C4 = gold reference

Output:
  benchmark/specs/<Task><C1..C4>.tla  +  .cfg
  benchmark/manifest.csv              (authoritative expected L1/L3/L4)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPECS = ROOT / "benchmark" / "specs"


TASKS = {
    "Counter": {
        "inv_name": "Inv",
        "inv_gold": "Inv == x >= 0",
        "body": r"""EXTENDS Integers
VARIABLE x
Init == x = 0
Next == (x < 10 /\ x' = x + 1) \/ (x = 10 /\ UNCHANGED x)
Spec == Init /\ [][Next]_x""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Inv\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 5, 1), "C4": (1, 5, 5)},
    },
    "Mutex": {
        "inv_name": "MutualExclusion",
        "inv_gold": "MutualExclusion == ~(p0_in_cs /\\ p1_in_cs)",
        "body": r"""VARIABLES p0_in_cs, p1_in_cs
Init == /\ p0_in_cs = FALSE
        /\ p1_in_cs = FALSE
P0Enter == ~p1_in_cs /\ p0_in_cs' = TRUE /\ UNCHANGED p1_in_cs
P0Exit  == p0_in_cs /\ p0_in_cs' = FALSE /\ UNCHANGED p1_in_cs
P1Enter == ~p0_in_cs /\ p1_in_cs' = TRUE /\ UNCHANGED p0_in_cs
P1Exit  == p1_in_cs /\ p1_in_cs' = FALSE /\ UNCHANGED p0_in_cs
Next == P0Enter \/ P0Exit \/ P1Enter \/ P1Exit
Spec == Init /\ [][Next]_<<p0_in_cs, p1_in_cs>>""",
        "cfg": "SPECIFICATION Spec\nINVARIANT MutualExclusion\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 4, 1), "C4": (1, 4, 5)},
    },
    "Buffer": {
        "inv_name": "SafetyInv",
        "inv_gold": "SafetyInv == Len(buffer) <= N",
        "body": r"""EXTENDS Sequences, Naturals
VARIABLE buffer
N == 3
Init == buffer = <<>>
Produce == /\ Len(buffer) < N
           /\ buffer' = Append(buffer, 1)
Consume == /\ Len(buffer) > 0
           /\ buffer' = Tail(buffer)
Next == Produce \/ Consume
Spec == Init /\ [][Next]_buffer""",
        "cfg": "SPECIFICATION Spec\nINVARIANT SafetyInv\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 4, 1), "C4": (1, 4, 5)},
    },
    "TwoPhaseCommit": {
        "inv_name": "GlobalConsistency",
        "inv_gold": 'GlobalConsistency == ~(p1_state = "commit" /\\ p2_state = "abort")\n'
        '                  /\\ ~(p1_state = "abort" /\\ p2_state = "commit")',
        "body": r"""VARIABLES p1_state, p2_state
Init == p1_state = "init" /\ p2_state = "init"
Vote1 == p1_state = "init" /\ p1_state' \in {"yes", "no"} /\ UNCHANGED p2_state
Vote2 == p2_state = "init" /\ p2_state' \in {"yes", "no"} /\ UNCHANGED p1_state
Decide == /\ p1_state \in {"yes", "no"}
          /\ p2_state \in {"yes", "no"}
          /\ IF p1_state = "yes" /\ p2_state = "yes"
             THEN (p1_state' = "commit" /\ p2_state' = "commit")
             ELSE (p1_state' = "abort" /\ p2_state' = "abort")
Done == /\ p1_state \in {"commit", "abort"}
        /\ p2_state \in {"commit", "abort"}
        /\ UNCHANGED <<p1_state, p2_state>>
Next == Vote1 \/ Vote2 \/ Decide \/ Done
Spec == Init /\ [][Next]_<<p1_state, p2_state>>""",
        "cfg": "SPECIFICATION Spec\nINVARIANT GlobalConsistency\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 5, 1), "C4": (1, 5, 5)},
    },
    "MajorityVote": {
        "inv_name": "Safety",
        "inv_gold": 'Safety == /\\ v1 \\in {"none", "yes", "no"}\n'
        '          /\\ v2 \\in {"none", "yes", "no"}\n'
        '          /\\ v3 \\in {"none", "yes", "no"}',
        "body": r"""VARIABLES v1, v2, v3
Init == v1 = "none" /\ v2 = "none" /\ v3 = "none"
Vote1 == v1 = "none" /\ v1' \in {"yes", "no"} /\ UNCHANGED <<v2, v3>>
Vote2 == v2 = "none" /\ v2' \in {"yes", "no"} /\ UNCHANGED <<v1, v3>>
Vote3 == v3 = "none" /\ v3' \in {"yes", "no"} /\ UNCHANGED <<v1, v2>>
Done == /\ v1 /= "none" /\ v2 /= "none" /\ v3 /= "none"
        /\ UNCHANGED <<v1, v2, v3>>
Next == Vote1 \/ Vote2 \/ Vote3 \/ Done
YesWin == (v1 = "yes" /\ v2 = "yes") \/ (v1 = "yes" /\ v3 = "yes") \/ (v2 = "yes" /\ v3 = "yes")
NoWin  == (v1 = "no" /\ v2 = "no") \/ (v1 = "no" /\ v3 = "no") \/ (v2 = "no" /\ v3 = "no")
Spec == Init /\ [][Next]_<<v1, v2, v3>>""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Safety\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 5, 1), "C4": (1, 5, 5)},
    },
    "AlternatingBit": {
        "inv_name": "Safety",
        "inv_gold": 'Safety == /\\ sbit \\in {0, 1}\n'
        '          /\\ rbit \\in {0, 1}\n'
        '          /\\ data \\in {-1, 0, 1}\n'
        '          /\\ ack \\in {-1, 0, 1}',
        "body": r"""EXTENDS Integers
VARIABLES sbit, rbit, data, ack
Init == sbit = 0 /\ rbit = 0 /\ data = -1 /\ ack = -1
Send == data = -1 /\ data' = sbit /\ UNCHANGED <<sbit, rbit, ack>>
Recv == /\ data /= -1
        /\ IF data = rbit
           THEN (rbit' = 1 - rbit /\ ack' = data)
           ELSE (rbit' = rbit /\ ack' = 1 - rbit)
        /\ data' = -1
        /\ UNCHANGED sbit
Ack == /\ ack /= -1
       /\ IF ack = sbit
          THEN sbit' = 1 - sbit
          ELSE sbit' = sbit
       /\ ack' = -1
       /\ UNCHANGED <<rbit, data>>
Next == Send \/ Recv \/ Ack
Liveness == (data = -1) ~> (data /= -1)
Spec == Init /\ [][Next]_<<sbit, rbit, data, ack>>
        /\ WF_<<sbit, rbit, data, ack>>(Send)
        /\ WF_<<sbit, rbit, data, ack>>(Recv)
        /\ WF_<<sbit, rbit, data, ack>>(Ack)""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Safety\nPROPERTY Liveness\n",
        "exp": {"C1": (0, -1, -1), "C2": (1, 1, -1), "C3": (1, 5, 1), "C4": (1, 5, 5)},
    },
}

CLASSES = {
    "C1": "Syntax Error",
    "C2": "Deadlock",
    "C3": "Weak Invariant",
    "C4": "Golden",
}


def build_variant(task: str, cand: str) -> tuple[str, str]:
    meta = TASKS[task]
    stem = f"{task}{cand}"
    body = meta["body"]
    inv = meta["inv_gold"]

    if cand == "C1":
        inv = inv + "\n/\\ UndefinedOperator(0)"
    elif cand == "C2":
        body = re.sub(r"^Next == .*$", "Next == FALSE", body, count=1, flags=re.MULTILINE)
    elif cand == "C3":
        inv = f'{meta["inv_name"]} == TRUE'
    # C4: gold unchanged

    text = f"---- MODULE {stem} ----\n{body}\n{inv}\n====\n"
    return text, meta["cfg"]


def main() -> int:
    SPECS.mkdir(parents=True, exist_ok=True)
    manifest = []
    for task in TASKS:
        for cand in CLASSES:
            text, cfg = build_variant(task, cand)
            stem = f"{task}{cand}"
            (SPECS / f"{stem}.tla").write_text(text, encoding="utf-8")
            (SPECS / f"{stem}.cfg").write_text(cfg, encoding="utf-8")
            l1, l3, l4 = TASKS[task]["exp"][cand]
            manifest.append(
                {
                    "task": task,
                    "candidate": cand,
                    "class": CLASSES[cand],
                    "expected_L1": l1,
                    "expected_L3": l3,
                    "expected_L4": l4,
                }
            )

    mpath = ROOT / "benchmark" / "manifest.csv"
    with mpath.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["task", "candidate", "class", "expected_L1", "expected_L3", "expected_L4"],
        )
        w.writeheader()
        w.writerows(manifest)

    n = len(list(SPECS.glob("*.tla")))
    print(f"Wrote {n} .tla/.cfg pairs into {SPECS}")
    print(f"Wrote {mpath} ({len(manifest)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
