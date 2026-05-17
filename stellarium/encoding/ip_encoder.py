"""Integer-programming encoding of Stellarium puzzles using Gurobi.

One binary variable per edge. Per-star degree constraints are linear sums
over incident edges (== 2 for ANCHOR, == 1 for RELAY, == 0 for DIM). Per
crossing pair (e1, e2): x_{e1} + x_{e2} <= 1. Objective is constant 0
(feasibility only). ``solve_with_blocking`` adds a no-good cut
``sum_{e in S}(1 - x_e) + sum_{e not in S} x_e >= 1`` that forbids exactly
the assignment ``S``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import gurobipy as gp
from gurobipy import GRB

from stellarium.puzzle.types import Instance, StarType


@dataclass
class IPResult:
    satisfiable: bool
    solution: Optional[List[int]]
    solve_time: float
    n_vars: int
    n_constraints: int
    nodes: int


class IPEncoder:
    def __init__(self, instance: Instance):
        self.instance = instance

    def _build_model(self) -> Tuple[gp.Model, dict]:
        model = gp.Model("stellarium")
        model.setParam("OutputFlag", 0)
        # Single thread to match single-threaded SAT/SMT comparisons.
        model.setParam("Threads", 1)

        edge_to_var = {
            e.id: model.addVar(vtype=GRB.BINARY, name=f"e_{e.id}")
            for e in self.instance.edges
        }
        model.update()

        adj = self.instance.adjacency()
        for star in self.instance.stars:
            incident = adj.get(star.id, [])
            lhs = gp.quicksum(edge_to_var[eid] for eid in incident) if incident else 0
            if star.star_type == StarType.ANCHOR:
                model.addConstr(lhs == 2, name=f"deg_anchor_{star.id}")
            elif star.star_type == StarType.RELAY:
                model.addConstr(lhs == 1, name=f"deg_relay_{star.id}")
            else:
                model.addConstr(lhs == 0, name=f"deg_dim_{star.id}")

        for e1, e2 in self.instance.crossing_pairs():
            model.addConstr(
                edge_to_var[e1] + edge_to_var[e2] <= 1,
                name=f"cross_{e1}_{e2}",
            )

        model.setObjective(0, GRB.MINIMIZE)
        return model, edge_to_var

    def _decode(self, edge_to_var: dict) -> List[int]:
        return sorted(eid for eid, var in edge_to_var.items() if var.X > 0.5)

    def solve(self) -> IPResult:
        model, edge_to_var = self._build_model()
        start = time.perf_counter()
        model.optimize()
        elapsed = time.perf_counter() - start
        sat = model.Status in (GRB.OPTIMAL, GRB.SUBOPTIMAL)
        solution = self._decode(edge_to_var) if sat else None
        return IPResult(
            satisfiable=sat,
            solution=solution,
            solve_time=elapsed,
            n_vars=int(model.NumVars),
            n_constraints=int(model.NumConstrs),
            nodes=int(model.NodeCount),
        )

    def solve_with_blocking(self, blocked_solution: List[int]) -> IPResult:
        model, edge_to_var = self._build_model()
        selected = set(blocked_solution)
        terms = []
        for eid, var in edge_to_var.items():
            if eid in selected:
                terms.append(1 - var)
            else:
                terms.append(var)
        if terms:
            model.addConstr(gp.quicksum(terms) >= 1, name="block")
        else:
            model.addConstr(gp.LinExpr() >= 1, name="block_empty")

        start = time.perf_counter()
        model.optimize()
        elapsed = time.perf_counter() - start
        sat = model.Status in (GRB.OPTIMAL, GRB.SUBOPTIMAL)
        solution = self._decode(edge_to_var) if sat else None
        return IPResult(
            satisfiable=sat,
            solution=solution,
            solve_time=elapsed,
            n_vars=int(model.NumVars),
            n_constraints=int(model.NumConstrs),
            nodes=int(model.NodeCount),
        )
