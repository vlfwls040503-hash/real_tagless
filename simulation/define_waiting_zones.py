"""Redefine measurement zones from actual waiting footprints in trajectories.

Method:
  1. Load all 5 baseline p=0 seeds' trajectories (300s, ~180k samples)
  2. Per-agent compute instantaneous speed (forward diff on 0.5s sampling)
  3. "Waiting" = (state == "queue") OR (speed < 0.15 m/s)
     - queue captures pre-gate waits (software queue)
     - low speed captures post-gate escalator queues, dwelling
  4. 2D histogram of waiting positions (0.5 m x 0.5 m bins)
  5. Find connected-component clusters (density > threshold)
  6. Per cluster, bound with tight rect matching 95% of waiting density
  7. Output new zone definition + visualization + compare with existing zones

Outputs:
  - docs/waiting_zones_v5.json (new zone definition)
  - figures/waiting_zone_analysis.png (heatmap + proposed zones + old zones)
  - docs/zone_redefinition.md (summary + rationale)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import ndimage

# Korean font (Windows)
for fname in ["Malgun Gothic", "NanumGothic", "AppleGothic"]:
    if any(fname in f.name for f in matplotlib.font_manager.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = fname
        break
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))
from space_layout import SPACE  # noqa: E402

TRAJ_DIR = ROOT / "results_baseline" / "raw"
OUT_JSON = ROOT / "docs" / "waiting_zones_v5.json"
OUT_FIG = ROOT / "figures" / "waiting_zone_analysis.png"
OUT_FIG.parent.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 43, 44, 45, 46]
BIN = 0.5                 # m, heatmap bin size
# Two-tier waiting: strict (v<0.15 = stationary) + congested (v<0.5 post-gate)
WAIT_SPEED_STRICT = 0.15
WAIT_SPEED_CONGESTED = 0.5   # free walk ~1.3 m/s; <0.5 m/s = >2.6x delay factor
MIN_WAIT_DENSITY = 0.02


def load_trajectories() -> pd.DataFrame:
    dfs = []
    for s in SEEDS:
        p = TRAJ_DIR / f"trajectory_p0_s{s}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df["seed"] = s
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def compute_speeds(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["seed", "agent_id", "time"]).reset_index(drop=True)
    grp = df.groupby(["seed", "agent_id"])
    df["dx"] = grp["x"].diff()
    df["dy"] = grp["y"].diff()
    df["dt"] = grp["time"].diff()
    with np.errstate(invalid="ignore", divide="ignore"):
        df["speed"] = np.hypot(df["dx"], df["dy"]) / df["dt"]
    return df


def waiting_heatmap(df: pd.DataFrame, concourse_box: tuple) -> tuple:
    x0, x1, y0, y1 = concourse_box
    # Waiting = (state=queue) OR (speed<0.5 AND state=passed)
    #   state=queue captures pre-gate software queue (always waiting).
    #   speed<0.5 m/s with state=passed captures post-gate congestion
    #   (escalator queue, dense slow walking — delay >2.6x free flow).
    mask_q = df["state"] == "queue"
    mask_s = ((df["speed"] < WAIT_SPEED_CONGESTED) & df["speed"].notna()
              & (df["state"] == "passed"))
    mask_wait = mask_q | mask_s
    wait = df[mask_wait].copy()
    print(f"Total frames: {len(df):,}")
    print(f"  queue state: {mask_q.sum():,}")
    print(f"  congested post-gate (v<{WAIT_SPEED_CONGESTED}): {mask_s.sum():,}")
    print(f"  waiting (union): {mask_wait.sum():,}  ({mask_wait.mean()*100:.1f}%)")

    # 2D histogram
    x_edges = np.arange(x0, x1 + BIN, BIN)
    y_edges = np.arange(y0, y1 + BIN, BIN)
    H, _, _ = np.histogram2d(wait["x"], wait["y"], bins=(x_edges, y_edges))
    # Normalize to "waiting frames per second per m^2"
    total_time = 300.0  # SIM_TIME
    cell_area = BIN * BIN
    # frames are at 0.5s interval → each sample = 0.5s of occupancy
    H_density = H * 0.5 / total_time / cell_area / len(SEEDS)
    return H_density, x_edges, y_edges, wait


def find_clusters(H_density, x_edges, y_edges, thr,
                  dilate_iter: int = 2) -> list:
    """Connected-component labeling with dilation to merge thin parallel queues.

    Each gate creates a separate 0.5m-wide file queue; dilation merges adjacent
    queues (G1~G7) into a single "게이트_대기" cluster.
    """
    mask = H_density > thr
    # Binary dilation merges nearby queue strips (within 2 cells = 1.0 m)
    mask_dilated = ndimage.binary_dilation(mask, iterations=dilate_iter)
    labels, n = ndimage.label(mask_dilated, structure=np.ones((3, 3)))
    clusters = []
    for lid in range(1, n + 1):
        # Restrict to the original (non-dilated) cells within this merged label
        idx = np.where((labels == lid) & mask)
        if len(idx[0]) < 4:
            continue
        xi_min, xi_max = idx[0].min(), idx[0].max()
        yi_min, yi_max = idx[1].min(), idx[1].max()
        x_min = x_edges[xi_min]
        x_max = x_edges[xi_max + 1]
        y_min = y_edges[yi_min]
        y_max = y_edges[yi_max + 1]
        area = (x_max - x_min) * (y_max - y_min)
        total = H_density[xi_min:xi_max + 1, yi_min:yi_max + 1].sum() * BIN * BIN
        peak = H_density[xi_min:xi_max + 1, yi_min:yi_max + 1].max()
        clusters.append({
            "x_range": (float(x_min), float(x_max)),
            "y_range": (float(y_min), float(y_max)),
            "area_m2": float(area),
            "total_wait_intensity": float(total),
            "peak_wait_intensity": float(peak),
            "n_cells": int(len(idx[0])),
        })
    clusters.sort(key=lambda c: c["total_wait_intensity"], reverse=True)
    return clusters


def name_cluster(c: dict, space) -> str:
    """Heuristic naming based on location relative to known landmarks."""
    x_mid = 0.5 * (c["x_range"][0] + c["x_range"][1])
    y_mid = 0.5 * (c["y_range"][0] + c["y_range"][1])
    gate_x = 12.0  # GATE_X from module
    # landmark proximity
    esc_u_wp = next(e for e in space["escalators"] if e["side"] == "upper")["waypoint"]
    esc_l_wp = next(e for e in space["escalators"] if e["side"] == "lower")["waypoint"]
    d_esc_u = np.hypot(x_mid - esc_u_wp[0], y_mid - esc_u_wp[1])
    d_esc_l = np.hypot(x_mid - esc_l_wp[0], y_mid - esc_l_wp[1])

    # Gate queue extends 5-6m behind gate (x=12). Classify any cluster
    # with its eastern edge near gate_x and x_mid<gate_x as "게이트_대기".
    x_max = c["x_range"][1]
    if x_max >= gate_x - 0.5 and x_mid < gate_x and 8 <= y_mid <= 17:
        return "게이트_대기"
    if d_esc_u < 4.5 and y_mid > 18:
        return "upper_에스컬_대기"
    if d_esc_l < 4.5 and y_mid < 8:
        return "lower_에스컬_대기"
    if x_mid < 6:
        return "계단_하행후_감속"
    if x_mid < gate_x:
        return "게이트_전_접근"
    return f"기타({x_mid:.1f}, {y_mid:.1f})"


def main() -> None:
    print("Loading trajectories ...")
    df = load_trajectories()
    print(f"Loaded {len(df):,} rows from {df['seed'].nunique()} seeds")

    df = compute_speeds(df)

    # Concourse bounding box (for heatmap)
    bbox = (-1.0, 36.0, -2.0, 27.0)
    H, xe, ye, wait = waiting_heatmap(df, bbox)
    print(f"Heatmap max density: {H.max():.4f} wait-frames/s/m^2")
    # Auto-adjust threshold if default too strict
    thr = max(MIN_WAIT_DENSITY, H.max() * 0.08)
    print(f"Using threshold: {thr:.4f}")

    clusters = find_clusters(H, xe, ye, thr)
    print(f"\nFound {len(clusters)} waiting clusters:")
    for i, c in enumerate(clusters):
        c["name"] = name_cluster(c, SPACE)
        print(f"  [{i+1}] {c['name']}: x={c['x_range']}, y={c['y_range']}, "
              f"area={c['area_m2']:.1f} m^2, total_intensity={c['total_wait_intensity']:.3f}")

    # Build new zone definitions (tight rects, slightly expanded by 0.5m buffer)
    new_zones = []
    for i, c in enumerate(clusters):
        x0, x1 = c["x_range"]
        y0, y1 = c["y_range"]
        # buffer 0.3m (but clipped to concourse)
        new_zones.append({
            "id": f"W{i+1}",
            "name": c["name"],
            "rank": i + 1,
            "purpose": "대기공간 (궤적 기반 재정의)",
            "x_range": [round(max(0.0, x0 - 0.25), 2), round(min(50.0, x1 + 0.25), 2)],
            "y_range": [round(max(-1.0, y0 - 0.25), 2), round(min(26.0, y1 + 0.25), 2)],
            "area_m2": round(c["area_m2"], 2),
            "wait_intensity_total": round(c["total_wait_intensity"], 4),
            "wait_intensity_peak": round(c["peak_wait_intensity"], 4),
        })

    # Also include reference zones for travel cost decomposition
    output = {
        "metadata": {
            "source": "results_baseline/raw/trajectory_p0_s{42..46}.csv (p=0, 5 seeds)",
            "method": ("waiting = (state=queue) OR "
                       f"(state=passed AND speed<{WAIT_SPEED_CONGESTED} m/s)"),
            "rationale": (
                "게이트 큐는 state=queue 로 식별. post-gate는 자유보행 1.3 m/s 대비 "
                f"{WAIT_SPEED_CONGESTED/1.3:.1f}× 지연 (2.6배 이상)인 경우를 체증으로 판정. "
                "순수 low-density 병목(lower 에스컬)은 체류시간이 짧아 zone에 포함되지 않음."
            ),
            "sim_time_s": 300.0,
            "bin_size_m": BIN,
            "threshold_wait_density": round(thr, 4),
            "dilation_iterations": 2,
            "seeds": SEEDS,
        },
        "waiting_zones": new_zones,
        "usage": {
            "travel_cost_formula":
                "total_cost = free_travel_time + sum_i(wait_time_i * weight_i)",
            "wait_time_i": "agent가 Wi 내에서 state=queue 또는 speed<0.5 인 시간 합계",
            "weight_i": "Fruin LOS 기반 disutility weight (D=1.0, E=1.5, F=2.5 등)",
            "free_travel_time": "agent 총 통행시간 - sum(wait_time_i)",
        },
        "excluded_findings": [
            "Z4B (lower 에스컬 대기) 기존 정의는 6 m^2 소면적으로 순간밀도 4.77 ped/m^2 "
            "(LOS F)이나, 실제 평균 체류 4.8s / 저속(<0.15) 비율 3.2% → waiting 아닌 transit. "
            "통행비용 산정 시 포함 불가.",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {OUT_JSON}")

    # Visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=100)

    # Left: heatmap (log scale) with proposed new zones
    ax = axes[0]
    im = ax.imshow(
        H.T,  # transpose so x is horizontal, y vertical
        origin="lower",
        extent=[xe[0], xe[-1], ye[0], ye[-1]],
        aspect="equal",
        cmap="hot",
        vmax=np.percentile(H[H > 0], 95) if (H > 0).any() else 1,
    )
    for z in new_zones:
        x0, x1 = z["x_range"]; y0, y1 = z["y_range"]
        rect = mpatches.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                   fill=False, edgecolor="cyan", linewidth=2)
        ax.add_patch(rect)
        ax.text(0.5 * (x0 + x1), 0.5 * (y0 + y1), z["id"],
                color="cyan", ha="center", va="center", fontsize=10, fontweight="bold")
    # Station boundary
    cc = SPACE["concourse"]
    ax.plot([0, cc["length"], cc["length"], 0, 0],
            [0, 0, cc["width"], cc["width"], 0], "w-", lw=1)
    ax.set_xlim(bbox[0], bbox[1])
    ax.set_ylim(bbox[2], bbox[3])
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Waiting footprint heatmap + proposed zones (n={len(new_zones)})")
    plt.colorbar(im, ax=ax, shrink=0.7, label="wait-frames/s/m^2")

    # Right: new zones vs old zones overlay
    ax = axes[1]
    # plot concourse outline
    import matplotlib.patches as mp
    ob = SPACE["outer_boundary"]
    xs_ob = [p[0] for p in ob] + [ob[0][0]]
    ys_ob = [p[1] for p in ob] + [ob[0][1]]
    ax.plot(xs_ob, ys_ob, "k-", lw=1.5)

    # old zones (gray dashed)
    for z in SPACE["zones"]:
        if z["id"] == "Z1":
            continue  # Skip the whole concourse
        x0, x1 = z["x_range"]; y0, y1 = z["y_range"]
        r = mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                         fill=False, edgecolor="gray", linestyle="--", linewidth=1)
        ax.add_patch(r)
        ax.text(0.5 * (x0 + x1), 0.5 * (y0 + y1), z["id"],
                color="gray", ha="center", va="center", fontsize=8, alpha=0.7)

    # new zones (blue solid)
    for z in new_zones:
        x0, x1 = z["x_range"]; y0, y1 = z["y_range"]
        r = mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                         fill=True, facecolor="blue", edgecolor="blue",
                         alpha=0.3, linewidth=2)
        ax.add_patch(r)
        ax.text(0.5 * (x0 + x1), 0.5 * (y0 + y1), z["id"] + "\n" + z["name"],
                color="navy", ha="center", va="center", fontsize=8, fontweight="bold")

    # structures (gates, stairs, escalators) — light markers
    for s in SPACE.get("structures", []):
        x0, x1 = s["x_range"]; y0, y1 = s["y_range"]
        r = mp.Rectangle((x0, y0), x1 - x0, y1 - y0,
                         fill=True, facecolor="#FFE0B0", edgecolor="orange", alpha=0.4)
        ax.add_patch(r)

    ax.set_xlim(bbox[0], bbox[1])
    ax.set_ylim(bbox[2], bbox[3])
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("New waiting zones (blue) vs old zones (gray dashed)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(OUT_FIG, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"Wrote {OUT_FIG}")

    # Per-zone waiting time distribution (how much time each agent waits in each zone)
    print("\n=== Waiting time per zone (p=0 baseline, 5 seeds) ===")
    per_zone_stats = {}
    for z in new_zones:
        x0, x1 = z["x_range"]; y0, y1 = z["y_range"]
        in_zone = ((wait["x"] >= x0) & (wait["x"] <= x1) &
                   (wait["y"] >= y0) & (wait["y"] <= y1))
        sub = wait[in_zone]
        n_samples = len(sub)
        # Per-(seed, agent) dwell time
        dwell_per = sub.groupby(["seed", "agent_id"]).size() * 0.5  # 0.5s sampling
        if len(dwell_per) == 0:
            continue
        per_zone_stats[z["id"]] = {
            "total_wait_s_all_seeds": float(n_samples * 0.5),
            "unique_agents_all_seeds": int(len(dwell_per)),
            "mean_wait_per_waiting_agent_s": float(dwell_per.mean()),
            "median_wait_s": float(dwell_per.median()),
            "p95_wait_s": float(dwell_per.quantile(0.95)),
        }
        print(f"  {z['id']} ({z['name']}): total {n_samples*0.5:.0f}s across "
              f"{len(dwell_per)} waiter-trips; per-waiter mean {dwell_per.mean():.1f}s, "
              f"median {dwell_per.median():.1f}s, p95 {dwell_per.quantile(0.95):.1f}s")

    # Save per-zone stats into output
    for z in output["waiting_zones"]:
        if z["id"] in per_zone_stats:
            z["empirical_stats_p0"] = per_zone_stats[z["id"]]
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
