"""Extract target metrics from Jülich 4D090 observation.

Writes data/julich/4D090_target_metrics.json with:
  - density (Y x X numpy array in bottleneck approach region)
  - mean_wall_dist: mean distance to nearest bottleneck wall
  - x_marginal, y_marginal
  - n_samples
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
OUT_JSON = ROOT / "data" / "julich" / "4D090_target_metrics.json"

SAVE_START = 10.0
SAVE_END = 50.0
GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2
BOTTLE_W = 1.0


def main() -> None:
    df = pd.read_csv(OBS_CSV)
    mask = (df["time"] >= SAVE_START) & (df["time"] <= SAVE_END)
    sub = df[mask]
    n_samples = sub["time"].nunique()
    H, _, _ = np.histogram2d(sub["y"], sub["x"], bins=(GRID_Y, GRID_X))
    density = H / n_samples / CELL

    # mean distance to bottleneck walls (y = +/- 0.5), within bottleneck approach
    approach = sub[(sub["x"] > -2.0) & (sub["x"] < 0.0) & (sub["y"].abs() < 2.0)]
    wall_dist = np.minimum((approach["y"] - BOTTLE_W / 2).abs(),
                           (approach["y"] + BOTTLE_W / 2).abs())
    mean_wall = float(wall_dist.mean())

    out = {
        "window_s": [SAVE_START, SAVE_END],
        "grid_x_edges": GRID_X.tolist(),
        "grid_y_edges": GRID_Y.tolist(),
        "density": density.tolist(),
        "x_marginal": density.sum(axis=0).tolist(),
        "y_marginal": density.sum(axis=1).tolist(),
        "max_density": float(density.max()),
        "mean_wall_dist": mean_wall,
        "n_samples": int(n_samples),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    print(f"  density shape: {density.shape}")
    print(f"  max density: {density.max():.2f} ped/m^2")
    print(f"  mean wall dist: {mean_wall:.3f} m")
    print(f"  samples (frames): {n_samples}")


if __name__ == "__main__":
    main()
