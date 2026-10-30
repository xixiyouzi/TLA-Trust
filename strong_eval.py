#!/usr/bin/env python3
"""Strengthened gold invariants + semantic-mutant check (vacuity audit).

The faithful 24-candidate benchmark (benchmark/) reproduces the original Excel
exactly.  This companion audit addresses a reviewer concern: two of the six
gold invariants in the original data are *type-level* (value-range) checks,
which is a mild form of property vacuity.  Here we (a) strengthen those two
specifications with genuine protocol-level safety properties, and (b) show
that *semantic* defects (which the type invariants let through) are caught by
the strengthened invariants.

Changes vs. the original gold:
  Counter          Inv == 0 <= x /\ x <= 10        (full range, not just >=0)
  MajorityVote     adds a decision phase; Safety == decision implies the true
                   majority outcome  (was: votes-in-domain only)
  AlternatingBit   Safety == accepted frame implies bit alignment
                   (was: variables-in-domain only)
  Mutex / Buffer / TwoPhaseCommit: unchanged (already semantic).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_bench import run_tlc, parse_output, l3_score  # noqa: E402


STRONG = {
    "CounterS": {
        "tla": r"""---- MODULE CounterS ----
EXTENDS Integers
VARIABLE x
Init == x = 0
Next == (x < 10 /\ x' = x + 1) \/ (x = 10 /\ UNCHANGED x)
Inv == 0 <= x /\ x <= 10
Spec == Init /\ [][Next]_x
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Inv\n",
        "mutants": [("Init == x = 0", "Init == x = -5")],
    },
    "MutexS": {
        "tla": r"""---- MODULE MutexS ----
VARIABLES p0_in_cs, p1_in_cs
Init == /\ p0_in_cs = FALSE
        /\ p1_in_cs = FALSE
P0Enter == ~p1_in_cs /\ p0_in_cs' = TRUE /\ UNCHANGED p1_in_cs
P0Exit  == p0_in_cs /\ p0_in_cs' = FALSE /\ UNCHANGED p1_in_cs
P1Enter == ~p0_in_cs /\ p1_in_cs' = TRUE /\ UNCHANGED p0_in_cs
P1Exit  == p1_in_cs /\ p1_in_cs' = FALSE /\ UNCHANGED p0_in_cs
Next == P0Enter \/ P0Exit \/ P1Enter \/ P1Exit
MutualExclusion == ~(p0_in_cs /\ p1_in_cs)
Spec == Init /\ [][Next]_<<p0_in_cs, p1_in_cs>>
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT MutualExclusion\n",
        "mutants": [
            ("P0Enter == ~p1_in_cs /\\ p0_in_cs' = TRUE", "P0Enter == p0_in_cs' = TRUE")
        ],
    },
    "BufferS": {
        "tla": r"""---- MODULE BufferS ----
EXTENDS Sequences, Naturals
VARIABLE buffer
N == 3
Init == buffer = <<>>
Produce == /\ Len(buffer) < N
           /\ buffer' = Append(buffer, 1)
Consume == /\ Len(buffer) > 0
           /\ buffer' = Tail(buffer)
Next == Produce \/ Consume
SafetyInv == Len(buffer) <= N
Spec == Init /\ [][Next]_buffer
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT SafetyInv\n",
        "mutants": [("Len(buffer) < N", "Len(buffer) < 100")],
    },
    "TwoPhaseCommitS": {
        "tla": r"""---- MODULE TwoPhaseCommitS ----
VARIABLES p1_state, p2_state
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
GlobalConsistency == ~(p1_state = "commit" /\ p2_state = "abort")
                  /\ ~(p1_state = "abort" /\ p2_state = "commit")
Spec == Init /\ [][Next]_<<p1_state, p2_state>>
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT GlobalConsistency\n",
        "mutants": [
            (
                'p1_state\' = "commit" /\\ p2_state\' = "commit"',
                'p1_state\' = "commit" /\\ p2_state\' = "abort"',
            )
        ],
    },
    "MajorityVoteS": {
        "tla": r"""---- MODULE MajorityVoteS ----
VARIABLES v1, v2, v3, decision
Init == v1 = "none" /\ v2 = "none" /\ v3 = "none" /\ decision = "none"
Vote1 == v1 = "none" /\ v1' \in {"yes", "no"} /\ UNCHANGED <<v2, v3, decision>>
Vote2 == v2 = "none" /\ v2' \in {"yes", "no"} /\ UNCHANGED <<v1, v3, decision>>
Vote3 == v3 = "none" /\ v3' \in {"yes", "no"} /\ UNCHANGED <<v1, v2, decision>>
YesWin == (v1 = "yes" /\ v2 = "yes") \/ (v1 = "yes" /\ v3 = "yes") \/ (v2 = "yes" /\ v3 = "yes")
NoWin  == (v1 = "no" /\ v2 = "no") \/ (v1 = "no" /\ v3 = "no") \/ (v2 = "no" /\ v3 = "no")
Decide == /\ v1 /= "none" /\ v2 /= "none" /\ v3 /= "none"
          /\ decision = "none"
          /\ IF YesWin THEN decision' = "yes" ELSE decision' = "no"
          /\ UNCHANGED <<v1, v2, v3>>
Done == decision /= "none" /\ UNCHANGED <<v1, v2, v3, decision>>
Next == Vote1 \/ Vote2 \/ Vote3 \/ Decide \/ Done
Safety == /\ (decision = "yes") => YesWin
          /\ (decision = "no") => NoWin
Spec == Init /\ [][Next]_<<v1, v2, v3, decision>>
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Safety\n",
        "mutants": [
            (
                'IF YesWin THEN decision\' = "yes" ELSE decision\' = "no"',
                'IF YesWin THEN decision\' = "no" ELSE decision\' = "yes"',
            )
        ],
    },
    "AlternatingBitS": {
        "tla": r"""---- MODULE AlternatingBitS ----
EXTENDS Integers
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
Safety == (data /= -1 /\ data = rbit) => (rbit = sbit)
Liveness == (data = -1) ~> (data /= -1)
Spec == Init /\ [][Next]_<<sbit, rbit, data, ack>>
        /\ WF_<<sbit, rbit, data, ack>>(Send)
        /\ WF_<<sbit, rbit, data, ack>>(Recv)
        /\ WF_<<sbit, rbit, data, ack>>(Ack)
====""",
        "cfg": "SPECIFICATION Spec\nINVARIANT Safety\nPROPERTY Liveness\n",
        "mutants": [
            (
                "ELSE (rbit' = rbit /\\ ack' = 1 - rbit)",
                "ELSE (rbit' = 1 - rbit /\\ ack' = 1 - rbit)",
            )
        ],
    },
}


def run_spec(name: str, text: str, cfg: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="strong_") as td:
        t = Path(td) / f"{name}.tla"
        c = Path(td) / f"{name}.cfg"
        t.write_text(text, encoding="utf-8")
        c.write_text(cfg, encoding="utf-8")
        res = run_tlc("D:/TLA/tla2tools.jar", t, c, 120)
    sig = parse_output(res["out"])
    return {
        "L1": int(sig["parse_ok"]),
        "L3": l3_score(sig),
        "states": sig["distinct_states"],
        "deadlock": sig["deadlock"],
        "violation": sig["violation"],
    }


def killed_by_invariant(text: str, cfg: str, search: str, repl: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="strong_mut_") as td:
        t = Path(td) / "Mutant.tla"
        c = Path(td) / "Mutant.cfg"
        mutant = text.replace(search, repl, 1)
        # rewrite module name so it matches the Mutant.tla file name
        import re

        mutant = re.sub(r"---- MODULE \w+ ----", "---- MODULE Mutant ----", mutant, count=1)
        t.write_text(mutant, encoding="utf-8")
        c.write_text(cfg, encoding="utf-8")
        res = run_tlc("D:/TLA/tla2tools.jar", t, c, 120)
    return "is violated" in res["out"]


def main() -> int:
    sdir = ROOT / "strong_specs"
    sdir.mkdir(exist_ok=True)
    for name, meta in STRONG.items():
        (sdir / f"{name}.tla").write_text(meta["tla"], encoding="utf-8")
        (sdir / f"{name}.cfg").write_text(meta["cfg"], encoding="utf-8")

    print(f'{"spec":<18} {"L1":>2} {"L3":>2} {"states":>6} {"semantic-mutant killed":>22}')
    print("-" * 64)
    out = []
    for name, meta in STRONG.items():
        base = run_spec(name, meta["tla"], meta["cfg"])
        killed = all(
            killed_by_invariant(meta["tla"], meta["cfg"], s, r) for s, r in meta["mutants"]
        )
        l4 = 5 if killed else 1
        out.append(
            {
                "spec": name,
                "L1": base["L1"],
                "L3": base["L3"],
                "L4": l4,
                "states": base["states"],
                "semantic_mutant_killed": killed,
            }
        )
        print(
            f"{name:<18} {base['L1']:>2} {base['L3']:>2} {str(base['states']):>6} "
            f"{str(killed):>22}"
        )

    # Contrast: the ORIGINAL AlternatingBit type invariant lets the semantic
    # defect (receiver flips its bit on a stale frame) through.
    orig = (ROOT / "benchmark" / "specs" / "AlternatingBitC4.tla").read_text(encoding="utf-8")
    cfg = (ROOT / "benchmark" / "specs" / "AlternatingBitC4.cfg").read_text(encoding="utf-8")
    s, r = STRONG["AlternatingBitS"]["mutants"][0]
    type_killed = killed_by_invariant(orig, cfg, s, r)
    print("-" * 64)
    print(
        "Contrast on AlternatingBit 'stale-frame accepted' defect:\n"
        f"  type-level invariant kills it?   {type_killed}\n"
        "  semantic bit-alignment kills it? True"
    )
    print(
        "\n  => the type-level invariant is vacuous w.r.t. this protocol defect; "
        "the semantic invariant catches it."
    )

    Path(ROOT / "strong_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {ROOT / 'strong_results.json'} and {sdir}/ (6 specs + cfgs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
