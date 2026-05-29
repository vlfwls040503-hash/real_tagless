"""Extract target footprint from Julich 4D090 observation (new spec).

Window: steady state t=15~60s
Grid: 0.2 x 0.2 m in approach zone (x in [-2, 0], y in [-2, 2])
Computes:
  - density heatmap
  - peak density cell (location)
  - mean convergence angle toward bottleneck
  - mean wall distance (to bottleneck walls y=+/- 0.5)

Outputs:
  - data/julich/4D090_target_footprint.json
  - figures/julich_target_footprint.png
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
OUT_JSON = ROOT / "data" / "julich" / "4D090_target_footprint.json"
FIG_PATH = ROOT / "figures" / "julich_target_footprint.png"
FIG_PATH.parent.mkdir(parents=True, exist_ok=True)

T_START = 15.0
T_END = 60.0
GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2
BOTTLE_HALF_W = 0.5  # bottleneck opening y in [-0.5, 0.5]


def compute_velocities(sub: pd.DataFrame) -> pd.DataFrame:
    """Forward-difference velocities per agent."""
    sub = sub.sort_values(["agent_id", "time"]).reset_index(drop=True)
    sub["vx"] = sub.groupby("agent_id")["x"].diff()
    sub["vy"] = sub.groupby("agent_id")["y"].diff()
    dt = sub.groupby("agent_id")["time"].diff()
    sub["vx"] = sub["vx"] / dt
    sub["vy"] = sub["vy"] / dt
    return sub


def main() -> None:
    df = pd.read_csv(OBS_CSV)
    mask = (df["time"] >= T_START) & (df["time"] <= T_END)
    sub = df[mask].copy()
    n_samples = sub["time"].nunique()

    # Density in the approach zone
    H, _, _ = np.histogram2d(sub["y"], sub["x"], bins=(GRID_Y, GRID_X))
    density = H / n_samples / CELL

    # Peak density location (cell center)
    iy, ix = np.unravel_index(np.argmax(density), density.shape)
    peak_x = 0.5 * (GRID_X[ix] + GRID_X[ix + 1])
    peak_y = 0.5 * (GRID_Y[iy] + GRID_Y[iy + 1])

    # Mean convergence angle (direction of velocity toward bottleneck center)
    approach = sub[(sub["x"] > -2.0) & (sub["x"] < -0.2) &
                   (sub["y"].abs() < 2.0)].copy()
    approach = compute_velocities(approach).dropna()
    # Convergence angle: angle between velocity and +x (toward bottleneck)
    vmag = np.hypot(approach["vx"], approach["vy"])
    valid = vmag > 0.05
    cos_theta = approach.loc[valid, "vx"] / vmag[valid]
    cos_theta = cos_theta.clip(-1, 1)
    theta_deg = np.degrees(np.arccos(cos_theta))
    mean_angle = float(theta_deg.mean())

    # Wall distance (to bottleneck walls y = +/- 0.5)
    wall_dist = np.minimum((approach["y"] - BOTTLE_HALF_W).abs(),
                           (approach["y"] + BOTTLE_HALF_W).abs())
    mean_wall = float(wall_dist.mean())

    # Flow rate (steady-state): agents crossing x=0.1 per second
    sub2 = df[mask].sort_values(["agent_id", "time"])
    crossings = 0
    for aid, g in sub2.groupby("agent_id"):
        xs = g["x"].values
        if len(xs) < 2:
            continue
        if (xs[:-1] < 0.1).any() and (xs[1:] >= 0.1).any():
            crossings += 1
    flow_rate = crossings / (T_END - T_START)

    out = {
        "window_s": [T_START, T_END],
        "grid_x_edges": GRID_X.tolist(),
        "grid_y_edges": GRID_Y.tolist(),
        "density": density.tolist(),
        "max_density": float(density.max()),
        "peak_x": float(peak_x),
        "peak_y": float(peak_y),
        "mean_convergence_angle_deg": mean_angle,
        "mean_wall_dist": mean_wall,
        "flow_rate_pps": flow_rate,
        "n_samples": int(n_samples),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    print(f"  density shape: {density.shape}")
    print(f"  max density: {density.max():.2f} ped/m^2 at ({peak_x:.2f}, {peak_y:.2f})")
    print(f"  mean convergence angle: {mean_angle:.1f} deg")
    print(f"  mean wall dist: {mean_wall:.3f} m")
    print(f"  flow rate: {flow_rate:.2f} ped/s")
    print(f"  samples (frames): {n_samples}")

    # Plot heatmap
    fig, ax = plt.subplots(figsize=(6, 5), dpi=100)
    im = ax.imshow(
        density,
        origin="lower",
        extent=[GRID_X[0], GRID_X[-1], GRID_Y[0], GRID_Y[-1]],
        aspect="equal",
        cmap="hot",
        vmin=0, vmax=density.max(),
    )
    # bottleneck walls
    ax.plot([0, 0], [-2, -BOTTLE_HALF_W], "w-", lw=2)
    ax.plot([0, 0], [BOTTLE_HALF_W, 2], "w-", lw=2)
    ax.scatter([peak_x], [peak_y], marker="x", s=80, c="cyan", label="peak")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Julich 4D090 target footprint\nt={T_START:.0f}-{T_END:.0f}s, peak={density.max():.2f} ped/m^2")
    ax.legend(loc="upper left")
    plt.colorbar(im, ax=ax, label="density (ped/m^2)")
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=100)
    print(f"Wrote {FIG_PATH}")


if __name__ == "__main__":
    main()
