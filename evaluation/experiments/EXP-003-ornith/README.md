# EXP-003: Ornith-9B Local Feasibility Study

This directory contains the experimental design, harness, and scripts for evaluating the local feasibility of **Ornith-9B** on an Apple Silicon M1 (8 GB Unified Memory).

## Files

* `EXPERIMENT_DESIGN.md`: The formal protocol covering objectives, four experimental phases, measurement metrics, and research decision criteria.
* `run_feasibility.py`: The automated test runner executing Phase 2 (progressive context & swap profiling) and Phase 3 (minimal capability smoke test).
* `README.md`: Directory overview and execution instructions.

## Execution

To execute the feasibility study:
```bash
python3 evaluation/experiments/EXP-003-ornith/run_feasibility.py
```

The runner will save raw measurements to:
`evaluation/results/EXP-003_feasibility.json`

And generate the evaluation report at:
`evaluation/reports/EXP-003_feasibility.md`
