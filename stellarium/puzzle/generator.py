"""Procedural generator for Stellarium puzzle instances.

Pipeline:
1. Sample n points uniformly in [0,1]^2 and compute the Delaunay triangulation.
2. Sample a random linear forest M: shuffle edges, admit each with probability
   p_keep if neither endpoint has reached degree 2. Each vertex's degree in M
   is then 0, 1, or 2.
3. Derive star types from M's degrees: 2 -> ANCHOR, 1 -> RELAY, 0 -> DIM.
   M is a valid solution by construction.
4. Iteratively call the SAT encoder with a blocking clause against M. While
   another solution alt exists, delete a random edge in alt \\ M. M is never
   touched, so it remains valid; each iteration strictly decreases the
   solution count. Terminates when blocking returns UNSAT.
5. Final unblocked SAT call records solver_decisions for difficulty bucketing.

Diversity comes from the planar sample, edge admission order, per-attempt
p_keep, and the random decoy removed at each step.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import Delaunay, QhullError

from stellarium.puzzle.types import Edge, Instance, Star, StarType


# Lower p_keep yields dim-heavy instances; higher p_keep yields anchor-heavy.
DEFAULT_P_KEEP_RANGE: Tuple[float, float] = (0.4, 0.85)

DEFAULT_MAX_SHRINK_ITERS = 2000


def sample_planar_graph(
    n: int, seed: Optional[int] = None
) -> Tuple[List[Star], List[Edge]]:
    """Sample n points uniformly in [0,1]^2; return stars + Delaunay edges."""
    rng = np.random.default_rng(seed)
    pts = rng.random(size=(n, 2))

    try:
        tri = Delaunay(pts)
    except QhullError:
        pts = pts + rng.normal(0, 1e-6, size=pts.shape)
        tri = Delaunay(pts)

    edge_set = set()
    for simplex in tri.simplices:
        a, b, c = int(simplex[0]), int(simplex[1]), int(simplex[2])
        for u, v in ((a, b), (b, c), (a, c)):
            if u == v:
                continue
            edge_set.add((min(u, v), max(u, v)))

    stars = [
        Star(id=i, x=float(pts[i, 0]), y=float(pts[i, 1]), star_type=StarType.DIM)
        for i in range(n)
    ]
    edges = [Edge(id=i, u=u, v=v) for i, (u, v) in enumerate(sorted(edge_set))]
    return stars, edges


def sample_random_solution(
    stars: List[Star],
    edges: List[Edge],
    p_keep: float,
    rng: random.Random,
) -> Tuple[List[int], Dict[int, int]]:
    """Sample a random linear forest M ⊆ edges (every vertex has degree ≤ 2).

    Returns (selected_edge_ids, degrees) where degrees[star.id] ∈ {0, 1, 2}.
    """
    if not 0.0 <= p_keep <= 1.0:
        raise ValueError(f"p_keep must be in [0, 1], got {p_keep}")

    degrees: Dict[int, int] = {s.id: 0 for s in stars}
    selected: List[int] = []

    order = list(edges)
    rng.shuffle(order)

    for e in order:
        if degrees[e.u] >= 2 or degrees[e.v] >= 2:
            continue
        if rng.random() >= p_keep:
            continue
        selected.append(e.id)
        degrees[e.u] += 1
        degrees[e.v] += 1

    return selected, degrees


_DEGREE_TO_TYPE = {
    0: StarType.DIM,
    1: StarType.RELAY,
    2: StarType.ANCHOR,
}


def types_from_degrees(
    stars: List[Star], degrees: Dict[int, int]
) -> List[Star]:
    """Map each star's degree (0/1/2) to a StarType (DIM/RELAY/ANCHOR)."""
    out: List[Star] = []
    for s in stars:
        d = degrees.get(s.id, 0)
        try:
            t = _DEGREE_TO_TYPE[d]
        except KeyError as exc:
            raise ValueError(
                f"vertex {s.id} has degree {d} in sampled solution; "
                f"expected 0, 1, or 2"
            ) from exc
        out.append(Star(id=s.id, x=s.x, y=s.y, star_type=t))
    return out


def shrink_to_unique(
    stars: List[Star],
    edges: List[Edge],
    sampled_solution: List[int],
    rng: random.Random,
    max_iters: int = DEFAULT_MAX_SHRINK_ITERS,
) -> Optional[List[Edge]]:
    """Remove non-M edges until the typed instance has M as its unique solution.

    Returns the pruned edges list once M is unique, or None if the iteration
    cap is hit.
    """
    from stellarium.encoding.sat_encoder import SATEncoder

    M_set = set(sampled_solution)
    cur_edges = list(edges)

    degrees = {s.id: 0 for s in stars}
    by_id = {e.id: e for e in cur_edges}
    for eid in sampled_solution:
        e = by_id[eid]
        degrees[e.u] += 1
        degrees[e.v] += 1
    typed_stars = types_from_degrees(stars, degrees)

    for _ in range(max_iters):
        candidate = Instance(
            id="_shrink", size_class="_shrink", stars=typed_stars, edges=cur_edges
        )
        result = SATEncoder(candidate).solve_with_blocking(sampled_solution)
        if not result.satisfiable:
            return cur_edges
        if result.solution is None:
            return None
        alt = set(result.solution)
        decoys = [e for e in cur_edges if e.id in alt and e.id not in M_set]
        if not decoys:
            return None
        to_remove = rng.choice(decoys)
        cur_edges = [e for e in cur_edges if e.id != to_remove.id]

    return None


def is_feasible(instance: Instance) -> bool:
    """Necessary feasibility check: each non-dim star has enough non-dim incident edges."""
    dim_stars = {s.id for s in instance.stars if s.star_type == StarType.DIM}
    non_dim_neighbors_count = {s.id: 0 for s in instance.stars}
    for e in instance.edges:
        if e.u in dim_stars or e.v in dim_stars:
            continue
        non_dim_neighbors_count[e.u] += 1
        non_dim_neighbors_count[e.v] += 1

    for star in instance.stars:
        if star.star_type == StarType.ANCHOR and non_dim_neighbors_count[star.id] < 2:
            return False
        if star.star_type == StarType.RELAY and non_dim_neighbors_count[star.id] < 1:
            return False
    return True


def generate_instance(
    n: int,
    size_class: str,
    instance_id: str,
    max_attempts: int = 1000,
    seed: Optional[int] = None,
    verbose: bool = False,
    p_keep_range: Tuple[float, float] = DEFAULT_P_KEEP_RANGE,
    max_shrink_iters: int = DEFAULT_MAX_SHRINK_ITERS,
) -> Optional[Instance]:
    """Generate one valid uniquely-solvable instance, or None if max_attempts hit."""
    from stellarium.encoding.sat_encoder import SATEncoder

    lo, hi = p_keep_range
    if not (0.0 <= lo <= hi <= 1.0):
        raise ValueError(f"invalid p_keep_range {p_keep_range}")

    rng = random.Random(seed)
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        sub_seed = rng.randrange(0, 2**31 - 1)
        attempt_rng = random.Random(sub_seed)

        stars, edges = sample_planar_graph(n, seed=sub_seed)

        p_keep = attempt_rng.uniform(lo, hi)
        sampled_solution, degrees = sample_random_solution(
            stars, edges, p_keep=p_keep, rng=attempt_rng
        )

        if not sampled_solution:
            continue

        typed_stars = types_from_degrees(stars, degrees)

        pruned = shrink_to_unique(
            typed_stars,
            edges,
            sampled_solution,
            rng=attempt_rng,
            max_iters=max_shrink_iters,
        )
        if pruned is None:
            continue

        candidate = Instance(
            id=instance_id, size_class=size_class, stars=typed_stars, edges=pruned
        )

        result = SATEncoder(candidate).solve()
        if not result.satisfiable or result.solution is None:
            continue

        candidate.solution = list(result.solution)
        candidate.solver_decisions = int(result.decisions)
        if verbose:
            print(
                f"[gen] {instance_id} accepted on attempt {attempts} "
                f"(p_keep={p_keep:.2f}, kept {len(pruned)}/{len(edges)} edges, "
                f"decisions={result.decisions})"
            )
        return candidate

    if verbose:
        print(f"[gen] {instance_id} failed after {attempts} attempts")
    return None
