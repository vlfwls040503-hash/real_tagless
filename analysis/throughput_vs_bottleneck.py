"""
게이트 처리율 vs 에스컬 앞 병목 상관분석.

게이트 처리율 정의:
- gate_tp = passed / SIM_TIME (ped/s) — 시스템 관점 실효 처리율
- per_gate_tp = gate_tp / N_gates_effective — 게이트당 처리율

병목 지표:
- Z_bmax = max(Z3B, Z4B) 평균 밀도 (ped/m^2)
- Z4B (주 병목, upper)

가설:
- H1: 게이트 처리율 ↑ -> Zone B 밀도 ↑ (병목 전이 양의 상관)
"""
from __future__ import annotations
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

SIM_TIME = 600.0

df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
df = df[df["config"].isin([1,2,3,4])].copy()  # 신뢰 데이터
df["gate_tp"] = df["passed"] / SIM_TIME          # 시스템 실효 처리율 (ped/s)
df["z_bmax"] = df[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)
df["z4b"] = df["zone4b_avg_density"]

print("=" * 70)
print("게이트 처리율 (= passed/SIM_TIME) vs 병목 밀도")
print("=" * 70)
print(f"표본 n = {len(df)}")
print(f"gate_tp 범위: {df.gate_tp.min():.2f} ~ {df.gate_tp.max():.2f} ped/s")
print(f"Z_bmax 범위: {df.z_bmax.min():.2f} ~ {df.z_bmax.max():.2f} ped/m^2")

# 전체 상관
for ylabel, ycol in [("Z3B","zone3b_avg_density"), ("Z4B","zone4b_avg_density"), ("Z_bmax","z_bmax")]:
    x = df.gate_tp.to_numpy()
    y = df[ycol].to_numpy()
    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    kr, kp = stats.kendalltau(x, y)
    print(f"\n[gate_tp vs {ylabel}]")
    print(f"  Pearson  r={pr:+.4f}  p={pp:.3g}")
    print(f"  Spearman r={sr:+.4f}  p={sp:.3g}")
    print(f"  Kendall  t={kr:+.4f}  p={kp:.3g}")

# p별 부분상관
print("\n" + "="*70)
print("p 통제 시 부분 상관 (각 p 내, n=20)")
print("="*70)
for p_val in sorted(df.p.unique()):
    sub = df[df.p == p_val]
    x = sub.gate_tp.to_numpy()
    y = sub.z_bmax.to_numpy()
    pr, pp = stats.pearsonr(x, y)
    print(f"p={p_val:.1f}: Pearson r={pr:+.3f}  p={pp:.3g}  "
          f"(gate_tp {sub.gate_tp.mean():.2f}ped/s, Z_bmax {sub.z_bmax.mean():.2f})")

# 배합 평균 기준
agg = df.groupby(["p","config"]).agg(
    gate_tp=("gate_tp","mean"),
    z_bmax=("z_bmax","mean"),
).reset_index()
print("\n배합 평균 (n=20):")
pr, pp = stats.pearsonr(agg.gate_tp, agg.z_bmax)
print(f"  gate_tp vs Z_bmax: Pearson r={pr:+.3f}  p={pp:.3g}")

# 시각화
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
colors = {0.1:"#1F77B4", 0.3:"#2CA02C", 0.5:"#FF7F0E", 0.7:"#D62728", 0.8:"#9467BD"}

ax = axes[0]
for p_val in sorted(df.p.unique()):
    sub = df[df.p == p_val]
    ax.scatter(sub.gate_tp, sub.z_bmax, c=colors[p_val], s=35, alpha=0.7,
               edgecolors="white", label=f"p={p_val}")
slope, intercept, r_v, p_v, _ = stats.linregress(df.gate_tp, df.z_bmax)
xs = np.linspace(df.gate_tp.min(), df.gate_tp.max(), 100)
ax.plot(xs, intercept + slope*xs, "k--", alpha=0.7,
        label=f"r={r_v:+.3f}, p={p_v:.2g}")
ax.axhline(2.0, color="red", linestyle=":", alpha=0.5, label="LOS F 경계")
ax.axhline(1.0, color="orange", linestyle=":", alpha=0.5, label="LOS D/E")
ax.set_xlabel("게이트 처리율 (ped/s)")
ax.set_ylabel("Z_bmax (ped/m²)")
ax.set_title("(a) 게이트 처리율 vs 에스컬 앞 병목 (n=100)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

ax = axes[1]
for p_val in sorted(agg.p.unique()):
    sub = agg[agg.p == p_val]
    ax.scatter(sub.gate_tp, sub.z_bmax, c=colors[p_val], s=100,
               label=f"p={p_val}", edgecolors="black")
    for _, r in sub.iterrows():
        ax.annotate(f"cfg{int(r.config)}", (r.gate_tp, r.z_bmax),
                    fontsize=7, ha="left", va="bottom")
ax.set_xlabel("게이트 처리율 (ped/s)")
ax.set_ylabel("Z_bmax (ped/m²)")
ax.set_title("(b) 배합 평균 (n=20)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(FIG / "throughput_vs_bottleneck.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'throughput_vs_bottleneck.png'}")
