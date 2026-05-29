"""
슬라이드 9 시각화 2종.
  fig1: 게이트 대기 ↔ W2 peak 산점도 (105 시나리오)
  fig2: 스냅샷 비교 — p=0.1 cfg1 (G 최적) vs p=0.8 cfg5 (G 최적)

DPI 130 (CLAUDE.md 이미지 규칙 준수, 가로 ≤ 1920px).
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
from matplotlib.patches import Rectangle, Circle
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))
from space_layout import SPACE  # noqa

# 한글 폰트
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

DPI = 130  # CLAUDE.md 규칙: 가로 ≤ 1920px

DENS = ROOT / "results" / "molit" / "density_union.csv"
RAW = ROOT / "results_cfsm_latest" / "raw"
OUT_DIR = ROOT / "figures"
OUT_DIR.mkdir(exist_ok=True)

# 색상 팔레트 (사용자 톤)
TAG_COLOR = "#5F5E5A"           # 진한 회색
TAGLESS_COLOR = "#534AB7"       # 보라
GATE_TAG = "#888780"            # 회색 게이트
GATE_TAGLESS = "#7F77DD"        # 보라 게이트
BOTTLENECK = "#D85A30"          # 코랄 (병목 원)
WALL_COLOR = "#888780"          # 외곽


def fig1_scatter():
    """산점도: 게이트 대기 ↔ W2 peak (105 시나리오)."""
    df = pd.read_csv(DENS)
    df = df[df["pass_rate"] >= 0.9]
    df = df[df["config"].isin([1, 2, 3, 4, 5, 6])]
    print(f"[fig1] n = {len(df)}")

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=DPI)

    # 변수 원래대로: x=게이트 대기시간, y=W2 평균밀도
    # 시소 시각화: x축 역순 (대기 ↓ 오른쪽) + y축 우측
    x_all = df["avg_gate_wait"].values
    y_all = df["W2_avg_density"].values

    ax.scatter(x_all, y_all, color="#534AB7", s=20, alpha=0.35,
               edgecolors="none", zorder=3)
    rho, pval = stats.spearmanr(x_all, y_all)

    # x축 역순 (게이트 대기 큰값=왼쪽, 작은값=오른쪽)
    ax.invert_xaxis()
    # y축 라벨/눈금 우측 배치
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()

    ax.set_xlabel("게이트 대기시간 (s) — 짧음 →", fontsize=11)
    ax.set_ylabel("후속시설 보행밀도 평균 (인/m²)", fontsize=11)
    # 범례 제거
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    for s in ["bottom", "right"]:
        ax.spines[s].set_linewidth(0.8)
    ax.grid(False)

    plt.tight_layout()
    out = OUT_DIR / "fig_scatter_gate_density.png"
    plt.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.1,
                transparent=True)
    plt.close()
    print(f"[fig1] 저장: {out}")
    print(f"[fig1] 검증 Spearman ρ = {rho:.4f}")


def _draw_geometry(ax, tagless_idx_set):
    """공간 geometry 그리기."""
    # 외곽
    ob = SPACE["outer_boundary"]
    xs = [p[0] for p in ob] + [ob[0][0]]
    ys = [p[1] for p in ob] + [ob[0][1]]
    ax.plot(xs, ys, color=WALL_COLOR, linewidth=0.8)

    # 비통행 구조물
    for s in SPACE.get("structures", []):
        x0, x1 = s["x_range"]; y0, y1 = s["y_range"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                               facecolor="#EEEEEE", edgecolor=WALL_COLOR,
                               linewidth=0.5, alpha=0.5))

    # 게이트 (직사각형 마커)
    gp = SPACE["gate_params"]
    gw = gp["passage_width"]; gl = gp["length"]
    for i, gy in enumerate(gp["y_positions"]):
        is_tagless = i in tagless_idx_set
        color = GATE_TAGLESS if is_tagless else GATE_TAG
        ax.add_patch(Rectangle((gp["x"], gy - gw/2), gl, gw,
                               facecolor=color, edgecolor="black",
                               linewidth=0.4))

    # 에스컬레이터
    for esc in SPACE["escalators"]:
        cx0, cx1 = esc["corridor"]["x_range"]
        cy0, cy1 = esc["corridor"]["y_range"]
        # corridor (보행자 가리지 않게 약하게)
        ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0,
                               facecolor="#F0F0F0", edgecolor=WALL_COLOR,
                               linewidth=0.5, alpha=0.4, zorder=1))
        # 화살표 (이동 방향: x 양의 방향 → 출구)
        ax.annotate("", xy=(cx1 - 1, (cy0 + cy1) / 2),
                    xytext=(cx0 + 1, (cy0 + cy1) / 2),
                    arrowprops=dict(arrowstyle="->", color="#666",
                                    linewidth=1.2, alpha=0.7))


def _snapshot_frame(sid, t_target):
    """trajectory + agents join → t 시점 frame."""
    traj = pd.read_csv(RAW / f"trajectory_{sid}.csv")
    agents = pd.read_csv(RAW / f"agents_{sid}.csv")
    # 가장 가까운 시간
    times = traj["time"].unique()
    t_close = times[np.argmin(np.abs(times - t_target))]
    frame = traj[traj["time"] == t_close].copy()
    frame = frame.merge(agents[["agent_id", "is_tagless"]],
                         on="agent_id", how="left")
    return frame, t_close


def fig2_snapshot():
    """스냅샷 비교: p=0.1 cfg1 (G 최적) vs p=0.8 cfg5 (G 최적)."""
    # G 최적 cfg = 게이트 대기 최소
    # p=0.1 cfg1, p=0.8 cfg5
    # 두 그림 모두 '에스컬 앞' 영역 비교 (upper 에스컬 = y≈25)
    cases = [
        ("p10_cfg1_s42", 0.1, 1, "p = 0.1 (낮은 이용률, cfg1)",
         "에스컬 앞: 한산 (병목 미발생)",
         frozenset({3}), (30, 25.5, 4.5)),
        ("p80_cfg5_s42", 0.8, 5, "p = 0.8 (높은 이용률, cfg5)",
         "에스컬 앞: 폭증 (병목 전이)",
         frozenset({1, 2, 3, 4, 5}), (30, 25.5, 4.5)),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=DPI)
    t_target = 90.0

    # 공통 좌표 범위
    XLIM = (-2, 42)
    YLIM = (-3, 28)

    for ax, (sid, p, cfg, title, caption, tagless_set, (cx, cy, r)) in zip(axes, cases):
        frame, t_actual = _snapshot_frame(sid, t_target)
        _draw_geometry(ax, tagless_set)

        # 보행자
        # - 게이트 큐 안 (is_tagless 알 수 있음): 태그/태그리스 색 구분
        # - 게이트 통과 후 (재투입으로 ID 변경, is_tagless NaN): 단일 회색
        tag = frame[frame["is_tagless"] == 0]
        tagless = frame[frame["is_tagless"] == 1]
        post_gate = frame[frame["is_tagless"].isna()]
        ax.scatter(post_gate["x"], post_gate["y"], s=40, c="#7A7770",
                   alpha=0.85, edgecolors="white", linewidths=0.3, zorder=7,
                   label=f"게이트 통과 후 ({len(post_gate)})")
        ax.scatter(tag["x"], tag["y"], s=40, c=TAG_COLOR, alpha=0.95,
                   edgecolors="white", linewidths=0.3, zorder=8,
                   label=f"태그 큐 ({len(tag)})")
        ax.scatter(tagless["x"], tagless["y"], s=40, c=TAGLESS_COLOR, alpha=0.95,
                   edgecolors="white", linewidths=0.3, zorder=8,
                   label=f"태그리스 큐 ({len(tagless)})")
        print(f"[fig2] {sid} t={t_actual:.1f}s: "
              f"태그 큐 {len(tag)}, 태그리스 큐 {len(tagless)}, "
              f"게이트 통과 후 {len(post_gate)}")

        # 병목 원
        ax.add_patch(Circle((cx, cy), r, fill=False,
                            edgecolor=BOTTLENECK, linestyle="--",
                            linewidth=2, alpha=0.8, zorder=6))
        ax.text(cx, cy + r + 0.3, "병목", color=BOTTLENECK,
                ha="center", va="bottom", fontsize=12, fontweight="bold", zorder=7)

        ax.set_xlim(XLIM); ax.set_ylim(YLIM)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("x (m)", fontsize=9)
        ax.set_ylabel("y (m)", fontsize=9)
        ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # 하단 캡션
        ax.text(0.5, -0.15, caption,
                transform=ax.transAxes, ha="center", va="top",
                fontsize=14, fontweight="bold", color=BOTTLENECK)

    print(f"[fig2] xlim 동일: {axes[0].get_xlim() == axes[1].get_xlim()}")
    print(f"[fig2] ylim 동일: {axes[0].get_ylim() == axes[1].get_ylim()}")

    plt.tight_layout()
    out = OUT_DIR / "fig_snapshot_p01_vs_p08.png"
    plt.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.1)
    plt.close()
    print(f"[fig2] 저장: {out}")


def font_check():
    """한글 폰트 더미 검증."""
    fig, ax = plt.subplots(figsize=(2, 0.5), dpi=80)
    ax.text(0.5, 0.5, "한글 테스트", ha="center", va="center")
    ax.axis("off")
    test = OUT_DIR / "_font_check.png"
    plt.savefig(test, dpi=80)
    plt.close()
    print(f"[font] OK ({test} 임시 생성)")
    test.unlink(missing_ok=True)


if __name__ == "__main__":
    font_check()
    fig1_scatter()
    fig2_snapshot()
    print("\n완료. 두 PNG:")
    print(f"  {OUT_DIR / 'fig_scatter_gate_density.png'}")
    print(f"  {OUT_DIR / 'fig_snapshot_p01_vs_p08.png'}")
