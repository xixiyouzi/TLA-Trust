#!/usr/bin/env python3
"""
run_bench.py -- batch-run SANY + TLC over a directory of TLA+ specs and
extract the L1 / L3 signals used by the TLA-Trust rubric.

For every <name>.tla that has a matching <name>.cfg in the same directory,
this script runs TLC via tla2tools.jar, parses the output, and reports:

  L1  : parse success (SANY finished)
  L3  : behavioral non-vacuity (distinct states, deadlock, property violation)

The L3 rule mirrors the paper's Algorithm 1:
  parse fail            -> L3 = -1   (not applicable)
  deadlock or <=1 state -> L3 = 1
  distinct >= 6         -> L3 = 5
  otherwise             -> L3 = 4
A safety/temporal property violation is treated as a counterexample and
capped at L3 = 1.

Usage:
  python run_bench.py --jar D:/TLA/tla2tools.jar --specs ./benchmark/specs \
      --out results.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


def resolve_java() -> str:
    """Return a real JDK java.exe, avoiding the Oracle javapath launcher shim
    (whose child-JVM indirection can drop output on long batch runs)."""
    import os

    candidates = []
    home = os.environ.get("JAVA_HOME")
    if home:
        candidates.append(Path(home) / "bin" / "java.exe")
    try:
        import winreg

        for base in (r"SOFTWARE\JavaSoft\JDK", r"SOFTWARE\JavaSoft\Java Development Kit"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
                    cur, _ = winreg.QueryValueEx(k, "CurrentVersion")
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + "\\" + cur) as k2:
                    jh, _ = winreg.QueryValueEx(k2, "JavaHome")
                candidates.append(Path(jh) / "bin" / "java.exe")
            except OSError:
                continue
    except Exception:
        pass
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return "java"


def run_tlc(jar: str, spec: Path, cfg: Path, timeout: int) -> Dict:
    """Run TLC on one specification and return its combined output."""
    with tempfile.TemporaryDirectory(prefix="tlc_meta_") as metadir:
        cmd = [
            resolve_java(), "-cp", jar, "tlc2.TLC",
            "-config", str(cfg),
            "-metadir", metadir,
            str(spec),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return {"timeout": True, "out": "", "code": -1}
        except OSError as exc:
            return {"timeout": False, "out": str(exc), "code": -2}
    return {
        "timeout": False,
        "out": (proc.stdout or "") + "\n" + (proc.stderr or ""),
        "code": proc.returncode,
    }


def parse_output(out: str) -> Dict:
    """Extract the L1 / L3 signals from a TLC run's text output."""
    # TLC 2.x (2026) prints "Starting..." even when semantic analysis fails,
    # so parse success must be "started AND produced no parse/semantic error".
    parse_fail = (
        "Unknown operator:" in out
        or "Semantic errors:" in out
        or "*** Errors:" in out
        or "Parsing or semantic analysis failed" in out
        or "syntax error" in out.lower()
    )
    parse_ok = ("Starting..." in out) and not parse_fail
    deadlock = "Deadlock reached." in out
    violation = ("is violated" in out) or ("Temporal properties were violated" in out)

    m = re.search(r"(\d+) distinct states found", out)
    distinct = int(m.group(1)) if m else None

    # Action coverage: TLC prints "<Action ...>: taken:enabled" pairs. We only
    # need to know whether any action was ever taken; >1 distinct state
    # already implies that, so this is left as a conservative fallback.
    coverage = bool(re.search(r"<[A-Za-z][^>]*>:\s*\d+\s*:\s*\d+", out))

    return {
        "parse_ok": parse_ok,
        "deadlock": deadlock,
        "violation": violation,
        "distinct_states": distinct,
        "coverage": coverage,
    }


def l3_score(sig: Dict) -> int:
    """Map parsed TLC signals onto the paper's L3 score (or -1 if n/a)."""
    if not sig["parse_ok"]:
        return -1
    if sig["violation"]:
        return 1
    if sig["deadlock"]:
        return 1
    n = sig["distinct_states"]
    if n is None:
        return 1
    if n <= 1:
        return 1
    if n >= 6:
        return 5
    return 4


def discover_specs(specs_dir: Path) -> List[Path]:
    """Return .tla files that have a same-basename .cfg next to them."""
    found: List[Path] = []
    for tla in sorted(specs_dir.rglob("*.tla")):
        if tla.name == "MC.tla":  # skip Toolbox wrapper files
            continue
        cfg = tla.with_suffix(".cfg")
        if cfg.exists():
            found.append(tla)
    return found


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", required=True, help="path to tla2tools.jar")
    ap.add_argument("--specs", required=True, help="directory of .tla/.cfg pairs")
    ap.add_argument("--out", default="results.json", help="output JSON path")
    ap.add_argument("--timeout", type=int, default=120, help="per-spec timeout (s)")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N specs")
    args = ap.parse_args(argv)

    specs_dir = Path(args.specs)
    specs = discover_specs(specs_dir)
    if args.limit > 0:
        specs = specs[: args.limit]

    rows = []
    for i, tla in enumerate(specs, 1):
        cfg = tla.with_suffix(".cfg")
        print(f"[{i}/{len(specs)}] {tla.name} ...", flush=True)
        res = run_tlc(args.jar, tla, cfg, args.timeout)
        sig = parse_output(res["out"])
        l3 = l3_score(sig)
        row = {
            "spec": tla.stem,
            "L1": int(sig["parse_ok"]),
            "L3": l3,
            "distinct_states": sig["distinct_states"],
            "deadlock": sig["deadlock"],
            "violation": sig["violation"],
            "timeout": res["timeout"],
            "exit_code": res["code"],
        }
        rows.append(row)
        print(f"       -> L1={row['L1']} L3={row['L3']} states={row['distinct_states']} "
              f"deadlock={row['deadlock']} violation={row['violation']}", flush=True)

    out = Path(args.out)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {out} ({len(rows)} specs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
