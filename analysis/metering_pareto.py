"""
미터링 (상류/하류 분리) + Pareto (효율성-안전성) 분석.

입력:
  - results_cfsm_latest/ (p=0.1~0.8 × K=1~6 × 5seed)
  - results_baseline_p0_k0/ (baseline: p=0 K=0 × 5seed)

출력:
  - analysis/upstream_downstream_summary.csv
  - analysis/k_comparison_p50.png
  - analysis/upstream_vs_downstream_metrics.png
  - analysis/pareto_scatter.png
  - analysis/pareto_frontier_table.csv
  - analysis/delta_table.csv
"""
from __future__ import annotations
from pathlib import Path
import sys
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))
from space_layout import SPACE  # noqa

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = ROOT / "analysis"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# 영역 정의
GATE_LINE_X = 12.0
UP_BBOX = (0.0, 12.0, 5.0, 20.0)        # 상류 (대합실 + 게이트 큐)
DOWN_BBOX = (13.5, 36.0, -2.0, 28.0)    # 하류 (게이트 후 ~ 에스컬)

UP_AREA = (UP_BBOX[1] - UP_BBOX[0]) * (UP_BBOX[3] - UP_BBOX[2])
DOWN_AREA = (DOWN_BBOX[1] - DOWN_BBOX[0]) * (DOWN_BBOX[3] - DOWN_BBOX[2])


def los_grade(d):
    if d <= 0.3: return "A"
    if d <= 0.4: return "B"
    if d <= 0.7: return "C"
    if d <= 1.0: return "D"
    if d <= 2.0: return "E"
    return "F"


def zone_peak_density(traj_df, bbox, t_window=(60, 540)):
    """zone 시점별 인구 (frame 단위) / 면적 → 시계열 max (이전 분석과 일관)."""
    sub = traj_df[(traj_df["time"] >= t_window[0]) & (traj_df["time"] <= t_window[1])]
    sub = sub[(sub["x"] >= bbox[0]) & (sub["x"] <= bbox[1]) &
              (sub["y"] >= bbox[2]) & (sub["y"] <= bbox[3])]
    if len(sub) == 0: return 0.0
    area = (bbox[1] - bbox[0]) * (bbox[3] - bbox[2])
    counts_per_t = sub.groupby("time").size()
    return float(counts_per_t.max() / area) if len(counts_per_t) else 0.0


def grid_peak_density(traj_df, bbox, t_window=(60, 540), grid_m=1.0, time_bin=1.0):
    """1m × 1m 격자, 1초 평균 → 시공간 max."""
    sub = traj_df[(traj_df["time"] >= t_window[0]) & (traj_df["time"] <= t_window[1])]
    sub = sub[(sub["x"] >= bbox[0]) & (sub["x"] <= bbox[1]) &
              (sub["y"] >= bbox[2]) & (sub["y"] <= bbox[3])]
    if len(sub) == 0:
        return 0.0
    times = np.arange(t_window[0], t_window[1], time_bin)
    xs = np.arange(bbox[0], bbox[1], grid_m)
    ys = np.arange(bbox[2], bbox[3], grid_m)
    peak = 0.0
    for t in times:
        f = sub[(sub["time"] >= t) & (sub["time"] < t + time_bin)]
        if len(f) == 0: continue
        H, _, _ = np.histogram2d(f["x"], f["y"], bins=[xs, ys])
        d = H / (grid_m * grid_m)
        peak = max(peak, d.max())
    return float(peak)


def queue_length(traj_df, t_window=(60, 540)):
    """state == 'queue' 의 평균 인원 = 평균 큐 길이 (m 환산은 인원수)."""
    sub = traj_df[(traj_df["time"] >= t_window[0]) & (traj_df["time"] <= t_window[1])]
    sub = sub[sub["state"] == "queue"]
    if len(sub) == 0: return 0.0
    return sub.groupby("time").size().mean()


def analyze_scenario(traj_path, agents_path):
    """단일 시나리오 metric."""
    traj = pd.read_csv(traj_path)
    agents = pd.read_csv(agents_path)

    up_density_peak = grid_peak_density(traj, UP_BBOX)
    down_density_peak = grid_peak_density(traj, DOWN_BBOX)
    # W2 zone (에스컬 앞) 시점별 평균 → max (학술 표준)
    W2_BBOX = (23.75, 28.75, 20.75, 24.75)
    w2_peak = zone_peak_density(traj, W2_BBOX)

    up_wait_mean = float(agents["gate_wait_time"].dropna().mean()) if "gate_wait_time" in agents else float("nan")
    esc_wait_mean = float(agents["esc_wait_precise"].dropna().mean()) if "esc_wait_precise" in agents else float("nan")
    travel_mean = float(agents["travel_time"].dropna().mean()) if "travel_time" in agents else float("nan")

    queue_avg = queue_length(traj)

    return {
        "up_wait": up_wait_mean,
        "up_peak": up_density_peak,
        "queue_avg": queue_avg,
        "down_peak_grid": down_density_peak,
        "W2_peak_zone": w2_peak,
        "esc_wait": esc_wait_mean,
        "travel": travel_mean,
    }


def collect_all():
    """모든 시나리오 + baseline 수집."""
    rows = []

    # 본 시뮬
    summary = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
    summary["pass_rate"] = summary["passed"] / summary["spawned"].clip(lower=1)
    valid = summary[(summary["pass_rate"] >= 0.9) &
                    (summary["config"].isin([1, 2, 3, 4, 5, 6]))]

    for _, r in valid.iterrows():
        sid = r["scenario_id"]
        tp = ROOT / "results_cfsm_latest" / "raw" / f"trajectory_{sid}.csv"
        ap = ROOT / "results_cfsm_latest" / "raw" / f"agents_{sid}.csv"
        if not (tp.exists() and ap.exists()): continue
        m = analyze_scenario(tp, ap)
        m.update({"p": r["p"], "K": int(r["config"]), "seed": int(r["seed"])})
        rows.append(m)

    # baseline (p=0 K=0)
    base_sum = pd.read_csv(ROOT / "results_baseline_p0_k0" / "summary.csv")
    for _, r in base_sum.iterrows():
        sid = r["scenario_id"]
        tp = ROOT / "results_baseline_p0_k0" / "raw" / f"trajectory_{sid}.csv"
        ap = ROOT / "results_baseline_p0_k0" / "raw" / f"agents_{sid}.csv"
        if not (tp.exists() and ap.exists()): continue
        m = analyze_scenario(tp, ap)
        m.update({"p": 0.0, "K": 0, "seed": int(r["seed"])})
        rows.append(m)

    return pd.DataFrame(rows)


def main():
    print("[1/5] 시나리오별 metric 추출 중...")
    df = collect_all()
    print(f"  총 {len(df)} 시나리오")

    # ── 미터링: (p, K) 평균 ──
    agg = df.groupby(["p", "K"]).agg(
        up_wait=("up_wait", "mean"),
        up_peak=("up_peak", "mean"),
        queue_avg=("queue_avg", "mean"),
        down_peak_grid=("down_peak_grid", "mean"),  # 격자 1m × 1m × 1초 max (spike)
        down_peak=("W2_peak_zone", "mean"),  # W2 zone 평균 → max (학술 표준)
        esc_wait=("esc_wait", "mean"),
        travel=("travel", "mean"),
        n=("seed", "count"),
    ).reset_index()
    agg["down_LOS"] = agg["down_peak"].apply(los_grade)
    agg.to_csv(OUT / "upstream_downstream_summary.csv", index=False, encoding="utf-8-sig")
    print(f"  저장: analysis/upstream_downstream_summary.csv ({len(agg)} 행)")

    # ── 미터링 그림 1: K=2 vs K=3 (p=0.5) 평면 비교 ──
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), dpi=130)
    for ax, K, sid in [
        (axes[0], 3, "p50_cfg3_s42"),
        (axes[1], 2, "p50_cfg2_s42"),
    ]:
        traj = pd.read_csv(ROOT / "results_cfsm_latest" / "raw" / f"trajectory_{sid}.csv")
        # t=240s 스냅샷
        f = traj[traj["time"] == 240.0]
        # 외곽
        ob = SPACE["outer_boundary"]
        ax.plot([p[0] for p in ob] + [ob[0][0]],
                [p[1] for p in ob] + [ob[0][1]],
                color="black", linewidth=1.5)
        # 영역
        ax.add_patch(Rectangle((UP_BBOX[0], UP_BBOX[2]),
                               UP_BBOX[1] - UP_BBOX[0], UP_BBOX[3] - UP_BBOX[2],
                               fill=False, edgecolor="#1F77B4", linewidth=1.5,
                               linestyle="--", alpha=0.7))
        ax.add_patch(Rectangle((DOWN_BBOX[0], DOWN_BBOX[2]),
                               DOWN_BBOX[1] - DOWN_BBOX[0], DOWN_BBOX[3] - DOWN_BBOX[2],
                               fill=False, edgecolor="#D62728", linewidth=1.5,
                               linestyle="--", alpha=0.7))
        # 게이트 라인
        ax.axvline(GATE_LINE_X, color="black", linestyle=":", linewidth=2, alpha=0.8)
        # 보행자 점
        ax.scatter(f["x"], f["y"], s=15, c="#534AB7", alpha=0.7, edgecolors="none")
        ax.set_xlim(-2, 38); ax.set_ylim(-3, 28)
        ax.set_aspect("equal")
        ax.set_title(f"K = {K} (p=0.5, t=240s)", fontsize=12, fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([])
        ax.text(6, 22, "상류", color="#1F77B4", fontsize=11, fontweight="bold")
        ax.text(25, 22, "하류", color="#D62728", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(FIG / "k_comparison_p50.png", dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  저장: figures/k_comparison_p50.png")

    # ── 미터링 그림 2: K별 상류/하류 peak 밀도 막대 (p=0.5) ──
    sub = agg[agg["p"] == 0.5].sort_values("K")
    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    x = np.arange(len(sub))
    w = 0.35
    ax.bar(x - w/2, sub["up_peak"], w, label="상류 peak 밀도", color="#1F77B4")
    ax.bar(x + w/2, sub["down_peak"], w, label="하류 peak 밀도", color="#D62728")
    ax.axhline(1.0, color="orange", linestyle="--", alpha=0.7, label="LOS D 한계 (1.0)")
    ax.axhline(2.0, color="red", linestyle="--", alpha=0.7, label="LOS E 한계 (2.0)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"K={int(k)}" for k in sub["K"]])
    ax.set_ylabel("Peak 밀도 (인/m²)", fontsize=11)
    ax.set_title("상류 vs 하류 peak 밀도 (p=0.5)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(FIG / "upstream_vs_downstream_metrics.png", dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  저장: figures/upstream_vs_downstream_metrics.png")

    # ── Pareto: 모든 (p, K) 평균 + frontier ──
    pareto_df = agg.copy()
    pareto_df["효율성"] = pareto_df["travel"]      # 작을수록 좋음
    pareto_df["안전성"] = pareto_df["down_peak"]   # 작을수록 좋음

    # Pareto frontier (둘 다 작을수록 좋음 → 비지배)
    def is_pareto(idx, df):
        x, y = df.loc[idx, "효율성"], df.loc[idx, "안전성"]
        for j in df.index:
            if j == idx: continue
            xj, yj = df.loc[j, "효율성"], df.loc[j, "안전성"]
            if xj <= x and yj <= y and (xj < x or yj < y):
                return False
        return True

    pareto_df["frontier"] = [is_pareto(i, pareto_df) for i in pareto_df.index]
    pareto_df.to_csv(OUT / "pareto_frontier_table.csv", index=False, encoding="utf-8-sig")
    print(f"  저장: analysis/pareto_frontier_table.csv")

    # Pareto 그림
    fig, ax = plt.subplots(figsize=(9, 6), dpi=130)
    p_levels = sorted(pareto_df["p"].unique())
    cmap = plt.get_cmap("viridis")
    p_colors = {p: cmap(i / max(len(p_levels)-1, 1)) for i, p in enumerate(p_levels)}
    K_markers = {0: "*", 1: "o", 2: "s", 3: "^", 4: "D", 5: "P", 6: "X"}

    for _, r in pareto_df.iterrows():
        m = K_markers.get(int(r["K"]), "o")
        c = p_colors[r["p"]]
        size = 200 if r["frontier"] else 80
        ax.scatter(r["효율성"], r["안전성"], c=[c], marker=m, s=size,
                   edgecolors="black", linewidths=1.2 if r["frontier"] else 0.5,
                   alpha=0.9, zorder=3)

    front = pareto_df[pareto_df["frontier"]].sort_values("효율성")
    if len(front) >= 2:
        ax.plot(front["효율성"], front["안전성"], "k-",
                linewidth=1.2, alpha=0.6, zorder=2, label="Pareto frontier")

    ax.axhline(0.7, color="green", linestyle="--", alpha=0.5, label="LOS C 한계 (0.7)")
    ax.axhline(1.0, color="orange", linestyle="--", alpha=0.5, label="LOS D 한계 (1.0)")
    ax.axhline(2.0, color="red", linestyle="--", alpha=0.5, label="LOS E 한계 (2.0)")

    ax.set_xlabel("평균 통행시간 (s) — 작을수록 효율적", fontsize=11)
    ax.set_ylabel("하류 peak 밀도 (인/m²) — 작을수록 안전", fontsize=11)
    ax.set_title("효율성 vs 안전성 Pareto 산점도\n(점 색=p, 마커=K, 큰 점=Pareto frontier)",
                 fontsize=12, fontweight="bold")
    # 범례
    p_handles = [plt.scatter([], [], c=[p_colors[p]], s=80, label=f"p={p}") for p in p_levels]
    K_handles = [plt.scatter([], [], c="gray", marker=K_markers[k], s=80, label=f"K={k}")
                 for k in sorted(pareto_df["K"].unique())]
    leg1 = ax.legend(handles=p_handles, loc="upper left", title="p", fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=K_handles, loc="upper right", title="K", fontsize=8)
    ax.grid(alpha=0.3)

    # 좌하단 라벨
    ax.text(0.02, 0.02, "← 효율↑ + 안전↑ 영역", transform=ax.transAxes,
            color="green", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(FIG / "pareto_scatter.png", dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  저장: figures/pareto_scatter.png")

    # ── Δ 표 (baseline 대비) ──
    base = pareto_df[(pareto_df["p"] == 0.0) & (pareto_df["K"] == 0)].iloc[0]
    delta = pareto_df.copy()
    delta["Δ통행시간(%)"] = (delta["travel"] - base["travel"]) / base["travel"] * 100
    delta["Δ최대밀도(%)"] = (delta["down_peak"] - base["down_peak"]) / base["down_peak"] * 100

    def evaluate(r):
        eff = "효율↑" if r["Δ통행시간(%)"] < 0 else "효율↓"
        saf = "안전↑" if r["Δ최대밀도(%)"] < 0 else "안전↓"
        return f"{eff}{saf}"
    delta["종합평가"] = delta.apply(evaluate, axis=1)
    delta_out = delta[["p", "K", "travel", "down_peak", "Δ통행시간(%)", "Δ최대밀도(%)", "종합평가"]]
    delta_out.columns = ["p", "K", "통행시간", "최대밀도", "Δ통행시간(%)", "Δ최대밀도(%)", "종합평가"]
    delta_out.to_csv(OUT / "delta_table.csv", index=False, encoding="utf-8-sig")
    print(f"  저장: analysis/delta_table.csv")
    print(f"\n[baseline] p=0 K=0: travel={base['travel']:.1f}s, down_peak={base['down_peak']:.2f}")
    print("\n=== Δ 표 (요약) ===")
    print(delta_out.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
