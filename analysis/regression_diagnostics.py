"""
M3 회귀모델 가정 검정 (LINE):
1) Linearity (선형성)
2) Independence (독립성)
3) Normality (잔차 정규성)
4) Equal variance / Homoscedasticity (등분산성)
+ 다중공선성 (VIF), 영향점 (Cook's D)
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
from statsmodels.stats.diagnostic import het_breuschpagan, het_white, linear_rainbow
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy import stats

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SIM_TIME = 600.0
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
df = df[df.config.isin([1,2,3,4])].copy()
df["throughput"] = df["passed"] / SIM_TIME
df["z_bmax"] = df[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)

# M3 fit
m3 = smf.ols("z_bmax ~ throughput + C(p) + C(config) + throughput:p", data=df).fit()
resid = m3.resid
fitted = m3.fittedvalues

print("="*78)
print("M3 회귀모델 가정 검정")
print("="*78)
print(f"R² = {m3.rsquared:.4f}, n = {m3.nobs:.0f}, df_resid = {m3.df_resid:.0f}")

# 1. Linearity — Rainbow test
print("\n[1] LINEARITY (선형성)")
try:
    rb_stat, rb_p = linear_rainbow(m3)
    print(f"  Rainbow test: F={rb_stat:.3f}, p={rb_p:.4f}")
    print(f"  -> {'통과 (선형)' if rb_p>0.05 else '위반 (비선형 가능)'}")
except Exception as e:
    print(f"  실행 실패: {e}")

# 2. Independence — Durbin-Watson
print("\n[2] INDEPENDENCE (독립성)")
dw = durbin_watson(resid)
print(f"  Durbin-Watson: {dw:.3f} (이상 2 부근 = 독립)")
dw_judge = "통과" if 1.5 < dw < 2.5 else "주의"
print(f"  -> {dw_judge}")

# 3. Normality — Shapiro-Wilk + Jarque-Bera
print("\n[3] NORMALITY (정규성)")
sw_stat, sw_p = stats.shapiro(resid)
print(f"  Shapiro-Wilk: W={sw_stat:.4f}, p={sw_p:.4f}")
print(f"  -> {'통과 (정규)' if sw_p>0.05 else '위반 (비정규)'}")
jb_stat, jb_p, skew, kurt = jarque_bera(resid)
print(f"  Jarque-Bera: JB={jb_stat:.3f}, p={jb_p:.4f}")
print(f"  잔차 왜도(skew)={skew:.3f}, 첨도(kurt)={kurt:.3f}")
print(f"  -> {'통과' if jb_p>0.05 else '위반'}")

# 4. Homoscedasticity — Breusch-Pagan + White
print("\n[4] HOMOSCEDASTICITY (등분산성)")
bp_stat, bp_p, _, _ = het_breuschpagan(resid, m3.model.exog)
print(f"  Breusch-Pagan: LM={bp_stat:.3f}, p={bp_p:.4f}")
print(f"  -> {'통과 (등분산)' if bp_p>0.05 else '위반 (이분산)'}")

# 5. VIF
print("\n[5] MULTICOLLINEARITY (VIF)")
X = m3.model.exog
for i, name in enumerate(m3.model.exog_names):
    if name == "Intercept": continue
    vif = variance_inflation_factor(X, i)
    flag = "OK" if vif < 5 else ("주의" if vif < 10 else "심각")
    print(f"  {name}: VIF={vif:.2f} ({flag})")

# 6. Influence — Cook's D
print("\n[6] INFLUENTIAL POINTS (Cook's D)")
infl = m3.get_influence()
cook_d = infl.cooks_distance[0]
threshold = 4 / m3.nobs
n_influential = (cook_d > threshold).sum()
print(f"  임계값 4/n = {threshold:.4f}")
print(f"  영향점 수: {n_influential} / {int(m3.nobs)}")
print(f"  최대 Cook's D: {cook_d.max():.4f}")

# 시각화
fig, axes = plt.subplots(2, 3, figsize=(15, 9))

# (a) Residuals vs Fitted (선형성, 등분산성)
ax = axes[0, 0]
ax.scatter(fitted, resid, alpha=0.6, s=25)
ax.axhline(0, color="red", linestyle="--")
# LOWESS 추세선
from statsmodels.nonparametric.smoothers_lowess import lowess
sm_line = lowess(resid, fitted, frac=0.5)
ax.plot(sm_line[:,0], sm_line[:,1], "g-", linewidth=2, label="LOWESS")
ax.set_xlabel("적합값 (fitted)"); ax.set_ylabel("잔차 (residual)")
ax.set_title("(a) 잔차 vs 적합값\n선형성 + 등분산성 확인")
ax.legend(); ax.grid(alpha=0.3)

# (b) Q-Q plot (정규성)
ax = axes[0, 1]
stats.probplot(resid, dist="norm", plot=ax)
ax.set_title(f"(b) Q-Q plot\nShapiro p={sw_p:.4f}")
ax.grid(alpha=0.3)

# (c) 잔차 히스토그램 (정규성)
ax = axes[0, 2]
ax.hist(resid, bins=20, density=True, alpha=0.7, color="steelblue", edgecolor="white")
xx = np.linspace(resid.min(), resid.max(), 100)
ax.plot(xx, stats.norm.pdf(xx, resid.mean(), resid.std()), "r-", linewidth=2, label="정규분포")
ax.set_xlabel("잔차"); ax.set_ylabel("밀도")
ax.set_title(f"(c) 잔차 히스토그램\nskew={skew:.2f}, kurt={kurt:.2f}")
ax.legend(); ax.grid(alpha=0.3)

# (d) Scale-Location (등분산성)
ax = axes[1, 0]
std_resid = resid / resid.std()
ax.scatter(fitted, np.sqrt(np.abs(std_resid)), alpha=0.6, s=25)
sm_line2 = lowess(np.sqrt(np.abs(std_resid)), fitted, frac=0.5)
ax.plot(sm_line2[:,0], sm_line2[:,1], "g-", linewidth=2)
ax.set_xlabel("적합값"); ax.set_ylabel("√|표준화 잔차|")
ax.set_title(f"(d) Scale-Location\nBreusch-Pagan p={bp_p:.4f}")
ax.grid(alpha=0.3)

# (e) Cook's D
ax = axes[1, 1]
ax.stem(range(len(cook_d)), cook_d, basefmt=" ")
ax.axhline(threshold, color="red", linestyle="--", label=f"임계값 4/n={threshold:.3f}")
ax.set_xlabel("관측치 index"); ax.set_ylabel("Cook's D")
ax.set_title(f"(e) 영향점 (Cook's D)\n초과 {n_influential}건")
ax.legend(); ax.grid(alpha=0.3)

# (f) Durbin-Watson (잔차 시계열)
ax = axes[1, 2]
ax.plot(range(len(resid)), resid, "o-", alpha=0.5, markersize=4)
ax.axhline(0, color="red", linestyle="--")
ax.set_xlabel("관측치 순서"); ax.set_ylabel("잔차")
ax.set_title(f"(f) 잔차 순서별\nDurbin-Watson={dw:.3f}")
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(ROOT/"figures"/"molit"/"regression_diagnostics.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {ROOT/'figures'/'molit'/'regression_diagnostics.png'}")

# 종합 판정
print("\n"+"="*78)
print("종합 판정")
print("="*78)
checks = [
    ("선형성", rb_p > 0.05, f"Rainbow p={rb_p:.4f}"),
    ("독립성", 1.5 < dw < 2.5, f"DW={dw:.3f}"),
    ("정규성 (SW)", sw_p > 0.05, f"Shapiro p={sw_p:.4f}"),
    ("정규성 (JB)", jb_p > 0.05, f"JB p={jb_p:.4f}"),
    ("등분산성", bp_p > 0.05, f"BP p={bp_p:.4f}"),
]
for name, ok, info in checks:
    print(f"  {name:>12}: {'PASS' if ok else 'FAIL'}  ({info})")
