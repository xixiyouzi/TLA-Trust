# TLA-Trust

Reference implementation for the manuscript
**"Towards Trustworthy TLA+ Specifications: Vacuity-Aware Quality Metrics and an
Open Reference Implementation"** (submitted to Science of Computer Programming).

- Zenodo (archived release): <https://doi.org/10.5281/zenodo.23614758>

TLA-Trust is a lightweight, reproducible evaluation harness for AI-assisted
TLA+ engineering. It computes the four closed-form metrics **FPSR**, **ARI**,
**RSR**, and **TSR**, implements the **L1–L4** quality rubric, performs
deadlock- and mutation-based vacuity detection, and includes a preliminary
Alloy/Kodkod-to-TLA+ bridge.

## What is in this repository

- `benchmark/specs/` — 24 candidate specifications (6 tasks × 4 defect classes)
  with matching `.cfg` files.
- `benchmark/manifest.csv` — authoritative expected L1/L3/L4 scores.
- `strong_specs/` — six gold specifications with protocol-level (semantic)
  invariants.
- `L2_reviewer_packet/` — double-blind scoring packet for the L2 semantic level.
- `Tla_record.xlsx` — the original human-verified result sheet.
- Result files (JSON/CSV) — see the list below.

## Requirements

- Python 3.10+
- Java 17 (tested with TLC 2026.07.31)
- `tla2tools.jar` (the TLC model checker), passed to each script with `--jar`

## Quick start — regenerate the controlled sanity-check results

```powershell
# 1. (re)build the 24 candidate specifications
python build_benchmark.py

# 2. batch-run SANY + TLC, score L1 / L3
python run_bench.py --jar D:/TLA/tla2tools.jar --specs benchmark/specs --out benchmark_results.json

# 3. verify against the original Excel sheet
python compare_bench.py

# 4. mutation sensitivity (L4)
python l4_mutation.py --jar D:/TLA/tla2tools.jar --specs benchmark/specs --results benchmark_results.json --out l4_results.json
```

`compare_bench.py` checks L1/L3 (from `benchmark_results.json`) and L4 (from
`l4_results.json`) against `benchmark/manifest.csv`.

## Repair loop — FPSR / ARI / RSR / TSR

```powershell
# LLM-driven repair (DeepSeek-chat). Set your key as an environment variable;
# never commit the key.
$env:DEEPSEEK_API_KEY = "sk-..."
python repair_loop.py --jar D:/TLA/tla2tools.jar --specs benchmark/specs --model deepseek-chat --out repair_results.json
```

The paper reports the DeepSeek-chat run (`repair_results.json`); the
DeepSeek-reasoner and rule-based runs are provided in
`repair_results_reasoner.json` and `repair_results_rule.json` for reference.

## Corpus-scale validation

```powershell
git clone https://github.com/tlaplus/Examples.git
python run_scale.py --jar D:/TLA/tla2tools.jar --root ./Examples --timeout 30 --out-csv examples_scale.csv --out-json examples_scale.json
```

The same runner works on other corpora (e.g. SysMoBench); add `--lib
"path/to/libraries;path/to/CommunityModules"` when a corpus `EXTENDS`
community modules.

## Vacuity audit of the gold set

```powershell
python strong_eval.py
```

`strong_specs/` holds the six gold specifications with protocol-level
invariants (MajorityVote gains decision consistency; AlternatingBit gains bit
alignment). `strong_eval.py` shows each semantic mutant is caught (L4 = 5).

## Notes

- `tla2tools.jar` is assumed at `D:/TLA/tla2tools.jar`; adjust `--jar` to your
  local path.
- Terminating gold specs (Counter, TwoPhaseCommit, MajorityVote) carry an
  explicit `Done` self-loop so TLC does not misreport intended termination as a
  deadlock.
- TLC may leave `*_TTrace_*.bin` viewer traces next to a spec after finding a
  deadlock/counterexample; they are harmless and ignored by the runners.

## License

MIT — see `LICENSE`.
