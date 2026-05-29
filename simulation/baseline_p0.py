"""Baseline p=0 simulation runner (all tag users, 5 seeds).

Reuses run_west_simulation_cfsm_escalator (same as batch_runner uses).
Does NOT modify any existing module.

Params (match scenarios/scenario_matrix.py v3 conventions):
  - TAGLESS_RATIO = 0.0 (all tag users)
  - BATCH_TAGLESS_ONLY_GATES = frozenset() (no tagless-only gates, all 7 gates accept tag)
  - TRAIN_INTERVAL = 150, TRAIN_ALIGHTING = 200, SIM_TIME = 300
  - seeds 42~46

Output (under results_baseline/):
  - raw/agents_p0_s{seed}.csv
  - raw/zones_p0_s{seed}.csv
  - raw/trajectory_p0_s{seed}.csv
  - p0_seed_{seed}.csv (flat trajectory copy per user spec)
  - p0_summary.json (all 5 seeds aggregated)
"""
from __future__ import annotations

import csv
import importlib
import json
import os
import pathlib
import sys
import time
from datetime import datetime

import numpy as np

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulation"))

OUT_DIR = ROOT / "results_baseline"
RAW_DIR = OUT_DIR / "raw"
OUT_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
LOG_PATH = OUT_DIR / "execution_log.txt"

SEEDS = [42, 43, 44, 45, 46]

# v3 scenario constants
TRAIN_INTERVAL = 150.0
TRAIN_ALIGHTING = 200
SIM_TIME = 300.0

# Zone areas (identical to batch_runner v3)
AREAS = {
    "z1": 50 * 25, "z2": 4 * 7,
    "z3a": 8 * 3, "z3b": 2 * 3, "z3c": 10 * 3,
    "z4a": 8 * 3, "z4b": 2 * 3, "z4c": 10 * 3,
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_seed(seed: int) -> dict:
    sid = f"p0_s{seed}"
    # Fresh reload to clear module-global state
    import run_west_simulation_cfsm_escalator as runner
    importlib.reload(runner)

    runner.TAGLESS_RATIO = 0.0
    runner.BATCH_TAGLESS_ONLY_GATES = frozenset()  # all tag gates
    runner.BATCH_SEED = seed
    runner.TRAIN_INTERVAL = TRAIN_INTERVAL
    runner.TRAIN_ALIGHTING = TRAIN_ALIGHTING
    runner.SIM_TIME = SIM_TIME

    runner.BATCH_METRICS_OUT = RAW_DIR / f"agents_{sid}.csv"
    runner.BATCH_ZONE_CSV_OUT = RAW_DIR / f"zones_{sid}.csv"
    runner.BATCH_OUTPUT_SUFFIX = f"_{sid}"
    runner.BATCH_SKIP_HEAVY_OUTPUTS = True
    runner.BATCH_SAVE_TRAJECTORY = True
    runner.BATCH_TRAJECTORY_OUT = RAW_DIR / f"trajectory_{sid}.csv"
    runner.BATCH_TRAJECTORY_INTERVAL = 0.5

    t0 = time.time()
    stats, spawned = runner.run_simulation()
    wall = time.time() - t0
    passed = sum(stats["gate_counts"])
    log(f"  {sid}: spawned={spawned} passed={passed} wall={wall:.1f}s")

    # Also copy trajectory to the user-spec flat path
    traj_src = RAW_DIR / f"trajectory_{sid}.csv"
    traj_dst = OUT_DIR / f"p0_seed_{seed}.csv"
    if traj_src.exists():
        traj_dst.write_bytes(traj_src.read_bytes())

    return _aggregate(sid, seed, spawned, passed, stats, wall)


def _aggregate(sid: str, seed: int, spawned: int, passed: int,
               stats: dict, wall: float) -> dict:
    agent_csv = RAW_DIR / f"agents_{sid}.csv"
    travel_times, gate_waits, post_gates, esc_precise = [], [], [], []
    n_exit1 = n_exit4 = 0
    if agent_csv.exists():
        with open(agent_csv, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                tt = row.get("travel_time")
                if tt and tt != "None":
                    travel_times.append(float(tt))
                gw = row.get("gate_wait_time")
                if gw and gw != "None":
                    gate_waits.append(float(gw))
                pg = row.get("post_gate_time")
                if pg and pg != "None":
                    post_gates.append(float(pg))
                ewp = row.get("esc_wait_precise")
                if ewp and ewp != "None":
                    esc_precise.append(float(ewp))
                side = row.get("sink_side", "")
                if side == "lower":
                    n_exit1 += 1
                elif side == "upper":
                    n_exit4 += 1

    zone_csv = RAW_DIR / f"zones_{sid}.csv"
    zone_series = {k: [] for k in AREAS}
    if zone_csv.exists():
        with open(zone_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            is_v3 = "zone3a_count" in header
            for row in reader:
                if is_v3:
                    t, z1, z2, z3a, z3b, z3c, z4a, z4b, z4c = row
                    vals = {"z1": z1, "z2": z2, "z3a": z3a, "z3b": z3b,
                            "z3c": z3c, "z4a": z4a, "z4b": z4b, "z4c": z4c}
                else:
                    t, z1, z2, z3, z4 = row
                    vals = {"z1": z1, "z2": z2, "z3b": z3, "z4b": z4,
                            "z3a": 0, "z3c": 0, "z4a": 0, "z4c": 0}
                for k in AREAS:
                    zone_series[k].append(int(vals[k]) / AREAS[k])

    def _s(series, fn, default=0.0):
        return float(fn(series)) if series else default

    out = {
        "scenario_id": sid,
        "seed": seed,
        "spawned": spawned,
        "passed": passed,
        "pass_rate": passed / spawned if spawned > 0 else 0.0,
        "wall_time_s": wall,
        "avg_travel_time": float(np.mean(travel_times)) if travel_times else 0.0,
        "p95_travel_time": float(np.percentile(travel_times, 95)) if travel_times else 0.0,
        "n_completed": len(travel_times),
        "avg_gate_wait": float(np.mean(gate_waits)) if gate_waits else 0.0,
        "p95_gate_wait": float(np.percentile(gate_waits, 95)) if gate_waits else 0.0,
        "avg_post_gate": float(np.mean(post_gates)) if post_gates else 0.0,
        "p95_post_gate": float(np.percentile(post_gates, 95)) if post_gates else 0.0,
        "avg_esc_wait_precise": float(np.mean(esc_precise)) if esc_precise else 0.0,
        "n_exit1": n_exit1,
        "n_exit4": n_exit4,
        "exit1_share": n_exit1 / (n_exit1 + n_exit4) if (n_exit1 + n_exit4) > 0 else 0.0,
    }
    for k in AREAS:
        out[f"{k}_avg"] = _s(zone_series[k], np.mean)
        out[f"{k}_max"] = _s(zone_series[k], np.max)
    return out


def main() -> None:
    log(f"Baseline p=0 run: {len(SEEDS)} seeds, SIM_TIME={SIM_TIME}s")
    all_results = []
    t_start = time.time()
    for seed in SEEDS:
        log(f"Starting seed={seed} ...")
        r = run_seed(seed)
        all_results.append(r)

    # summary
    summary = {
        "config": {
            "p": 0.0,
            "tagless_only_gates": [],
            "train_interval": TRAIN_INTERVAL,
            "train_alighting": TRAIN_ALIGHTING,
            "sim_time": SIM_TIME,
            "seeds": SEEDS,
            "model": "CFSM V2 (escalator variant)",
        },
        "per_seed": all_results,
    }

    # Aggregate across seeds
    keys_numeric = [k for k in all_results[0] if isinstance(all_results[0][k], (int, float))
                    and k not in ("seed",)]
    agg = {}
    for k in keys_numeric:
        vals = [r[k] for r in all_results]
        agg[k] = {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
                  "min": float(np.min(vals)), "max": float(np.max(vals))}
    summary["aggregated"] = agg

    with open(OUT_DIR / "p0_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log(f"Wrote {OUT_DIR / 'p0_summary.json'}")
    log(f"Total wall time: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
