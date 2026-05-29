"""Re-run best-calibrated AVM params with 10 seeds, saving full trajectories.

Reads best_params.json from calibration_runs/.
Saves validate_traj_AxxBxxCxx.csv (pooled trajectory, 10 seeds).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Import sim functions from calibration module
sys.path.insert(0, str(Path(__file__).parent))
from julich_calibration import (  # noqa: E402
    build_geometry, hex_positions, DT, SIM_TIME, N_AGENTS, V0_MEAN, V0_STD,
    V0_MIN, V0_MAX, BOTTLE_LEN, POST_LEN, POST_HALF_W,
)

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "data" / "julich" / "calibration_runs"
BEST_JSON = RUNS_DIR / "best_params.json"


def run_traj(A: float, B: float, C: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    walkable = build_geometry()
    model = jps.AnticipationVelocityModel()
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
            jps.AnticipationVelocityModelAgentParameters(
                journey_id=jid, stage_id=wp_b, position=(x, y),
                desired_speed=float(v0),
                time_gap=0.80, radius=0.15,
                strength_neighbor_repulsion=A,
                range_neighbor_repulsion=0.1,
                wall_buffer_distance=C,
                anticipation_time=1.0,
                reaction_time=B,
            )
        )
    rows = []
    max_steps = int(SIM_TIME / DT)
    for step in range(max_steps):
        sim.iterate()
        t = (step + 1) * DT
        for a in sim.agents():
            rows.append((seed, t, int(a.id), float(a.position[0]), float(a.position[1])))
        if sim.agent_count() == 0:
            break
    return pd.DataFrame(rows, columns=["seed", "time", "agent_id", "x", "y"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    args = ap.parse_args()

    best_info = json.loads(BEST_JSON.read_text(encoding="utf-8"))
    A = best_info["best"]["A"]
    B = best_info["best"]["B"]
    C = best_info["best"]["C"]
    print(f"Validating best: A={A} B={B} C={C} with {args.seeds} seeds")

    all_dfs = []
    t0 = time.time()
    for i in range(args.seeds):
        seed = 100 + i
        df = run_traj(A, B, C, seed)
        exited = N_AGENTS - df[df["time"] == df["time"].max()]["agent_id"].nunique()
        print(f"  seed={seed}: {len(df):,} rows, exited={exited}, "
              f"t={time.time()-t0:.1f}s total")
        all_dfs.append(df)
    combined = pd.concat(all_dfs, ignore_index=True)
    tag = f"A{A}_B{B}_C{C}"
    out = RUNS_DIR / f"validate_traj_{tag}.csv"
    combined.to_csv(out, index=False, float_format="%.4f")
    print(f"\nWrote {out} ({len(combined):,} rows)")


if __name__ == "__main__":
    main()
