"""
GAM 모델 가정 검정 — LinearGAM (Gaussian)
- 잔차 정규성, 등분산성, 독립성
- (선형성은 자동 곡선이라 검정 불필요)
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from pygam import LinearGAM, s

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SIM_TIME = 600.0
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
df = df[df.config.isin([1,2,3,4])].copy()
df["throughput"] = df["passed"] / SIM_TIME
df["z_bmax"] = df[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)

X = df[["throughput","p"]].to_numpy()
y = df["z_bmax"].to_numpy()
gam = LinearGAM(s(0, n_splines=10) + s(1, n_splines=5)).fit(X, y)

fitted = gam.predict(X)
resid = y - fitted

print("="*78)
print("GAM 가정 검정")
print("="*78)
print(f"Pseudo R² = {gam.statistics_['pseudo_r2']['explained_deviance']:.4f}")
print(f"Effective DoF = {gam.statistics_['edof']:.2f}")
print(f"GCV = {gam.statistics_['GCV']:.4f}")

print("\n[1] 잔차 정규성")
sw_stat, sw_p = stats.shapiro(resid)
print(f"  Shapiro-Wilk: W={sw_stat:.4f}, p={sw_p:.4f}")
print(f"  -> {'PASS' if sw_p>0.05 else 'FAIL'}")

print("\n[2] 잔차 평균 (~0 이어야 함)")
print(f"  잔차 평균: {resid.mean():.4f}")
print(f"  잔차 std: {resid.std():.4f}")

print("\n[3] 등분산성 (Breusch-Pagan 유사 — 잔차² vs fitted)")
# 표준 회귀로 잔차^2 ~ fitted 회귀해서 유의성 확인
import statsmodels.api as sm
bp_x = sm.add_constant(fitted)
bp_model = sm.OLS(resid**2, bp_x).fit()
print(f"  잔차² ~ fitted 회귀 p값: {bp_model.f_pvalue:.4f}")
print(f"  -> {'PASS (등분산)' if bp_model.f_pvalue>0.05 else 'FAIL (이분산)'}")

print("\n[4] 독립성 (Durbin-Watson)")
from statsmodels.stats.stattools import durbin_watson
dw = durbin_watson(resid)
print(f"  DW = {dw:.3f}")
print(f"  -> {'PASS' if 1.5<dw<2.5 else '주의'}")

# 시각화
fig, axes = plt.subplots(1, 4, figsize=(18, 4))

# Residuals vs Fitted
ax = axes[0]
ax.scatter(fitted, resid, alpha=0.6, s=25)
ax.axhline(0, color="red", linestyle="--")
from statsmodels.nonparametric.smoothers_lowess import lowess
sm_line = lowess(resid, fitted, frac=0.5)
ax.plot(sm_line[:,0], sm_line[:,1], "g-", linewidth=2)
ax.set_xlabel("적합값"); ax.set_ylabel("잔차")
ax.set_title("(a) 잔차 vs 적합값\n(랜덤 분포 = OK)")
ax.grid(alpha=0.3)

# Q-Q plot
ax = axes[1]
stats.probplot(resid, dist="norm", plot=ax)
ax.set_title(f"(b) Q-Q plot\nShapiro p={sw_p:.4f}")
ax.grid(alpha=0.3)

# Histogram
ax = axes[2]
ax.hist(resid, bins=20, density=True, alpha=0.7, color="steelblue", edgecolor="white")
xx = np.linspace(resid.min(), resid.max(), 100)
ax.plot(xx, stats.norm.pdf(xx, resid.mean(), resid.std()), "r-", linewidth=2)
ax.set_xlabel("잔차"); ax.set_ylabel("밀도")
ax.set_title("(c) 잔차 히스토그램")
ax.grid(alpha=0.3)

# Scale-Location
ax = axes[3]
std_resid = resid / resid.std()
ax.scatter(fitted, np.sqrt(np.abs(std_resid)), alpha=0.6, s=25)
sm_line2 = lowess(np.sqrt(np.abs(std_resid)), fitted, frac=0.5)
ax.plot(sm_line2[:,0], sm_line2[:,1], "g-", linewidth=2)
ax.set_xlabel("적합값"); ax.set_ylabel("√|표준화 잔차|")
ax.set_title(f"(d) Scale-Location\nBP p={bp_model.f_pvalue:.4f}")
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(ROOT/"figures"/"molit"/"gam_diagnostics.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {ROOT/'figures'/'molit'/'gam_diagnostics.png'}")

# 종합
print("\n"+"="*78)
print("GAM 종합 판정 (선형성은 자동 처리되므로 제외)")
print("="*78)
print(f"  잔차 정규성: {'PASS' if sw_p>0.05 else 'FAIL'} (p={sw_p:.4f})")
print(f"  등분산성:   {'PASS' if bp_model.f_pvalue>0.05 else 'FAIL'} (p={bp_model.f_pvalue:.4f})")
print(f"  독립성:     {'PASS' if 1.5<dw<2.5 else '주의'} (DW={dw:.3f})")
