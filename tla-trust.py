"""
TLA-Trust -- reference implementation of the vacuity-aware TLA+ evaluation
harness described in the manuscript "Towards Trustworthy TLA+ Specification
and Verification".

This single-file prototype implements:

  * the L1--L4 four-tier quality rubric (Eq. "trust indicator" in the paper);
  * the FPSR / ARI / RSR / TSR closed-loop repair metrics;
  * automated deadlock-vacuity scoring (L3) and mutation-based property-vacuity
    detection (L4);
  * a Kodkod / Alloy XML instance -> TLA+ CONSTANTS + Init bridge.

It is intentionally dependency-free (Python >= 3.9, standard library only) so
the metrics and bridge layers run without installation:

    python tlatrust.py eval    --tasks tasks.json
    python tlatrust.py bridge  --kodkod instance.xml --out Spec.tla
    python tlatrust.py mutants --spec module.tla --out-dir mutants/

External verifiers (SANY, Snowcat, TLC, Apalache) can be wired in through the
`--tla2tools` jar path; otherwise the harness consumes pre-computed JSON
results, which keeps the metric layer fully runnable offline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class LevelScores:
    """Four-tier quality scores for a single specification."""

    L1: int = 0  
    L2: int = 1   
    L3: int = 1  
    L4: int = 1   

    @property
    def trustworthy(self) -> bool:
        return self.L1 == 1 and self.L2 >= 4 and self.L3 >= 4 and self.L4 >= 4

    @classmethod
    def from_dict(cls, d: Dict) -> "LevelScores":
        return cls(
            L1=int(d.get("L1", 0)),
            L2=int(d.get("L2", 1)),
            L3=int(d.get("L3", 1)),
            L4=int(d.get("L4", 1)),
        )


def l3_score(state_count: int, action_coverage: int, deadlock: bool) -> int:
    """Map a TLC run summary onto the L3 behavioral-fidelity score (1-5).

    L3 >= 4 is the paper's explicit anti-vacuity gate: the run must explore
    more than one distinct state, with non-zero action coverage and no
    unintended deadlock.
    """
    if state_count <= 1 or deadlock:
        return 1
    if state_count > 1 and action_coverage == 0:
        return 3
    if state_count >= 6:
        return 5
    return 4


def l4_score(mutant_killed: int, mutant_total: int) -> int:
    """Map mutation-testing results onto the L4 property-adequacy score (1-5).

    L4 >= 4 requires the invariant to reject a high fraction of injected AST
    mutants, penalizing tautological (TRUE-equivalent) invariants.
    """
    if mutant_total <= 0:
        return 1
    ratio = mutant_killed / mutant_total
    if ratio >= 0.8:
        return 5
    if ratio >= 0.5:
        return 4
    if ratio >= 0.25:
        return 3
    return 2


@dataclass
class TaskResult:
    id: str
    init: LevelScores
    final: LevelScores
    iterations: int = 0

    @property
    def repaired(self) -> bool:
        return (not self.init.trustworthy) and self.final.trustworthy


def _trust_frac(tasks: Sequence[TaskResult], stage: str) -> float:
    n = len(tasks)
    if n == 0:
        return 0.0
    return sum(1 for t in tasks if getattr(t, stage).trustworthy) / n


def compute_metrics(
    tasks: Sequence[TaskResult], iteration_cap: int = 5
) -> Dict[str, float]:
    """Return FPSR, ARI_succ, ARI_all, RSR, TSR plus a conservation check."""
    n = len(tasks)
    if n == 0:
        return {"FPSR": 0.0, "ARI_succ": 0.0, "ARI_all": 0.0,
                "RSR": 0.0, "TSR": 0.0, "conservation_ok": True}

    fpsr = _trust_frac(tasks, "init")
    failures = [t for t in tasks if not t.init.trustworthy]
    repaired = [t for t in failures if t.final.trustworthy]

    ari_succ = (
        sum(t.iterations for t in repaired) / len(repaired)
        if repaired
        else 0.0
    )
    ari_all = (
        sum(
            t.iterations if t.final.trustworthy else iteration_cap
            for t in failures
        )
        / len(failures)
        if failures
        else 0.0
    )
    rsr = len(repaired) / len(failures) if failures else 0.0
    tsr = _trust_frac(tasks, "final")

    check = abs(tsr - (fpsr + (1.0 - fpsr) * rsr)) < 1e-9
    return {
        "FPSR": fpsr,
        "ARI_succ": ari_succ,
        "ARI_all": ari_all,
        "RSR": rsr,
        "TSR": tsr,
        "conservation_ok": check,
    }


@dataclass(frozen=True)
class Mutator:
    name: str
    pattern: "re.Pattern[str]"
    replacement: str


_MUTATORS: List[Mutator] = [

    Mutator("flip_neq", re.compile(r"/="), "="),
    Mutator("flip_eq", re.compile(r"(?<![=<>!/])=(?!=)"), "/="),
    Mutator("flip_le", re.compile(r"(?<![=<>!])<="), ">="),
    Mutator("flip_ge", re.compile(r"(?<![=<>!])>="), "<="),
    Mutator("flip_lt", re.compile(r"(?<![=<>!])<(?!=)"), ">"),
    Mutator("flip_gt", re.compile(r"(?<![=<>!])>(?!=)"), "<"),
  
    Mutator("flip_in", re.compile(r"\\in(?![A-Za-z])"), r"\notin"),
    Mutator("flip_notin", re.compile(r"\\notin(?![A-Za-z])"), r"\in"),
   
    Mutator(
        "drop_unchanged",
        re.compile(r"UNCHANGED\s+[A-Za-z_][A-Za-z0-9_,\s]*"),
        "TRUE",
    ),
]


def generate_mutants(spec: str, max_mutants: int = 16) -> List[Tuple[str, str]]:
    """Return (mutator_name, mutated_spec) pairs applied at the first match.

    This is the lightweight reference implementation; the manuscript positions
    mutation testing as a deterministic gate, so a production deployment should
    use a real TLA+ AST (e.g., SANY's parse tree) rather than textual regexes.
    """
    mutants: List[Tuple[str, str]] = []
    for m in _MUTATORS:
        if len(mutants) >= max_mutants:
            break
        if m.pattern.search(spec):
            mutants.append((m.name, m.pattern.sub(m.replacement, spec, count=1)))
    return mutants

def _sanitize(atom_label: str) -> str:
    """Map an Alloy/Kodkod atom label to a TLA+ identifier fragment."""
    frag = atom_label.split("/")[-1]
    return frag.replace("$", "_").replace("-", "_")


def _role(rel_label: str) -> str:
    """Extract the field 'role' name (last segment after '$' or '/')."""
    frag = rel_label.split("$")[-1].split("/")[-1]
    return frag.replace("-", "_")


def _atom_label(atom_el: ET.Element) -> str:
    return atom_el.get("label", "")


def _tla_value(atom_label: str) -> str:
    return '"{}"'.format(atom_label.replace('"', '\\"'))


def kodkod_to_tla(
    xml_text: str, schema: Optional[Dict[str, List[str]]] = None
) -> str:
    """Parse an Alloy/Kodkod XML instance and emit TLA+ constants + Init.

    Supports the two common shapes emitted by the Alloy Analyzer:
      * Alloy XML: `<sig label="...">` containing `<atom>` children, and
        `<field label="...">` containing `<tuple>` children.
      * Kodkod XML: top-level `<atom>` and `<relation>`/`<tuple>` elements.

    Unary relations become set-valued CONSTANTS; n-ary relations become sets of
    TLA+ records (when ``schema`` supplies the field/role names) or sets of
    TLA+ tuples otherwise. A trailing comment shows how to seed a state
    variable from the snapshot, since variable names are chosen by the
    specifier rather than by the bridge.
    """
    schema = schema or {}
    root = ET.fromstring(xml_text)

    sig_atoms: Dict[str, List[str]] = {}
    for sig in root.iter("sig"):
        label = sig.get("label", "")
        if not label:
            continue
        atoms = [a.get("label", "") for a in sig.iter("atom") if a.get("label")]
        if atoms:
            sig_atoms.setdefault(label, [])
            for a in atoms:
                if a not in sig_atoms[label]:
                    sig_atoms[label].append(a)

    relations: Dict[str, List[Tuple[str, ...]]] = {}
    for field_el in root.iter("field"):
        label = field_el.get("label", "")
        if not label:
            continue
        tuples = []
        for tup in field_el.iter("tuple"):
            atoms = tuple(a.get("label", "") for a in tup.iter("atom"))
            if atoms and all(atoms):
                tuples.append(atoms)
        if tuples:
            relations.setdefault(label, [])
            for t in tuples:
                if t not in relations[label]:
                    relations[label].append(t)

    if not relations:
        for rel in root.iter("relation"):
            label = rel.get("label", "") or rel.get("name", "")
            if not label:
                continue
            tuples = []
            for tup in rel.iter("tuple"):
                atoms = tuple(a.get("label", "") for a in tup.iter("atom"))
                if atoms and all(atoms):
                    tuples.append(atoms)
            if tuples:
                relations.setdefault(label, [])
                for t in tuples:
                    if t not in relations[label]:
                        relations[label].append(t)

    header: List[str] = [
        r"\* ---- Auto-generated by TLA-Trust Alloy->TLA+ bridge ----",
        r"\* Static relational snapshot (SAT-certified by Alloy/Kodkod)",
        "",
    ]

    constants: Dict[str, str] = {}
    guidance: List[str] = []

    for sig_label in sorted(sig_atoms):
        name = _sanitize(sig_label)
        elems = ", ".join(_tla_value(a) for a in sorted(set(sig_atoms[sig_label])))
        constants[name] = f"{name} == {{{elems}}}"

    for rel_label in sorted(relations):
        name = _sanitize(rel_label)
        tuples = relations[rel_label]
        if all(len(t) == 1 for t in tuples):

            elems = ", ".join(_tla_value(t[0]) for t in tuples)
            constants[name] = f"{name} == {{{elems}}}"
        else:
           
            fields = schema.get(rel_label) or schema.get(name)
            if fields and all(len(t) == len(fields) for t in tuples):
                records = ", ".join(
                    "[" + ", ".join(
                        f"{_sanitize(fields[j])} |-> {_tla_value(a)}"
                        for j, a in enumerate(t)
                    ) + "]"
                    for t in tuples
                )
                constants[name] = f"{name} == {{{records}}}"
            else:
                tla_tuples = ", ".join(
                    "<<" + ", ".join(_tla_value(a) for a in t) + ">>"
                    for t in tuples
                )
                constants[name] = f"{name} == {{{tla_tuples}}}"
            guidance.append(r"\* Seed a state variable from the snapshot, e.g.:")
            guidance.append(rf"\* VARIABLES {name}_state")
            guidance.append(rf"\* Init == /\ {name}_state = {name}")

    lines = list(header)
    if constants:
        lines.append("CONSTANTS " + ", ".join(sorted(constants)))
        lines.append("")
        for name in sorted(constants):
            lines.append(constants[name])
            lines.append("")

    if guidance:
        lines.append("")
        lines.extend(guidance)

    return "\n".join(lines).rstrip() + "\n"

def _load_tasks(path: Path) -> List[TaskResult]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = []
    for raw in data.get("tasks", []):
        if "task" in raw and "cand" in raw:
            task_id = f"{raw['task']}-{raw['cand']}"
            init_dict = {
                "L1": raw.get("L1", 0),
                "L2": raw.get("L2", 1),
                "L3": raw.get("L3", 1),
                "L4": raw.get("L4", 1)
            }
            final_dict = {
                "L1": raw.get("final_L1", 0),
                "L2": raw.get("final_L2", 1),
                "L3": raw.get("final_L3", 1),
                "L4": raw.get("final_L4", 1)
            }
            iterations = int(raw.get("repair_rounds", 0))
        else:
            task_id = raw.get("id", "Unknown")
            init_dict = raw.get("init", {})
            final_dict = raw.get("final", {})
            iterations = int(raw.get("iterations", 0))

        tasks.append(
            TaskResult(
                id=task_id,
                init=LevelScores.from_dict(init_dict),
                final=LevelScores.from_dict(final_dict),
                iterations=iterations,
            )
        )
    return tasks


def _cmd_eval(args: argparse.Namespace) -> int:
    tasks = _load_tasks(Path(args.tasks))
    metrics = compute_metrics(tasks, args.cap)
    print(json.dumps(metrics, indent=2))
    return 0


def _cmd_mutants(args: argparse.Namespace) -> int:
    spec = Path(args.spec).read_text(encoding="utf-8")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, (name, mutated) in enumerate(generate_mutants(spec, args.max_mutants)):
        (out_dir / f"{i:02d}_{name}.tla").write_text(mutated, encoding="utf-8")
        print(f"{out_dir / f'{i:02d}_{name}.tla'}")
    return 0


def _cmd_bridge(args: argparse.Namespace) -> int:
    xml_text = Path(args.kodkod).read_text(encoding="utf-8")
    schema = None
    if args.schema:
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    tla = kodkod_to_tla(xml_text, schema)
    out = Path(args.out)
    out.write_text(tla, encoding="utf-8")
    print(tla)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tlatrust",
        description="Vacuity-aware TLA+ evaluation harness (reference implementation).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("eval", help="compute FPSR/ARI/RSR/TSR from task results")
    e.add_argument("--tasks", required=True)
    e.add_argument("--cap", type=int, default=5)
    e.set_defaults(func=_cmd_eval)

    m = sub.add_parser("mutants", help="generate AST mutants for a module")
    m.add_argument("--spec", required=True)
    m.add_argument("--out-dir", required=True)
    m.add_argument("--max-mutants", type=int, default=16)
    m.set_defaults(func=_cmd_mutants)

    b = sub.add_parser("bridge", help="convert an Alloy/Kodkod instance to TLA+")
    b.add_argument("--kodkod", required=True)
    b.add_argument("--out", required=True)
    b.add_argument(
        "--schema",
        default=None,
        help="optional JSON mapping relation label -> field names",
    )
    b.set_defaults(func=_cmd_bridge)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
