# TLA-Trust: Vacuity-aware TLA+ Evaluation Harness

This repository contains the reference implementation for the manuscript "Towards Trustworthy TLA+ Specification and Verification".

## Features
- Computes FPSR, ARI, RSR, and TSR metrics (Eqs. 8--11 in the paper).
- Implements the L1--L4 four-tier quality rubric.
- Includes an Alloy/Kodkod XML to TLA+ bridge.
- Automated mutation testing for property vacuity (L4).

## Quick Start
```bash
# Evaluate the 24-task benchmark
python tlatrust.py eval --tasks tasks.json# TLA-Trust
