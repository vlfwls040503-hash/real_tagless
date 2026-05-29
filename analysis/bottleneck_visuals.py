"""
슬라이드 9 시각화 — 옵션 1 (수요-공급) + 옵션 2 (Trade-off 산점도).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
DENS = ROOT / "results" / "molit" / "density_union.csv"
OUT_DIR = ROOT / "figures" / "molit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOS_E = 1.0
COLORS = {0.1:"#1F77B4", 0.3:"#2CA02C", 0.5:"#FF7F0E", 0.7:"#D62728", 0.8:"#9467BD"}

df = pd.read_csv(DENS)
df = df[df["pass_rate"] >= 0.9]
df = df[df["config"].isin([1,2,3,4,5,6])]

agg = df.groupby(["p","config"]).agg(
    gw=("avg_gate_wait","mean"),
    W2pk=("W2_peak_density","mean"),
).reset_index()

# ─── 옵션 1: 수요-공급 곡선 (p별 5 subplot, 한 그림) ───
fig, axes = plt.subplots(1, 5, figsize=(15, 3.5), dpi=100, sharey=False)
p_list = sorted(agg["p"].unique())
for ax, p_val in zip(axes, p_list):
    sub = agg[agg["p"] == p_val].sort_values("config")
    cfg = sub["config"].values
    gw  = sub["gw"].values
    w2  = sub["W2pk"].values

    # 좌축: gate_wait
    color1 = "#1f77b4"
    ax.plot(cfg, gw, "o-", color=color1, linewidth=2, label="게이트 대기(s)", markersize=7)
    ax.set_xlabel("cfg")
    ax.set_ylabel("게이트 대기 (s)", color=color1)
    ax.tick_params(axis="y", labelcolor=color1)
    ax.set_title(f"p = {p_val}")
    ax.grid(alpha=0.3)
    ax.set_xticks(cfg)

    # 우축: W2 peak
    ax2 = ax.twinx()
    color2 = "#d62728"
    ax2.plot(cfg, w2, "s-", color=color2, linewidth=2, label="W2 peak", markersize=7)
    ax2.axhline(LOS_E, color="black", linestyle="--", linewidth=1, alpha=0.7)
    ax2.set_ylabel("W2 peak (인/m²)", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)

    # 임계 cfg (W2pk가 LOS_E 넘는 첫 cfg) 표시
    over = sub[sub["W2pk"] > LOS_E]
    if len(over) > 0:
        c_crit = int(over["config"].min())
        ax2.axvline(c_crit, color="orange", linestyle=":", alpha=0.6)
        ax2.text(c_crit, LOS_E*1.05, f"LOS E\n위반 시작", color="orange",
                 ha="center", fontsize=8)

fig.suptitle("게이트 대기시간 (감소) vs W2 peak (증가) — 임계 cfg 도출",
             fontsize=12, fontweight="bold", y=1.02)
plt.tight_layout()
out1 = OUT_DIR / "slide9_supply_demand.png"
plt.savefig(out1, dpi=100, bbox_inches="tight")
plt.close()
print(f"옵션 1 저장: {out1}")

# ─── 옵션 2: Trade-off 산점도 ───
fig, ax = plt.subplots(figsize=(8, 5), dpi=100)

for p_val in p_list:
    sub = df[df["p"] == p_val]
    ax.scatter(sub["avg_gate_wait"], sub["W2_peak_density"],
               c=COLORS[p_val], s=45, alpha=0.65,
               edgecolors="white", label=f"p = {p_val}")

# 회귀선 (전체)
from scipy import stats as sst
sl, ic, _, _, _ = sst.linregress(df["avg_gate_wait"], df["W2_peak_density"])
xs = np.linspace(df["avg_gate_wait"].min(), df["avg_gate_wait"].max(), 50)
ax.plot(xs, ic + sl * xs, "k--", alpha=0.6, label=f"추세선 (Spearman ρ=-0.93)")

# LOS 임계선
ax.axhline(LOS_E, color="red", linestyle=":", linewidth=2, alpha=0.7,
           label="LOS E 한계 (= 1.0)")
ax.fill_between(xs, LOS_E, ax.get_ylim()[1] if ax.get_ylim()[1] > LOS_E else 2.0,
                alpha=0.08, color="red")

ax.set_xlabel("게이트 대기시간 (s)", fontsize=11)
ax.set_ylabel("W2 peak 보행밀도 (인/m²)", fontsize=11)
ax.set_title("게이트 대기 ↔ W2 peak 시소 관계 (n = 105)",
             fontsize=12, fontweight="bold")
ax.legend(loc="upper right", fontsize=9)
ax.grid(alpha=0.3)
ax.text(35, 1.7, "LOS F 위반 영역", color="red", fontsize=10, alpha=0.7)
ax.text(35, 0.3, "LOS 통과 영역", color="green", fontsize=10, alpha=0.7)

plt.tight_layout()
out2 = OUT_DIR / "slide9_tradeoff_scatter.png"
plt.savefig(out2, dpi=100, bbox_inches="tight")
plt.close()
print(f"옵션 2 저장: {out2}")
