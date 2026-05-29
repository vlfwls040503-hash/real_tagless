"""Escalator queue-violation behavior analysis for CFSM V2 escalator sim.

Goal: identify why some agents ignore queue and charge through others to
reach the escalator waypoint.

Trajectory: output/trajectories_escalator.csv  (t, agent_id, x, y, gate_idx, state)

Escalator positions (from seongsu_west_escalator SPACE):
  lower_wp = (25.0, -1.0), capture = (24.5-26.0, -1.0-0.0)
  upper_wp = (25.0, 25.0), capture = (24.5-26.0, 25.0-26.0)

Violations analyzed:
  V1) Overtake: agent reaches wp region but an earlier-arriver is still waiting.
  V2) Dense-push: agent moves at high speed while >=2 agents within 0.5m.
  V3) Lateral approach (side entry): agent enters capture from outside the
     waiting zone cone (ex: y=23 moving sideways to wp(25,25) from x<24).
  V4) Boundary cut: agent trajectory passes closer than 0.2m to wall
     y=0 or y=25 (corridor wall) while going to wp.

Outputs:
  data/escalator_analysis/violations_per_agent.csv
  figures/escalator_violation_trajectories.png  (top offenders)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TRAJ = ROOT / "output" / "trajectories_escalator.csv"
OUT_DIR = ROOT / "data" / "escalator_analysis"
OUT_DIR.mkdir(exist_ok=True)
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

plt.rcParams["figure.dpi"] = 100
plt.rcParams["savefig.dpi"] = 100

WP_UPPER = np.array([25.0, 25.0])
WP_LOWER = np.array([25.0, -1.0])
SPREAD_R = 1.2       # same as STOPPED_SPREAD_R
QUEUE_Y_BAND = 1.8   # consider agents within this y-dist of wp as "in waiting zone"


def add_kinematics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["agent_id", "time"]).copy()
    df["dx"] = df.groupby("agent_id")["x"].diff()
    df["dy"] = df.groupby("agent_id")["y"].diff()
    df["dt"] = df.groupby("agent_id")["time"].diff()
    df["speed"] = np.hypot(df["dx"], df["dy"]) / df["dt"]
    return df


def assign_side(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["side"] = np.where(df["y"] > 12.5, "upper", "lower")
    df["wp_x"] = np.where(df["side"] == "upper", WP_UPPER[0], WP_LOWER[0])
    df["wp_y"] = np.where(df["side"] == "upper", WP_UPPER[1], WP_LOWER[1])
    df["d_wp"] = np.hypot(df["x"] - df["wp_x"], df["y"] - df["wp_y"])
    return df


def detect_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-agent violation flags."""
    out = []
    # only look at agents that actually approach escalator zone
    near = df[df["d_wp"] < 3.0]
    for aid, g in near.groupby("agent_id"):
        if len(g) < 5:
            continue
        side = g["side"].iloc[-1]
        wp = WP_UPPER if side == "upper" else WP_LOWER
        # V2 dense-push
        frames = df[df["time"].isin(g["time"])]
        push_frames = 0
        for t, sub in frames.groupby("time"):
            me = sub[sub["agent_id"] == aid]
            if me.empty:
                continue
            mx, my = me["x"].iloc[0], me["y"].iloc[0]
            me_sp = me["speed"].iloc[0] if not np.isnan(me["speed"].iloc[0]) else 0
            if me_sp < 0.4:
                continue
            others = sub[sub["agent_id"] != aid]
            close = others[np.hypot(others["x"] - mx, others["y"] - my) < 0.5]
            if len(close) >= 2:
                push_frames += 1
        v2_dense_push = push_frames
        # V3 lateral approach: when first crossing d_wp<1.5, check angle vs wp
        cross = g[g["d_wp"] < 1.5]
        v3_lateral = 0
        if len(cross) > 0:
            first = cross.iloc[0]
            # direction vector (from gate area toward wp)
            dx_to_wp = wp[0] - first["x"]
            dy_to_wp = wp[1] - first["y"]
            # For upper wp, agents should approach primarily +y. For lower wp, -y.
            # Lateral if |dx| > |dy|
            if abs(dx_to_wp) > abs(dy_to_wp):
                v3_lateral = 1
        # V4 boundary cut: y range close to bottleneck walls
        v4_boundary = 0
        if side == "upper":
            v4_boundary = int(((g["y"] > 24.0) & (g["x"] < 24.0)).any()
                              or ((g["y"] > 24.0) & (g["x"] > 26.5)).any())
        else:
            v4_boundary = int(((g["y"] < 1.0) & (g["x"] < 24.0)).any()
                              or ((g["y"] < 1.0) & (g["x"] > 26.5)).any())
        # V1 overtake: did this agent enter capture before any earlier-entering
        # agent left? (need capture_enter times — proxy: first time in capture zone)
        cap = g[g["d_wp"] < 1.0]
        my_enter_t = cap["time"].min() if not cap.empty else None

        max_speed_near_wp = g[g["d_wp"] < 1.5]["speed"].max() if (g["d_wp"] < 1.5).any() else 0
        min_nbr_dist_near_wp = float("nan")

        out.append({
            "agent_id": aid,
            "side": side,
            "v2_dense_push": v2_dense_push,
            "v3_lateral": v3_lateral,
            "v4_boundary": v4_boundary,
            "max_speed_near_wp": float(max_speed_near_wp) if not np.isnan(max_speed_near_wp) else 0.0,
            "my_capture_enter": my_enter_t,
            "min_d_wp": g["d_wp"].min(),
        })
    return pd.DataFrame(out)


def plot_top_offenders(df: pd.DataFrame, viol: pd.DataFrame, n: int = 8) -> None:
    viol2 = viol.copy()
    viol2["score"] = (viol2["v2_dense_push"] + 3 * viol2["v3_lateral"]
                      + 5 * viol2["v4_boundary"])
    top = viol2.sort_values("score", ascending=False).head(n)
    fig, axes = plt.subplots(2, 4, figsize=(13, 7), sharex=True, sharey=True)
    for ax, (_, row) in zip(axes.flat, top.iterrows()):
        aid = row["agent_id"]
        tr = df[df["agent_id"] == aid].sort_values("time")
        # plot other nearby agents at time of approach
        first_close = tr[tr["d_wp"] < 2.0].iloc[:1] if (tr["d_wp"] < 2.0).any() else None
        if first_close is not None and len(first_close):
            t_focus = first_close["time"].iloc[0]
            others = df[(df["time"] > t_focus - 0.2) & (df["time"] < t_focus + 0.2)
                        & (df["agent_id"] != aid)]
            ax.scatter(others["x"], others["y"], s=2, c="lightgray", alpha=0.7)
        ax.plot(tr["x"], tr["y"], "r-", lw=1.2, alpha=0.9)
        ax.plot(tr["x"].iloc[0], tr["y"].iloc[0], "go", ms=6, label="start")
        ax.plot(tr["x"].iloc[-1], tr["y"].iloc[-1], "rx", ms=8, label="end")
        wp = WP_UPPER if row["side"] == "upper" else WP_LOWER
        ax.plot(wp[0], wp[1], "b*", ms=10)
        ax.set_title(f"agent {aid} {row['side']}\n"
                     f"push={row['v2_dense_push']} lat={row['v3_lateral']} bd={row['v4_boundary']}",
                     fontsize=9)
        ax.set_aspect("equal")
    fig.suptitle("Top queue-violation offenders (CFSM V2 escalator sim)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "escalator_violation_trajectories.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = pd.read_csv(TRAJ)
    df = add_kinematics(df)
    df = assign_side(df)
    print(f"rows: {len(df):,}, agents: {df['agent_id'].nunique()}")

    viol = detect_violations(df)
    viol.to_csv(OUT_DIR / "violations_per_agent.csv", index=False)
    print(f"\nViolation summary (n_agents: {len(viol)}):")
    print(f"  V2 dense-push frames > 0: {(viol['v2_dense_push'] > 0).sum()} agents")
    print(f"  V2 mean push frames: {viol['v2_dense_push'].mean():.2f}")
    print(f"  V3 lateral approach: {viol['v3_lateral'].sum()} agents ({100*viol['v3_lateral'].mean():.1f}%)")
    print(f"  V4 boundary cut: {viol['v4_boundary'].sum()} agents ({100*viol['v4_boundary'].mean():.1f}%)")
    print(f"  max speed near wp: mean={viol['max_speed_near_wp'].mean():.2f}, "
          f"p95={viol['max_speed_near_wp'].quantile(0.95):.2f} m/s")

    # Summary by side
    for side in ["upper", "lower"]:
        s = viol[viol["side"] == side]
        print(f"\n{side}: n={len(s)} agents, "
              f"v2>0={((s['v2_dense_push']>0).sum())}, "
              f"v3={s['v3_lateral'].sum()}, "
              f"v4={s['v4_boundary'].sum()}")

    plot_top_offenders(df, viol)
    print(f"\nWrote {OUT_DIR/'violations_per_agent.csv'}")
    print(f"Wrote {FIG_DIR/'escalator_violation_trajectories.png'}")


if __name__ == "__main__":
    main()
