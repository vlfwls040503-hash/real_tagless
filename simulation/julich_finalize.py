"""Run best CFSM params with 5 seeds, make final comparison figures.

Outputs:
  - data/julich/sim_cfsm_best.csv (5 seeds, full trajectories)
  - figures/calibration_result.png (obs vs default vs best heatmap)
  - figures/trajectory_before_after.png (sample trajectories overlay)
  - data/julich/final_metrics.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import wasserstein_distance

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "julich" / "sim_cfsm_best.csv"
TARGET = ROOT / "data" / "julich" / "4D090_target_footprint.json"
SIM_CFSM_DEF = ROOT / "data" / "julich" / "sim_cfsm_default.csv"
OBS_CSV = ROOT / "data" / "julich" / "4D090_trajectory.csv"
FIG_CAL = ROOT / "figures" / "calibration_result.png"
FIG_TRAJ = ROOT / "figures" / "trajectory_before_after.png"
OUT_JSON = ROOT / "data" / "julich" / "final_metrics.json"

DT = 0.05
SIM_TIME = 75.0
SAMPLE_INTERVAL = 0.1
N_AGENTS = 129
SEMI_RADIUS = 3.3
BOTTLE_W = 1.0
BOTTLE_LEN = 0.2
POST_HALF_W = 2.0
POST_LEN = 3.0
V0_MEAN, V0_STD, V0_MIN, V0_MAX = 1.34, 0.26, 0.8, 2.0

T_START = 15.0
T_END = 60.0
GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2
X_CENTERS = 0.5 * (GRID_X[:-1] + GRID_X[1:])
Y_CENTERS = 0.5 * (GRID_Y[:-1] + GRID_Y[1:])

# Best params from scan (non-gridlocked minimum Wasserstein)
BEST_A = 4.0
BEST_B = 1.0
BEST_C = 5.0
SEEDS = [42, 43, 44, 45, 46]


def build_geometry() -> Polygon:
    arc_pts = []
    n_arc = 24
    for i in range(n_arc + 1):
        theta = np.pi / 2 + i * np.pi / n_arc
        arc_pts.append((SEMI_RADIUS * np.cos(theta), SEMI_RADIUS * np.sin(theta)))
    verts = [(0.0, SEMI_RADIUS)]
    verts.extend(arc_pts[1:-1])
    verts.extend([
        (0.0, -SEMI_RADIUS),
        (0.0, -BOTTLE_W / 2),
        (BOTTLE_LEN, -BOTTLE_W / 2),
        (BOTTLE_LEN, -POST_HALF_W),
        (BOTTLE_LEN + POST_LEN, -POST_HALF_W),
        (BOTTLE_LEN + POST_LEN, POST_HALF_W),
        (BOTTLE_LEN, POST_HALF_W),
        (BOTTLE_LEN, BOTTLE_W / 2),
        (0.0, BOTTLE_W / 2),
    ])
    return Polygon(verts)


def sample_positions(rng, n):
    dx = 0.36
    dy = dx * np.sqrt(3) / 2
    candidates = []
    ny = int(np.ceil(2 * SEMI_RADIUS / dy)) + 2
    nx = int(np.ceil(SEMI_RADIUS / dx)) + 2
    for iy in range(-ny, ny + 1):
        y = iy * dy
        x_off = (dx / 2) if (iy % 2) else 0.0
        for ix in range(-nx, 1):
            x = ix * dx + x_off - 0.2
            if x > -0.2:
                continue
            if x * x + y * y > (SEMI_RADIUS - 0.15) ** 2:
                continue
            candidates.append((x, y))
    candidates.sort(key=lambda p: p[0] ** 2 + p[1] ** 2)
    chosen = candidates[:n]
    return np.array([(x + rng.uniform(-0.01, 0.01),
                      y + rng.uniform(-0.01, 0.01)) for x, y in chosen])


def run_best(seed: int, A: float, B: float, C: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    walkable = build_geometry()
    model = jps.CollisionFreeSpeedModelV2()
    sim = jps.Simulation(model=model, geometry=walkable, dt=DT)

    exit_poly = Polygon([
        (BOTTLE_LEN + POST_LEN - 0.3, -POST_HALF_W + 0.1),
        (BOTTLE_LEN + POST_LEN - 0.05, -POST_HALF_W + 0.1),
        (BOTTLE_LEN + POST_LEN - 0.05, POST_HALF_W - 0.1),
        (BOTTLE_LEN + POST_LEN - 0.3, POST_HALF_W - 0.1),
    ])
    exit_id = sim.add_exit_stage(exit_poly)
    wp_bottle = sim.add_waypoint_stage((BOTTLE_LEN / 2, 0.0), 0.4)
    wp_post = sim.add_waypoint_stage((BOTTLE_LEN + 1.5, 0.0), 0.5)
    journey = jps.JourneyDescription([wp_bottle, wp_post, exit_id])
    journey.set_transition_for_stage(wp_bottle, jps.Transition.create_fixed_transition(wp_post))
    journey.set_transition_for_stage(wp_post, jps.Transition.create_fixed_transition(exit_id))
    journey_id = sim.add_journey(journey)

    positions = sample_positions(rng, N_AGENTS)
    speeds = np.clip(rng.normal(V0_MEAN, V0_STD, N_AGENTS), V0_MIN, V0_MAX)

    for (x, y), v in zip(positions, speeds):
        sim.add_agent(
            jps.CollisionFreeSpeedModelV2AgentParameters(
                journey_id=journey_id,
                stage_id=wp_bottle,
                position=(x, y),
                desired_speed=float(v),
                radius=0.15,
                time_gap=B,
                strength_neighbor_repulsion=A,
                range_neighbor_repulsion=0.1,
                strength_geometry_repulsion=C,
                range_geometry_repulsion=0.02,
            )
        )

    rows = []
    max_steps = int(SIM_TIME / DT)
    sample_every = max(1, int(round(SAMPLE_INTERVAL / DT)))
    for step in range(max_steps):
        sim.iterate()
        if (step + 1) % sample_every == 0:
            t_cur = (step + 1) * DT
            for agent in sim.agents():
                px, py = agent.position
                rows.append((seed, t_cur, int(agent.id), float(px), float(py)))
        if sim.agent_count() == 0:
            break
    df = pd.DataFrame(rows, columns=["seed", "time", "agent_id", "x", "y"])
    print(f"  seed={seed}: {len(df):,} rows, final={sim.agent_count()}")
    return df


def density_heatmap(df: pd.DataFrame, has_seed=True) -> np.ndarray:
    mask = (df["time"] >= T_START) & (df["time"] <= T_END)
    sub = df[mask]
    heatmaps = []
    iterable = sub.groupby("seed") if has_seed else [("obs", sub)]
    for _, g in iterable:
        n_frames = g["time"].nunique()
        if n_frames == 0:
            continue
        H, _, _ = np.histogram2d(g["y"], g["x"], bins=(GRID_Y, GRID_X))
        heatmaps.append(H / n_frames / CELL)
    if not heatmaps:
        return np.zeros((len(GRID_Y) - 1, len(GRID_X) - 1))
    return np.mean(heatmaps, axis=0)


def wasserstein_xy(d_sim, d_obs):
    def _n(m): return m / m.sum() if m.sum() > 0 else m
    wx = wasserstein_distance(X_CENTERS, X_CENTERS,
                              u_weights=_n(d_sim.sum(axis=0)),
                              v_weights=_n(d_obs.sum(axis=0)))
    wy = wasserstein_distance(Y_CENTERS, Y_CENTERS,
                              u_weights=_n(d_sim.sum(axis=1)),
                              v_weights=_n(d_obs.sum(axis=1)))
    return float(wx + wy)


def flow_per_seed(df):
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
        results.append((int(seed), crossings / (T_END - T_START)))
    return results


def main():
    print(f"Running best CFSM params A={BEST_A}, B={BEST_B}, C={BEST_C} "
          f"with {len(SEEDS)} seeds ...")
    dfs = []
    t0 = time.time()
    for s in SEEDS:
        dfs.append(run_best(s, BEST_A, BEST_B, BEST_C))
    df_best = pd.concat(dfs, ignore_index=True)
    df_best.to_csv(OUT_CSV, index=False, float_format="%.4f")
    print(f"  wrote {OUT_CSV} ({len(df_best):,} rows, {time.time()-t0:.0f}s)")

    # Load target & default
    with open(TARGET) as f:
        target = json.load(f)
    d_obs = np.array(target["density"])
    df_def = pd.read_csv(SIM_CFSM_DEF)
    df_obs = pd.read_csv(OBS_CSV)

    d_def = density_heatmap(df_def)
    d_best = density_heatmap(df_best)

    w_def = wasserstein_xy(d_def, d_obs)
    w_best = wasserstein_xy(d_best, d_obs)
    improvement = (w_def - w_best) / w_def * 100

    flows_def = flow_per_seed(df_def)
    flows_best = flow_per_seed(df_best)

    print("\n=== Final metrics ===")
    print(f"  Target flow: {target['flow_rate_pps']:.2f} ped/s, peak: {target['max_density']:.2f}")
    print(f"  Default W: {w_def:.4f}, flows: {flows_def}")
    print(f"  Best    W: {w_best:.4f}, flows: {flows_best}")
    print(f"  Improvement: {improvement:.1f}%")
    print(f"  Best peak density: {d_best.max():.2f}, default peak: {d_def.max():.2f}")

    # Save metrics
    with open(OUT_JSON, "w") as f:
        json.dump({
            "best_params": {"strength_neighbor_repulsion": BEST_A,
                            "time_gap": BEST_B,
                            "strength_geometry_repulsion": BEST_C},
            "wasserstein": {"default": w_def, "best": w_best, "improvement_pct": improvement},
            "flow_default": flows_def,
            "flow_best": flows_best,
            "peak_density": {"obs": float(d_obs.max()),
                             "default": float(d_def.max()),
                             "best": float(d_best.max())},
            "target_flow": target["flow_rate_pps"],
        }, f, indent=2)
    print(f"  wrote {OUT_JSON}")

    # Figure 1: calibration_result (obs vs default vs best)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=100)
    vmax = max(d_obs.max(), d_def.max(), d_best.max())
    titles = [
        f"Observed 4D090\npeak {d_obs.max():.2f} ped/m^2",
        f"CFSM default\nW={w_def:.3f}, peak {d_def.max():.2f}",
        f"CFSM best (A={BEST_A},B={BEST_B},C={BEST_C})\nW={w_best:.3f}, peak {d_best.max():.2f}",
    ]
    for ax, d, title in zip(axes, [d_obs, d_def, d_best], titles):
        im = ax.imshow(d, origin="lower",
                       extent=[GRID_X[0], GRID_X[-1], GRID_Y[0], GRID_Y[-1]],
                       aspect="equal", cmap="hot", vmin=0, vmax=vmax)
        ax.plot([0, 0], [-2, -0.5], "w-", lw=2)
        ax.plot([0, 0], [0.5, 2], "w-", lw=2)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(title, fontsize=10)
    plt.colorbar(im, ax=axes.ravel().tolist(), shrink=0.8, label="density (ped/m^2)")
    plt.suptitle(f"Calibration result: improvement {improvement:.1f}%", fontsize=12)
    plt.savefig(FIG_CAL, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  wrote {FIG_CAL}")

    # Figure 2: trajectory overlay (obs vs default seed=42 vs best seed=42)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), dpi=100)

    # Observed
    obs_sub = df_obs[(df_obs["time"] >= T_START) & (df_obs["time"] <= T_END)]
    # Sample N agents
    agent_ids = obs_sub["agent_id"].unique()[:40]
    for aid in agent_ids:
        g = obs_sub[obs_sub["agent_id"] == aid]
        axes[0].plot(g["x"], g["y"], lw=0.5, alpha=0.6)
    axes[0].set_title(f"Observed (40 agents)")

    # Default seed 42
    def_sub = df_def[(df_def["seed"] == 42) &
                     (df_def["time"] >= T_START) & (df_def["time"] <= T_END)]
    agent_ids = def_sub["agent_id"].unique()[:40]
    for aid in agent_ids:
        g = def_sub[def_sub["agent_id"] == aid]
        axes[1].plot(g["x"], g["y"], lw=0.5, alpha=0.6)
    axes[1].set_title("CFSM default (seed 42)")

    # Best seed 42
    best_sub = df_best[(df_best["seed"] == 42) &
                       (df_best["time"] >= T_START) & (df_best["time"] <= T_END)]
    agent_ids = best_sub["agent_id"].unique()[:40]
    for aid in agent_ids:
        g = best_sub[best_sub["agent_id"] == aid]
        axes[2].plot(g["x"], g["y"], lw=0.5, alpha=0.6)
    axes[2].set_title(f"CFSM best (seed 42)")

    for ax in axes:
        ax.plot([0, 0], [-2.0, -0.5], "k-", lw=2)
        ax.plot([0, 0], [0.5, 2.0], "k-", lw=2)
        ax.set_xlim(-3.5, 1.5)
        ax.set_ylim(-2.5, 2.5)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
    plt.suptitle("Trajectory overlay (steady state t=15-60s)", fontsize=12)
    plt.tight_layout()
    plt.savefig(FIG_TRAJ, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  wrote {FIG_TRAJ}")


if __name__ == "__main__":
    main()
