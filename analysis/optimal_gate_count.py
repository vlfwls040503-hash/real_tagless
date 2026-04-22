"""
이용률 p별 최적 전용 개찰구 수 도출 — 2관점.

(G) 게이트 관점: 평균 게이트 대기시간 최소화
(S) 시스템 관점: 에스컬 앞 보행공간 밀도 ≤ 국토부 LOS E (2.0 ped/m²)
                 즉 LOS F 방지하는 최대 config (또는 최소 config)

두 관점의 임계점이 p별로 어느 쪽이 먼저 바인딩(binding)되는지 시각화.

가정:
- 겸용 게이트 제외, 첨두/비첨두 구분 제외 (사용자 제약)
- 결과 왜곡 금지 (지표 신설/선택적 보고 금지)

출력:
- results/molit/optimal_gate_count.csv
- figures/molit/optimal_gate_count.png
"""
from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import zone_grade, WALKWAY_LOS

OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(OUT / "molit_los_100scenarios.csv")

# 지표 정의
df["z_bmax"] = df[["zone3b_density_avg", "zone4b_density_avg"]].max(axis=1)
LOS_F_WALKWAY = 2.0     # MOLIT 표 2.3 보행로 LOS E 상한 (F 시작)
LOS_E_WALKWAY = 1.0     # LOS D/E 경계
LOS_D_WALKWAY = 0.7     # LOS C/D 경계

# seed 평균 집계
agg = df.groupby(["p", "config"]).agg(
    gate_wait=("avg_gate_wait", "mean"),
    gate_wait_std=("avg_gate_wait", "std"),
    gate_wait_p95=("p95_gate_wait", "mean"),
    z3b=("zone3b_density_avg", "mean"),
    z4b=("zone4b_density_avg", "mean"),
    z_bmax=("z_bmax", "mean"),
    z_bmax_std=("z_bmax", "std"),
).reset_index()

print("=" * 70)
print("p별 최적 개찰구 수 도출 (2관점)")
print("=" * 70)

results = []
for p_val in sorted(agg["p"].unique()):
    sub = agg[agg["p"] == p_val].sort_values("config")
    # (G) 게이트 관점: gate_wait 최소 config
    g_opt_idx = sub["gate_wait"].idxmin()
    g_opt_cfg = int(sub.loc[g_opt_idx, "config"])
    g_opt_wait = sub.loc[g_opt_idx, "gate_wait"]

    # (S) 시스템 관점: z_bmax <= LOS_F_WALKWAY (2.0) 만족하는 config 중
    #     게이트 대기 최소
    safe = sub[sub["z_bmax"] <= LOS_F_WALKWAY]
    if len(safe) == 0:
        s_opt_cfg = np.nan
        s_opt_wait = np.nan
        s_opt_density = sub["z_bmax"].min()
        s_feasible = False
    else:
        s_opt_idx = safe["gate_wait"].idxmin()
        s_opt_cfg = int(safe.loc[s_opt_idx, "config"])
        s_opt_wait = safe.loc[s_opt_idx, "gate_wait"]
        s_opt_density = safe.loc[s_opt_idx, "z_bmax"]
        s_feasible = True

    # 어느 관점이 먼저 바인딩?
    if not s_feasible:
        binding = "시스템 (전 config F 초과)"
    elif g_opt_cfg == s_opt_cfg:
        binding = "일치"
    else:
        binding = f"분리 (gate:{g_opt_cfg} vs sys:{s_opt_cfg})"

    # z_bmax 가 처음 2.0 넘는 config (config 증가 시)
    above_F = sub[sub["z_bmax"] > LOS_F_WALKWAY]
    first_f_cfg = int(above_F["config"].min()) if len(above_F)>0 else None

    record = {
        "p": p_val,
        "gate_opt_cfg": g_opt_cfg,
        "gate_opt_wait": g_opt_wait,
        "sys_opt_cfg": s_opt_cfg,
        "sys_opt_wait": s_opt_wait,
        "sys_opt_density": s_opt_density,
        "sys_feasible": s_feasible,
        "first_F_cfg": first_f_cfg,
        "binding": binding,
    }
    results.append(record)
    print(f"\np={p_val:.1f}:")
    print(f"  [G] 게이트 최적:     cfg={g_opt_cfg}, gate_wait={g_opt_wait:.1f}s")
    if s_feasible:
        print(f"  [S] 시스템 최적:     cfg={s_opt_cfg}, gate_wait={s_opt_wait:.1f}s, "
              f"z_bmax={s_opt_density:.2f} ped/m^2")
    else:
        print(f"  [S] 시스템 최적:     없음 (모든 config 에서 z_bmax > 2.0)")
    print(f"  바인딩: {binding}")

results_df = pd.DataFrame(results)
results_df.to_csv(OUT / "optimal_gate_count.csv", index=False, encoding="utf-8-sig")

# =============================================================================
# 시각화: 2관점 통합 한 장
# =============================================================================
fig = plt.figure(figsize=(14, 9))
gs = fig.add_gridspec(2, 2, width_ratios=[1.4, 1], hspace=0.3, wspace=0.25)

# (a) 게이트 대기 히트맵 (p × config)
ax1 = fig.add_subplot(gs[0, 0])
pivot_gw = agg.pivot(index="p", columns="config", values="gate_wait")
im1 = ax1.imshow(pivot_gw.values, cmap="RdYlGn_r", aspect="auto", origin="lower")
ax1.set_xticks(range(len(pivot_gw.columns)))
ax1.set_xticklabels([f"cfg{c}" for c in pivot_gw.columns])
ax1.set_yticks(range(len(pivot_gw.index)))
ax1.set_yticklabels([f"p={p}" for p in pivot_gw.index])
ax1.set_title("(a) 게이트 관점: 평균 대기시간 (초)")
# 최적 marking
for i, p in enumerate(pivot_gw.index):
    for j, c in enumerate(pivot_gw.columns):
        v = pivot_gw.iloc[i, j]
        if not np.isnan(v):
            ax1.text(j, i, f"{v:.1f}", ha="center", va="center",
                     fontsize=9, color="black")
for i, p in enumerate(pivot_gw.index):
    r = results_df[results_df["p"]==p].iloc[0]
    opt_j = list(pivot_gw.columns).index(r["gate_opt_cfg"])
    ax1.add_patch(plt.Rectangle((opt_j-0.5, i-0.5), 1, 1, fill=False,
                                edgecolor="blue", lw=3))
plt.colorbar(im1, ax=ax1, label="대기시간 (s)")

# (b) 시스템 관점 밀도 히트맵
ax2 = fig.add_subplot(gs[1, 0])
pivot_den = agg.pivot(index="p", columns="config", values="z_bmax")
im2 = ax2.imshow(pivot_den.values, cmap="RdYlGn_r", aspect="auto", origin="lower",
                 vmin=0, vmax=3.0)
ax2.set_xticks(range(len(pivot_den.columns)))
ax2.set_xticklabels([f"cfg{c}" for c in pivot_den.columns])
ax2.set_yticks(range(len(pivot_den.index)))
ax2.set_yticklabels([f"p={p}" for p in pivot_den.index])
ax2.set_title("(b) 시스템 관점: Zone B max 평균밀도 (ped/m²)\n"
              "빨간 테두리 = LOS F 초과 (>2.0) | 파란 테두리 = 시스템 최적")
for i, p in enumerate(pivot_den.index):
    for j, c in enumerate(pivot_den.columns):
        v = pivot_den.iloc[i, j]
        if np.isnan(v):
            continue
        color = "red" if v > LOS_F_WALKWAY else "black"
        weight = "bold" if v > LOS_F_WALKWAY else "normal"
        ax2.text(j, i, f"{v:.2f}", ha="center", va="center",
                 fontsize=9, color=color, fontweight=weight)
        if v > LOS_F_WALKWAY:
            ax2.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                                        edgecolor="red", lw=2, linestyle="--"))
for i, p in enumerate(pivot_den.index):
    r = results_df[results_df["p"]==p].iloc[0]
    if r["sys_feasible"]:
        opt_j = list(pivot_den.columns).index(r["sys_opt_cfg"])
        ax2.add_patch(plt.Rectangle((opt_j-0.5, i-0.5), 1, 1, fill=False,
                                    edgecolor="blue", lw=3))
plt.colorbar(im2, ax=ax2, label="밀도 (ped/m²)")

# (c) 2관점 비교: p별 최적 cfg
ax3 = fig.add_subplot(gs[:, 1])
ps = results_df["p"].values
g_cfgs = results_df["gate_opt_cfg"].values
s_cfgs = results_df["sys_opt_cfg"].values
x = np.arange(len(ps))
w = 0.35
bars_g = ax3.bar(x - w/2, g_cfgs, w, color="#1F77B4", label="게이트 관점 최적 cfg")
s_valid = ~np.isnan(s_cfgs)
s_plot = np.where(s_valid, s_cfgs, 0)
bars_s = ax3.bar(x + w/2, s_plot, w, color="#FF7F0E", label="시스템 관점 최적 cfg")
for i, v in enumerate(s_cfgs):
    if np.isnan(v):
        ax3.text(x[i]+w/2, 0.5, "불가", ha="center", fontsize=8, color="red")

# binding 표시
for i, p in enumerate(ps):
    r = results_df[results_df["p"]==p].iloc[0]
    if "분리" in r["binding"]:
        ax3.annotate("", xy=(x[i]+w/2, s_cfgs[i]+0.1), xytext=(x[i]-w/2, g_cfgs[i]+0.1),
                     arrowprops=dict(arrowstyle="<->", color="red", lw=1.5))

ax3.set_xticks(x)
ax3.set_xticklabels([f"p={p}" for p in ps])
ax3.set_ylabel("최적 config 번호 (전용 게이트 수 → 1~4)")
ax3.set_title("(c) p별 2관점 최적 config\n(빨간 화살표 = 관점별 분리)")
ax3.legend(loc="upper left")
ax3.grid(alpha=0.3, axis="y")
ax3.set_ylim(0, 5)

fig.suptitle("국토부 LOS 기준 기반 이용률별 최적 개찰구 수",
             fontsize=14, fontweight="bold")
plt.savefig(FIG / "optimal_gate_count.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'optimal_gate_count.png'}")

# =============================================================================
# 결론 요약
# =============================================================================
print("\n" + "=" * 70)
print("결론 요약")
print("=" * 70)
for _, r in results_df.iterrows():
    p = r["p"]; g = r["gate_opt_cfg"]; s = r["sys_opt_cfg"]
    if r["sys_feasible"]:
        s_str = f"cfg{s}"
    else:
        s_str = "불가"
    bind = r["binding"]
    print(f"  p={p:.1f}: 게이트 관점 cfg{g} | 시스템 관점 {s_str} | 바인딩: {bind}")
