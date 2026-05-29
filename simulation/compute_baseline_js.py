"""Compute baseline AVM (default params) JS divergence vs Jülich 4D090 target.

Uses the existing simulated_4D090.csv (strength=8.0, reaction=0.3, wall_buf=0.1).
This is the FAIL run. We use it as the baseline for calibration improvement.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

ROOT = Path(__file__).resolve().parent.parent
SIM_CSV = ROOT / "data" / "julich" / "simulated_4D090.csv"
TARGET_JSON = ROOT / "data" / "julich" / "4D090_target_metrics.json"
OUT_JSON = ROOT / "data" / "julich" / "baseline_metrics.json"

GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2


def main() -> None:
    target = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    target_dens = np.array(target["density"])

    sim = pd.read_csv(SIM_CSV)
    n_seeds = sim["seed"].nunique()

    # Aggregate density over [10, 50]s (same window as target)
    sub = sim[(sim["time"] >= 10.0) & (sim["time"] <= 50.0)]
    n_times = sub["time"].nunique()
    H, _, _ = np.histogram2d(sub["y"], sub["x"], bins=(GRID_Y, GRID_X))
    density = H / (n_times * n_seeds) / CELL

    # JS div
    p = density.flatten()
    q = target_dens.flatten()
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum()
    m = 0.5 * (p + q)
    def _kl(a, b):
        mask = (a > 0) & (b > 0)
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))
    js = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)

    x_centers = 0.5 * (GRID_X[:-1] + GRID_X[1:])
    y_centers = np.abs(0.5 * (GRID_Y[:-1] + GRID_Y[1:]))
    x_marg_sim = density.sum(axis=0)
    x_marg_obs = target_dens.sum(axis=0)
    w_x = wasserstein_distance(x_centers, x_centers,
                               x_marg_sim / x_marg_sim.sum(),
                               x_marg_obs / x_marg_obs.sum())
    y_marg_sim = density.sum(axis=1)
    y_marg_obs = target_dens.sum(axis=1)
    w_y = wasserstein_distance(y_centers, y_centers,
                               y_marg_sim / y_marg_sim.sum(),
                               y_marg_obs / y_marg_obs.sum())
    score = js + w_x + w_y

    result = {
        "description": "Default AVM (strength=8.0, reaction=0.3, wall_buf=0.1, time_gap=0.80)",
        "js_div": float(js),
        "w_x": float(w_x),
        "w_y": float(w_y),
        "score": float(score),
        "max_density_sim": float(density.max()),
        "max_density_obs": float(target_dens.max()),
        "n_seeds": int(n_seeds),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
