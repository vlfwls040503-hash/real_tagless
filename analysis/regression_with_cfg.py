"""
회귀 모델에 cfg 추가:
1) Z_bmax ~ throughput + p + C(config)        — cfg 통제
2) Z_bmax ~ throughput + p + C(config) + interaction
3) 다중공선성 (VIF) 체크
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parent.parent
SIM_TIME = 600.0
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
df = df[df.config.isin([1,2,3,4])].copy()
df["throughput"] = df["passed"] / SIM_TIME
df["z_bmax"] = df[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)

print("="*78)
print("[다중공선성 체크 — VIF]")
print("="*78)
X_for_vif = df[["throughput", "p", "config"]].assign(intercept=1)
vifs = pd.DataFrame({
    "변수": ["throughput", "p", "config"],
    "VIF": [variance_inflation_factor(X_for_vif.values, i) for i in range(3)]
})
print(vifs.to_string(index=False))
print("(VIF > 10 = 심각, 5~10 = 주의, <5 = OK)")

print("\n"+"="*78)
print("[모델 1] Z_bmax ~ throughput + C(p)  (이전, baseline)")
print("="*78)
m1 = smf.ols("z_bmax ~ throughput + C(p)", data=df).fit()
print(m1.summary().tables[1])
print(f"R^2 = {m1.rsquared:.4f}, AIC = {m1.aic:.1f}")

print("\n"+"="*78)
print("[모델 2] Z_bmax ~ throughput + C(p) + C(config)  (cfg 추가)")
print("="*78)
m2 = smf.ols("z_bmax ~ throughput + C(p) + C(config)", data=df).fit()
print(m2.summary().tables[1])
print(f"R^2 = {m2.rsquared:.4f}, AIC = {m2.aic:.1f}")

print("\n"+"="*78)
print("[모델 3] Z_bmax ~ throughput + C(p) + C(config) + throughput:p")
print("="*78)
m3 = smf.ols("z_bmax ~ throughput + C(p) + C(config) + throughput:p", data=df).fit()
print(m3.summary().tables[1])
print(f"R^2 = {m3.rsquared:.4f}, AIC = {m3.aic:.1f}")

print("\n"+"="*78)
print("[모델 4] Z_bmax ~ throughput * C(p) * C(config)  (full interaction)")
print("="*78)
m4 = smf.ols("z_bmax ~ throughput + C(p) + C(config) + throughput:C(p) + throughput:C(config) + C(p):C(config)", data=df).fit()
print(f"R^2 = {m4.rsquared:.4f}, AIC = {m4.aic:.1f}")
print(f"파라미터 수: {len(m4.params)}")

print("\n"+"="*78)
print("모델 비교")
print("="*78)
comp = pd.DataFrame([
    {"모델": "M1: throughput + p", "R²": m1.rsquared, "AIC": m1.aic, "파라미터 수": len(m1.params)},
    {"모델": "M2: + C(config)", "R²": m2.rsquared, "AIC": m2.aic, "파라미터 수": len(m2.params)},
    {"모델": "M3: M2 + thr×p", "R²": m3.rsquared, "AIC": m3.aic, "파라미터 수": len(m3.params)},
    {"모델": "M4: 전체 interaction", "R²": m4.rsquared, "AIC": m4.aic, "파라미터 수": len(m4.params)},
])
print(comp.to_string(index=False))

# F-test for cfg effect
from statsmodels.stats.anova import anova_lm
print("\n"+"="*78)
print("[ANOVA: M1 vs M2] (cfg 추가 가치)")
print("="*78)
anova_12 = anova_lm(m1, m2)
print(anova_12)
print("\n[ANOVA: M2 vs M3] (interaction 추가 가치)")
anova_23 = anova_lm(m2, m3)
print(anova_23)
