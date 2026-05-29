"""Jülich 4D090 vs AVM simulation comparison (bottleneck form & dynamics).

Loads:
  data/julich/4D090_trajectory.csv      (observed)
  data/julich/simulated_4D090.csv       (AVM, 5 seeds pooled)

Metrics:
  A) density heatmap over -2m semicircle (grid 0.2m)
  B) density timeseries in 0.5m-front region
  C) trajectory overlay (selected 20 agents)
  D) speed profile along x (-3m .. +2m, 0.2m bins)
  E) extent of accumulation (>= 1 ped/m^2)

Outputs (dpi=100, figsize <= 10x6 per CLAUDE.md rule):
  figures/julich_density_heatmap.png
  figures/julich_density_timeseries.png
  figures/julich_velocity_profile.png
  figures/julich_snapshots_comparison.png
  figures/julich_trajectory_overlay.png
  data/julich/validation_metrics.json
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parent.parent
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
SIM_CSV = ROOT / "data" / "julich" / "simulated_4D090.csv"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)
METRICS_JSON = ROOT / "data" / "julich" / "validation_metrics.json"

# Matplotlib low-res defaults per CLAUDE.md rule (no >2000px images)
plt.rcParams["figure.dpi"] = 100
plt.rcParams["savefig.dpi"] = 100

# Analysis grid (pre-bottleneck semicircle region)
GRID_RES = 0.2
GRID_X = np.arange(-2.0, 0.0 + 1e-6, GRID_RES)  # 10 bins
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, GRID_RES)  # 20 bins
X_SPEED_BINS = np.arange(-3.0, 2.0 + 1e-6, 0.2)


def add_speed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["agent_id", "time"]).copy()
    df["dx"] = df.groupby("agent_id")["x"].diff()
    df["dy"] = df.groupby("agent_id")["y"].diff()
    df["dt"] = df.groupby("agent_id")["time"].diff()
    df["speed"] = np.hypot(df["dx"], df["dy"]) / df["dt"]
    df.loc[df["dt"].isna() | (df["dt"] <= 0), "speed"] = np.nan
    return df


# ---------- metric A: density heatmap ----------

def density_heatmap(df: pd.DataFrame, t_min: float, t_max: float) -> np.ndarray:
    """Time-averaged density over pre-bottleneck region. Returns (Y, X) array (ped/m^2).

    Counts agent-frames per cell, normalizes by total number of distinct
    (time, seed) samples so multiple seeds are averaged not summed.
    """
    mask = (df["time"] >= t_min) & (df["time"] <= t_max)
    sub = df[mask]
    cell_area = GRID_RES * GRID_RES
    H, _, _ = np.histogram2d(sub["y"], sub["x"], bins=(GRID_Y, GRID_X))
    # Number of time-snapshots (per-seed): n_unique_times * n_seeds if seed col exists
    n_times = sub["time"].nunique()
    n_seeds = sub["seed"].nunique() if "seed" in sub.columns else 1
    n_samples = n_times * n_seeds
    if n_samples == 0:
        return np.zeros_like(H)
    return H / n_samples / cell_area


# ---------- metric B: density timeseries in 0.5m strip ----------

def density_front_strip(df: pd.DataFrame, strip=(-0.5, 0.0)) -> pd.Series:
    """Per-1s-bin mean density in the front strip (0.5m x 2m = 1 m²)."""
    mask = (df["x"] >= strip[0]) & (df["x"] < strip[1]) & (df["y"].abs() < 1.0)
    sub = df[mask].copy()
    area = (strip[1] - strip[0]) * 2.0
    n_seeds = df["seed"].nunique() if "seed" in df.columns else 1
    sub["t_bin"] = np.floor(sub["time"]).astype(int)
    # counts per second = 25 frames × n_seeds samples per second-bin
    counts = sub.groupby("t_bin").size() / (25.0 * n_seeds)
    return counts / area


# ---------- metric D: speed profile along x ----------

def speed_profile(df: pd.DataFrame) -> pd.Series:
    sub = df[df["speed"].notna() & df["y"].abs() < 1.5]
    sub = sub.copy()
    sub["x_bin"] = pd.cut(sub["x"], X_SPEED_BINS)
    return sub.groupby("x_bin", observed=True)["speed"].mean()


# ---------- metric E: accumulation extent ----------

def accumulation_extent(df: pd.DataFrame) -> pd.Series:
    """Per 1-s bin: min x where density >= 1 ped/m^2 (queue back extent)."""
    extents = {}
    n_seeds = df["seed"].nunique() if "seed" in df.columns else 1
    for t_start in range(0, int(df["time"].max())):
        mask = (df["time"] >= t_start) & (df["time"] < t_start + 1)
        sub = df[mask]
        if len(sub) < 10:
            continue
        n_times = sub["time"].nunique() or 1
        H, _, _ = np.histogram2d(
            sub["y"], sub["x"],
            bins=(np.arange(-2, 2.01, 0.5), np.arange(-5, 0.01, 0.5)))
        dens = H / (n_times * n_seeds) / (0.5 * 0.5)
        col_max = dens.max(axis=0)
        x_bins = np.arange(-5, 0.01, 0.5)[:-1]
        high = x_bins[col_max >= 1.0]
        if len(high):
            extents[t_start] = high.min()
    return pd.Series(extents, name="extent_x")


# ---------- main ----------

def main() -> None:
    print("Loading ...")
    obs = pd.read_csv(OBS_CSV)
    sim = pd.read_csv(SIM_CSV)
    print(f"  obs: {len(obs):,} rows, {obs['agent_id'].nunique()} agents")
    print(f"  sim: {len(sim):,} rows, {sim['agent_id'].nunique()} agents / {sim['seed'].nunique()} seeds")

    obs = add_speed(obs)
    # For sim, compute speed per-seed-per-agent (combine agent_id + seed)
    sim_list = []
    for seed, g in sim.groupby("seed"):
        g = g.copy()
        g["agent_id"] = g["agent_id"].astype(str) + f"_{seed}"
        sim_list.append(g)
    sim_all = pd.concat(sim_list, ignore_index=True)
    sim_all = add_speed(sim_all)

    # Analysis time window: use 5s ~ 60s (overlap of obs 75s and most sim seeds)
    T_MIN, T_MAX = 5.0, 60.0

    print("\n=== A) Density heatmap ===")
    obs_heat = density_heatmap(obs, T_MIN, T_MAX)
    sim_heat = density_heatmap(sim_all, T_MIN, T_MAX)
    # Spatial correlation
    flat_o = obs_heat.flatten()
    flat_s = sim_heat.flatten()
    mask_nz = (flat_o > 0) | (flat_s > 0)
    r_spatial = np.corrcoef(flat_o[mask_nz], flat_s[mask_nz])[0, 1]
    print(f"  Spatial correlation r = {r_spatial:.3f}")
    print(f"  obs max density = {obs_heat.max():.2f}, sim max = {sim_heat.max():.2f}")

    print("\n=== B) Density timeseries (front 0.5m strip) ===")
    obs_ts = density_front_strip(obs)
    sim_ts = density_front_strip(sim_all)
    common = obs_ts.index.intersection(sim_ts.index)
    r_time = np.corrcoef(obs_ts.loc[common], sim_ts.loc[common])[0, 1]
    print(f"  Temporal correlation r = {r_time:.3f}")
    print(f"  obs peak: {obs_ts.max():.2f} at t={obs_ts.idxmax()}s")
    print(f"  sim peak: {sim_ts.max():.2f} at t={sim_ts.idxmax()}s")

    print("\n=== D) Speed profile along x ===")
    obs_v = speed_profile(obs)
    sim_v = speed_profile(sim_all)
    common_idx = obs_v.index.intersection(sim_v.index)
    obs_v_c = obs_v.loc[common_idx].values
    sim_v_c = sim_v.loc[common_idx].values
    rmse_speed = np.sqrt(np.nanmean((obs_v_c - sim_v_c) ** 2))
    print(f"  Speed RMSE = {rmse_speed:.3f} m/s")
    print(f"  obs min speed = {np.nanmin(obs_v_c):.2f} at x={obs_v.index[np.nanargmin(obs_v_c)]}")
    print(f"  sim min speed = {np.nanmin(sim_v_c):.2f} at x={sim_v.index[np.nanargmin(sim_v_c)]}")

    print("\n=== E) Accumulation extent ===")
    obs_ext = accumulation_extent(obs)
    # For sim, run on a single seed that matches best (pool for average)
    sim_ext = accumulation_extent(sim_all)
    obs_mean_ext = obs_ext.mean()
    sim_mean_ext = sim_ext.mean() if len(sim_ext) else np.nan
    ext_err = abs((sim_mean_ext - obs_mean_ext) / obs_mean_ext) * 100 if obs_mean_ext else np.nan
    print(f"  obs mean queue extent: {obs_mean_ext:.2f} m")
    print(f"  sim mean queue extent: {sim_mean_ext:.2f} m")
    print(f"  error: {ext_err:.1f}%")

    # === Plots ===
    # A) Heatmap side-by-side + diff
    print("\nPlotting ...")
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4), constrained_layout=True)
    vmax = max(obs_heat.max(), sim_heat.max())
    extent = [GRID_X[0], GRID_X[-1], GRID_Y[0], GRID_Y[-1]]
    im0 = axes[0].imshow(obs_heat, origin="lower", extent=extent, vmax=vmax, cmap="hot_r", aspect="equal")
    axes[0].set_title("Jülich 4D090 (obs)")
    axes[0].set_xlabel("x (m)")
    axes[0].set_ylabel("y (m)")
    axes[0].axvline(0, color="blue", lw=1)
    fig.colorbar(im0, ax=axes[0], label="ped/m²", shrink=0.7)
    im1 = axes[1].imshow(sim_heat, origin="lower", extent=extent, vmax=vmax, cmap="hot_r", aspect="equal")
    axes[1].set_title("AVM sim (5 seeds avg)")
    axes[1].set_xlabel("x (m)")
    axes[1].axvline(0, color="blue", lw=1)
    fig.colorbar(im1, ax=axes[1], label="ped/m²", shrink=0.7)
    diff = obs_heat - sim_heat
    dmax = np.abs(diff).max()
    im2 = axes[2].imshow(diff, origin="lower", extent=extent, vmin=-dmax, vmax=dmax, cmap="RdBu", aspect="equal")
    axes[2].set_title("Diff (obs - sim)")
    axes[2].set_xlabel("x (m)")
    axes[2].axvline(0, color="black", lw=1)
    fig.colorbar(im2, ax=axes[2], label="Δ ped/m²", shrink=0.7)
    fig.suptitle(f"Density heatmap: t=[{T_MIN:.0f}, {T_MAX:.0f}]s  |  spatial r={r_spatial:.2f}")
    fig.savefig(FIG_DIR / "julich_density_heatmap.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    # B) density timeseries
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(obs_ts.index, obs_ts.values, "b-", label="obs", lw=1.5)
    ax.plot(sim_ts.index, sim_ts.values, "r-", label="sim (avg)", lw=1.5)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("density in front 0.5m strip (ped/m²)")
    ax.set_title(f"Density timeseries (front 0.5m)  |  temporal r={r_time:.2f}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "julich_density_timeseries.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    # D) speed profile
    fig, ax = plt.subplots(figsize=(9, 4))
    xs = [interval.mid for interval in obs_v.index]
    xs_s = [interval.mid for interval in sim_v.index]
    ax.plot(xs, obs_v.values, "b-o", label="obs", ms=4)
    ax.plot(xs_s, sim_v.values, "r-s", label="sim", ms=4)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("mean speed (m/s)")
    ax.axvline(0, color="k", ls="--", alpha=0.5, label="bottleneck")
    ax.axvline(0.2, color="k", ls="--", alpha=0.5)
    ax.set_title(f"Speed profile along x  |  RMSE={rmse_speed:.2f} m/s")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "julich_velocity_profile.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    # snapshots comparison at 5 timestamps
    stamps = [10, 20, 30, 45, 60]
    fig, axes = plt.subplots(2, 5, figsize=(12, 5), sharex=True, sharey=True)
    for j, t_stamp in enumerate(stamps):
        for row, (df_, name) in enumerate([(obs, "obs"), (sim_all, "sim")]):
            ax = axes[row, j]
            snap = df_[(df_["time"] >= t_stamp) & (df_["time"] < t_stamp + 0.04)]
            ax.scatter(snap["x"], snap["y"], s=4, c="navy" if row == 0 else "crimson", alpha=0.6)
            ax.axvline(0, color="gray", lw=0.5)
            ax.axvline(0.2, color="gray", lw=0.5)
            ax.set_xlim(-4, 2.5)
            ax.set_ylim(-2.5, 2.5)
            ax.set_aspect("equal")
            if row == 0:
                ax.set_title(f"t={t_stamp}s")
            if j == 0:
                ax.set_ylabel(f"{name}\ny (m)")
            if row == 1:
                ax.set_xlabel("x (m)")
    fig.suptitle("Snapshots: Jülich 4D090 (top) vs AVM sim (bottom)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "julich_snapshots_comparison.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    # trajectory overlay (select 20 agents from each)
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

    sim_agents = sim_all["agent_id"].unique()
    sim_ids = rng.choice(sim_agents, 20, replace=False)
    for aid in sim_ids:
        tr = sim_all[sim_all["agent_id"] == aid].sort_values("time")
        axes[1].plot(tr["x"], tr["y"], lw=0.8, alpha=0.6)
    axes[1].set_title("AVM sim: 20 trajectories")
    axes[1].set_xlabel("x (m)")
    axes[1].axvline(0, color="k", ls="--", alpha=0.4)
    axes[1].axvline(0.2, color="k", ls="--", alpha=0.4)
    axes[1].set_xlim(-4, 2.5)
    axes[1].set_ylim(-3, 3)
    axes[1].set_aspect("equal")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "julich_trajectory_overlay.png", dpi=100, bbox_inches="tight")
    plt.close(fig)

    # Outflow comparison (supplementary)
    obs_outflow = 129 / 75.16
    sim_final_counts = sim.groupby("seed")["agent_id"].nunique() - sim[
        sim["time"] >= 99].groupby("seed")["agent_id"].nunique().reindex(
        sim["seed"].unique(), fill_value=0)
    # simpler: count agents remaining at last frame per seed
    last_sim = sim[sim["time"] > sim["time"].max() - 0.1]
    remain_by_seed = last_sim.groupby("seed")["agent_id"].nunique()
    exited_by_seed = 129 - remain_by_seed
    mean_sim_outflow = exited_by_seed.mean() / 100.0
    print(f"\nOutflow: obs = {obs_outflow:.2f} ped/s, sim mean = {mean_sim_outflow:.2f} ped/s")
    print(f"  per seed: exited={exited_by_seed.to_dict()}")

    # Save metrics
    metrics = {
        "window_s": [T_MIN, T_MAX],
        "density_spatial_r": float(r_spatial),
        "density_timeseries_r": float(r_time),
        "obs_max_density": float(obs_heat.max()),
        "sim_max_density": float(sim_heat.max()),
        "obs_peak_ts": float(obs_ts.max()),
        "sim_peak_ts": float(sim_ts.max()),
        "obs_peak_ts_time": int(obs_ts.idxmax()),
        "sim_peak_ts_time": int(sim_ts.idxmax()),
        "speed_rmse": float(rmse_speed),
        "obs_min_speed": float(np.nanmin(obs_v_c)),
        "sim_min_speed": float(np.nanmin(sim_v_c)),
        "obs_mean_queue_extent_m": float(obs_mean_ext) if not np.isnan(obs_mean_ext) else None,
        "sim_mean_queue_extent_m": float(sim_mean_ext) if not np.isnan(sim_mean_ext) else None,
        "queue_extent_error_pct": float(ext_err) if not np.isnan(ext_err) else None,
        "obs_outflow_ped_per_s": float(obs_outflow),
        "sim_outflow_mean_ped_per_s": float(mean_sim_outflow),
        "sim_exited_per_seed": {int(k): int(v) for k, v in exited_by_seed.items()},
    }
    # Criteria evaluation
    metrics["criteria"] = {
        "spatial_r_gt_0.6": bool(r_spatial > 0.6),
        "temporal_r_gt_0.7": bool(r_time > 0.7),
        "speed_rmse_lt_0.25": bool(rmse_speed < 0.25),
        "extent_error_lt_30pct": bool(ext_err is not None and ext_err < 30),
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {METRICS_JSON}")
    print("Criteria:")
    for k, v in metrics["criteria"].items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")


if __name__ == "__main__":
    main()
