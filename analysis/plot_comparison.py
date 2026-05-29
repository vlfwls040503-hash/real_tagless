"""
2-panel 비교 시각화 — 게이트 vs 시스템 최적화 시나리오.

DPI 200 (CLAUDE.md 규칙: 가로 ≤ 1820 px).
출력: PNG + PDF + 단일 panel PNG 2개.

사용:
    compare_scenarios(
        traj_A_path="results_cfsm_latest/raw/trajectory_p50_cfg3_s42.csv",
        meta_A={"p":0.5, "K":3, "gate_wait":12.2, "peak_density":1.34, "LOS":"F"},
        label_A="게이트 대기시간 최적화 (K=3)",
        traj_B_path="results_cfsm_latest/raw/trajectory_p50_cfg2_s42.csv",
        meta_B={"p":0.5, "K":2, "gate_wait":16.7, "peak_density":0.92, "LOS":"E"},
        label_B="시스템 전체 최적화 (K=2)",
        start_time=120.0, end_time=500.0,
        out_stem="fig11_bottleneck_transfer_2panel",
    )
"""
from __future__ import annotations
from pathlib import Path
import sys
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))
sys.path.insert(0, str(ROOT / "analysis"))
from space_layout import SPACE  # noqa
from grid_density import time_averaged_density

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

DPI = 200
BBOX = (20.0, 35.0, 17.0, 28.0)  # upper 에스컬 앞 zoom
GRID_RES = 0.1
SMOOTH_SIGMA = 0.2
VMIN = 0.0
VMAX = 0.6  # cap 낮춰서 약한 밀도도 진하게

# 투명 → 빨강 colormap (alpha 강화)
from matplotlib.colors import LinearSegmentedColormap
TRANS_RED = LinearSegmentedColormap.from_list(
    "trans_red",
    [(1.0, 1.0, 1.0, 0.0),     # 0:    완전 투명
     (1.0, 0.95, 0.8, 0.35),   # 0.15: 매우 연한 노랑 (alpha 시작)
     (1.0, 0.75, 0.4, 0.65),   # 0.30: 살구
     (1.0, 0.45, 0.2, 0.85),   # 0.45: 주황-빨강
     (0.85, 0.10, 0.05, 1.0),  # 0.60: 진한 빨강
     (0.40, 0.00, 0.00, 1.0)], # max:  매우 진한 빨강
    N=256,
)

OUT_DIR = ROOT / "figures"
OUT_DIR.mkdir(exist_ok=True)

# 시나리오별 태그리스 게이트 (cfg → idx set)
TAGLESS_BY_CFG = {
    1: {3}, 2: {2, 4}, 3: {2, 3, 4}, 4: {1, 2, 4, 5},
    5: {1, 2, 3, 4, 5}, 6: {0, 1, 2, 3, 4, 5},
}


def _draw_geometry(ax, K: int):
    """공간 geometry: 벽 / 게이트 / 에스컬 — 라벨 X, 외곽선만."""
    # 외곽 벽
    ob = SPACE["outer_boundary"]
    xs = [p[0] for p in ob] + [ob[0][0]]
    ys = [p[1] for p in ob] + [ob[0][1]]
    ax.plot(xs, ys, color="black", linewidth=2.2, zorder=10)

    # 비통행 구조물 (벽 영역)
    for s in SPACE.get("structures", []):
        x0, x1 = s["x_range"]; y0, y1 = s["y_range"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                               facecolor="#BBBBBB", edgecolor="black",
                               linewidth=1.2, hatch="//", alpha=0.9, zorder=9))

    # 게이트 (태그리스/태그 색 구분, 라벨 X)
    gp = SPACE["gate_params"]
    gw = gp["passage_width"]; gl = gp["length"]
    tagless_set = TAGLESS_BY_CFG.get(K, set())
    for i, gy in enumerate(gp["y_positions"]):
        if i in tagless_set:
            color = "#534AB7"   # 태그리스: 보라
        else:
            color = "#5F5E5A"   # 태그: 진회색
        ax.add_patch(Rectangle((gp["x"], gy - gw/2), gl, gw,
                               facecolor=color, edgecolor="black",
                               linewidth=1.0, zorder=11))

    # 에스컬레이터 corridor (명확한 외곽 + 패턴)
    for esc in SPACE["escalators"]:
        cx0, cx1 = esc["corridor"]["x_range"]
        cy0, cy1 = esc["corridor"]["y_range"]
        ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0,
                               facecolor="#E8DDF5", edgecolor="black",
                               linewidth=1.5, hatch="\\\\\\", alpha=0.85, zorder=9))
        # 진행 방향 화살표 (글자 없이)
        mid_y = (cy0 + cy1) / 2
        ax.annotate("", xy=(cx1 - 1.0, mid_y),
                    xytext=(cx0 + 1.0, mid_y),
                    arrowprops=dict(arrowstyle="-|>", color="black",
                                    linewidth=2.0, alpha=0.9,
                                    mutation_scale=18), zorder=12)


def _add_metrics_box(ax, meta: dict):
    """우상단 정량 지표 박스."""
    txt = (f"Gate wait: {meta['gate_wait']:.1f} s\n"
           f"Peak density: {meta['peak_density']:.2f} ped/m²\n"
           f"LOS: {meta['LOS']}")
    ax.text(0.98, 0.98, txt, transform=ax.transAxes,
            ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="white", edgecolor="lightgray", alpha=0.95),
            zorder=20)


def _add_bottleneck_arrow(ax, panel_type: str):
    """병목 위치 어노테이션 (확대 영역에 맞춰)."""
    if panel_type == "gate_optimal":
        ax.annotate("병목 (LOS F)",
                    xy=(30, 25), xytext=(22, 19),
                    fontsize=10, ha="center", color="#FFFFFF",
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#FFFFFF",
                                    linewidth=2), zorder=20)
    else:
        ax.annotate("병목 해소 (LOS E)",
                    xy=(30, 25), xytext=(22, 19),
                    fontsize=10, ha="center", color="#FFFFFF",
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#FFFFFF",
                                    linewidth=2), zorder=20)


def compare_scenarios(traj_A_path: str, meta_A: dict, label_A: str,
                       traj_B_path: str, meta_B: dict, label_B: str,
                       start_time: float, end_time: float,
                       out_stem: str = "fig11_bottleneck_transfer_2panel"):
    """2-panel 비교 시각화 + 단일 panel 출력."""
    print(f"[load] A: {traj_A_path}")
    print(f"[load] B: {traj_B_path}")
    df_A = pd.read_csv(traj_A_path)
    df_B = pd.read_csv(traj_B_path)

    print(f"[density] A 시간평균 ({start_time}~{end_time}s)...")
    dens_A, xs, ys = time_averaged_density(
        df_A, BBOX, start_time, end_time,
        grid_res=GRID_RES, smooth_sigma_m=SMOOTH_SIGMA)
    print(f"[density] B 시간평균...")
    dens_B, _, _ = time_averaged_density(
        df_B, BBOX, start_time, end_time,
        grid_res=GRID_RES, smooth_sigma_m=SMOOTH_SIGMA)

    # 보행자 위치 누적 (overlay 용)
    pos_A = df_A[(df_A.time >= start_time) & (df_A.time <= end_time)][["x", "y"]]
    pos_B = df_B[(df_B.time >= start_time) & (df_B.time <= end_time)][["x", "y"]]

    print(f"[range] dens_A: min={dens_A.min():.2f}, max={dens_A.max():.2f}")
    print(f"[range] dens_B: min={dens_B.min():.2f}, max={dens_B.max():.2f}")

    # ── 2-panel ──
    fig = plt.figure(figsize=(9.0, 5.0625), dpi=DPI)
    gs = fig.add_gridspec(1, 2, wspace=0.10)
    axes = [fig.add_subplot(gs[0, i]) for i in range(2)]

    extent = [xs[0], xs[-1], ys[0], ys[-1]]
    for ax, dens, pos, meta in [
        (axes[0], dens_A, pos_A, meta_A),
        (axes[1], dens_B, pos_B, meta_B),
    ]:
        ax.scatter(pos["x"], pos["y"], s=1.5, c="#600000",
                   alpha=0.05, zorder=3, edgecolors="none")
        ax.imshow(dens, extent=extent, origin="lower",
                  cmap=TRANS_RED, vmin=VMIN, vmax=VMAX, aspect="equal",
                  interpolation="bilinear", zorder=4)
        _draw_geometry(ax, meta["K"])
        ax.set_xlim(BBOX[0], BBOX[1])
        ax.set_ylim(BBOX[2], BBOX[3])
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)

    out_png = OUT_DIR / f"{out_stem}.png"
    out_pdf = OUT_DIR / f"{out_stem}.pdf"
    plt.savefig(out_png, dpi=DPI, bbox_inches="tight", pad_inches=0.05)
    plt.savefig(out_pdf, bbox_inches="tight", pad_inches=0.05)
    plt.close()
    print(f"[save] {out_png}")
    print(f"[save] {out_pdf}")

    # ── 단일 panel 2개 ──
    for dens, pos, meta, suffix in [
        (dens_A, pos_A, meta_A, "panel_A_gate_optimal"),
        (dens_B, pos_B, meta_B, "panel_B_system_optimal"),
    ]:
        fig1 = plt.figure(figsize=(5.5, 4.5), dpi=DPI)
        ax1 = fig1.add_subplot(111)
        ax1.scatter(pos["x"], pos["y"], s=1.5, c="#600000",
                    alpha=0.05, zorder=3, edgecolors="none")
        ax1.imshow(dens, extent=extent, origin="lower",
                   cmap=TRANS_RED, vmin=VMIN, vmax=VMAX, aspect="equal",
                   interpolation="bilinear", zorder=4)
        _draw_geometry(ax1, meta["K"])
        ax1.set_xlim(BBOX[0], BBOX[1])
        ax1.set_ylim(BBOX[2], BBOX[3])
        ax1.set_xticks([]); ax1.set_yticks([])
        for s in ax1.spines.values():
            s.set_visible(False)
        out_single = OUT_DIR / f"fig11_{suffix}.png"
        plt.savefig(out_single, dpi=DPI, bbox_inches="tight", pad_inches=0.05)
        plt.close()
        print(f"[save] {out_single}")


if __name__ == "__main__":
    # 기본 시나리오: p=0.5 (cfg3 vs cfg2)
    compare_scenarios(
        traj_A_path=str(ROOT / "results_cfsm_latest/raw/trajectory_p50_cfg3_s42.csv"),
        meta_A={"p": 0.5, "K": 3, "gate_wait": 12.2, "peak_density": 1.34, "LOS": "F"},
        label_A="게이트 대기시간 최적화 (K=3)",
        traj_B_path=str(ROOT / "results_cfsm_latest/raw/trajectory_p50_cfg2_s42.csv"),
        meta_B={"p": 0.5, "K": 2, "gate_wait": 16.7, "peak_density": 0.92, "LOS": "E"},
        label_B="시스템 전체 최적화 (K=2)",
        start_time=200.0, end_time=280.0,  # 두 번째 열차 직후 첨두
    )
