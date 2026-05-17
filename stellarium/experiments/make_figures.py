"""Render figures from the CSVs in results/ as PDF and PNG."""

from __future__ import annotations

import os
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
FIG_DIR = os.path.join(HERE, "figures")

ENC_COLOR = {
    "sat": "#3a6ff7",
    "smt": "#26a96b",
    "ip":  "#e08a17",
}
ENC_LABEL = {
    "sat": "SAT (CaDiCaL)",
    "smt": "SMT (Z3)",
    "ip":  "IP (Gurobi)",
}
SIZE_ORDER = ["XS", "S", "M", "L", "XL"]
SIZE_RANGES = {"XS": "8–10", "S": "15–20", "M": "25–35", "L": "45–55", "XL": "70–80"}


def _setup_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "grid.linewidth": 0.5,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 110,
    })


def _save(fig: plt.Figure, name: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    pdf = os.path.join(FIG_DIR, f"{name}.pdf")
    png = os.path.join(FIG_DIR, f"{name}.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"  wrote {pdf}  +  {png}")


def fig_encoding_solve_time(enc_df: pd.DataFrame) -> None:
    """Boxplot of solve_time (ms) by encoding × size class."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))

    encodings = ["sat", "smt", "ip"]
    n_sizes = len(SIZE_ORDER)
    width = 0.25

    for i, enc in enumerate(encodings):
        sub = enc_df[enc_df.encoding == enc]
        positions = np.arange(n_sizes) + (i - 1) * width
        data = [sub[sub.size_class == s].solve_time.values * 1000 for s in SIZE_ORDER]
        bp = ax.boxplot(
            data, positions=positions, widths=width * 0.85,
            patch_artist=True, showfliers=False,
            medianprops=dict(color="black", linewidth=1.2),
            boxprops=dict(facecolor=ENC_COLOR[enc], edgecolor=ENC_COLOR[enc],
                          alpha=0.78, linewidth=0),
            whiskerprops=dict(color=ENC_COLOR[enc], linewidth=1),
            capprops=dict(color=ENC_COLOR[enc], linewidth=1),
        )
        # Add a clean legend handle using a proxy patch.
        ax.plot([], [], color=ENC_COLOR[enc], lw=8, alpha=0.78, label=ENC_LABEL[enc])

    ax.set_yscale("log")
    ax.set_xticks(np.arange(n_sizes))
    ax.set_xticklabels([f"{s}\n(n={SIZE_RANGES[s]})" for s in SIZE_ORDER])
    ax.set_xlabel("Size class")
    ax.set_ylabel("Solve time (ms, log scale)")
    ax.set_title("Solve time per encoding across size classes (n=20 each)")
    ax.legend(loc="upper left", ncol=3)
    fig.tight_layout()
    _save(fig, "fig1_encoding_solve_time")


def fig_scaling(enc_df: pd.DataFrame) -> None:
    """Median solve time vs n_stars per encoding (with min–max bands)."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for enc in ("sat", "smt", "ip"):
        sub = enc_df[enc_df.encoding == enc]
        agg = sub.groupby("n_stars")["solve_time"].agg(["median", "min", "max"])
        ax.plot(agg.index, agg["median"] * 1000, "o-",
                color=ENC_COLOR[enc], label=ENC_LABEL[enc],
                markersize=4, linewidth=1.5, alpha=0.9)
        ax.fill_between(agg.index, agg["min"] * 1000, agg["max"] * 1000,
                        color=ENC_COLOR[enc], alpha=0.10, linewidth=0)
    ax.set_yscale("log")
    ax.set_xlabel("Number of stars (n)")
    ax.set_ylabel("Solve time (ms, log scale)")
    ax.set_title("Scaling: median solve time vs instance size  (shaded: min–max)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    _save(fig, "fig2_scaling")


def fig_sat_solver_comparison(slv_df: pd.DataFrame) -> None:
    """CaDiCaL vs Minisat22 on the same SAT encoding."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    sat = slv_df[slv_df.encoding == "sat"]
    solvers = ["Cadical103", "Minisat22"]
    colours = {"Cadical103": "#3a6ff7", "Minisat22": "#7a4cff"}
    width = 0.36

    for i, sv in enumerate(solvers):
        sub = sat[sat.solver == sv]
        positions = np.arange(len(SIZE_ORDER)) + (i - 0.5) * width
        data = [sub[sub.size_class == s].solve_time.values * 1000 for s in SIZE_ORDER]
        bp = ax.boxplot(
            data, positions=positions, widths=width * 0.85,
            patch_artist=True, showfliers=False,
            medianprops=dict(color="black", linewidth=1.2),
            boxprops=dict(facecolor=colours[sv], edgecolor=colours[sv],
                          alpha=0.78, linewidth=0),
            whiskerprops=dict(color=colours[sv], linewidth=1),
            capprops=dict(color=colours[sv], linewidth=1),
        )
        ax.plot([], [], color=colours[sv], lw=8, alpha=0.78, label=sv)

    ax.set_yscale("log")
    ax.set_xticks(np.arange(len(SIZE_ORDER)))
    ax.set_xticklabels(SIZE_ORDER)
    ax.set_xlabel("Size class")
    ax.set_ylabel("Solve time (ms, log scale)")
    ax.set_title("CaDiCaL vs Minisat22 on the same SAT encoding")
    ax.legend(loc="upper left", ncol=2)
    fig.tight_layout()
    _save(fig, "fig3_sat_solver_comparison")


def fig_acceptance_rate(acc_df: pd.DataFrame) -> None:
    """Bar chart of single-shot acceptance per size class."""
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    df = acc_df.set_index("size_class").reindex(SIZE_ORDER)
    bars = ax.bar(df.index, df["acceptance_rate"],
                  color="#26a96b", edgecolor="none", width=0.55)
    for bar, rate, n_acc, n_tr in zip(
        bars, df["acceptance_rate"], df["n_accepted"], df["n_trials"]
    ):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{int(rate * 100)}%\n({n_acc}/{n_tr})",
                ha="center", va="bottom", fontsize=8.5, color="#444")
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("Acceptance rate (single-shot)")
    ax.set_xlabel("Size class")
    ax.set_title("Generator acceptance rate (max_attempts = 1, 50 trials per class)")
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    fig.tight_layout()
    _save(fig, "fig4_acceptance_rate")


def fig_constraint_counts(enc_df: pd.DataFrame) -> None:
    """Median model size per encoding × size class."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    sat = enc_df[enc_df.encoding == "sat"].groupby("size_class")["n_clauses"].median()
    smt = enc_df[enc_df.encoding == "smt"].groupby("size_class")["n_constraints"].median()
    ip  = enc_df[enc_df.encoding == "ip" ].groupby("size_class")["n_constraints"].median()
    sat = sat.reindex(SIZE_ORDER); smt = smt.reindex(SIZE_ORDER); ip = ip.reindex(SIZE_ORDER)

    x = np.arange(len(SIZE_ORDER))
    w = 0.27
    ax.bar(x - w, sat, width=w, color=ENC_COLOR["sat"], label="SAT (clauses)", edgecolor="none")
    ax.bar(x,     smt, width=w, color=ENC_COLOR["smt"], label="SMT (assertions)", edgecolor="none")
    ax.bar(x + w, ip,  width=w, color=ENC_COLOR["ip"],  label="IP (constraints)", edgecolor="none")

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s}\n(n={SIZE_RANGES[s]})" for s in SIZE_ORDER])
    ax.set_xlabel("Size class")
    ax.set_ylabel("Median model size (log scale)")
    ax.set_title("Encoding overhead: model size per encoding")
    ax.legend(loc="upper left", ncol=3)
    fig.tight_layout()
    _save(fig, "fig5_constraint_counts")


def fig_difficulty_regression(coef_df: pd.DataFrame, diff_df: pd.DataFrame) -> None:
    """Bar chart of regression coefficients, with R² in the title."""
    coefs = coef_df.set_index("feature")["coefficient"]
    r2 = float(coefs.pop("r_squared"))
    intercept = float(coefs.pop("intercept"))
    coefs = coefs.sort_values(key=lambda s: s.abs(), ascending=True)

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    colours = ["#cf3a55" if v < 0 else "#3a6ff7" for v in coefs.values]
    ax.barh(coefs.index, coefs.values, color=colours, edgecolor="none")
    ax.axvline(0, color="black", linewidth=0.6, alpha=0.6)
    ax.set_xlabel("Coefficient (decisions per unit feature)")
    ax.set_title(f"Difficulty regression: features vs solver decisions  (R² = {r2:.3f})")
    fig.tight_layout()
    _save(fig, "fig6_difficulty_regression")


def main() -> None:
    _setup_style()
    print("Loading CSVs from", RESULTS_DIR)
    enc_df  = pd.read_csv(os.path.join(RESULTS_DIR, "encoding_comparison.csv"))
    slv_df  = pd.read_csv(os.path.join(RESULTS_DIR, "solver_comparison.csv"))
    diff_df = pd.read_csv(os.path.join(RESULTS_DIR, "difficulty_analysis.csv"))
    acc_df  = pd.read_csv(os.path.join(RESULTS_DIR, "acceptance_rate.csv"))
    coef_df = pd.read_csv(os.path.join(RESULTS_DIR, "regression_coefficients.csv"))

    print("Writing figures to", FIG_DIR)
    fig_encoding_solve_time(enc_df)
    fig_scaling(enc_df)
    fig_sat_solver_comparison(slv_df)
    fig_acceptance_rate(acc_df)
    fig_constraint_counts(enc_df)
    fig_difficulty_regression(coef_df, diff_df)
    print("Done.")


if __name__ == "__main__":
    main()
