#!/usr/bin/env python3
"""Scale runner: batch SANY+TLC over a whole TLA+ corpus.

Works on any directory tree of .tla files (tlaplus/Examples, SysMoBench, ...).
For every non-Toolbox .tla file it:
  - pairs it with a config: same-basename .cfg, else the single .cfg in the
    same directory, else MC.cfg;
  - runs TLC with a per-spec timeout (Java heap-friendly: sequential);
  - scores L1 (parse) and L3 (behavioral non-vacuity) exactly like run_bench;
  - skips specs with no config instead of crashing.

Outputs one CSV + JSON row per spec, then prints a summary.

Usage:
  python run_scale.py --jar D:/TLA/tla2tools.jar --root ./Examples \
      --lib "path/to/libraries;path/to/CommunityModules" \
      --out-csv scale_results.csv --out-json scale_results.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_bench import parse_output, l3_score  # noqa: E402


def resolve_java() -> str:
    """Return the path to a real JDK `java.exe`, avoiding the Oracle javapath
    launcher shim (which spawns a child JVM that survives our kill and leaks
    an orphan process)."""
    candidates = []
    home = os.environ.get("JAVA_HOME")
    if home:
        candidates.append(Path(home) / "bin" / "java.exe")
    try:
        import winreg

        for base in (
            r"SOFTWARE\JavaSoft\JDK",
            r"SOFTWARE\JavaSoft\Java Development Kit",
        ):
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


def _kill_tree(pid: int) -> None:
    # On Windows, `java` is often a launcher shim that spawns the real JVM as a
    # child, so killing only the direct child leaves an orphan that keeps
    # burning CPU and holds the output file open. taskkill /T kills the tree.
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _rmtree(path: str) -> None:
    for _ in range(6):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.5)


def run_tlc(jar: str, spec: Path, cfg: Path, timeout: int, lib: str | None, xmx: str, java: str) -> dict:
    env = os.environ.copy()
    if lib:
        env["TLA_LIBRARY_PATH"] = lib
    metadir = tempfile.mkdtemp(prefix="scale_meta_")
    try:
        out_file = Path(metadir) / "tlc.out"
        cmd = [
            java,
            "-XX:+UseParallelGC",
            f"-Xmx{xmx}",
            "-cp",
            jar,
            "tlc2.TLC",
            "-config",
            str(cfg),
            "-metadir",
            metadir,
            str(spec),
        ]
        t0 = time.time()
        with out_file.open("wb") as fh:
            proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
            try:
                proc.wait(timeout=timeout)
                code, timed_out = proc.returncode, False
            except subprocess.TimeoutExpired:
                _kill_tree(proc.pid)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                time.sleep(0.5)  # let Windows release TLC's state-file handles
                code, timed_out = -1, True
        try:
            out = out_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out = ""
        return {
            "timeout": timed_out,
            "out": out,
            "code": code,
            "seconds": round(time.time() - t0, 1),
        }
    finally:
        _rmtree(metadir)


def find_cfg(tla: Path) -> Path | None:
    same = tla.with_suffix(".cfg")
    if same.exists():
        return same
    cfgs = sorted(tla.parent.glob("*.cfg"))
    if len(cfgs) == 1:
        return cfgs[0]
    mc = tla.parent / "MC.cfg"
    if mc.exists():
        return mc
    return None


def discover(root: Path):
    pairs: list[tuple[Path, Path]] = []
    skipped: list[tuple[Path, str]] = []
    for tla in sorted(root.rglob("*.tla")):
        if tla.name == "MC.tla":  # Toolbox wrapper, not a spec
            continue
        if "_TTrace_" in tla.name:  # TLC deadlock/counterexample trace, not a spec
            continue
        cfg = find_cfg(tla)
        if cfg is None:
            skipped.append((tla, "no_config"))
        else:
            pairs.append((tla, cfg))
    return pairs, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", required=True)
    ap.add_argument("--root", required=True, help="corpus root directory")
    ap.add_argument("--java", default=None, help="path to java.exe (default: auto-resolve real JDK)")
    ap.add_argument("--lib", default=None, help="TLA_LIBRARY_PATH (semicolon-separated)")
    ap.add_argument("--timeout", type=int, default=60, help="per-spec timeout (s)")
    ap.add_argument("--xmx", default="4g", help="JVM max heap per TLC run")
    ap.add_argument("--limit", type=int, default=0, help="run only first N paired specs")
    ap.add_argument("--out-csv", default="scale_results.csv")
    ap.add_argument("--out-json", default="scale_results.json")
    args = ap.parse_args()

    root = Path(args.root)
    java = args.java or resolve_java()
    print(f"using java: {java}", flush=True)
    pairs, skipped = discover(root)
    n_pairs_full = len(pairs)
    n_skipped_full = len(skipped)
    if args.limit > 0:
        pairs = pairs[: args.limit]

    rows = []
    for i, (tla, cfg) in enumerate(pairs, 1):
        rel_dir = str(tla.parent.relative_to(root))
        res = run_tlc(args.jar, tla, cfg, args.timeout, args.lib, args.xmx, java)
        sig = parse_output(res["out"])
        l1 = int(sig["parse_ok"])
        l3 = l3_score(sig)
        row = {
            "dir": rel_dir,
            "spec": tla.name,
            "cfg": cfg.name,
            "L1": l1,
            "L3": l3,
            "distinct_states": sig["distinct_states"],
            "deadlock": sig["deadlock"],
            "violation": sig["violation"],
            "timeout": res["timeout"],
            "exit_code": res["code"],
            "seconds": res["seconds"],
        }
        rows.append(row)
        # checkpoint after every spec so an interrupted run keeps its progress
        Path(args.out_json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        time_s = "TIMEOUT" if res["timeout"] else f'{res["seconds"]}s'
        print(
            f"[{i}/{len(pairs)}] {rel_dir}/{tla.name}  "
            f"L1={l1} L3={l3} states={sig['distinct_states']} "
            f"deadlock={sig['deadlock']} violation={sig['violation']} "
            f"{time_s}",
            flush=True,
        )

    for tla, reason in skipped:
        rows.append(
            {
                "dir": str(tla.parent.relative_to(root)),
                "spec": tla.name,
                "cfg": "",
                "L1": -1,
                "L3": -1,
                "distinct_states": None,
                "deadlock": False,
                "violation": False,
                "timeout": False,
                "exit_code": None,
                "seconds": 0.0,
                "skipped": reason,
            }
        )

    Path(args.out_csv).write_text(_to_csv(rows), encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    parsed = sum(1 for r in rows if r["L1"] == 1)
    substantive = sum(1 for r in rows if r.get("L3", -1) >= 4)
    deadlocks = sum(1 for r in rows if r.get("deadlock"))
    violations = sum(1 for r in rows if r.get("violation"))
    timeouts = sum(1 for r in rows if r.get("timeout"))
    parse_err = sum(1 for r in rows if r.get("L1") == 0 and not r.get("timeout"))
    print(f"specs found (excl. Toolbox wrappers): {n_pairs_full + n_skipped_full}")
    print(f"  with config   : {n_pairs_full}")
    print(f"  without config: {n_skipped_full} (skipped)")
    print(f"parsed (L1=1)   : {parsed}")
    print(f"parse/other err : {parse_err} (excl. timeouts)")
    print(f"substantive (L3>=4): {substantive}")
    print(f"deadlock        : {deadlocks}")
    print(f"violation       : {violations}")
    print(f"timeout         : {timeouts}")
    if parsed:
        naive = sum(1 for r in rows if r.get("L1") == 1 and not r.get("violation"))
        print(f"\nnaive pass      : {naive}/{parsed} ({100*naive/parsed:.1f}% of parsed)")
        print(f"substantive rate: {substantive}/{parsed} ({100*substantive/parsed:.1f}% of parsed)")

    print("\nper-directory (top level):")
    by_dir: dict[str, dict] = {}
    for r in rows:
        d = r["dir"].split("/")[0].split("\\")[0] if r["dir"] else "."
        s = by_dir.setdefault(d, {"n": 0, "parsed": 0, "subst": 0, "timeout": 0})
        s["n"] += 1
        s["parsed"] += 1 if r.get("L1") == 1 else 0
        s["subst"] += 1 if r.get("L3", -1) >= 4 else 0
        s["timeout"] += 1 if r.get("timeout") else 0
    for d in sorted(by_dir):
        s = by_dir[d]
        print(f"  {d:<24} n={s['n']:<4} parsed={s['parsed']:<4} subst={s['subst']:<4} timeout={s['timeout']}")

    print(f"\nWrote {args.out_csv} and {args.out_json} ({len(rows)} rows)")
    return 0


def _to_csv(rows) -> str:
    import io

    fields = [
        "dir",
        "spec",
        "cfg",
        "L1",
        "L3",
        "distinct_states",
        "deadlock",
        "violation",
        "timeout",
        "exit_code",
        "seconds",
        "skipped",
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        r = dict(r)
        r.setdefault("skipped", "")
        w.writerow(r)
    return buf.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
