"""
비모수 분석 — throughput vs Z_bmax 의 관계.
모수적 가정 (정규성/선형성/등분산성) 없이 검정.

방법:
1) Spearman ρ + 부트스트랩 95% CI
2) Kendall τ + 부트스트랩 95% CI
3) Permutation test (귀무: 독립)
4) p별 부분상관 (Spearman, 통제변수 p)
5) cfg별 Kruskal-Wallis (cfg 효과 비모수 검정)
6) Mann-Whitney U (이용률 그룹 비교)
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

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

print("="*78)
print("비모수 분석: throughput vs Z_bmax (n=100)")
print("="*78)

x = df.throughput.to_numpy()
y = df.z_bmax.to_numpy()

# 1) Spearman + bootstrap CI
print("\n[1] Spearman ρ + 부트스트랩 95% CI (n_boot=10000)")
sr, sp = stats.spearmanr(x, y)
print(f"  Spearman ρ = {sr:+.4f}, p = {sp:.3e}")
rng = np.random.default_rng(42)
n_boot = 10000
boot_rho = []
n = len(x)
for _ in range(n_boot):
    idx = rng.choice(n, n, replace=True)
    boot_rho.append(stats.spearmanr(x[idx], y[idx])[0])
boot_rho = np.array(boot_rho)
ci_lo, ci_hi = np.percentile(boot_rho, [2.5, 97.5])
print(f"  95% CI: [{ci_lo:+.3f}, {ci_hi:+.3f}]")

# 2) Kendall τ + bootstrap CI
print("\n[2] Kendall τ + 부트스트랩 95% CI")
kr, kp = stats.kendalltau(x, y)
print(f"  Kendall τ = {kr:+.4f}, p = {kp:.3e}")
boot_tau = []
for _ in range(n_boot):
    idx = rng.choice(n, n, replace=True)
    boot_tau.append(stats.kendalltau(x[idx], y[idx])[0])
boot_tau = np.array(boot_tau)
ci_lo_k, ci_hi_k = np.percentile(boot_tau, [2.5, 97.5])
print(f"  95% CI: [{ci_lo_k:+.3f}, {ci_hi_k:+.3f}]")

# 3) Permutation test
print("\n[3] Permutation test (귀무: throughput과 Z_bmax 독립, n_perm=10000)")
n_perm = 10000
observed = stats.spearmanr(x, y)[0]
perm_rho = []
for _ in range(n_perm):
    y_shuffled = rng.permutation(y)
    perm_rho.append(stats.spearmanr(x, y_shuffled)[0])
perm_rho = np.array(perm_rho)
p_perm = (np.abs(perm_rho) >= np.abs(observed)).mean()
print(f"  관측 Spearman ρ = {observed:+.4f}")
print(f"  Permutation p = {p_perm:.4f}")
print(f"  -> {'귀무 기각 (관계 있음)' if p_perm < 0.05 else '기각 못함'}")

# 4) p별 Spearman 부분상관
print("\n[4] p별 부분 Spearman (p 통제 = 같은 p 내에서)")
for p_val in sorted(df.p.unique()):
    sub = df[df.p == p_val]
    rho, pp = stats.spearmanr(sub.throughput, sub.z_bmax)
    print(f"  p={p_val:.1f}: Spearman ρ = {rho:+.4f}  p = {pp:.3e}")

# 5) Kruskal-Wallis: cfg가 Z_bmax에 영향?
print("\n[5] Kruskal-Wallis test (cfg별 Z_bmax 차이)")
groups_cfg = [df[df.config==c].z_bmax.values for c in sorted(df.config.unique())]
kw_stat, kw_p = stats.kruskal(*groups_cfg)
print(f"  H = {kw_stat:.3f}, p = {kw_p:.3e}")
print(f"  -> {'cfg별 Z_bmax 분포 다름' if kw_p<0.05 else '같음'}")
# cfg별 중앙값
print(f"  cfg별 중앙값:")
for c in sorted(df.config.unique()):
    sub = df[df.config==c].z_bmax
    print(f"    cfg{c}: median={sub.median():.3f}, IQR=[{sub.quantile(0.25):.3f}, {sub.quantile(0.75):.3f}]")

# 6) p별 Kruskal-Wallis: 이용률 효과
print("\n[6] Kruskal-Wallis test (p별 Z_bmax 차이)")
groups_p = [df[df.p==p_val].z_bmax.values for p_val in sorted(df.p.unique())]
kw_p_stat, kw_p_p = stats.kruskal(*groups_p)
print(f"  H = {kw_p_stat:.3f}, p = {kw_p_p:.3e}")
print(f"  -> {'p별 Z_bmax 분포 다름' if kw_p_p<0.05 else '같음'}")
for p_val in sorted(df.p.unique()):
    sub = df[df.p==p_val].z_bmax
    print(f"    p={p_val}: median={sub.median():.3f}, IQR=[{sub.quantile(0.25):.3f}, {sub.quantile(0.75):.3f}]")

# 시각화
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

# (a) 부트스트랩 분포
ax = axes[0]
ax.hist(boot_rho, bins=50, alpha=0.7, color="steelblue", edgecolor="white", density=True)
ax.axvline(sr, color="red", linewidth=2, label=f"관측 ρ={sr:.3f}")
ax.axvline(ci_lo, color="orange", linestyle="--", label=f"95% CI [{ci_lo:.3f}, {ci_hi:.3f}]")
ax.axvline(ci_hi, color="orange", linestyle="--")
ax.set_xlabel("Spearman ρ")
ax.set_ylabel("밀도")
ax.set_title(f"(a) 부트스트랩 분포 (n_boot=10000)")
ax.legend()
ax.grid(alpha=0.3)

# (b) Permutation 귀무분포 vs 관측치
ax = axes[1]
ax.hist(perm_rho, bins=50, alpha=0.7, color="gray", edgecolor="white", density=True)
ax.axvline(observed, color="red", linewidth=2, label=f"관측 ρ={observed:+.3f}")
ax.axvline(-observed, color="red", linewidth=2, linestyle="--")
ax.set_xlabel("Spearman ρ (귀무 가정)")
ax.set_ylabel("밀도")
ax.set_title(f"(b) Permutation 귀무분포\np_perm = {p_perm:.4f}")
ax.legend()
ax.grid(alpha=0.3)

# (c) cfg별 Z_bmax 박스플롯
ax = axes[2]
data_to_plot = [df[df.config==c].z_bmax.values for c in sorted(df.config.unique())]
bp = ax.boxplot(data_to_plot, labels=[f"cfg{c}" for c in sorted(df.config.unique())],
                patch_artist=True, showmeans=True)
for patch, color in zip(bp['boxes'], ['#1F77B4','#2CA02C','#FF7F0E','#D62728']):
    patch.set_facecolor(color)
    patch.set_alpha(0.6)
ax.set_ylabel("Z_bmax (ped/m²)")
ax.set_title(f"(c) cfg별 Z_bmax 분포\nKruskal-Wallis p={kw_p:.3e}")
ax.grid(alpha=0.3, axis="y")

plt.tight_layout()
plt.savefig(ROOT/"figures"/"molit"/"nonparametric.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {ROOT/'figures'/'molit'/'nonparametric.png'}")

# 종합
print("\n" + "="*78)
print("비모수 분석 종합")
print("="*78)
print(f"1. throughput - Z_bmax Spearman ρ = {sr:+.3f}, 95%CI [{ci_lo:+.3f}, {ci_hi:+.3f}]")
print(f"2. throughput - Z_bmax Kendall τ = {kr:+.3f}, 95%CI [{ci_lo_k:+.3f}, {ci_hi_k:+.3f}]")
print(f"3. Permutation test: p = {p_perm:.4f} (독립 가설 {'기각' if p_perm<0.05 else '유지'})")
print(f"4. cfg 효과 (Kruskal-Wallis): p = {kw_p:.3e} ({'유의' if kw_p<0.05 else '비유의'})")
print(f"5. p 효과 (Kruskal-Wallis): p = {kw_p_p:.3e} ({'유의' if kw_p_p<0.05 else '비유의'})")
