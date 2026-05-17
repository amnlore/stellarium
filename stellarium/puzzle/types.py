from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class StarType(Enum):
    ANCHOR = "anchor"
    RELAY = "relay"
    DIM = "dim"


@dataclass
class Star:
    id: int
    x: float
    y: float
    star_type: StarType


@dataclass
class Edge:
    id: int
    u: int
    v: int


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
    return (
        min(ax, bx) <= cx <= max(ax, bx)
        and min(ay, by) <= cy <= max(ay, by)
    )


def segments_cross(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
    eps: float = 1e-12,
) -> bool:
    """True iff p1p2 properly intersects p3p4 (shared endpoints don't count)."""
    o1 = _orient(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    o2 = _orient(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    o3 = _orient(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    o4 = _orient(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])

    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (
        o3 > eps and o4 < -eps or o3 < -eps and o4 > eps
    ):
        return True

    return False


@dataclass
class Instance:
    id: str
    size_class: str
    stars: List[Star]
    edges: List[Edge]
    solution: Optional[List[int]] = None
    solver_decisions: Optional[int] = None
    difficulty_bucket: Optional[str] = None
    _adjacency_cache: Optional[Dict[int, List[int]]] = field(
        default=None, repr=False, compare=False
    )
    _crossing_cache: Optional[List[Tuple[int, int]]] = field(
        default=None, repr=False, compare=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "size_class": self.size_class,
            "stars": [
                {"id": s.id, "x": s.x, "y": s.y, "star_type": s.star_type.value}
                for s in self.stars
            ],
            "edges": [{"id": e.id, "u": e.u, "v": e.v} for e in self.edges],
            "solution": list(self.solution) if self.solution is not None else None,
            "solver_decisions": self.solver_decisions,
            "difficulty_bucket": self.difficulty_bucket,
        }

    @staticmethod
    def from_dict(d: dict) -> "Instance":
        stars = [
            Star(id=s["id"], x=s["x"], y=s["y"], star_type=StarType(s["star_type"]))
            for s in d["stars"]
        ]
        edges = [Edge(id=e["id"], u=e["u"], v=e["v"]) for e in d["edges"]]
        return Instance(
            id=d["id"],
            size_class=d["size_class"],
            stars=stars,
            edges=edges,
            solution=d.get("solution"),
            solver_decisions=d.get("solver_decisions"),
            difficulty_bucket=d.get("difficulty_bucket"),
        )

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str) -> "Instance":
        with open(path) as f:
            return Instance.from_dict(json.load(f))

    def adjacency(self) -> Dict[int, List[int]]:
        if self._adjacency_cache is not None:
            return self._adjacency_cache
        adj: Dict[int, List[int]] = {s.id: [] for s in self.stars}
        for e in self.edges:
            adj[e.u].append(e.id)
            adj[e.v].append(e.id)
        self._adjacency_cache = adj
        return adj

    def incident_edges(self, star_id: int) -> List[Edge]:
        ids = set(self.adjacency().get(star_id, []))
        return [e for e in self.edges if e.id in ids]

    def crossing_pairs(self) -> List[Tuple[int, int]]:
        if self._crossing_cache is not None:
            return self._crossing_cache
        pos = {s.id: (s.x, s.y) for s in self.stars}
        pairs: List[Tuple[int, int]] = []
        edges = self.edges
        n = len(edges)
        for i in range(n):
            ei = edges[i]
            pi_u = pos[ei.u]
            pi_v = pos[ei.v]
            for j in range(i + 1, n):
                ej = edges[j]
                if ei.u == ej.u or ei.u == ej.v or ei.v == ej.u or ei.v == ej.v:
                    continue
                if segments_cross(pi_u, pi_v, pos[ej.u], pos[ej.v]):
                    pairs.append((ei.id, ej.id))
        self._crossing_cache = pairs
        return pairs

    def n_stars_by_type(self) -> Dict[StarType, int]:
        counts = {t: 0 for t in StarType}
        for s in self.stars:
            counts[s.star_type] += 1
        return counts
