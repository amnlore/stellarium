# Stellarium

A new constellation-themed planar puzzle, three encodings (SAT, SMT, IP), a procedural generator, a 100-instance benchmark suite, and a comparison study. Final project for CS498 Algorithmic Engineering (UIUC, Spring 2026, Track C: Solve a New Problem).

## The puzzle

An instance is a straight-line graph in the unit square. Every star has one of three types, each fixing its required edge count:

- **Anchor** — degree exactly 2
- **Relay**  — degree exactly 1
- **Dim**    — degree exactly 0

Pick a subset of edges so that (i) every star meets its degree and (ii) no two selected segments cross. A *valid* instance has exactly one such subset.

## Three encodings of the same problem

One Boolean per edge `x_e`. The constraints are identical in spirit, but each backend expresses them differently:

| Backend | Library          | Cardinality                 | Crossing pair       | File                              |
|---------|------------------|-----------------------------|---------------------|-----------------------------------|
| SAT     | PySAT + CaDiCaL  | `CardEnc.equals` seqcounter | binary clause       | `stellarium/encoding/sat_encoder.py` |
| SMT     | Z3               | `PbEq`                      | `Not(And(...))`     | `stellarium/encoding/smt_encoder.py` |
| IP      | Gurobi           | linear `==` equality        | `x_i + x_j <= 1`    | `stellarium/encoding/ip_encoder.py`  |

Each encoder exposes `solve()` and `solve_with_blocking(prev_solution)`. The latter adds a no-good cut that forbids exactly `prev_solution`, which is the primitive both the generator and the uniqueness checker use.

A unified entry point `stellarium.solver.solve.solve(instance, encoding=...)` returns a single `SolveResult` dataclass with timing, decisions/nodes, model size, and the recovered solution.

## The generator (solution-first + SAT-blocking shrink)

`stellarium/puzzle/generator.py` produces uniquely-solvable instances. Rather than typing a random graph and rejecting multi-solution ones, it:

1. Samples a Delaunay-triangulated planar graph from `n` random points.
2. Samples a random linear forest `M` (every vertex has `M`-degree 0/1/2).
3. Types each vertex from its `M`-degree, so `M` is a valid solution by construction.
4. Iteratively asks the SAT oracle for *another* solution while blocking `M`. Each time it gets one, deletes a random decoy edge from the alternate solution. `M` is never touched, so the solution set shrinks monotonically until the SAT call returns UNSAT.
5. Records `solver_decisions` from the final unblocked SAT call (used for difficulty bucketing).

The acceptance experiment in the report shows this succeeds on the first attempt 100% of the time across all five size classes.

## Repository layout

```
stellarium/
  puzzle/
    types.py            Star, Edge, Instance dataclasses; orientation-based crossing test
    generator.py        Solution-first generate-and-shrink pipeline
  encoding/
    sat_encoder.py      PySAT CNF encoder (CaDiCaL / Minisat22)
    smt_encoder.py      Z3 PbEq encoder
    ip_encoder.py       Gurobi IP encoder
  solver/
    solve.py            Unified solve() + uniqueness checker + verify_solution()
  benchmark/
    generate_suite.py   Build 100 instances (20 each: XS, S, M, L, XL)
    instances/          The 100 generated JSON instances
  experiments/
    run_experiments.py  Encoding, solver, difficulty, acceptance experiments
    make_figures.py     Generate the six PDF/PNG plots
    results/            CSVs of every experiment
    figures/            Plot outputs
  visualizer/           Matplotlib renderer for spot-checks
  web/                  Static browser frontend with an animated JS solver
  tests/                pytest suite (24 tests)
```

### Generate a single instance

```python
from stellarium.puzzle.generator import generate_instance
inst = generate_instance(n=20, size_class="S", instance_id="demo", seed=42, verbose=True)
print(inst.solution)
```

### Solve with each backend

```python
from stellarium.solver.solve import solve
for enc, slv in [("sat", "Cadical103"), ("smt", "Z3"), ("ip", "Gurobi")]:
    r = solve(inst, encoding=enc, solver_name=slv)
    print(f"{enc:3s}/{slv:10s}  {r.solve_time*1e6:7.1f} us  solution={r.solution}")
```

### Verify a solution standalone

```python
from stellarium.solver.solve import verify_solution
ok, msg = verify_solution(inst, inst.solution)
assert ok, msg
```

## Reproducing the report

Each step is one command from the repository root.

```bash
# 1. Regenerate the 100-instance benchmark (deterministic; seed=42; ~1-2 min)
python -m stellarium.benchmark.generate_suite

# 2. Run all four experiments (writes CSVs to stellarium/experiments/results/)
python -m stellarium.experiments.run_experiments

# 3. Regenerate the six figures (writes PDFs/PNGs to stellarium/experiments/figures/)
python -m stellarium.experiments.make_figures

# 4. Run the test suite (24 tests)
pytest stellarium/tests/ -v
```

The four experiments and what they produce:

| Experiment             | Output CSV                       | Figures                  |
|------------------------|----------------------------------|--------------------------|
| Encoding comparison    | `encoding_comparison.csv`        | `fig1`, `fig2`, `fig5`   |
| Solver comparison      | `solver_comparison.csv`          | `fig3`                   |
| Difficulty regression  | `difficulty_analysis.csv`, `regression_coefficients.csv` | `fig6` |
| Generator acceptance   | `acceptance_rate.csv`            | `fig4`                   |

## Web frontend

```bash
cd stellarium/web
python -m http.server 8000
# open http://localhost:8000
```

`build_instances.py` pre-bakes the suite into `instances.js` so the page loads with no backend. `solver.js` is a hand-written DPLL-style solver that animates unit propagation on the chosen puzzle.

