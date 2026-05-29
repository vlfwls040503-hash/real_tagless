"""Jülich 4D090 AVM parameter calibration for spatial bottleneck form.

Goal: find AVM (strength_neighbor_repulsion, reaction_time,
wall_buffer_distance) that minimizes spatial density mismatch vs the
Jülich 4D090 observation.

Grid (5 x 4 x 4 x 3 seeds = 240 runs):
  A: strength_neighbor_repulsion [0.5, 1.0, 1.5, 2.0, 3.0]
  B: reaction_time               [0.3, 0.5, 0.8, 1.2]
  C: wall_buffer_distance        [0.05, 0.10, 0.20, 0.35]
  seeds:                          [42, 43, 44]

Run:
    py -3.12 simulation/julich_calibration.py         # full scan
    py -3.12 simulation/julich_calibration.py --test  # 1 combo x 1 seed
    py -3.12 simulation/julich_calibration.py --validate A B C  # 10 seeds at given params

Outputs:
    data/julich/calibration_runs/params_A_B_C_seedS.npz  (per-run density)
    data/julich/calibration_runs/progress.jsonl         (per-run log)
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

import jupedsim as jps
from shapely import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "julich" / "calibration_runs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TARGET_JSON = ROOT / "data" / "julich" / "4D090_target_metrics.json"
PROGRESS = OUT_DIR / "progress.jsonl"

DT = 0.04
SIM_TIME = 60.0           # shortened from 100 — need steady-state form only
SAVE_START = 10.0         # skip initial transient
SAVE_END = 50.0           # window [10, 50]s for analysis
N_AGENTS = 129
SEMI_RADIUS = 3.3
BOTTLE_W = 1.0
BOTTLE_LEN = 0.2
POST_HALF_W = 2.0
POST_LEN = 3.0
V0_MEAN, V0_STD, V0_MIN, V0_MAX = 1.34, 0.26, 0.8, 2.0

# analysis grid (bottleneck approach region)
GRID_X = np.arange(-2.0, 0.0 + 1e-6, 0.2)
GRID_Y = np.arange(-2.0, 2.0 + 1e-6, 0.2)
CELL = 0.2 * 0.2

GRID_A = [0.5, 1.0, 1.5, 2.0, 3.0]
GRID_B = [0.3, 0.5, 0.8, 1.2]
GRID_C = [0.05, 0.10, 0.20, 0.35]
SEEDS = [42, 43, 44]


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


def hex_positions(rng: np.random.Generator, n: int) -> np.ndarray:
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
    if len(chosen) < n:
        raise RuntimeError(f"Only {len(chosen)} slots for {n}")
    return np.array([(x + rng.uniform(-0.01, 0.01), y + rng.uniform(-0.01, 0.01))
                     for x, y in chosen])


def run_sim(A: float, B: float, C: float, seed: int) -> dict:
    """Run one simulation, return summary + density heatmap."""
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
                time_gap=0.80,
                radius=0.15,
                strength_neighbor_repulsion=A,
                range_neighbor_repulsion=0.1,
                wall_buffer_distance=C,
                anticipation_time=1.0,
                reaction_time=B,
            )
        )

    # accumulate density in analysis window
    H = np.zeros((len(GRID_Y) - 1, len(GRID_X) - 1), dtype=np.float64)
    n_samples = 0
    wall_dist_sum = 0.0
    wall_dist_n = 0
    x_marginal = np.zeros(len(GRID_X) - 1)
    y_marginal_abs = np.zeros(len(GRID_Y) - 1)
    max_steps = int(SIM_TIME / DT)
    t0 = time.time()
    for step in range(max_steps):
        sim.iterate()
        t_cur = (step + 1) * DT
        if SAVE_START <= t_cur <= SAVE_END:
            xs = [a.position[0] for a in sim.agents()]
            ys = [a.position[1] for a in sim.agents()]
            if xs:
                h, _, _ = np.histogram2d(ys, xs, bins=(GRID_Y, GRID_X))
                H += h
                # Also accumulate wall-distance for agents in bottleneck approach (x < 0, |y|<2)
                for x, y in zip(xs, ys):
                    if -2.0 < x < 0.0 and abs(y) < 2.0:
                        wall_dist_sum += min(abs(y - BOTTLE_W / 2), abs(y + BOTTLE_W / 2))
                        wall_dist_n += 1
                n_samples += 1
        if sim.agent_count() == 0:
            break
    elapsed = time.time() - t0
    density = H / max(n_samples, 1) / CELL  # ped/m^2

    return {
        "A": A, "B": B, "C": C, "seed": seed,
        "density": density,
        "exited": N_AGENTS - sim.agent_count(),
        "elapsed": elapsed,
        "mean_wall_dist": (wall_dist_sum / wall_dist_n) if wall_dist_n else 0.0,
        "n_samples": n_samples,
    }


def compute_distance(density: np.ndarray, target: dict) -> dict:
    """Three similarity metrics vs target."""
    target_density = np.array(target["density"])

    # 1. Flattened 2D distribution → Jensen-Shannon divergence (JS)
    p = density.flatten()
    q = target_density.flatten()
    if p.sum() == 0 or q.sum() == 0:
        js = float("inf")
    else:
        p = p / p.sum()
        q = q / q.sum()
        m = 0.5 * (p + q)

        def _kl(a, b):
            mask = (a > 0) & (b > 0)
            return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))

        js = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)

    # 2. 1D Wasserstein on x-marginal (shape of queue tail along x)
    x_marg_sim = density.sum(axis=0)
    x_marg_obs = target_density.sum(axis=0)
    x_centers = 0.5 * (GRID_X[:-1] + GRID_X[1:])
    if x_marg_sim.sum() > 0 and x_marg_obs.sum() > 0:
        w_x = wasserstein_distance(x_centers, x_centers,
                                   x_marg_sim / x_marg_sim.sum(),
                                   x_marg_obs / x_marg_obs.sum())
    else:
        w_x = float("inf")

    # 3. 1D Wasserstein on |y|-marginal (queue width from centerline)
    y_centers = 0.5 * (GRID_Y[:-1] + GRID_Y[1:])
    y_abs_bins = np.abs(y_centers)
    y_marg_sim = density.sum(axis=1)
    y_marg_obs = target_density.sum(axis=1)
    if y_marg_sim.sum() > 0 and y_marg_obs.sum() > 0:
        w_y = wasserstein_distance(y_abs_bins, y_abs_bins,
                                   y_marg_sim / y_marg_sim.sum(),
                                   y_marg_obs / y_marg_obs.sum())
    else:
        w_y = float("inf")

    # Composite score (lower is better). Weight JS heavier for shape match.
    score = float(js) + float(w_x) + float(w_y)
    return {"js_div": float(js), "w_x": float(w_x), "w_y": float(w_y),
            "score": float(score)}


def append_progress(record: dict) -> None:
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def run_one(A, B, C, seed, target):
    result = run_sim(A, B, C, seed)
    dist = compute_distance(result["density"], target)
    # Save per-run density + metadata
    tag = f"A{A}_B{B}_C{C}_s{seed}"
    np.savez_compressed(OUT_DIR / f"params_{tag}.npz",
                        density=result["density"],
                        A=A, B=B, C=C, seed=seed,
                        exited=result["exited"],
                        mean_wall_dist=result["mean_wall_dist"])
    record = {
        "tag": tag, "A": A, "B": B, "C": C, "seed": seed,
        "exited": int(result["exited"]),
        "mean_wall_dist": result["mean_wall_dist"],
        "elapsed": result["elapsed"],
        **dist,
    }
    append_progress(record)
    return record


def full_scan(target: dict, resume: bool = True) -> None:
    done = set()
    if resume and PROGRESS.exists():
        with open(PROGRESS, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                done.add(rec["tag"])
        print(f"Resume: {len(done)} runs already done")

    total = len(GRID_A) * len(GRID_B) * len(GRID_C) * len(SEEDS)
    i = 0
    t_start = time.time()
    for A, B, C, seed in itertools.product(GRID_A, GRID_B, GRID_C, SEEDS):
        i += 1
        tag = f"A{A}_B{B}_C{C}_s{seed}"
        if tag in done:
            continue
        try:
            rec = run_one(A, B, C, seed, target)
            elapsed_total = time.time() - t_start
            avg_per_run = elapsed_total / max(i - len(done), 1)
            remaining = (total - i) * avg_per_run
            print(f"[{i}/{total}] A={A} B={B} C={C} s={seed}  "
                  f"exited={rec['exited']}  score={rec['score']:.3f}  "
                  f"t={rec['elapsed']:.1f}s  ETA={remaining/60:.1f}min",
                  flush=True)
        except Exception as e:
            print(f"[{i}/{total}] {tag} FAILED: {e}", flush=True)
            append_progress({"tag": tag, "A": A, "B": B, "C": C, "seed": seed,
                             "error": str(e)})


def validate(A: float, B: float, C: float, n_seeds: int = 10) -> None:
    """Re-run best params with many seeds for validation."""
    target = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    records = []
    for seed in range(100, 100 + n_seeds):
        rec = run_one(A, B, C, seed, target)
        print(f"validate seed={seed}: score={rec['score']:.3f} exited={rec['exited']}")
        records.append(rec)
    out = OUT_DIR / f"validate_A{A}_B{B}_C{C}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"\nWrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="run 1 combo x 1 seed")
    ap.add_argument("--validate", nargs=3, type=float, metavar=("A", "B", "C"),
                    help="validate 10 seeds at given params")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    if not TARGET_JSON.exists():
        print(f"Target metrics missing: {TARGET_JSON}")
        print("Run extract_target_metrics first.")
        sys.exit(1)
    target = json.loads(TARGET_JSON.read_text(encoding="utf-8"))

    if args.test:
        rec = run_one(1.5, 0.5, 0.10, 42, target)
        print("test result:", rec)
        return
    if args.validate is not None:
        A, B, C = args.validate
        validate(A, B, C)
        return
    full_scan(target, resume=not args.no_resume)


if __name__ == "__main__":
    main()
