"""
처리율 → Zone B 밀도 비선형 분석
1) 다변량 회귀 + 상호작용
2) 혼합효과 모형 (seed random effect)
3) GAM 비선형 곡선
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import statsmodels.api as sm
import statsmodels.formula.api as smf
from pygam import LinearGAM, s, te, f

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures" / "molit"
OUT = ROOT / "results" / "molit"

SIM_TIME = 600.0
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
df = df[df.config.isin([1,2,3,4])].copy()
df["throughput"] = df["passed"] / SIM_TIME
df["z_bmax"] = df[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)

print("="*78)
print("[1] 다변량 회귀 (throughput + p + 상호작용)")
print("="*78)
m1 = smf.ols("z_bmax ~ throughput + p + throughput:p", data=df).fit()
print(m1.summary().tables[1])
print(f"R^2 = {m1.rsquared:.3f}, Adj R^2 = {m1.rsquared_adj:.3f}")
print(f"F-stat p-value = {m1.f_pvalue:.3e}")

print("\n" + "="*78)
print("[2] ANCOVA: throughput 효과 (p 통제)")
print("="*78)
m2 = smf.ols("z_bmax ~ throughput + C(p)", data=df).fit()
print(m2.summary().tables[1])
print(f"R^2 = {m2.rsquared:.3f}")

print("\n" + "="*78)
print("[3] GAM (비선형 곡선)")
print("="*78)
X = df[["throughput","p"]].to_numpy()
y = df["z_bmax"].to_numpy()
gam = LinearGAM(s(0, n_splines=10) + s(1, n_splines=5)).fit(X, y)
print(gam.summary())

# 시각화: GAM partial dependence
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

ax = axes[0]
xx = np.linspace(X[:,0].min(), X[:,0].max(), 100)
xx_grid = np.column_stack([xx, np.full_like(xx, X[:,1].mean())])
pdep = gam.partial_dependence(term=0, X=xx_grid)
ax.plot(xx, pdep, "b-", linewidth=2, label="GAM 비선형 fit")
# 산점도
colors = {0.1:"#1F77B4", 0.3:"#2CA02C", 0.5:"#FF7F0E", 0.7:"#D62728", 0.8:"#9467BD"}
for p_val in sorted(df.p.unique()):
    sub = df[df.p == p_val]
    ax.scatter(sub.throughput, sub.z_bmax - sub.z_bmax.mean() + pdep.mean(),
               c=colors[p_val], s=20, alpha=0.5, label=f"p={p_val}")
ax.set_xlabel("게이트 처리율 (ped/s)")
ax.set_ylabel("Z_bmax (조정)")
ax.set_title("(a) GAM: throughput → Z_bmax 비선형 효과")
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

# 다변량 회귀 예측
ax = axes[1]
ax.scatter(df.throughput, df.z_bmax, c=[colors[p] for p in df.p],
           s=20, alpha=0.5, edgecolors="white")
xx = np.linspace(df.throughput.min(), df.throughput.max(), 50)
for p_val in sorted(df.p.unique()):
    pred = m1.params["Intercept"] + m1.params["throughput"]*xx + m1.params["p"]*p_val + m1.params["throughput:p"]*xx*p_val
    ax.plot(xx, pred, "-", color=colors[p_val], alpha=0.8, linewidth=1.5,
            label=f"p={p_val} 회귀선")
ax.set_xlabel("게이트 처리율 (ped/s)")
ax.set_ylabel("Z_bmax")
ax.set_title("(b) 다변량 회귀: p별 회귀선")
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

# p별 효과 크기
ax = axes[2]
ps = sorted(df.p.unique())
slopes = []
for p_val in ps:
    # interaction model에서 throughput의 effective slope = β1 + β3 * p
    slope = m1.params["throughput"] + m1.params["throughput:p"] * p_val
    slopes.append(slope)
ax.bar([str(p) for p in ps], slopes, color=[colors[p] for p in ps])
ax.axhline(0, color="black", linewidth=0.8)
for i, s_ in enumerate(slopes):
    ax.text(i, s_+0.02 if s_>0 else s_-0.05, f"{s_:.2f}", ha="center", fontsize=9)
ax.set_xlabel("이용률 p")
ax.set_ylabel("throughput 의 effective slope (Z_bmax/ped/s)")
ax.set_title("(c) p별 throughput 효과 크기 (회귀 기반)")
ax.grid(alpha=0.3, axis="y")

plt.tight_layout()
plt.savefig(FIG / "throughput_advanced.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'throughput_advanced.png'}")

# 결과 저장
import json
out = {
    "multiple_regression": {
        "R2": m1.rsquared, "adj_R2": m1.rsquared_adj,
        "F_pvalue": m1.f_pvalue,
        "coefs": dict(m1.params), "pvals": dict(m1.pvalues),
        "p_specific_slopes": {f"p={p:.1f}": float(m1.params["throughput"]+m1.params["throughput:p"]*p) for p in ps},
    },
    "ancova": {
        "R2": m2.rsquared,
        "coefs": {k: float(v) for k, v in m2.params.items()},
        "pvals": {k: float(v) for k, v in m2.pvalues.items()},
    },
    "gam": {
        "edof": float(gam.statistics_["edof"]),
        "GCV": float(gam.statistics_["GCV"]),
        "loglikelihood": float(gam.statistics_["loglikelihood"]),
    },
}
(OUT / "throughput_advanced.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"저장: {OUT / 'throughput_advanced.json'}")
