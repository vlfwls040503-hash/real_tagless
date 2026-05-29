"""Run CFSM V2 and AVM with library defaults (3 seeds each).

Identical geometry to julich_bottleneck.py: semicircle r=3.3m, w=1.0m
bottleneck, 129 agents.

Outputs:
  - data/julich/sim_cfsm_default.csv
  - data/julich/sim_avm_default.csv
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
OUT_DIR = ROOT / "data" / "julich"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DT = 0.05
SIM_TIME = 75.0
SAMPLE_INTERVAL = 0.1  # 10 Hz
N_AGENTS = 129
SEMI_RADIUS = 3.3
BOTTLE_W = 1.0
BOTTLE_LEN = 0.2
POST_HALF_W = 2.0
POST_LEN = 3.0
V0_MEAN, V0_STD, V0_MIN, V0_MAX = 1.34, 0.26, 0.8, 2.0

# Library defaults
CFSM_DEFAULTS = dict(
    time_gap=1.0,
    radius=0.15,
    strength_neighbor_repulsion=8.0,
    range_neighbor_repulsion=0.1,
    strength_geometry_repulsion=5.0,
    range_geometry_repulsion=0.02,
)
AVM_DEFAULTS = dict(
    time_gap=1.06,
    radius=0.15,
    strength_neighbor_repulsion=8.0,
    range_neighbor_repulsion=0.1,
    wall_buffer_distance=0.1,
    anticipation_time=1.0,
    reaction_time=0.3,
)


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
    if len(candidates) < n:
        raise RuntimeError(f"Only {len(candidates)} slots for {n} agents")
    candidates.sort(key=lambda p: p[0] ** 2 + p[1] ** 2)
    chosen = candidates[:n]
    return np.array([(x + rng.uniform(-0.01, 0.01),
                      y + rng.uniform(-0.01, 0.01)) for x, y in chosen])


def run_one(model_name: str, seed: int, params: dict) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    walkable = build_geometry()

    if model_name == "cfsm":
        model = jps.CollisionFreeSpeedModelV2()
        AgentParams = jps.CollisionFreeSpeedModelV2AgentParameters
        speed_key = "desired_speed"
    elif model_name == "avm":
        model = jps.AnticipationVelocityModel()
        AgentParams = jps.AnticipationVelocityModelAgentParameters
        speed_key = "desired_speed"
    else:
        raise ValueError(model_name)

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
        kwargs = dict(params)
        kwargs.update({
            "journey_id": journey_id,
            "stage_id": wp_bottle,
            "position": (x, y),
            speed_key: float(v),
        })
        sim.add_agent(AgentParams(**kwargs))

    rows = []
    t0 = time.time()
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

    elapsed = time.time() - t0
    df = pd.DataFrame(rows, columns=["seed", "time", "agent_id", "x", "y"])
    final_n = 0
    try:
        final_n = sim.agent_count()
    except Exception:
        pass
    print(f"  {model_name} seed={seed}: {step+1} steps, {len(df):,} rows, "
          f"final={final_n}, {elapsed:.1f}s")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--models", nargs="+", default=["cfsm", "avm"])
    args = parser.parse_args()

    for model_name in args.models:
        params = CFSM_DEFAULTS if model_name == "cfsm" else AVM_DEFAULTS
        print(f"Running {model_name} defaults ...")
        dfs = [run_one(model_name, s, params) for s in args.seeds]
        combined = pd.concat(dfs, ignore_index=True)
        out = OUT_DIR / f"sim_{model_name}_default.csv"
        combined.to_csv(out, index=False, float_format="%.4f")
        print(f"  wrote {out} ({len(combined):,} rows)")


if __name__ == "__main__":
    main()
