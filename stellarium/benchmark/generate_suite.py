from __future__ import annotations

import os
import random
import time
from typing import List, Tuple

from stellarium.puzzle.generator import generate_instance
from stellarium.puzzle.types import Instance


SIZE_CLASSES: List[Tuple[str, int, int, int]] = [
    ("XS", 8, 10, 20),
    ("S", 15, 20, 20),
    ("M", 25, 35, 20),
    ("L", 45, 55, 20),
    ("XL", 70, 80, 20),
]


def assign_difficulty_buckets(instances: List[Instance]) -> List[Instance]:
    """Assign easy/medium_easy/medium_hard/hard quartile labels by solver_decisions."""
    if not instances:
        return instances
    decisions = sorted(
        (inst.solver_decisions if inst.solver_decisions is not None else 0)
        for inst in instances
    )
    n = len(decisions)
    q1 = decisions[max(0, n // 4 - 1)]
    q2 = decisions[max(0, n // 2 - 1)]
    q3 = decisions[max(0, (3 * n) // 4 - 1)]

    for inst in instances:
        d = inst.solver_decisions if inst.solver_decisions is not None else 0
        if d <= q1:
            inst.difficulty_bucket = "easy"
        elif d <= q2:
            inst.difficulty_bucket = "medium_easy"
        elif d <= q3:
            inst.difficulty_bucket = "medium_hard"
        else:
            inst.difficulty_bucket = "hard"
    return instances


def generate_suite(
    output_dir: str,
    seed: int = 42,
    max_attempts_per_size: dict | None = None,
    verbose: bool = True,
) -> List[Instance]:
    """Generate 100 instances (20 per size class) and write each to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    if max_attempts_per_size is None:
        max_attempts_per_size = {
            "XS": 500,
            "S": 1000,
            "M": 2000,
            "L": 4000,
            "XL": 8000,
        }

    rng = random.Random(seed)
    all_instances: List[Instance] = []
    suite_start = time.perf_counter()

    for class_name, n_min, n_max, count in SIZE_CLASSES:
        if verbose:
            print(f"\n=== Size class {class_name} (n in [{n_min},{n_max}], {count} instances) ===")

        produced = 0
        attempts_total = 0
        attempts_accepted = 0
        class_start = time.perf_counter()
        decisions = []

        while produced < count:
            inst_id = f"stellarium_{class_name}_{produced:03d}"
            n = rng.randint(n_min, n_max)
            sub_seed = rng.randrange(0, 2**31 - 1)
            inst = generate_instance(
                n=n,
                size_class=class_name,
                instance_id=inst_id,
                seed=sub_seed,
                max_attempts=max_attempts_per_size[class_name],
                verbose=False,
            )
            attempts_total += 1
            if inst is None:
                if verbose:
                    print(f"  [warn] {inst_id} exhausted attempts; retrying with new seed")
                continue
            attempts_accepted += 1
            all_instances.append(inst)
            decisions.append(inst.solver_decisions or 0)
            produced += 1
            if verbose:
                print(
                    f"  [{produced:02d}/{count}] {inst_id} "
                    f"(n={n}, edges={len(inst.edges)}, decisions={inst.solver_decisions})"
                )

        elapsed = time.perf_counter() - class_start
        rate = attempts_accepted / max(attempts_total, 1)
        if verbose:
            print(
                f"  -> class {class_name} done in {elapsed:.1f}s; "
                f"acceptance={rate:.2f}; "
                f"decisions min/median/max={min(decisions)}/"
                f"{sorted(decisions)[len(decisions)//2]}/{max(decisions)}"
            )

    assign_difficulty_buckets(all_instances)

    for inst in all_instances:
        inst.save(os.path.join(output_dir, f"{inst.id}.json"))

    if verbose:
        total = time.perf_counter() - suite_start
        print(f"\nSuite generated in {total:.1f}s; wrote {len(all_instances)} files to {output_dir}")

    return all_instances


if __name__ == "__main__":
    here = os.path.dirname(__file__)
    out = os.path.join(here, "instances")
    generate_suite(out)
