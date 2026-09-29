# FPGA Benchmark System

This repository now includes a minimal benchmark system for the single-FPGA line.

## Goals

1. Turn generation quality into a scored, repeatable suite.
2. Keep benchmark cases open, file-based, and easy to review.
3. Reuse the existing task service and workflow instead of introducing a second execution stack.

## Case Layout

Each case lives in its own directory and contains at least:

1. task.md
2. benchmark_case.json
3. Optional sibling interface contract such as task.interface.v
4. Optional `oracle_tb.v`, referenced by `oracle_testbench` in the case JSON

The benchmark_case.json file defines the task kind and scoring expectations.

When `oracle_testbench` is present, the runner never injects that file into the Agent prompt. It first lets the Agent complete its normal RTL/TB flow, then runs the generated RTL against the independent oracle. Scores use this hidden result and preserve the Agent-authored TB result separately as `self_eda_summary`.

## Current Scoring Model

The runner scores each case against active expectations and normalizes the result to 100.

Current checks include:

1. Task execution status
2. overall_pass
3. simulation_passed
4. synthesis_passed
5. repair attempt budget
6. required artifact presence
7. forbidden precheck substring absence

## Running a Suite

Example:

```powershell
python -m digital_ic_agent benchmark-run --suite-dir benchmarks/fpga --output-dir runs/benchmark_fpga
```

Competition blind suite:

```powershell
python -m digital_ic_agent benchmark-run --suite-dir benchmarks/blind_v1 --output-dir runs/blind_v1
```

`blind_v1` contains five categories: combinational ALU, overlapping FSM, synchronous FIFO, SPI controller, and saturating-counter repair.

This writes:

1. benchmark_report.json
2. benchmark_report.md
3. One output directory per benchmark case

## Design Intent

This benchmark system is intentionally narrow:

1. Focus on the FPGA line first.
2. Prefer small, reviewable cases before complex system-level crypto benchmarks.
3. Let recurring benchmark failures feed the adaptive feedback memory so prompt constraints improve over time.

## Recommended Next Benchmark Layers

1. Interface-contract micro-cases
2. FSM and handshake holding cases
3. Width and carry propagation cases
4. RAM/FIFO inference cases
5. TB stimulus discipline cases
6. Crypto-control-shell cases
