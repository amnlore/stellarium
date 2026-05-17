from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import z3

from stellarium.puzzle.types import Instance, StarType


@dataclass
class SMTResult:
    satisfiable: bool
    solution: Optional[List[int]]
    solve_time: float
    n_constraints: int


class SMTEncoder:
    def __init__(self, instance: Instance):
        self.instance = instance
        self.edge_var = {e.id: z3.Bool(f"e_{e.id}") for e in instance.edges}

    def build_solver(self) -> Tuple[z3.Solver, int]:
        solver = z3.Solver()
        n_constraints = 0
        adj = self.instance.adjacency()

        for star in self.instance.stars:
            lits = [self.edge_var[eid] for eid in adj.get(star.id, [])]
            if star.star_type == StarType.DIM:
                for v in lits:
                    solver.add(z3.Not(v))
                    n_constraints += 1
            else:
                if star.star_type == StarType.ANCHOR:
                    k = 2
                else:
                    k = 1
                if not lits:
                    solver.add(z3.BoolVal(False))
                    n_constraints += 1
                    continue
                solver.add(z3.PbEq([(v, 1) for v in lits], k))
                n_constraints += 1

        for e1, e2 in self.instance.crossing_pairs():
            solver.add(z3.Not(z3.And(self.edge_var[e1], self.edge_var[e2])))
            n_constraints += 1

        return solver, n_constraints

    def decode_model(self, model: z3.ModelRef) -> List[int]:
        selected: List[int] = []
        for edge_id, var in self.edge_var.items():
            val = model.eval(var, model_completion=True)
            if z3.is_true(val):
                selected.append(edge_id)
        return sorted(selected)

    def solve(self) -> SMTResult:
        solver, n_constraints = self.build_solver()
        start = time.perf_counter()
        check = solver.check()
        elapsed = time.perf_counter() - start
        if check == z3.sat:
            return SMTResult(
                satisfiable=True,
                solution=self.decode_model(solver.model()),
                solve_time=elapsed,
                n_constraints=n_constraints,
            )
        return SMTResult(
            satisfiable=False,
            solution=None,
            solve_time=elapsed,
            n_constraints=n_constraints,
        )

    def solve_with_blocking(self, blocked_solution: List[int]) -> SMTResult:
        solver, n_constraints = self.build_solver()
        selected = set(blocked_solution)
        disjuncts: List[z3.BoolRef] = []
        for edge_id, var in self.edge_var.items():
            if edge_id in selected:
                disjuncts.append(z3.Not(var))
            else:
                disjuncts.append(var)
        if disjuncts:
            solver.add(z3.Or(*disjuncts))
            n_constraints += 1
        else:
            solver.add(z3.BoolVal(False))
            n_constraints += 1

        start = time.perf_counter()
        check = solver.check()
        elapsed = time.perf_counter() - start
        if check == z3.sat:
            return SMTResult(
                satisfiable=True,
                solution=self.decode_model(solver.model()),
                solve_time=elapsed,
                n_constraints=n_constraints,
            )
        return SMTResult(
            satisfiable=False,
            solution=None,
            solve_time=elapsed,
            n_constraints=n_constraints,
        )
