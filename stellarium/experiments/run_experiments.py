from __future__ import annotations

import glob
import os
from typing import List, Tuple

import numpy as np
import pandas as pd

from stellarium.benchmark.generate_suite import SIZE_CLASSES
from stellarium.puzzle.generator import generate_instance
from stellarium.puzzle.types import Instance, StarType
from stellarium.solver.solve import solve


RESULTS_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), "results")


def load_all_instances(instances_dir: str) -> List[Instance]:
    paths = sorted(glob.glob(os.path.join(instances_dir, "*.json")))
    return [Instance.load(p) for p in paths]


def _instance_features(inst: Instance) -> dict:
    counts = inst.n_stars_by_type()
    n_stars = len(inst.stars)
    n_edges = len(inst.edges)
    return {
        "instance_id": inst.id,
        "size_class": inst.size_class,
        "n_stars": n_stars,
        "n_edges": n_edges,
        "n_anchor": counts[StarType.ANCHOR],
        "n_relay": counts[StarType.RELAY],
        "n_dim": counts[StarType.DIM],
        "p_anchor": counts[StarType.ANCHOR] / n_stars if n_stars else 0.0,
        "p_relay": counts[StarType.RELAY] / n_stars if n_stars else 0.0,
        "graph_density": (n_edges / n_stars) if n_stars else 0.0,
        "n_crossing_pairs": len(inst.crossing_pairs()),
        "solver_decisions": inst.solver_decisions or 0,
        "difficulty_bucket": inst.difficulty_bucket,
    }


def _row(inst: Instance, r) -> dict:
    return {
        "instance_id": inst.id,
        "size_class": inst.size_class,
        "n_stars": len(inst.stars),
        "n_edges": len(inst.edges),
        "difficulty_bucket": inst.difficulty_bucket,
        "encoding": r.encoding,
        "solver": r.solver,
        "solve_time": r.solve_time,
        "decisions": r.decisions,
        "n_clauses": r.n_clauses,
        "n_constraints": r.n_constraints,
        "n_vars": r.n_vars,
        "nodes": r.nodes,
        "satisfiable": r.satisfiable,
    }


def experiment_encoding_comparison(
    instances: List[Instance], results_dir: str = RESULTS_DIR_DEFAULT
) -> pd.DataFrame:
    """SAT (CaDiCaL) vs SMT (Z3) vs IP (Gurobi), one row per (instance, encoding)."""
    rows = []
    for inst in instances:
        for encoding, solver_name in (
            ("sat", "Cadical103"),
            ("smt", "Z3"),
            ("ip", "Gurobi"),
        ):
            r = solve(inst, encoding=encoding, solver_name=solver_name)
            rows.append(_row(inst, r))
    df = pd.DataFrame(rows)
    os.makedirs(results_dir, exist_ok=True)
    df.to_csv(os.path.join(results_dir, "encoding_comparison.csv"), index=False)
    return df


def experiment_solver_comparison(
    instances: List[Instance], results_dir: str = RESULTS_DIR_DEFAULT
) -> pd.DataFrame:
    """CaDiCaL, Minisat22, Z3, Gurobi — one row per (instance, solver)."""
    rows = []
    configs: List[Tuple[str, str]] = [
        ("sat", "Cadical103"),
        ("sat", "Minisat22"),
        ("smt", "Z3"),
        ("ip",  "Gurobi"),
    ]
    for inst in instances:
        for encoding, solver_name in configs:
            r = solve(inst, encoding=encoding, solver_name=solver_name)
            rows.append(_row(inst, r))
    df = pd.DataFrame(rows)
    os.makedirs(results_dir, exist_ok=True)
    df.to_csv(os.path.join(results_dir, "solver_comparison.csv"), index=False)
    return df


def experiment_difficulty_analysis(
    instances: List[Instance], results_dir: str = RESULTS_DIR_DEFAULT
) -> pd.DataFrame:
    rows = [_instance_features(inst) for inst in instances]
    df = pd.DataFrame(rows)
    os.makedirs(results_dir, exist_ok=True)
    df.to_csv(os.path.join(results_dir, "difficulty_analysis.csv"), index=False)

    feature_cols = [
        "n_stars",
        "n_edges",
        "n_anchor",
        "n_relay",
        "n_dim",
        "p_anchor",
        "p_relay",
        "graph_density",
        "n_crossing_pairs",
    ]
    X = df[feature_cols].to_numpy(dtype=float)
    y = df["solver_decisions"].to_numpy(dtype=float)

    X_aug = np.hstack([np.ones((X.shape[0], 1)), X])
    coeffs, residuals, rank, sv = np.linalg.lstsq(X_aug, y, rcond=None)

    y_hat = X_aug @ coeffs
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    coeff_df = pd.DataFrame(
        {
            "feature": ["intercept"] + feature_cols,
            "coefficient": coeffs.tolist(),
        }
    )
    coeff_df.loc[len(coeff_df)] = ["r_squared", r2]
    coeff_df.to_csv(
        os.path.join(results_dir, "regression_coefficients.csv"), index=False
    )
    return df


def experiment_acceptance_rate(
    size_classes=SIZE_CLASSES,
    n_trials: int = 50,
    seed: int = 99,
    results_dir: str = RESULTS_DIR_DEFAULT,
) -> pd.DataFrame:
    """Per size class, count single-shot (max_attempts=1) successful generations."""
    import random as _random

    rng = _random.Random(seed)
    rows = []
    for class_name, n_min, n_max, _ in size_classes:
        accepted = 0
        for _ in range(n_trials):
            n = rng.randint(n_min, n_max)
            sub_seed = rng.randrange(0, 2**31 - 1)
            inst = generate_instance(
                n=n,
                size_class=class_name,
                instance_id=f"trial_{class_name}",
                seed=sub_seed,
                max_attempts=1,
                verbose=False,
            )
            if inst is not None:
                accepted += 1
        rows.append(
            {
                "size_class": class_name,
                "n_trials": n_trials,
                "n_accepted": accepted,
                "acceptance_rate": accepted / n_trials,
            }
        )
    df = pd.DataFrame(rows)
    os.makedirs(results_dir, exist_ok=True)
    df.to_csv(os.path.join(results_dir, "acceptance_rate.csv"), index=False)
    return df


def run_all(
    instances_dir: str, results_dir: str = RESULTS_DIR_DEFAULT
) -> None:
    instances = load_all_instances(instances_dir)
    print(f"Loaded {len(instances)} instances from {instances_dir}")
    print("Running encoding comparison...")
    experiment_encoding_comparison(instances, results_dir)
    print("Running solver comparison...")
    experiment_solver_comparison(instances, results_dir)
    print("Running difficulty analysis...")
    experiment_difficulty_analysis(instances, results_dir)
    print("Running acceptance-rate measurement...")
    experiment_acceptance_rate(results_dir=results_dir)
    print(f"All experiments done. Results in {results_dir}")


if __name__ == "__main__":
    here = os.path.dirname(__file__)
    instances_dir = os.path.normpath(
        os.path.join(here, "..", "benchmark", "instances")
    )
    run_all(instances_dir)
