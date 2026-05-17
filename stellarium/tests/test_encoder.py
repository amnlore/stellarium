from stellarium.encoding.ip_encoder import IPEncoder
from stellarium.encoding.sat_encoder import SATEncoder
from stellarium.encoding.smt_encoder import SMTEncoder
from stellarium.puzzle.types import Edge, Instance, Star, StarType
from stellarium.solver.solve import verify_solution


def make_simple_instance() -> Instance:
    """4 stars in a square with the four side edges; unique solution {0, 1}.

        0 (anchor) --- 1 (relay)
        |              |
        2 (relay)  --- 3 (dim)
    """
    stars = [
        Star(0, 0.0, 0.0, StarType.ANCHOR),
        Star(1, 1.0, 0.0, StarType.RELAY),
        Star(2, 0.0, 1.0, StarType.RELAY),
        Star(3, 1.0, 1.0, StarType.DIM),
    ]
    edges = [
        Edge(0, 0, 1),
        Edge(1, 0, 2),
        Edge(2, 1, 3),
        Edge(3, 2, 3),
    ]
    return Instance(id="simple", size_class="XS", stars=stars, edges=edges)


def make_x_pattern_instance() -> Instance:
    """4 corner stars with all 4 sides + both diagonals; the diagonals cross."""
    stars = [
        Star(0, 0.0, 0.0, StarType.ANCHOR),
        Star(1, 1.0, 0.0, StarType.RELAY),
        Star(2, 0.0, 1.0, StarType.RELAY),
        Star(3, 1.0, 1.0, StarType.ANCHOR),
    ]
    edges = [
        Edge(0, 0, 1),  # bottom
        Edge(1, 0, 2),  # left
        Edge(2, 1, 3),  # right
        Edge(3, 2, 3),  # top
        Edge(4, 0, 3),  # diagonal 0-3
        Edge(5, 1, 2),  # diagonal 1-2 (crosses 4)
    ]
    return Instance(id="xpat", size_class="XS", stars=stars, edges=edges)


def test_sat_encoder_finds_solution():
    instance = make_simple_instance()
    encoder = SATEncoder(instance)
    result = encoder.solve()
    assert result.satisfiable
    assert set(result.solution) == {0, 1}


def test_smt_encoder_finds_solution():
    instance = make_simple_instance()
    encoder = SMTEncoder(instance)
    result = encoder.solve()
    assert result.satisfiable
    assert set(result.solution) == {0, 1}


def test_verify_solution_correct():
    instance = make_simple_instance()
    valid, msg = verify_solution(instance, [0, 1])
    assert valid, msg


def test_verify_solution_wrong_degree():
    instance = make_simple_instance()
    valid, _ = verify_solution(instance, [0])
    assert not valid


def test_blocking_clause_gives_unsat():
    instance = make_simple_instance()
    encoder = SATEncoder(instance)
    first = encoder.solve()
    assert first.satisfiable
    assert first.solution is not None
    second = encoder.solve_with_blocking(first.solution)
    assert not second.satisfiable


def test_smt_blocking_clause_gives_unsat():
    instance = make_simple_instance()
    encoder = SMTEncoder(instance)
    first = encoder.solve()
    assert first.satisfiable
    second = encoder.solve_with_blocking(first.solution)
    assert not second.satisfiable


def test_crossing_constraint():
    instance = make_x_pattern_instance()
    crossings = instance.crossing_pairs()
    assert (4, 5) in crossings or (5, 4) in crossings
    encoder = SATEncoder(instance)
    result = encoder.solve()
    assert result.satisfiable
    assert not (4 in result.solution and 5 in result.solution)
    valid, msg = verify_solution(instance, result.solution)
    assert valid, msg


def test_ip_encoder_finds_solution():
    instance = make_simple_instance()
    encoder = IPEncoder(instance)
    result = encoder.solve()
    assert result.satisfiable
    assert set(result.solution) == {0, 1}


def test_ip_blocking_cut_gives_infeasible():
    instance = make_simple_instance()
    encoder = IPEncoder(instance)
    first = encoder.solve()
    assert first.satisfiable
    second = encoder.solve_with_blocking(first.solution)
    assert not second.satisfiable


def test_ip_crossing_constraint():
    instance = make_x_pattern_instance()
    encoder = IPEncoder(instance)
    result = encoder.solve()
    assert result.satisfiable
    assert not (4 in result.solution and 5 in result.solution)
    valid, msg = verify_solution(instance, result.solution)
    assert valid, msg


def test_three_encodings_agree_on_simple():
    """All three encodings return the same solution on the toy puzzle."""
    instance = make_simple_instance()
    sat = SATEncoder(instance).solve()
    smt = SMTEncoder(instance).solve()
    ip  = IPEncoder(instance).solve()
    assert sat.satisfiable and smt.satisfiable and ip.satisfiable
    assert set(sat.solution) == set(smt.solution) == set(ip.solution)
