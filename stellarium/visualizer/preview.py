"""Generate a few instances and save PNGs for visual inspection."""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stellarium.puzzle.generator import generate_instance
from stellarium.visualizer.draw import BACKGROUND_COLOR, draw_grid, draw_instance


def main(out_dir: str = "/tmp/stellarium_preview") -> None:
    os.makedirs(out_dir, exist_ok=True)

    samples = [
        ("XS", 10, 1),
        ("S", 18, 2),
        ("M", 30, 3),
        ("L", 50, 4),
    ]

    instances = []
    for size_class, n, seed in samples:
        print(f"generating {size_class} (n={n}, seed={seed})...", flush=True)
        inst = generate_instance(
            n=n,
            size_class=size_class,
            instance_id=f"preview_{size_class}",
            seed=seed,
            max_attempts=5000,
            verbose=False,
        )
        if inst is None:
            print(f"  -> FAILED to find unique instance for {size_class}")
            continue
        instances.append(inst)
        path_solution = os.path.join(out_dir, f"{size_class}_with_solution.png")
        path_blank = os.path.join(out_dir, f"{size_class}_blank.png")
        fig = draw_instance(inst, show_solution=True, title=f"{inst.id} (solution)")
        fig.savefig(path_solution, dpi=150, facecolor=BACKGROUND_COLOR, bbox_inches="tight")
        plt.close(fig)
        fig = draw_instance(inst, show_solution=False, title=f"{inst.id} (puzzle)")
        fig.savefig(path_blank, dpi=150, facecolor=BACKGROUND_COLOR, bbox_inches="tight")
        plt.close(fig)
        print(
            f"  saved {path_solution}  (n_edges={len(inst.edges)}, "
            f"sol_size={len(inst.solution)}, decisions={inst.solver_decisions})"
        )

    if instances:
        grid = draw_grid(instances, cols=2, show_solution=True)
        grid_path = os.path.join(out_dir, "grid_solutions.png")
        grid.savefig(grid_path, dpi=130, facecolor=BACKGROUND_COLOR, bbox_inches="tight")
        plt.close(grid)
        print(f"\ngrid saved: {grid_path}")

    print(f"\nDone. Open the images:\n  open {out_dir}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stellarium_preview"
    main(out)
