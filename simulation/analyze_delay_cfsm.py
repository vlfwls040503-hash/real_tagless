"""Delay-based travel cost analysis for 100 CFSM scenarios.

Per-agent metrics (trajectory + agents CSV):
  - actual_time_total = sink_time - spawn_time
  - path_distance     = cumulative Euclidean distance from trajectory
  - free_time_total   = path_distance / 1.34
  - total_delay       = actual_time_total - free_time_total
  - t_gate            = first trajectory time with x >= GATE_X
  - gate_actual_time  = t_gate - spawn_time
  - gate_path_dist    = cumulative distance up to t_gate
  - free_time_gate    = gate_path_dist / 1.34
  - gate_delay        = gate_actual_time - free_time_gate
  - post_gate_delay   = total_delay - gate_delay
  - W1_time, W1_wait  = time in W1 box, and time in W1 with speed<0.2
  - W2_time, W2_wait  = time in W2 box, and time in W2 with speed<0.2
  - congestion_pre    = time with x<GATE_X and speed<0.2
  - congestion_post   = time with x>=GATE_X and speed<0.2

Only `serviced=1` agents are included.

Outputs:
  - results_cfsm_latest/agent_level_delay.csv
  - results_cfsm_latest/delay_analysis.csv
  - figures/delay_breakdown.png
  - figures/optimal_cfg_delay_based.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time as timemod
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from scipy import stats

# Korean font
for fname in ["Malgun Gothic", "NanumGothic", "AppleGothic"]:
    if any(fname in f.name for f in matplotlib.font_manager.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = fname
        break
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent

# ── Constants ───────────────────────────────────────────────────────────────
V_FREE = 1.34             # m/s, Weidmann mean
CONG_SPEED = 0.2          # m/s, congestion threshold
GATE_X = 12.0             # gate x coordinate
DT_SAMPLE = 0.5           # trajectory sampling interval (s)

# Redefined waiting zones (from docs/waiting_zones_v5.json)
W1_BOX = (6.25, 12.25, 9.25, 15.75)      # 게이트_대기
W2_BOX = (21.75, 26.75, 21.75, 26.0)     # upper_에스컬_대기

SEEDS = [42, 43, 44, 45, 46]
P_LEVELS = [0.1, 0.3, 0.5, 0.7, 0.8]
CFG_LEVELS = [1, 2, 3, 4]


def in_box(x: np.ndarray, y: np.ndarray, box: tuple) -> np.ndarray:
    x0, x1, y0, y1 = box
    return (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)


def _path_metrics(t: np.ndarray, x: np.ndarray, y: np.ndarray
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (dt, step_dist, cum_dist, speed) with len(cum_dist) = len(t)."""
    dx = np.diff(x); dy = np.diff(y); dt = np.diff(t)
    step = np.hypot(dx, dy)
    cum = np.concatenate(([0.0], np.cumsum(step)))
    speed = step / np.where(dt > 0, dt, np.inf)
    return dt, step, cum, speed


def process_agent_pair(pre: pd.DataFrame, post: pd.DataFrame,
                       spawn_time: float, approach_time: float,
                       sink_time: float, desired_speed: float,
                       ) -> dict | None:
    """Combine pre-gate + post-gate trajectory into one path.

    pre/post are trajectory rows (sorted by time) for pre- and post-gate IDs.
    The agent teleports from last pre-gate pos to first post-gate pos at the
    gate; we add the gate-housing length (BOTTLE_LEN ~0.3m) to the path.
    """
    if len(pre) < 2 or len(post) < 2:
        return None

    t_pre = pre["time"].values; x_pre = pre["x"].values; y_pre = pre["y"].values
    t_post = post["time"].values; x_post = post["x"].values; y_post = post["y"].values

    dt_pre, _, cum_pre, speed_pre = _path_metrics(t_pre, x_pre, y_pre)
    dt_post, _, cum_post, speed_post = _path_metrics(t_post, x_post, y_post)

    # Gate bridge: last pre-gate to first post-gate (straight line through gate)
    bridge = float(np.hypot(x_post[0] - x_pre[-1], y_post[0] - y_pre[-1]))
    pre_path = float(cum_pre[-1])
    post_path = float(cum_post[-1])
    path_distance = pre_path + bridge + post_path

    actual_time_total = sink_time - spawn_time
    free_time_total = path_distance / V_FREE
    total_delay = actual_time_total - free_time_total

    # Gate split at approach_enter_time (from agents CSV)
    gate_actual_time = approach_time - spawn_time
    # free_time to gate = pre_path + half of bridge
    free_time_gate = (pre_path + bridge * 0.5) / V_FREE
    gate_delay = gate_actual_time - free_time_gate
    post_gate_delay = total_delay - gate_delay

    # Congestion (each side)
    slow_pre = speed_pre < CONG_SPEED
    slow_post = speed_post < CONG_SPEED
    cong_pre = float(dt_pre[slow_pre].sum())
    cong_post = float(dt_post[slow_post].sum())

    # Zone W1 / W2 occupancy and wait (samples aligned to positions)
    x_all = np.concatenate([x_pre, x_post])
    y_all = np.concatenate([y_pre, y_post])
    in_w1_any = in_box(x_all, y_all, W1_BOX)
    in_w2_any = in_box(x_all, y_all, W2_BOX)
    w1_time = float(in_w1_any.sum() * DT_SAMPLE)
    w2_time = float(in_w2_any.sum() * DT_SAMPLE)

    # Wait in W1/W2: step-level (position at step end; speed during step)
    in_w1_pre_step = in_box(x_pre[1:], y_pre[1:], W1_BOX)
    in_w1_post_step = in_box(x_post[1:], y_post[1:], W1_BOX)
    in_w2_pre_step = in_box(x_pre[1:], y_pre[1:], W2_BOX)
    in_w2_post_step = in_box(x_post[1:], y_post[1:], W2_BOX)
    w1_wait = float(dt_pre[in_w1_pre_step & slow_pre].sum()
                    + dt_post[in_w1_post_step & slow_post].sum())
    w2_wait = float(dt_pre[in_w2_pre_step & slow_pre].sum()
                    + dt_post[in_w2_post_step & slow_post].sum())

    return {
        "actual_time_total": actual_time_total,
        "path_distance": path_distance,
        "free_time_total": free_time_total,
        "total_delay": total_delay,
        "t_gate": approach_time,
        "gate_actual_time": gate_actual_time,
        "free_time_gate": free_time_gate,
        "gate_delay": gate_delay,
        "post_gate_delay": post_gate_delay,
        "congestion_pre": cong_pre,
        "congestion_post": cong_post,
        "w1_time": w1_time,
        "w1_wait": w1_wait,
        "w2_time": w2_time,
        "w2_wait": w2_wait,
        "desired_speed": desired_speed,
    }


def process_scenario(p: float, cfg: int, seed: int, results_dir: Path,
                     ) -> tuple[pd.DataFrame, dict] | tuple[None, None]:
    sid = f"p{int(p*100):02d}_cfg{cfg}_s{seed}"
    agents_csv = results_dir / "raw" / f"agents_{sid}.csv"
    traj_csv = results_dir / "raw" / f"trajectory_{sid}.csv"
    if not agents_csv.exists() or not traj_csv.exists():
        return None, None

    agents = pd.read_csv(agents_csv)
    traj = pd.read_csv(traj_csv)

    # Only serviced agents
    agents = agents[agents["serviced"] == 1].reset_index(drop=True)
    n_serviced = len(agents)
    if n_serviced == 0:
        return None, None

    # Split trajectory by agent_id; identify pre- vs post-gate agents
    traj_grouped = {aid: g.sort_values("time").reset_index(drop=True)
                    for aid, g in traj.groupby("agent_id")}

    # Classify: agents whose FIRST x < GATE_X are pre-gate; else post-gate
    first_rows = traj.groupby("agent_id").first()
    pre_ids = set(first_rows[first_rows["x"] < GATE_X].index)
    post_ids_all = [aid for aid in first_rows.index if aid not in pre_ids]

    # Build post-gate lookup: by gate_idx → list of (first_time, agent_id)
    post_by_gate = {g: [] for g in range(7)}
    for aid in post_ids_all:
        first = traj_grouped[aid].iloc[0]
        post_by_gate[int(first["gate_idx"])].append(
            (float(first["time"]), aid))
    for g in post_by_gate:
        post_by_gate[g].sort()

    # FIFO match: for each primary (sorted by approach_enter_time within gate),
    # take next available post-gate ID.
    match = {}  # primary_aid -> post_aid
    agents_by_gate = {g: [] for g in range(7)}
    for _, ar in agents.iterrows():
        agents_by_gate[int(ar["gate_idx"])].append(
            (float(ar["approach_enter_time"]), int(ar["agent_id"])))
    for g in agents_by_gate:
        agents_by_gate[g].sort()
        post_list = post_by_gate.get(g, [])
        for i, (at, aid) in enumerate(agents_by_gate[g]):
            if i < len(post_list):
                match[aid] = post_list[i][1]

    rows = []
    for _, ar in agents.iterrows():
        aid = int(ar["agent_id"])
        if aid not in match or aid not in traj_grouped:
            continue
        pre = traj_grouped[aid]
        post = traj_grouped[match[aid]]
        m = process_agent_pair(
            pre, post,
            float(ar["spawn_time"]), float(ar["approach_enter_time"]),
            float(ar["sink_time"]), float(ar["desired_speed"]),
        )
        if m is None:
            continue
        m["scenario_id"] = sid
        m["p"] = p
        m["config"] = cfg
        m["seed"] = seed
        m["agent_id"] = aid
        m["is_tagless"] = int(ar["is_tagless"])
        m["sink_side"] = ar["sink_side"]
        rows.append(m)

    if not rows:
        return None, None
    df_agents = pd.DataFrame(rows)

    # Scenario aggregation
    agg = {
        "scenario_id": sid, "p": p, "config": cfg, "seed": seed,
        "n_serviced": n_serviced,
        "n_analyzed": len(df_agents),
        "avg_total_delay": float(df_agents["total_delay"].mean()),
        "p95_total_delay": float(df_agents["total_delay"].quantile(0.95)),
        "avg_gate_delay": float(df_agents["gate_delay"].mean()),
        "p95_gate_delay": float(df_agents["gate_delay"].quantile(0.95)),
        "avg_post_gate_delay": float(df_agents["post_gate_delay"].mean()),
        "p95_post_gate_delay": float(df_agents["post_gate_delay"].quantile(0.95)),
        "avg_congestion_pre": float(df_agents["congestion_pre"].mean()),
        "avg_congestion_post": float(df_agents["congestion_post"].mean()),
        "avg_w1_wait": float(df_agents["w1_wait"].mean()),
        "avg_w2_wait": float(df_agents["w2_wait"].mean()),
        "avg_path_distance": float(df_agents["path_distance"].mean()),
        "avg_actual_time": float(df_agents["actual_time_total"].mean()),
        "avg_free_time": float(df_agents["free_time_total"].mean()),
        "post_gate_delay_share": float(
            df_agents["post_gate_delay"].mean()
            / max(df_agents["total_delay"].mean(), 1e-6)),
    }
    return df_agents, agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results_cfsm_latest")
    ap.add_argument("--smoke", action="store_true", help="1 scenario test")
    args = ap.parse_args()

    results_dir = ROOT / args.results_dir
    if not results_dir.exists():
        print(f"ERROR: {results_dir} not found")
        sys.exit(1)

    all_agents = []
    all_scen = []
    combos = [(p, cfg, s) for p in P_LEVELS for cfg in CFG_LEVELS for s in SEEDS]
    if args.smoke:
        combos = combos[:1]

    t0 = timemod.time()
    n_missing = 0
    for i, (p, cfg, s) in enumerate(combos, 1):
        df_a, agg = process_scenario(p, cfg, s, results_dir)
        if df_a is None:
            n_missing += 1
            continue
        all_agents.append(df_a)
        all_scen.append(agg)
        if i % 20 == 0 or args.smoke:
            print(f"  [{i}/{len(combos)}] processed, elapsed {timemod.time()-t0:.0f}s")

    if not all_scen:
        print("No scenarios processed. Check results_dir.")
        sys.exit(1)

    df_agents_all = pd.concat(all_agents, ignore_index=True)
    df_scen = pd.DataFrame(all_scen)

    out_agent = results_dir / "agent_level_delay.csv"
    out_scen = results_dir / "delay_analysis.csv"
    df_agents_all.to_csv(out_agent, index=False, float_format="%.4f")
    df_scen.to_csv(out_scen, index=False, float_format="%.4f")
    print(f"Wrote {out_agent} ({len(df_agents_all):,} agents)")
    print(f"Wrote {out_scen} ({len(df_scen)} scenarios)")
    if n_missing:
        print(f"Missing/empty scenarios: {n_missing}")

    return df_agents_all, df_scen


if __name__ == "__main__":
    main()
