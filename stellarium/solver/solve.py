from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

from stellarium.encoding.ip_encoder import IPEncoder
from stellarium.encoding.sat_encoder import SATEncoder
from stellarium.encoding.smt_encoder import SMTEncoder
from stellarium.puzzle.types import Instance, StarType


@dataclass
class SolveResult:
    satisfiable: bool
    solution: Optional[List[int]]
    decisions: Optional[int]
    solve_time: float
    n_clauses: Optional[int]
    n_constraints: Optional[int]
    n_vars: Optional[int]
    nodes: Optional[int]
    encoding: str
    solver: str


def solve(
    instance: Instance,
    encoding: Literal["sat", "smt", "ip"] = "sat",
    solver_name: str = "Cadical103",
) -> SolveResult:
    """Solve via SAT (CaDiCaL/Minisat22), SMT (Z3), or IP (Gurobi).

    solver_name is honoured only when encoding="sat".
    """
    if encoding == "sat":
        enc = SATEncoder(instance, solver_name=solver_name)
        r = enc.solve()
        return SolveResult(
            satisfiable=r.satisfiable,
            solution=r.solution,
            decisions=r.decisions,
            solve_time=r.solve_time,
            n_clauses=r.n_clauses,
            n_constraints=None,
            n_vars=None,
            nodes=None,
            encoding="sat",
            solver=solver_name,
        )
    if encoding == "smt":
        enc = SMTEncoder(instance)
        r = enc.solve()
        return SolveResult(
            satisfiable=r.satisfiable,
            solution=r.solution,
            decisions=None,
            solve_time=r.solve_time,
            n_clauses=None,
            n_constraints=r.n_constraints,
            n_vars=None,
            nodes=None,
            encoding="smt",
            solver="Z3",
        )
    if encoding == "ip":
        enc = IPEncoder(instance)
        r = enc.solve()
        return SolveResult(
            satisfiable=r.satisfiable,
            solution=r.solution,
            decisions=None,
            solve_time=r.solve_time,
            n_clauses=None,
            n_constraints=r.n_constraints,
            n_vars=r.n_vars,
            nodes=r.nodes,
            encoding="ip",
            solver="Gurobi",
        )
    raise ValueError(f"Unknown encoding: {encoding}")


def check_unique(
    instance: Instance,
    first_solution: List[int],
    encoding: Literal["sat", "smt", "ip"] = "sat",
    solver_name: str = "Cadical103",
) -> bool:
    """True iff first_solution is the unique solution (blocking clause + UNSAT)."""
    if encoding == "sat":
        enc = SATEncoder(instance, solver_name=solver_name)
        r = enc.solve_with_blocking(first_solution)
        return not r.satisfiable
    if encoding == "smt":
        enc = SMTEncoder(instance)
        r = enc.solve_with_blocking(first_solution)
        return not r.satisfiable
    if encoding == "ip":
        enc = IPEncoder(instance)
        r = enc.solve_with_blocking(first_solution)
        return not r.satisfiable
    raise ValueError(f"Unknown encoding: {encoding}")


def verify_solution(instance: Instance, solution: List[int]) -> Tuple[bool, str]:
    selected = set(solution)
    edge_ids = {e.id for e in instance.edges}
    unknown = selected - edge_ids
    if unknown:
        return False, f"solution references unknown edge ids: {sorted(unknown)}"

    adj = instance.adjacency()
    for star in instance.stars:
        deg = sum(1 for eid in adj.get(star.id, []) if eid in selected)
        if star.star_type == StarType.ANCHOR and deg != 2:
            return False, f"anchor star {star.id} has degree {deg}, expected 2"
        if star.star_type == StarType.RELAY and deg != 1:
            return False, f"relay star {star.id} has degree {deg}, expected 1"
        if star.star_type == StarType.DIM and deg != 0:
            return False, f"dim star {star.id} has degree {deg}, expected 0"

    for e1, e2 in instance.crossing_pairs():
        if e1 in selected and e2 in selected:
            return False, f"selected edges {e1} and {e2} cross"

    return True, "ok"
