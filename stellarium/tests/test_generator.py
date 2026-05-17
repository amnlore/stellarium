import random

from stellarium.puzzle.generator import (
    generate_instance,
    is_feasible,
    sample_planar_graph,
    sample_random_solution,
    shrink_to_unique,
    types_from_degrees,
)
from stellarium.puzzle.types import Instance, StarType
from stellarium.solver.solve import check_unique, verify_solution


def test_generated_instance_has_unique_solution():
    instance = generate_instance(
        n=10, size_class="XS", instance_id="test_001", seed=42, max_attempts=500
    )
    assert instance is not None
    assert instance.solution is not None
    valid, msg = verify_solution(instance, instance.solution)
    assert valid, msg
    assert check_unique(instance, instance.solution)


def test_serialization_roundtrip():
    instance = generate_instance(
        n=10, size_class="XS", instance_id="test_002", seed=123, max_attempts=500
    )
    assert instance is not None
    d = instance.to_dict()
    restored = Instance.from_dict(d)
    assert restored.id == instance.id
    assert len(restored.stars) == len(instance.stars)
    assert len(restored.edges) == len(instance.edges)
    assert restored.solution == instance.solution
    assert restored.solver_decisions == instance.solver_decisions


def test_crossing_pairs_symmetric():
    instance = generate_instance(
        n=15, size_class="S", instance_id="test_003", seed=7, max_attempts=500
    )
    assert instance is not None
    pairs = instance.crossing_pairs()
    pair_set = {frozenset(p) for p in pairs}
    assert len(pair_set) == len(pairs)
    # Delaunay triangulation should produce no crossings.
    assert len(pairs) == 0


def test_sample_random_solution_respects_degree_cap():
    """Every vertex ends with degree ≤ 2 and the degrees match selected."""
    stars, edges = sample_planar_graph(n=30, seed=1)
    rng = random.Random(99)
    selected, degrees = sample_random_solution(stars, edges, p_keep=0.9, rng=rng)
    assert all(0 <= d <= 2 for d in degrees.values())
    recomputed = {s.id: 0 for s in stars}
    edge_by_id = {e.id: e for e in edges}
    for eid in selected:
        e = edge_by_id[eid]
        recomputed[e.u] += 1
        recomputed[e.v] += 1
    assert recomputed == degrees


def test_sample_random_solution_p_keep_bounds():
    """p_keep=0 selects no edges; p_keep=1 selects a maximal linear forest."""
    stars, edges = sample_planar_graph(n=20, seed=2)

    empty, degrees_empty = sample_random_solution(
        stars, edges, p_keep=0.0, rng=random.Random(0)
    )
    assert empty == []
    assert all(d == 0 for d in degrees_empty.values())

    # With p_keep=1 the greedy must produce a maximal linear forest: every
    # rejected edge has at least one saturated endpoint.
    full, degrees_full = sample_random_solution(
        stars, edges, p_keep=1.0, rng=random.Random(0)
    )
    full_set = set(full)
    for e in edges:
        if e.id in full_set:
            continue
        assert degrees_full[e.u] >= 2 or degrees_full[e.v] >= 2


def test_types_from_degrees_mapping():
    stars, _ = sample_planar_graph(n=6, seed=3)
    degrees = {0: 0, 1: 1, 2: 2, 3: 0, 4: 2, 5: 1}
    typed = types_from_degrees(stars, degrees)
    expected = {
        0: StarType.DIM,
        1: StarType.RELAY,
        2: StarType.ANCHOR,
        3: StarType.DIM,
        4: StarType.ANCHOR,
        5: StarType.RELAY,
    }
    for s in typed:
        assert s.star_type == expected[s.id]
        original = next(o for o in stars if o.id == s.id)
        assert s.x == original.x and s.y == original.y


def test_solution_first_pipeline_is_feasible_by_construction():
    """Every solution-first attempt produces a feasible instance."""
    rng = random.Random(2026)
    for trial in range(20):
        sub_seed = rng.randrange(0, 2**31 - 1)
        stars, edges = sample_planar_graph(n=40, seed=sub_seed)
        attempt_rng = random.Random(sub_seed)
        _, degrees = sample_random_solution(
            stars, edges, p_keep=attempt_rng.uniform(0.35, 0.75), rng=attempt_rng
        )
        typed = types_from_degrees(stars, degrees)
        inst = Instance(
            id=f"feasibility_{trial}", size_class="M", stars=typed, edges=edges
        )
        assert is_feasible(inst), f"trial {trial} produced an infeasible instance"


def test_generate_instance_scales_to_large_n():
    """A 50-star instance must be produced within 20 attempts."""
    instance = generate_instance(
        n=50, size_class="L", instance_id="test_large", seed=2026, max_attempts=20
    )
    assert instance is not None
    assert instance.solution is not None
    valid, msg = verify_solution(instance, instance.solution)
    assert valid, msg


def test_shrink_to_unique_produces_unique_instance():
    """The shrink loop must drive the typed instance to a unique solution."""
    rng = random.Random(11)
    stars, edges = sample_planar_graph(n=20, seed=11)
    sampled, degrees = sample_random_solution(stars, edges, p_keep=0.7, rng=rng)
    assert sampled, "p_keep=0.7 on 20 points should select at least one edge"

    typed = types_from_degrees(stars, degrees)
    pruned = shrink_to_unique(typed, edges, sampled, rng=rng, max_iters=500)
    assert pruned is not None, "shrink_to_unique should converge for n=20"

    pruned_ids = {e.id for e in pruned}
    assert set(sampled).issubset(pruned_ids), "M must be preserved during shrinking"

    inst = Instance(id="shrink_test", size_class="S", stars=typed, edges=pruned)
    valid, msg = verify_solution(inst, sampled)
    assert valid, msg
    assert check_unique(inst, sampled)


def test_shrink_to_unique_preserves_types_and_M():
    """Shrinking only deletes non-M edges; types remain consistent with M."""
    rng = random.Random(13)
    stars, edges = sample_planar_graph(n=15, seed=13)
    sampled, degrees = sample_random_solution(stars, edges, p_keep=0.6, rng=rng)
    assert sampled

    typed = types_from_degrees(stars, degrees)
    type_by_id = {s.id: s.star_type for s in typed}

    pruned = shrink_to_unique(typed, edges, sampled, rng=rng, max_iters=500)
    assert pruned is not None

    pruned_by_id = {e.id: e for e in pruned}
    recomputed = {s.id: 0 for s in stars}
    for eid in sampled:
        e = pruned_by_id[eid]
        recomputed[e.u] += 1
        recomputed[e.v] += 1
    for s in typed:
        d = recomputed[s.id]
        if type_by_id[s.id] == StarType.ANCHOR:
            assert d == 2
        elif type_by_id[s.id] == StarType.RELAY:
            assert d == 1
        else:
            assert d == 0
