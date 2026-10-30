#!/usr/bin/env python3
"""Feedback-directed repair loop (DeepSeek) for the TLA-Trust benchmark.

For each of the 24 candidates it first scores L1/L3/L4. Candidates that are not
trustworthy (L1=1 and L3>=4 and L4>=4) are repaired by a DeepSeek LLM using the
TLC/SANY diagnostic, up to --max-rounds (default 5), then re-scored. Finally it
prints the four paper metrics FPSR / ARI / RSR / TSR.

Requires: requests (pip install requests) and the DeepSeek API key in the
environment variable DEEPSEEK_API_KEY.

Usage:
  $env:DEEPSEEK_API_KEY = "sk-..."
  python repair_loop.py --jar D:/TLA/tla2tools.jar --specs benchmark/specs

  # no-LLM sanity check of the scoring / metric wiring only:
  python repair_loop.py --jar D:/TLA/tla2tools.jar --specs benchmark/specs --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from run_bench import run_tlc, parse_output, l3_score  # noqa: E402
from l4_mutation import MUTATIONS, l4_from_kill_ratio  # noqa: E402
from build_benchmark import build_variant  # noqa: E402


DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM = (
    "You are an expert in TLA+ and the TLC model checker. You repair defective "
    "TLA+ specifications. Reply with ONLY the corrected TLA+ module inside a "
    "single ```tla code block, with no prose. Keep the SPECIFICATION and "
    "INVARIANT operator names and the variable names unchanged."
)

TASK_DESCRIPTIONS = {
    "Counter": "a counter that starts at 0, increments while below 10, and never goes negative",
    "Mutex": "a two-process mutual-exclusion protocol where the two processes must never be in the critical section simultaneously",
    "Buffer": "a bounded producer-consumer buffer of capacity 3 whose length never exceeds 3",
    "TwoPhaseCommit": "a two-phase commit protocol with two participants that must always agree (both commit or both abort, never a commit/abort mismatch)",
    "MajorityVote": "a three-voter majority protocol whose final decision must agree with the actual majority of the votes",
    "AlternatingBit": "an alternating-bit sender/receiver protocol where an accepted frame must satisfy bit alignment",
}


def evaluate(spec_text: str, cfg_text: str, task: str, jar: str, timeout: int):
    """Return (L1, L3, L4, tlc_output) for one spec. L4 = -1 if not applicable."""
    m = re.search(r"----\s*MODULE\s+(\w+)\s*----", spec_text)
    module = m.group(1) if m else "Spec"
    with tempfile.TemporaryDirectory(prefix="repair_") as td:
        sp = Path(td) / f"{module}.tla"
        cp = Path(td) / f"{module}.cfg"
        sp.write_text(spec_text, encoding="utf-8")
        cp.write_text(cfg_text, encoding="utf-8")
        res = run_tlc(jar, sp, cp, timeout)
    sig = parse_output(res["out"])
    l1 = int(sig["parse_ok"])
    l3 = l3_score(sig)
    l4 = -1
    if l1 == 1 and l3 >= 4:
        l4 = check_l4(spec_text, cfg_text, task, jar, timeout)
    return l1, l3, l4, res["out"]


def check_l4(spec_text: str, cfg_text: str, task: str, jar: str, timeout: int) -> int:
    """Inject the task's canonical defect and return the L4 score (-1 if the
    defect site cannot be located in this repaired variant)."""
    m = re.search(r"----\s*MODULE\s+(\w+)\s*----", spec_text)
    module = m.group(1) if m else "Spec"
    killed = 0
    total = 0
    for search, repl in MUTATIONS[task]:
        if search not in spec_text:
            continue
        total += 1
        mutant = spec_text.replace(search, repl, 1)
        with tempfile.TemporaryDirectory(prefix="repair_mut_") as td:
            mt = Path(td) / f"{module}.tla"
            mc = Path(td) / f"{module}.cfg"
            mt.write_text(mutant, encoding="utf-8")
            mc.write_text(cfg_text, encoding="utf-8")
            res = run_tlc(jar, mt, mc, timeout)
            if "is violated" in res["out"]:
                killed += 1
    if total == 0:
        return -1
    return l4_from_kill_ratio(killed / total)


def describe(l1: int, l3: int, l4: int, out: str) -> str:
    tail = out[-2500:]
    if l1 == 0:
        return f"SANY parse failed (L1=0). Diagnostic:\n{tail}"
    if l3 <= 1:
        return f"TLC found a deadlock or single-state vacuity (L3={l3}). Diagnostic:\n{tail}"
    if l4 < 4:
        return (
            f"TLC passes but the invariant is weak/tautological (L4={l4}): it fails "
            f"to reject a defect injected into the transition system. Replace it "
            f"with a correct, non-vacuous invariant."
        )
    return f"TLC diagnostic:\n{tail}"


def build_prompt(task: str, spec_text: str, cfg_text: str, diag: str, round_no: int) -> str:
    desc = TASK_DESCRIPTIONS[task]
    return (
        f"Task: {task} -- model {desc}.\n\n"
        "Repair this defective TLA+ specification so that it:\n"
        "1. parses cleanly with SANY (L1=1),\n"
        "2. model-checks with TLC without premature deadlock and with a meaningful "
        "state space (L3>=4),\n"
        "3. carries a correct, non-vacuous invariant that catches a defect injected "
        "into the transition system (L4>=4).\n\n"
        f"Config file (.cfg):\n```\n{cfg_text}\n```\n\n"
        f"Current specification (.tla):\n```tla\n{spec_text}\n```\n\n"
        f"Diagnostic:\n{diag}\n\n"
        f"Repair round {round_no}. Return only the corrected .tla in a ```tla code block."
    )


def call_deepseek(api_key: str, model: str, base_url: str, prompt: str, timeout: int = 300) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    last = None
    for attempt in range(4):
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 8192,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (requests.exceptions.RequestException, ValueError, KeyError) as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise last


def rule_repair(task: str, stem: str) -> str:
    """Deterministic gold-oracle repairer (no model). Sanity-check only."""
    gold, _ = build_variant(task, "C4")
    return re.sub(
        r"----\s*MODULE\s+\w+\s*----",
        f"---- MODULE {stem} ----",
        gold,
        count=1,
    )


def extract_tla(reply: str) -> str | None:
    m = re.search(r"```(?:tla)?\s*\n(.*?)```", reply, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"----\s*MODULE\s+.*?====\s*", reply, re.DOTALL)
    if m:
        return m.group(0).strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", required=True)
    ap.add_argument("--specs", required=True)
    ap.add_argument("--out", default="repair_results.json")
    ap.add_argument("--max-rounds", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="only process first N candidates (0 = all)")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="OpenAI-compatible base URL (DeepSeek, or local Ollama http://localhost:11434/v1)",
    )
    ap.add_argument(
        "--repairer",
        choices=["llm", "rule"],
        default="llm",
        help="llm = call the model; rule = deterministic gold-oracle (no API, sanity check)",
    )
    ap.add_argument("--llm-timeout", type=int, default=300, help="seconds to wait per LLM call")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true", help="score only, do not call the LLM")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not args.dry_run and args.repairer == "llm" and not api_key:
        print("ERROR: set the DEEPSEEK_API_KEY environment variable.", file=sys.stderr)
        return 2

    specs_dir = Path(args.specs)
    manifest = specs_dir.parent / "manifest.csv"
    with manifest.open(encoding="utf-8") as fh:
        rows_in = list(csv.DictReader(fh))
    if args.limit > 0:
        rows_in = rows_in[: args.limit]

    out_path = Path(args.out)
    existing = {}
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            for r in prev.get("results", []):
                existing[r["task"] + r["candidate"]] = r
        except Exception:
            existing = {}

    results = []
    for row in rows_in:
        task, cand, cls = row["task"], row["candidate"], row["class"]
        stem = task + cand
        if stem in existing:
            results.append(existing[stem])
            print(f"{stem:<20} (resumed)", flush=True)
            continue
        spec_text = (specs_dir / f"{stem}.tla").read_text(encoding="utf-8")
        cfg_text = (specs_dir / f"{stem}.cfg").read_text(encoding="utf-8")

        l1, l3, l4, out = evaluate(spec_text, cfg_text, task, args.jar, args.timeout)
        init = {"L1": l1, "L3": l3, "L4": l4}
        trustworthy = l1 == 1 and l3 >= 4 and l4 >= 4
        cur_text = spec_text
        rounds = 0
        repaired = trustworthy

        if not trustworthy and not args.dry_run:
            for r in range(1, args.max_rounds + 1):
                if args.repairer == "rule":
                    new_text = rule_repair(task, stem)
                else:
                    diag = describe(l1, l3, l4, out)
                    prompt = build_prompt(task, cur_text, cfg_text, diag, r)
                    reply = call_deepseek(api_key, args.model, args.base_url, prompt, args.llm_timeout)
                    new_text = extract_tla(reply)
                if new_text:
                    cur_text = new_text
                l1, l3, l4, out = evaluate(cur_text, cfg_text, task, args.jar, args.timeout)
                rounds = r
                if l1 == 1 and l3 >= 4 and l4 >= 4:
                    repaired = True
                    break

        results.append(
            {
                "task": task,
                "candidate": cand,
                "class": cls,
                "initial": init,
                "repaired": repaired,
                "rounds": rounds,
                "final": {"L1": l1, "L3": l3, "L4": l4},
            }
        )
        print(
            f"{stem:<20} init=(L1={init['L1']},L3={init['L3']},L4={init['L4']}) "
            f"-> repaired={repaired} rounds={rounds} final=(L1={l1},L3={l3},L4={l4})",
            flush=True,
        )
        out_path.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")

    # paper metrics
    n = len(results)
    first_pass = sum(1 for r in results if r["initial"]["L1"] == 1 and r["initial"]["L3"] >= 4 and r["initial"]["L4"] >= 4)
    fpsr = first_pass / n
    defective = [r for r in results if not (r["initial"]["L1"] == 1 and r["initial"]["L3"] >= 4 and r["initial"]["L4"] >= 4)]
    repaired_n = sum(1 for r in defective if r["repaired"])
    rsr = repaired_n / len(defective) if defective else 1.0
    ari = sum(r["rounds"] for r in defective if r["repaired"]) / repaired_n if repaired_n else 0.0
    tsr = fpsr + (1 - fpsr) * rsr

    print("\n" + "=" * 64)
    print(f"FPSR = {fpsr*100:.1f}%  ({first_pass}/{n})")
    print(f"ARI  = {ari:.2f} rounds")
    print(f"RSR  = {rsr*100:.1f}%  ({repaired_n}/{len(defective)})")
    print(f"TSR  = {tsr*100:.1f}%")

    out = {"fpsr": fpsr, "ari": ari, "rsr": rsr, "tsr": tsr, "results": results}
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
