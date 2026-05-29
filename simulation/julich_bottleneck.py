"""Jülich 4D090 bottleneck reproduction with AVM.

Geometry:
  - Bottleneck: width 1.0 m, length 0.2 m, centered at origin.
    opening: x in [0, 0.2], y in [-0.5, 0.5]
  - Pre (holding area): semicircle of radius 2 m for x <= 0
    (approximated by a polygon with 24 arc vertices)
  - Post: x in [0.2, 3.2], widening to y in [-2, 2]

AVM params: default tagless project values (Xu 2021 + Weidmann speed).
Purpose: check whether AVM with current params reproduces bottleneck
form/dynamics (not to tune).

Usage:
    py -3.12 simulation/julich_bottleneck.py [--seeds 42 43 44 45 46]

Outputs:
    data/julich/simulated_4D090.csv  (columns: seed, time, agent_id, x, y)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "julich" / "simulated_4D090.csv"
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# Simulation params
DT = 0.04
SIM_TIME = 100.0
SAVE_INTERVAL = 0.04  # 25 fps
N_AGENTS = 129
# Note: spec said 2m radius, but 129 agents with r=0.15 cannot fit in
# semicircle of area 6.28 m^2 (would need ~20 ped/m^2). Enlarged to 3m
# to match Jülich's actual holding area extent (their x_min ~ -7.7m).
SEMI_RADIUS = 3.3
BOTTLE_W = 1.0
BOTTLE_LEN = 0.2
POST_HALF_W = 2.0
POST_LEN = 3.0

# AVM params (Weidmann + project defaults)
V0_MEAN = 1.34
V0_STD = 0.26
V0_MIN = 0.8
V0_MAX = 2.0
AVM_PARAMS = dict(
    time_gap=0.80,           # tagless project value (matches avm_demo)
    radius=0.15,
    strength_neighbor_repulsion=8.0,
    range_neighbor_repulsion=0.1,
    wall_buffer_distance=0.1,
    anticipation_time=1.0,
    reaction_time=0.3,
)


def build_geometry() -> Polygon:
    """Walkable polygon: semicircle holding + bottleneck + post region."""
    arc_pts = []
    n_arc = 24
    for i in range(n_arc + 1):
        theta = np.pi / 2 + i * np.pi / n_arc  # 90° -> 270°
        x = SEMI_RADIUS * np.cos(theta)
        y = SEMI_RADIUS * np.sin(theta)
        arc_pts.append((x, y))

    # Pre region (semicircle): top -> left -> bottom along arc
    verts = []
    verts.append((0.0, SEMI_RADIUS))        # top of semicircle
    verts.extend(arc_pts[1:-1])             # arc (left side)
    verts.append((0.0, -SEMI_RADIUS))       # bottom of semicircle

    # Step up to bottleneck bottom
    verts.append((0.0, -BOTTLE_W / 2))      # bottleneck inlet bottom
    verts.append((BOTTLE_LEN, -BOTTLE_W / 2))  # bottleneck outlet bottom

    # Post region bottom: widen to -POST_HALF_W
    verts.append((BOTTLE_LEN, -POST_HALF_W))
    verts.append((BOTTLE_LEN + POST_LEN, -POST_HALF_W))
    verts.append((BOTTLE_LEN + POST_LEN, POST_HALF_W))
    verts.append((BOTTLE_LEN, POST_HALF_W))

    # Back to bottleneck outlet top
    verts.append((BOTTLE_LEN, BOTTLE_W / 2))
    verts.append((0.0, BOTTLE_W / 2))

    return Polygon(verts)


def sample_positions(rng: np.random.Generator, n: int) -> np.ndarray:
    """Place n agents on a hex grid inside the semicircle (x<0), jittered."""
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
    if len(candidates) < n:
        raise RuntimeError(f"Only {len(candidates)} grid slots available for {n} agents")
    # Sort by distance from bottleneck (closest first), take the n closest
    candidates.sort(key=lambda p: p[0] ** 2 + p[1] ** 2)
    chosen = candidates[:n]
    pts = []
    for x, y in chosen:
        pts.append((x + rng.uniform(-0.01, 0.01), y + rng.uniform(-0.01, 0.01)))
    return np.array(pts)


def run_one_seed(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    walkable = build_geometry()

    model = jps.AnticipationVelocityModel()
    sim = jps.Simulation(model=model, geometry=walkable, dt=DT)

    # Exit at far end
    exit_poly = Polygon([
        (BOTTLE_LEN + POST_LEN - 0.3, -POST_HALF_W + 0.1),
        (BOTTLE_LEN + POST_LEN - 0.05, -POST_HALF_W + 0.1),
        (BOTTLE_LEN + POST_LEN - 0.05, POST_HALF_W - 0.1),
        (BOTTLE_LEN + POST_LEN - 0.3, POST_HALF_W - 0.1),
    ])
    exit_id = sim.add_exit_stage(exit_poly)

    # Waypoint at bottleneck center to channel movement
    wp_bottleneck = sim.add_waypoint_stage((BOTTLE_LEN / 2, 0.0), 0.4)
    wp_post = sim.add_waypoint_stage((BOTTLE_LEN + 1.5, 0.0), 0.5)

    journey = jps.JourneyDescription([wp_bottleneck, wp_post, exit_id])
    journey.set_transition_for_stage(
        wp_bottleneck, jps.Transition.create_fixed_transition(wp_post))
    journey.set_transition_for_stage(
        wp_post, jps.Transition.create_fixed_transition(exit_id))
    journey_id = sim.add_journey(journey)

    # Spawn 129 agents
    positions = sample_positions(rng, N_AGENTS)
    speeds = np.clip(rng.normal(V0_MEAN, V0_STD, N_AGENTS), V0_MIN, V0_MAX)

    for (x, y), v0 in zip(positions, speeds):
        sim.add_agent(
            jps.AnticipationVelocityModelAgentParameters(
                journey_id=journey_id,
                stage_id=wp_bottleneck,
                position=(x, y),
                desired_speed=float(v0),
                **AVM_PARAMS,
            )
        )

    # Run & sample every step (DT=0.04 matches 25fps exactly)
    rows = []
    t0 = time.time()
    max_steps = int(SIM_TIME / DT)
    for step in range(max_steps):
        sim.iterate()
        t_cur = (step + 1) * DT
        for agent in sim.agents():
            px, py = agent.position
            rows.append((seed, t_cur, int(agent.id), float(px), float(py)))
        if sim.agent_count() == 0:
            break

    elapsed = time.time() - t0
    df = pd.DataFrame(rows, columns=["seed", "time", "agent_id", "x", "y"])
    print(f"  seed={seed}: {step+1} steps, {len(df):,} rows, "
          f"final_agents={sim.agent_count()}, elapsed={elapsed:.1f}s")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    args = parser.parse_args()

    all_dfs = []
    for seed in args.seeds:
        print(f"Running seed={seed} ...")
        df = run_one_seed(seed)
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(OUT_CSV, index=False, float_format="%.4f")
    print(f"\nWrote {OUT_CSV} ({len(combined):,} rows, {len(args.seeds)} seeds)")


if __name__ == "__main__":
    main()
