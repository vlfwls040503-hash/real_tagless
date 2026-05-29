"""Compare CFSM & AVM defaults vs observed Julich 4D090 footprint.

Metrics:
  - Density heatmap (observed vs CFSM vs AVM)
  - Wasserstein distance on density marginals
  - Outflow stability across seeds (gridlock check)
  - Trajectory overlay

Outputs:
  - figures/default_comparison.png
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import wasserstein_distance

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "julich" / "4D090_target_footprint.json"
SIM_CFSM = ROOT / "data" / "julich" / "sim_cfsm_default.csv"
SIM_AVM = ROOT / "data" / "julich" / "sim_avm_default.csv"
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
FIG = ROOT / "figures" / "default_comparison.png"
FIG.parent.mkdir(parents=True, exist_ok=True)

T_START = 15.0
T_END = 60.0
GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2


def density_heatmap(df: pd.DataFrame) -> np.ndarray:
    mask = (df["time"] >= T_START) & (df["time"] <= T_END)
    sub = df[mask]
    # Normalize per-seed frame count then average
    heatmaps = []
    for seed, g in sub.groupby("seed") if "seed" in sub.columns else [("obs", sub)]:
        n_frames = g["time"].nunique()
        if n_frames == 0:
            continue
        H, _, _ = np.histogram2d(g["y"], g["x"], bins=(GRID_Y, GRID_X))
        heatmaps.append(H / n_frames / CELL)
    if not heatmaps:
        return np.zeros((len(GRID_Y) - 1, len(GRID_X) - 1))
    return np.mean(heatmaps, axis=0)


def wasserstein_2d_marginals(d_sim: np.ndarray, d_obs: np.ndarray) -> float:
    """Sum of Wasserstein on x-marginal and y-marginal."""
    def _norm_marg(m):
        return m / m.sum() if m.sum() > 0 else m
    x_sim = _norm_marg(d_sim.sum(axis=0))
    x_obs = _norm_marg(d_obs.sum(axis=0))
    y_sim = _norm_marg(d_sim.sum(axis=1))
    y_obs = _norm_marg(d_obs.sum(axis=1))
    # weighted by bin positions
    x_centers = 0.5 * (GRID_X[:-1] + GRID_X[1:])
    y_centers = 0.5 * (GRID_Y[:-1] + GRID_Y[1:])
    wx = wasserstein_distance(x_centers, x_centers, u_weights=x_sim, v_weights=x_obs)
    wy = wasserstein_distance(y_centers, y_centers, u_weights=y_sim, v_weights=y_obs)
    return float(wx + wy)


def outflow_rate(df: pd.DataFrame) -> list[tuple[int, float, int]]:
    """Per-seed: (seed, flow_rate_pps, final_agents_in_domain)."""
    results = []
    for seed, g in df.groupby("seed"):
        mask = (g["time"] >= T_START) & (g["time"] <= T_END)
        sub = g[mask].sort_values(["agent_id", "time"])
        crossings = 0
        for aid, gg in sub.groupby("agent_id"):
            xs = gg["x"].values
            if len(xs) < 2:
                continue
            if (xs[:-1] < 0.1).any() and (xs[1:] >= 0.1).any():
                crossings += 1
        flow = crossings / (T_END - T_START)
        # final agents still in domain at end of sim
        t_max = g["time"].max()
        final_n = int((g["time"] == t_max).sum())
        results.append((int(seed), float(flow), final_n))
    return results


def main() -> None:
    with open(TARGET) as f:
        target = json.load(f)
    d_obs = np.array(target["density"])

    df_cfsm = pd.read_csv(SIM_CFSM)
    df_avm = pd.read_csv(SIM_AVM)

    d_cfsm = density_heatmap(df_cfsm)
    d_avm = density_heatmap(df_avm)

    w_cfsm = wasserstein_2d_marginals(d_cfsm, d_obs)
    w_avm = wasserstein_2d_marginals(d_avm, d_obs)

    flow_cfsm = outflow_rate(df_cfsm)
    flow_avm = outflow_rate(df_avm)

    print("=== Wasserstein (x+y marginals, lower is better) ===")
    print(f"  CFSM default: {w_cfsm:.4f}")
    print(f"  AVM default : {w_avm:.4f}")
    print()
    print("=== Outflow rates (ped/s) and final_in_domain (gridlock) ===")
    print(f"  CFSM: {flow_cfsm}")
    print(f"  AVM : {flow_avm}")
    print(f"  Target flow: {target['flow_rate_pps']:.2f} ped/s")
    print(f"  Target peak density: {target['max_density']:.2f} at ({target['peak_x']},{target['peak_y']})")
    print(f"  CFSM peak: {d_cfsm.max():.2f}")
    print(f"  AVM peak:  {d_avm.max():.2f}")

    # Determine winner (lower wasserstein, but also penalize gridlock)
    cfsm_final = np.mean([r[2] for r in flow_cfsm])
    avm_final = np.mean([r[2] for r in flow_avm])
    cfsm_flow_cv = np.std([r[1] for r in flow_cfsm]) / max(np.mean([r[1] for r in flow_cfsm]), 1e-6)
    avm_flow_cv = np.std([r[1] for r in flow_avm]) / max(np.mean([r[1] for r in flow_avm]), 1e-6)
    print(f"  CFSM avg final in domain: {cfsm_final:.1f}, flow CV: {cfsm_flow_cv:.3f}")
    print(f"  AVM  avg final in domain: {avm_final:.1f}, flow CV: {avm_flow_cv:.3f}")

    # Pick winner
    gridlock_cfsm = cfsm_final > 50 or cfsm_flow_cv > 0.1
    gridlock_avm = avm_final > 50 or avm_flow_cv > 0.1
    if gridlock_cfsm and not gridlock_avm:
        winner = "avm"
    elif gridlock_avm and not gridlock_cfsm:
        winner = "cfsm"
    else:
        winner = "cfsm" if w_cfsm < w_avm else "avm"
    print(f"\nWinner: {winner.upper()}")

    with open(ROOT / "data" / "julich" / "default_comparison.json", "w") as f:
        json.dump({
            "wasserstein": {"cfsm": w_cfsm, "avm": w_avm},
            "flow_cfsm": flow_cfsm,
            "flow_avm": flow_avm,
            "peak_density": {"cfsm": float(d_cfsm.max()), "avm": float(d_avm.max()),
                             "obs": float(d_obs.max())},
            "winner": winner,
        }, f, indent=2)

    # Plot heatmaps 1x3
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=100)
    vmax = max(d_obs.max(), d_cfsm.max(), d_avm.max())
    titles = [f"Observed (max {d_obs.max():.2f})",
              f"CFSM V2 default\nW={w_cfsm:.3f}, peak {d_cfsm.max():.2f}",
              f"AVM default\nW={w_avm:.3f}, peak {d_avm.max():.2f}"]
    for ax, d, title in zip(axes, [d_obs, d_cfsm, d_avm], titles):
        im = ax.imshow(d, origin="lower",
                       extent=[GRID_X[0], GRID_X[-1], GRID_Y[0], GRID_Y[-1]],
                       aspect="equal", cmap="hot", vmin=0, vmax=vmax)
        ax.plot([0, 0], [-2, -0.5], "w-", lw=2)
        ax.plot([0, 0], [0.5, 2], "w-", lw=2)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(title, fontsize=10)
    plt.colorbar(im, ax=axes.ravel().tolist(), shrink=0.8, label="density (ped/m^2)")
    plt.suptitle(f"Default comparison (Winner: {winner.upper()})", fontsize=12)
    plt.savefig(FIG, dpi=100, bbox_inches="tight")
    print(f"Wrote {FIG}")


if __name__ == "__main__":
    main()
