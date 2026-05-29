"""Aggregate calibration scan, pick best params, produce figures."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "data" / "julich" / "calibration_runs"
TARGET_JSON = ROOT / "data" / "julich" / "4D090_target_metrics.json"
PROGRESS = RUNS_DIR / "progress.jsonl"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
BEST_JSON = RUNS_DIR / "best_params.json"

plt.rcParams["figure.dpi"] = 100
plt.rcParams["savefig.dpi"] = 100

GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)


def load_progress() -> pd.DataFrame:
    records = []
    with open(PROGRESS, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    df = pd.DataFrame(records)
    df = df[df["score"].notna()] if "score" in df.columns else df
    return df


def aggregate_by_combo(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby(["A", "B", "C"]).agg(
        score_mean=("score", "mean"),
        score_std=("score", "std"),
        js_mean=("js_div", "mean"),
        w_x_mean=("w_x", "mean"),
        w_y_mean=("w_y", "mean"),
        exited_mean=("exited", "mean"),
        wall_dist_mean=("mean_wall_dist", "mean"),
    ).reset_index()
    return agg.sort_values("score_mean")


def pick_best(agg: pd.DataFrame, target: dict) -> dict:
    best = agg.iloc[0]
    # mean wall dist from target for reference
    info = {
        "A": float(best["A"]),
        "B": float(best["B"]),
        "C": float(best["C"]),
        "score_mean": float(best["score_mean"]),
        "score_std": float(best["score_std"]),
        "js_mean": float(best["js_mean"]),
        "w_x_mean": float(best["w_x_mean"]),
        "w_y_mean": float(best["w_y_mean"]),
        "exited_mean": float(best["exited_mean"]),
        "wall_dist_mean": float(best["wall_dist_mean"]),
        "target_wall_dist": target["mean_wall_dist"],
    }
    return info


def plot_scan_heatmap(agg: pd.DataFrame) -> None:
    """For each (B, C), show 1D line over A of score_mean. Grid: rows=B, cols=C."""
    Bs = sorted(agg["B"].unique())
    Cs = sorted(agg["C"].unique())
    fig, axes = plt.subplots(len(Bs), len(Cs), figsize=(11, 8), sharex=True, sharey=True)
    vmin = agg["score_mean"].min()
    vmax = np.percentile(agg["score_mean"], 95)
    for i, B in enumerate(Bs):
        for j, C in enumerate(Cs):
            ax = axes[i, j]
            sub = agg[(agg["B"] == B) & (agg["C"] == C)].sort_values("A")
            ax.plot(sub["A"], sub["score_mean"], "o-", color="navy", ms=5)
            if "score_std" in sub.columns:
                ax.fill_between(sub["A"],
                                sub["score_mean"] - sub["score_std"],
                                sub["score_mean"] + sub["score_std"],
                                alpha=0.2, color="navy")
            ax.set_ylim(vmin * 0.95, vmax * 1.1)
            ax.grid(alpha=0.3)
            if i == 0:
                ax.set_title(f"C={C}", fontsize=9)
            if j == 0:
                ax.set_ylabel(f"B={B}\nscore", fontsize=9)
            if i == len(Bs) - 1:
                ax.set_xlabel("A (strength)", fontsize=9)
    fig.suptitle("Calibration scan: score by (A, B, C), lower is better")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "calibration_scan_heatmap.png", dpi=100, bbox_inches="tight")
    plt.close(fig)


def plot_best_density(best: dict, target: dict) -> None:
    """Density heatmap: observed vs calibrated best vs diff."""
    tag = f"A{best['A']}_B{best['B']}_C{best['C']}_s42"
    f1 = RUNS_DIR / f"params_{tag}.npz"
    if not f1.exists():
        print(f"Missing {f1}, skipping density plot")
        return
    sim_heat = np.load(f1)["density"]
    obs_heat = np.array(target["density"])
    vmax = max(sim_heat.max(), obs_heat.max())
    extent = [GRID_X[0], GRID_X[-1], GRID_Y[0], GRID_Y[-1]]

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4), constrained_layout=True)
    im0 = axes[0].imshow(obs_heat, origin="lower", extent=extent, vmax=vmax, cmap="hot_r", aspect="equal")
    axes[0].set_title("Jülich 4D090 (obs)")
    axes[0].axvline(0, color="blue", lw=1)
    axes[0].set_xlabel("x (m)")
    axes[0].set_ylabel("y (m)")
    fig.colorbar(im0, ax=axes[0], shrink=0.7, label="ped/m²")
    im1 = axes[1].imshow(sim_heat, origin="lower", extent=extent, vmax=vmax, cmap="hot_r", aspect="equal")
    axes[1].set_title(f"AVM calibrated\nA={best['A']} B={best['B']} C={best['C']}")
    axes[1].axvline(0, color="blue", lw=1)
    axes[1].set_xlabel("x (m)")
    fig.colorbar(im1, ax=axes[1], shrink=0.7, label="ped/m²")
    diff = obs_heat - sim_heat
    dmax = np.abs(diff).max()
    im2 = axes[2].imshow(diff, origin="lower", extent=extent, vmin=-dmax, vmax=dmax, cmap="RdBu", aspect="equal")
    axes[2].set_title("Diff (obs - sim)")
    axes[2].axvline(0, color="black", lw=1)
    axes[2].set_xlabel("x (m)")
    fig.colorbar(im2, ax=axes[2], shrink=0.7, label="Δ ped/m²")
    fig.suptitle(f"Best-calibrated density: score={best['score_mean']:.3f}, js={best['js_mean']:.3f}")
    fig.savefig(FIG_DIR / "calibrated_density_heatmap.png", dpi=100, bbox_inches="tight")
    plt.close(fig)


def plot_best_trajectory(best: dict) -> None:
    """Trajectory overlay: 20 obs vs 20 calibrated sim (from first seed run)."""
    # Load observed
    obs = pd.read_csv(OBS_CSV)
    # No sim trajectory saved in scan (only density). Skip or re-run quickly.
    # Alternative: if validate file exists, load from there.
    best_tag = f"A{best['A']}_B{best['B']}_C{best['C']}"
    val_csv = RUNS_DIR / f"validate_traj_{best_tag}.csv"
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    rng = np.random.default_rng(0)
    obs_ids = rng.choice(obs["agent_id"].unique(), 20, replace=False)
    for aid in obs_ids:
        tr = obs[obs["agent_id"] == aid].sort_values("time")
        axes[0].plot(tr["x"], tr["y"], lw=0.8, alpha=0.6)
    axes[0].set_title("Jülich 4D090: 20 trajectories")
    axes[0].set_xlabel("x (m)")
    axes[0].set_ylabel("y (m)")
    axes[0].axvline(0, color="k", ls="--", alpha=0.4)
    axes[0].axvline(0.2, color="k", ls="--", alpha=0.4)
    axes[0].set_xlim(-4, 2.5)
    axes[0].set_ylim(-3, 3)
    axes[0].set_aspect("equal")

    if val_csv.exists():
        sim = pd.read_csv(val_csv)
        sim_ids = rng.choice(sim["agent_id"].unique(), 20, replace=False)
        for aid in sim_ids:
            tr = sim[sim["agent_id"] == aid].sort_values("time")
            axes[1].plot(tr["x"], tr["y"], lw=0.8, alpha=0.6)
        title = f"AVM calibrated: A={best['A']} B={best['B']} C={best['C']}"
    else:
        axes[1].text(0.5, 0.5, "No validate trajectory saved\n(run_validate_traj.py)",
                     ha="center", va="center", transform=axes[1].transAxes)
        title = "AVM calibrated (missing)"
    axes[1].set_title(title)
    axes[1].set_xlabel("x (m)")
    axes[1].axvline(0, color="k", ls="--", alpha=0.4)
    axes[1].axvline(0.2, color="k", ls="--", alpha=0.4)
    axes[1].set_xlim(-4, 2.5)
    axes[1].set_ylim(-3, 3)
    axes[1].set_aspect("equal")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "calibrated_trajectory_overlay.png", dpi=100, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_progress()
    print(f"Loaded {len(df)} run records")
    if "score" not in df.columns or df.empty:
        print("No runs with score yet")
        return
    target = json.loads(TARGET_JSON.read_text(encoding="utf-8"))

    agg = aggregate_by_combo(df)
    print(f"\nTop 10 combos by score (lower=better):")
    print(agg.head(10).to_string(index=False))

    best = pick_best(agg, target)
    print(f"\nBEST: A={best['A']} B={best['B']} C={best['C']}")
    print(f"  score={best['score_mean']:.3f} (std={best['score_std']:.3f})")
    print(f"  js={best['js_mean']:.3f}, w_x={best['w_x_mean']:.3f}, w_y={best['w_y_mean']:.3f}")
    print(f"  exited mean={best['exited_mean']:.1f} / 129")
    print(f"  wall dist: sim={best['wall_dist_mean']:.3f} obs={target['mean_wall_dist']:.3f}")
    with open(BEST_JSON, "w", encoding="utf-8") as f:
        json.dump({"best": best, "top10": agg.head(10).to_dict(orient="records")},
                  f, indent=2)
    print(f"Wrote {BEST_JSON}")

    # Baseline score for comparison: default AVM strength=8, reaction=0.3, wall_buf=0.1
    # NOT in grid — report that baseline was from previous fail analysis
    print(f"\nBaseline AVM (strength=8.0, reaction=0.3, wall_buf=0.1) JS:")
    print(f"  (calibrated best js_mean: {agg['js_mean'].min():.3f} vs baseline in baseline_metrics.json)")

    plot_scan_heatmap(agg)
    print("Wrote figures/calibration_scan_heatmap.png")
    plot_best_density(best, target)
    plot_best_trajectory(best)
    print("Done.")


if __name__ == "__main__":
    main()
