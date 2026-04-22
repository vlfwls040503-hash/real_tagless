"""
병목 전이 상관분석:
H0 — 게이트 대기시간과 후속 시설(에스컬 앞 Zone B) 보행밀도는 독립이다.
H1 — 게이트 대기시간이 짧을수록 (= 개찰구 처리율 ↑) → Zone B 보행밀도 ↑ (병목 전이)

지표 (국토부 기준에 맞춘 보행밀도):
 X: avg_gate_wait (s)                — 게이트 병목 강도
 Y: zone4b 평균밀도 (ped/m²)         — upper 에스컬 앞 보행공간 밀도 (MOLIT 표 2.3)
 Y': zone3b 평균밀도                 — lower 에스컬 앞
 Y_sys: max(z3b, z4b) per scenario   — 시스템 관점 최대

통계 검정: Pearson / Spearman / Kendall (n=100)
"""
from __future__ import annotations
import json
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
sys.path.insert(0, str(ROOT))
from analysis.molit_los import WALKWAY_LOS, los_threshold

OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 데이터 로드
# =============================================================================
df = pd.read_csv(OUT / "molit_los_100scenarios.csv")

# 지표 정의
df["z_bmax"] = df[["zone3b_density_avg", "zone4b_density_avg"]].max(axis=1)  # 시스템 관점
df["z_b_sum"] = df["zone3b_density_avg"] + df["zone4b_density_avg"]

# =============================================================================
# 1. 상관분석 (3가지 종속변수 × 3가지 상관계수)
# =============================================================================
print("=" * 70)
print("병목 전이 상관분석 (n=100 시나리오)")
print("=" * 70)

results = []
for y_label, y_col in [
    ("Zone 3B avg (exit1)",  "zone3b_density_avg"),
    ("Zone 4B avg (exit4)",  "zone4b_density_avg"),
    ("Zone B max (시스템)",  "z_bmax"),
]:
    x = df["avg_gate_wait"].to_numpy()
    y = df[y_col].to_numpy()
    pear_r, pear_p = stats.pearsonr(x, y)
    spr_r,  spr_p  = stats.spearmanr(x, y)
    ken_r,  ken_p  = stats.kendalltau(x, y)

    print(f"\n[{y_label}]")
    print(f"  Pearson  r={pear_r:+.4f}  p={pear_p:.4g}")
    print(f"  Spearman ρ={spr_r:+.4f}  p={spr_p:.4g}")
    print(f"  Kendall  τ={ken_r:+.4f}  p={ken_p:.4g}")

    results.append({
        "y_label": y_label,
        "y_col": y_col,
        "pearson_r": pear_r, "pearson_p": pear_p,
        "spearman_r": spr_r, "spearman_p": spr_p,
        "kendall_tau": ken_r, "kendall_p": ken_p,
        "n": len(df),
    })

pd.DataFrame(results).to_csv(OUT / "correlation_gate_vs_zoneB.csv", index=False, encoding="utf-8-sig")

# =============================================================================
# 2. 배합별(p×config) 집계 후 상관 (seed 평균 제거로 노이즈 감소)
# =============================================================================
agg = df.groupby(["p", "config"]).agg(
    gate_wait=("avg_gate_wait", "mean"),
    z3b=("zone3b_density_avg", "mean"),
    z4b=("zone4b_density_avg", "mean"),
    z_bmax=("z_bmax", "mean"),
).reset_index()

print("\n" + "=" * 70)
print("배합(p×config) 평균 기준 상관분석 (n=20 배합)")
print("=" * 70)
x2 = agg["gate_wait"].to_numpy()
for label, col in [("Zone 3B", "z3b"), ("Zone 4B", "z4b"), ("Zone B max", "z_bmax")]:
    y2 = agg[col].to_numpy()
    r, p = stats.pearsonr(x2, y2)
    rho, pp = stats.spearmanr(x2, y2)
    print(f"[{label}] Pearson r={r:+.4f} p={p:.4g} | Spearman ρ={rho:+.4f} p={pp:.4g}")

# =============================================================================
# 3. 시각화: 산점도 + 회귀선
# =============================================================================
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (y_label, y_col) in zip(axes, [
    ("Zone 3B avg (exit1)", "zone3b_density_avg"),
    ("Zone 4B avg (exit4)", "zone4b_density_avg"),
    ("Zone B max (시스템)", "z_bmax"),
]):
    x = df["avg_gate_wait"]
    y = df[y_col]
    colors = {0.1:"#1F77B4", 0.3:"#2CA02C", 0.5:"#FF7F0E", 0.7:"#D62728", 0.8:"#9467BD"}
    for p_val in sorted(df["p"].unique()):
        sub = df[df["p"] == p_val]
        ax.scatter(sub["avg_gate_wait"], sub[y_col], c=colors[p_val],
                   label=f"p={p_val}", s=35, alpha=0.7, edgecolors="white")
    # 회귀선
    slope, intercept, r_v, p_v, _ = stats.linregress(x, y)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, intercept + slope*xs, "k--", alpha=0.7,
            label=f"r={r_v:+.3f}, p={p_v:.2g}")
    # MOLIT 보행로 임계선
    ax.axhline(2.0, color="red", linestyle=":", alpha=0.6, label="LOS F (보행로 >2.0)")
    ax.axhline(1.0, color="orange", linestyle=":", alpha=0.6, label="LOS D/E 경계 (1.0)")
    ax.set_xlabel("평균 게이트 대기시간 (s)")
    ax.set_ylabel(f"{y_label} 밀도 (ped/m²)")
    ax.set_title(y_label)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")
plt.suptitle("병목 전이: 게이트 대기 ↓ → 에스컬 앞 밀도 ↑ (MOLIT 기준)", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(FIG / "bottleneck_transfer_scatter.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'bottleneck_transfer_scatter.png'}")

# =============================================================================
# 4. p별 분석 — 이용률 통제 시 상관
# =============================================================================
print("\n" + "=" * 70)
print("이용률 p 통제 시 부분 상관 (같은 p 내에서 config만 변화)")
print("=" * 70)
part_results = []
for p_val in sorted(df["p"].unique()):
    sub = df[df["p"] == p_val]
    x = sub["avg_gate_wait"].to_numpy()
    for label, col in [("3B", "zone3b_density_avg"), ("4B", "zone4b_density_avg"), ("Bmax", "z_bmax")]:
        y = sub[col].to_numpy()
        if len(np.unique(y)) < 2:
            continue
        r, p = stats.pearsonr(x, y)
        rho, _ = stats.spearmanr(x, y)
        print(f"  p={p_val}: {label} Pearson r={r:+.3f} (p={p:.3g})  Spearman ρ={rho:+.3f}")
        part_results.append({"p": p_val, "target": label, "pearson_r": r, "pearson_p": p, "spearman_rho": rho})

pd.DataFrame(part_results).to_csv(OUT / "correlation_by_p.csv", index=False, encoding="utf-8-sig")

# =============================================================================
# 5. 결론 출력
# =============================================================================
print("\n" + "=" * 70)
print("결론")
print("=" * 70)
main = results[2]  # Zone B max
print(f"- 게이트 대기 - Zone B (시스템) 평균 밀도: "
      f"r = {main['pearson_r']:+.3f} (p = {main['pearson_p']:.2e})")
print(f"- 부호 해석: r<0 -> 게이트 대기 짧을수록 에스컬 앞 밀도 상승 -> 병목 전이 증거")

sig = main["pearson_p"] < 0.001
print(f"- 통계적 유의성 (alpha=0.001): {'유의' if sig else '비유의'}")
