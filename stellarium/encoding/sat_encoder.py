from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from pysat.card import CardEnc, EncType
from pysat.formula import CNF
from pysat.solvers import Solver

from stellarium.puzzle.types import Instance, StarType


@dataclass
class SATResult:
    satisfiable: bool
    solution: Optional[List[int]]
    decisions: int
    solve_time: float
    n_clauses: int


class SATEncoder:
    def __init__(self, instance: Instance, solver_name: str = "Cadical103"):
        self.instance = instance
        self.solver_name = solver_name
        # PySAT variables are 1-indexed.
        self.edge_var = {e.id: idx + 1 for idx, e in enumerate(instance.edges)}
        self.var_to_edge = {v: k for k, v in self.edge_var.items()}
        self.n_edge_vars = len(instance.edges)
        self._cnf: Optional[CNF] = None

    def edge_to_var(self, edge_id: int) -> int:
        return self.edge_var[edge_id]

    def build_formula(self) -> CNF:
        cnf = CNF()
        # Track top variable so CardEnc auxiliary variables don't collide.
        top = self.n_edge_vars

        adj = self.instance.adjacency()

        for star in self.instance.stars:
            incident_edge_ids = adj.get(star.id, [])
            lits = [self.edge_var[eid] for eid in incident_edge_ids]

            if star.star_type == StarType.DIM:
                for v in lits:
                    cnf.append([-v])
            else:
                bound = 2 if star.star_type == StarType.ANCHOR else 1

                if not lits or len(lits) < bound:
                    cnf.append([])
                    continue

                card = CardEnc.equals(
                    lits=lits,
                    bound=bound,
                    top_id=top,
                    encoding=EncType.seqcounter,
                )
                cnf.extend(card.clauses)
                if card.nv > top:
                    top = card.nv

        for e1, e2 in self.instance.crossing_pairs():
            cnf.append([-self.edge_var[e1], -self.edge_var[e2]])

        cnf.nv = max(top, cnf.nv if cnf.nv else 0)
        self._cnf = cnf
        return cnf

    def decode_model(self, model: List[int]) -> List[int]:
        true_vars = {abs(lit) for lit in model if lit > 0}
        return sorted(
            edge_id for edge_id, var in self.edge_var.items() if var in true_vars
        )

    def solve(self) -> SATResult:
        cnf = self.build_formula()
        return self._solve_cnf(cnf, extra_clauses=None)

    def _solve_cnf(
        self, cnf: CNF, extra_clauses: Optional[List[List[int]]]
    ) -> SATResult:
        solver = Solver(name=self.solver_name, bootstrap_with=cnf.clauses)
        if extra_clauses:
            for cl in extra_clauses:
                solver.add_clause(cl)

        has_empty = any(len(c) == 0 for c in cnf.clauses)

        start = time.perf_counter()
        sat = False if has_empty else solver.solve()
        elapsed = time.perf_counter() - start

        decisions = 0
        try:
            stats = solver.accum_stats()
            if isinstance(stats, dict):
                decisions = int(stats.get("decisions", 0))
        except Exception:
            decisions = 0

        solution: Optional[List[int]] = None
        if sat:
            model = solver.get_model() or []
            solution = self.decode_model(model)

        n_clauses = len(cnf.clauses) + (len(extra_clauses) if extra_clauses else 0)
        solver.delete()

        return SATResult(
            satisfiable=bool(sat),
            solution=solution,
            decisions=decisions,
            solve_time=elapsed,
            n_clauses=n_clauses,
        )

    def solve_with_blocking(self, blocked_solution: List[int]) -> SATResult:
        cnf = self.build_formula()
        blocking_clause = self._make_blocking_clause(blocked_solution)
        return self._solve_cnf(cnf, extra_clauses=[blocking_clause])

    def _make_blocking_clause(self, blocked_solution: List[int]) -> List[int]:
        selected = set(blocked_solution)
        clause: List[int] = []
        for edge_id, var in self.edge_var.items():
            if edge_id in selected:
                clause.append(-var)
            else:
                clause.append(var)
        return clause
