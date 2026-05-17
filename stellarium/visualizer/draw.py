from __future__ import annotations

import math
import os
from typing import Dict, List, Optional

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from stellarium.puzzle.types import Instance, StarType


COLORS: Dict[str, str] = {
    "anchor": "#FFD700",  # gold
    "relay": "#FFFFFF",   # white
    "dim": "#555555",     # dark grey
}
EDGE_COLOR_CANDIDATE = "#222244"
EDGE_COLOR_SOLUTION = "#4488FF"
BACKGROUND_COLOR = "#0a0a1a"

STAR_SIZE = {
    StarType.ANCHOR: 140.0,
    StarType.RELAY: 90.0,
    StarType.DIM: 50.0,
}


def draw_instance(
    instance: Instance,
    show_solution: bool = True,
    ax: Optional[plt.Axes] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    if ax is None:
        fig, ax = plt.subplots(figsize=(5, 5))
    else:
        fig = ax.figure

    ax.set_facecolor(BACKGROUND_COLOR)
    ax.set_aspect("equal")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])

    pos = {s.id: (s.x, s.y) for s in instance.stars}
    solution_set = set(instance.solution or []) if show_solution else set()

    for e in instance.edges:
        x1, y1 = pos[e.u]
        x2, y2 = pos[e.v]
        if e.id in solution_set:
            ax.plot(
                [x1, x2],
                [y1, y2],
                color=EDGE_COLOR_SOLUTION,
                linewidth=2.0,
                alpha=0.95,
                zorder=2,
            )
        else:
            ax.plot(
                [x1, x2],
                [y1, y2],
                color=EDGE_COLOR_CANDIDATE,
                linewidth=0.5,
                alpha=0.7,
                zorder=1,
            )

    by_type: Dict[StarType, List] = {t: [] for t in StarType}
    for s in instance.stars:
        by_type[s.star_type].append(s)
    for star_type, stars in by_type.items():
        if not stars:
            continue
        xs = [s.x for s in stars]
        ys = [s.y for s in stars]
        ax.scatter(
            xs,
            ys,
            s=STAR_SIZE[star_type],
            c=COLORS[star_type.value],
            edgecolors="black",
            linewidths=0.5,
            zorder=3,
            label=star_type.value,
        )

    if title:
        ax.set_title(title, color="white")

    handles = [
        mpatches.Patch(color=COLORS["anchor"], label="anchor (deg=2)"),
        mpatches.Patch(color=COLORS["relay"], label="relay (deg=1)"),
        mpatches.Patch(color=COLORS["dim"], label="dim (deg=0)"),
    ]
    ax.legend(
        handles=handles,
        loc="upper right",
        facecolor="#222244",
        edgecolor="white",
        labelcolor="white",
        fontsize=7,
    )

    return fig


def draw_grid(
    instances: List[Instance],
    cols: int = 4,
    show_solution: bool = True,
) -> plt.Figure:
    n = len(instances)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    if rows == 1 and cols == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [axes]
    elif cols == 1:
        axes = [[ax] for ax in axes]

    for idx in range(rows * cols):
        r, c = divmod(idx, cols)
        ax = axes[r][c]
        if idx < n:
            inst = instances[idx]
            title = f"{inst.id}\n{inst.size_class} / {inst.difficulty_bucket or '-'}"
            draw_instance(inst, show_solution=show_solution, ax=ax, title=title)
        else:
            ax.set_facecolor(BACKGROUND_COLOR)
            ax.set_xticks([])
            ax.set_yticks([])

    fig.tight_layout()
    return fig


def save_example_images(instances_dir: str, output_dir: str) -> None:
    """Pick one instance per (size_class, difficulty_bucket) combo and save PNGs."""
    import glob

    os.makedirs(output_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(instances_dir, "*.json")))
    instances = [Instance.load(p) for p in paths]

    chosen: Dict[tuple, Instance] = {}
    for inst in instances:
        key = (inst.size_class, inst.difficulty_bucket or "unbucketed")
        if key not in chosen:
            chosen[key] = inst

    for (sc, bucket), inst in sorted(chosen.items()):
        fig = draw_instance(
            inst,
            show_solution=True,
            title=f"{inst.id}  ({sc} / {bucket})",
        )
        out = os.path.join(output_dir, f"{sc}_{bucket}_{inst.id}.png")
        fig.savefig(out, dpi=150, facecolor=BACKGROUND_COLOR, bbox_inches="tight")
        plt.close(fig)
    print(f"Saved {len(chosen)} example images to {output_dir}")
