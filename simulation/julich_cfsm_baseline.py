"""CFSM V2 baseline validation vs Jülich 4D090 (5 seeds, 40s).

Uses project defaults: time_gap=0.80, radius=0.15, other CFSM V2 defaults.
Computes same JS/w_x/w_y score as AVM calibration for direct comparison.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

sys.path.insert(0, str(Path(__file__).parent))
from julich_calibration import (  # noqa: E402
    build_geometry, hex_positions, DT, N_AGENTS, V0_MEAN, V0_STD,
    V0_MIN, V0_MAX, BOTTLE_LEN, POST_LEN, POST_HALF_W,
    GRID_X, GRID_Y,
)

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "julich" / "simulated_4D090_cfsm.csv"
TARGET_JSON = ROOT / "data" / "julich" / "4D090_target_metrics.json"
METRICS_JSON = ROOT / "data" / "julich" / "cfsm_baseline_metrics.json"

SIM_TIME = 40.0  # steady-state reached by 20s; analyze [10, 35]
SAVE_START = 10.0
SAVE_END = 35.0
SEEDS = [42, 43, 44, 45, 46]

# CFSM V2 project defaults
PARAMS = dict(
    time_gap=0.80,
    radius=0.15,
    strength_neighbor_repulsion=8.0,
    range_neighbor_repulsion=0.1,
    strength_geometry_repulsion=5.0,
    range_geometry_repulsion=0.02,
)


def run_one_seed(seed: int) -> pd.DataFrame:
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
    wp_b = sim.add_waypoint_stage((BOTTLE_LEN / 2, 0.0), 0.4)
    wp_p = sim.add_waypoint_stage((BOTTLE_LEN + 1.5, 0.0), 0.5)
    journey = jps.JourneyDescription([wp_b, wp_p, exit_id])
    journey.set_transition_for_stage(wp_b, jps.Transition.create_fixed_transition(wp_p))
    journey.set_transition_for_stage(wp_p, jps.Transition.create_fixed_transition(exit_id))
    jid = sim.add_journey(journey)
    positions = hex_positions(rng, N_AGENTS)
    speeds = np.clip(rng.normal(V0_MEAN, V0_STD, N_AGENTS), V0_MIN, V0_MAX)
    for (x, y), v0 in zip(positions, speeds):
        sim.add_agent(
            jps.CollisionFreeSpeedModelV2AgentParameters(
                journey_id=jid, stage_id=wp_b, position=(x, y),
                desired_speed=float(v0),
                **PARAMS,
            )
        )
    rows = []
    for step in range(int(SIM_TIME / DT)):
        sim.iterate()
        t = (step + 1) * DT
        for a in sim.agents():
            rows.append((seed, t, int(a.id), float(a.position[0]), float(a.position[1])))
        if sim.agent_count() == 0:
            break
    return pd.DataFrame(rows, columns=["seed", "time", "agent_id", "x", "y"])


def compute_density(df: pd.DataFrame) -> np.ndarray:
    sub = df[(df["time"] >= SAVE_START) & (df["time"] <= SAVE_END)]
    n_times = sub["time"].nunique()
    n_seeds = sub["seed"].nunique()
    H, _, _ = np.histogram2d(sub["y"], sub["x"], bins=(GRID_Y, GRID_X))
    return H / (n_times * n_seeds) / 0.04


def compute_score(density: np.ndarray, target: dict) -> dict:
    target_d = np.array(target["density"])
    p = density.flatten()
    q = target_d.flatten()
    if p.sum() > 0:
        p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)
    def _kl(a, b):
        mask = (a > 0) & (b > 0)
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))
    js = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    x_c = 0.5 * (GRID_X[:-1] + GRID_X[1:])
    y_c = np.abs(0.5 * (GRID_Y[:-1] + GRID_Y[1:]))
    xs, xo = density.sum(0), target_d.sum(0)
    ys, yo = density.sum(1), target_d.sum(1)
    w_x = wasserstein_distance(x_c, x_c, xs / xs.sum(), xo / xo.sum()) if xs.sum() > 0 else float("inf")
    w_y = wasserstein_distance(y_c, y_c, ys / ys.sum(), yo / yo.sum()) if ys.sum() > 0 else float("inf")
    # spatial Pearson (the AVM missed this in baseline)
    r = float(np.corrcoef(p, q)[0, 1]) if p.sum() > 0 else 0.0
    return {
        "js_div": float(js), "w_x": float(w_x), "w_y": float(w_y),
        "score": float(js + w_x + w_y), "spatial_r": r,
    }


def main() -> None:
    target = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    print(f"CFSM V2 baseline: {PARAMS}")
    all_dfs = []
    t0 = time.time()
    exit_per_seed = {}
    for seed in SEEDS:
        df = run_one_seed(seed)
        last = df[df["time"] >= df["time"].max() - 0.05]
        exited = N_AGENTS - last["agent_id"].nunique()
        exit_per_seed[seed] = int(exited)
        print(f"  seed={seed}: {len(df):,} rows, exited={exited}, elapsed={time.time()-t0:.1f}s")
        all_dfs.append(df)
    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(OUT_CSV, index=False, float_format="%.4f")

    density = compute_density(combined)
    score = compute_score(density, target)
    print(f"\nScore: {score}")
    print(f"Max density (sim): {density.max():.2f} ped/m^2")
    print(f"Mean exits: {np.mean(list(exit_per_seed.values())):.1f} / 129")

    result = {
        "model": "CFSM V2",
        "params": PARAMS,
        "window_s": [SAVE_START, SAVE_END],
        "n_seeds": len(SEEDS),
        "exits_per_seed": exit_per_seed,
        "mean_exits": float(np.mean(list(exit_per_seed.values()))),
        "max_density_sim": float(density.max()),
        **score,
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {METRICS_JSON}")


if __name__ == "__main__":
    main()
