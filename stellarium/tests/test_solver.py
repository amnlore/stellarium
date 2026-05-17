from stellarium.puzzle.types import Edge, Instance, Star, StarType
from stellarium.solver.solve import solve, verify_solution
from stellarium.tests.test_encoder import make_simple_instance


def test_sat_and_smt_agree():
    instance = make_simple_instance()
    sat_result = solve(instance, encoding="sat")
    smt_result = solve(instance, encoding="smt")
    assert sat_result.satisfiable == smt_result.satisfiable
    assert sat_result.solution is not None
    assert smt_result.solution is not None
    assert set(sat_result.solution) == set(smt_result.solution)


def test_unsatisfiable_instance():
    """Anchor with only one incident edge cannot reach degree 2."""
    stars = [
        Star(0, 0.0, 0.0, StarType.ANCHOR),
        Star(1, 1.0, 0.0, StarType.RELAY),
    ]
    edges = [Edge(0, 0, 1)]
    instance = Instance(id="unsat", size_class="XS", stars=stars, edges=edges)
    sat_result = solve(instance, encoding="sat")
    smt_result = solve(instance, encoding="smt")
    assert not sat_result.satisfiable
    assert not smt_result.satisfiable


def test_solver_minisat_alternative():
    instance = make_simple_instance()
    result = solve(instance, encoding="sat", solver_name="Minisat22")
    assert result.satisfiable
    assert set(result.solution) == {0, 1}
    valid, msg = verify_solution(instance, result.solution)
    assert valid, msg
