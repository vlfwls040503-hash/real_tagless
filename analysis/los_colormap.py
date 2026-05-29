"""
국토부 LOS 등급 기반 커스텀 colormap.

표 2.3 보행로 LOS 임계 (인/m²):
  A ≤ 0.3   연한 청록
  B ≤ 0.4   청록
  C ≤ 0.7   황록
  D ≤ 1.0   노랑
  E ≤ 2.0   주황 → 빨강
  F > 2.0   진한 빨강
"""
from __future__ import annotations
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import matplotlib as mpl

LOS_BOUNDARIES = [0.0, 0.3, 0.4, 0.7, 1.0, 2.0, 6.0]
LOS_LABELS = ["A", "B", "C", "D", "E", "F"]
LOS_COLORS = [
    "#9FE5D8",  # A — 연한 청록
    "#5FB8A5",  # B — 청록
    "#A8C95F",  # C — 황록
    "#F5D04E",  # D — 노랑
    "#EE7B30",  # E — 주황
    "#B71C1C",  # F — 진한 빨강
]


def make_los_cmap_norm(vmax: float = 6.0):
    """LOS 기반 BoundaryNorm + ListedColormap.

    Returns: (cmap, norm, boundaries, labels)
    """
    boundaries = LOS_BOUNDARIES.copy()
    boundaries[-1] = max(vmax, boundaries[-1])
    cmap = mpl.colors.ListedColormap(LOS_COLORS)
    norm = BoundaryNorm(boundaries, cmap.N)
    return cmap, norm, boundaries, LOS_LABELS


def add_los_colorbar(fig, mappable, ax_or_cax, label="보행밀도 (인/m²)"):
    """LOS 등급 라벨 + 임계선 표시된 colorbar.

    ax_or_cax: ax (axes) 또는 cax (colorbar axes)
    """
    cbar = fig.colorbar(mappable, cax=ax_or_cax, label=label,
                        orientation="vertical", extend="max")
    # 등급 경계선 위치에 눈금
    boundaries = LOS_BOUNDARIES
    cbar.set_ticks(boundaries[:-1] + [boundaries[-1]])
    cbar.set_ticklabels([f"{b}" for b in boundaries[:-1]] + [f"{boundaries[-1]:.0f}"])
    # 등급 라벨 추가 (각 등급 중간 위치)
    for i, lbl in enumerate(LOS_LABELS):
        y = (boundaries[i] + boundaries[i+1]) / 2
        cbar.ax.text(1.5, y, lbl, transform=cbar.ax.get_yaxis_transform(),
                     ha="left", va="center", fontsize=9, fontweight="bold")
    return cbar
