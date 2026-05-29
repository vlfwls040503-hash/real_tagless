"""CFSM V2 parameter scan on Julich 4D090 bottleneck.

3 params x 3 levels x 2 seeds = 54 runs.

Parameters (CFSM V2 mapping):
  pedestrian_repulsion_strength = strength_neighbor_repulsion
  relaxation_time               = time_gap (closest CFSM analog)
  wall_repulsion_strength       = strength_geometry_repulsion

Default: A=8.0, B=1.0, C=5.0 (library defaults).
Grid:    A in [4.0, 8.0, 12.0], B in [0.5, 1.0, 1.5], C in [2.5, 5.0, 7.5].

Outputs:
  data/julich/scan_results.csv  (per-run: A, B, C, seed, w_distance, flow_rate, peak_density, final_in_domain)
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "julich" / "scan_results.csv"
TARGET = ROOT / "data" / "julich" / "4D090_target_footprint.json"

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

GRID_A = [4.0, 8.0, 12.0]      # strength_neighbor_repulsion
GRID_B = [0.5, 1.0, 1.5]        # time_gap
GRID_C = [2.5, 5.0, 7.5]        # strength_geometry_repulsion
SEEDS = [42, 43]


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


def sample_positions(rng: np.random.Generator, n: int) -> np.ndarray:
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


def run_one(A: float, B: float, C: float, seed: int) -> dict:
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

    max_steps = int(SIM_TIME / DT)
    sample_every = max(1, int(round(SAMPLE_INTERVAL / DT)))
    xs_all = []
    ys_all = []
    ts_all = []
    ids_all = []
    crossings = set()
    prev_x = {}
    for step in range(max_steps):
        sim.iterate()
        t_cur = (step + 1) * DT
        # track crossings at x=0.1
        for agent in sim.agents():
            aid = int(agent.id)
            px = agent.position[0]
            if aid in prev_x and prev_x[aid] < 0.1 and px >= 0.1:
                crossings.add(aid)
            prev_x[aid] = px
        if (step + 1) % sample_every == 0 and T_START <= t_cur <= T_END:
            for agent in sim.agents():
                px, py = agent.position
                if -2.0 <= px <= 0.0 and -2.0 <= py <= 2.0:
                    xs_all.append(px); ys_all.append(py); ts_all.append(t_cur); ids_all.append(int(agent.id))
        if sim.agent_count() == 0:
            break

    # density
    xs = np.array(xs_all); ys = np.array(ys_all); ts = np.array(ts_all)
    n_frames = len(set(ts.tolist())) if len(ts) else 1
    H, _, _ = np.histogram2d(ys, xs, bins=(GRID_Y, GRID_X))
    density = H / max(n_frames, 1) / CELL

    # Wasserstein vs target
    with open(TARGET) as f:
        target = json.load(f)
    d_obs = np.array(target["density"])
    def _norm(m):
        s = m.sum()
        return m / s if s > 0 else m
    x_sim = _norm(density.sum(axis=0))
    x_obs = _norm(d_obs.sum(axis=0))
    y_sim = _norm(density.sum(axis=1))
    y_obs = _norm(d_obs.sum(axis=1))
    if x_sim.sum() > 0 and y_sim.sum() > 0:
        wx = wasserstein_distance(X_CENTERS, X_CENTERS, u_weights=x_sim, v_weights=x_obs)
        wy = wasserstein_distance(Y_CENTERS, Y_CENTERS, u_weights=y_sim, v_weights=y_obs)
        w = float(wx + wy)
    else:
        w = float("inf")

    flow = len(crossings) / (T_END - T_START)
    final_n = sim.agent_count()

    return {
        "A": A, "B": B, "C": C, "seed": seed,
        "wasserstein": w,
        "flow_rate": flow,
        "peak_density": float(density.max()),
        "final_in_domain": int(final_n),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="1 combo only")
    args = parser.parse_args()

    combos = list(itertools.product(GRID_A, GRID_B, GRID_C))
    if args.test:
        combos = combos[:1]

    total = len(combos) * len(SEEDS)
    print(f"Running {total} simulations ({len(combos)} combos x {len(SEEDS)} seeds) ...")
    results = []
    t0 = time.time()
    for i, (A, B, C) in enumerate(combos):
        for seed in SEEDS:
            r = run_one(A, B, C, seed)
            results.append(r)
            elapsed = time.time() - t0
            remaining = (total - len(results)) * elapsed / max(len(results), 1)
            print(f"  [{len(results):3d}/{total}] A={A}, B={B}, C={C}, s={seed} -> "
                  f"W={r['wasserstein']:.3f} flow={r['flow_rate']:.2f} peak={r['peak_density']:.1f} "
                  f"final={r['final_in_domain']} ({elapsed:.0f}s elapsed, {remaining:.0f}s remaining)")

    df = pd.DataFrame(results)
    df.to_csv(OUT_CSV, index=False, float_format="%.4f")
    print(f"\nWrote {OUT_CSV} ({len(df)} rows)")

    # Aggregate
    agg = df.groupby(["A", "B", "C"]).agg(
        w_mean=("wasserstein", "mean"),
        w_std=("wasserstein", "std"),
        flow_mean=("flow_rate", "mean"),
        flow_cv=("flow_rate", lambda x: np.std(x) / np.mean(x) if np.mean(x) > 0 else np.inf),
        final_mean=("final_in_domain", "mean"),
    ).reset_index()
    agg = agg.sort_values("w_mean")
    print("\nTop 10 by Wasserstein:")
    print(agg.head(10).to_string(index=False))

    # Filter out gridlocked
    agg_clean = agg[(agg["flow_cv"] < 0.15) & (agg["final_mean"] < 40)].copy()
    print("\nTop 5 non-gridlocked:")
    print(agg_clean.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
