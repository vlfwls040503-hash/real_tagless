"""
종속변수 변경: 총 통행시간 (avg_travel_time = gate + post_gate + esc) 기준 최적 cfg.

(G) 게이트 관점:  avg_gate_wait 최소화
(S) 시스템 관점:  avg_travel_time 최소화 (시스템 전체 효율)

각 관점 최적 cfg 에서 Zone B LOS (보행로 기준, MOLIT 표 2.3) 동시 보고.
"""
from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import zone_grade

OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# 100 시나리오 raw + Zone 밀도
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")

# Zone B max (시스템) 밀도 추가
df["z_bmax_avg"] = df[["zone3b_avg_density", "zone4b_avg_density"]].max(axis=1)
df["z_bmax_max"] = df[["zone3b_max_density", "zone4b_max_density"]].max(axis=1)

# 시드 평균
agg = df.groupby(["p","config"]).agg(
    gate_wait=("avg_gate_wait", "mean"),
    gate_wait_std=("avg_gate_wait", "std"),
    esc_wait=("avg_esc_wait_precise", "mean"),
    travel=("avg_travel_time", "mean"),
    travel_std=("avg_travel_time", "std"),
    z3b=("zone3b_avg_density", "mean"),
    z4b=("zone4b_avg_density", "mean"),
    z_bmax=("z_bmax_avg", "mean"),
    z3b_max=("zone3b_max_density", "mean"),
    z4b_max=("zone4b_max_density", "mean"),
    z2_avg=("zone2_avg_density", "mean"),
).reset_index()
agg["los_z3b"]  = agg["z3b"].apply(lambda d: zone_grade("zone3b", d))
agg["los_z4b"]  = agg["z4b"].apply(lambda d: zone_grade("zone4b", d))
agg["los_zbmax"]= agg["z_bmax"].apply(lambda d: zone_grade("zone3b", d))  # 보행로 기준

print("=" * 90)
print("종속변수: 총 통행시간 (gate + post_gate + esc) 기준 시스템 최적 cfg")
print("=" * 90)

# 결과 표
results = []
for p_val in sorted(agg["p"].unique()):
    sub = agg[agg["p"] == p_val].sort_values("config")
    g_idx = sub["gate_wait"].idxmin()
    s_idx = sub["travel"].idxmin()
    g_cfg = int(sub.loc[g_idx, "config"])
    s_cfg = int(sub.loc[s_idx, "config"])
    g_row = sub.loc[g_idx]
    s_row = sub.loc[s_idx]
    record = {
        "p": p_val,
        "G_cfg": g_cfg,
        "G_gate_wait": g_row["gate_wait"],
        "G_esc_wait": g_row["esc_wait"],
        "G_travel": g_row["travel"],
        "G_z_bmax": g_row["z_bmax"],
        "G_los_zbmax": g_row["los_zbmax"],
        "S_cfg": s_cfg,
        "S_gate_wait": s_row["gate_wait"],
        "S_esc_wait": s_row["esc_wait"],
        "S_travel": s_row["travel"],
        "S_z_bmax": s_row["z_bmax"],
        "S_los_zbmax": s_row["los_zbmax"],
        "binding": "일치" if g_cfg == s_cfg else f"분리 (G:{g_cfg}/S:{s_cfg})",
        "savings_s": g_row["travel"] - s_row["travel"],   # G 대비 S 절약 (초)
    }
    results.append(record)
    print(f"\np={p_val:.1f}:")
    print(f"  [G] 게이트 관점: cfg={g_cfg}, gate={g_row['gate_wait']:.1f}s, esc={g_row['esc_wait']:.1f}s, "
          f"travel={g_row['travel']:.1f}s, Z_bmax={g_row['z_bmax']:.2f} (LOS {g_row['los_zbmax']})")
    print(f"  [S] 시스템 관점: cfg={s_cfg}, gate={s_row['gate_wait']:.1f}s, esc={s_row['esc_wait']:.1f}s, "
          f"travel={s_row['travel']:.1f}s, Z_bmax={s_row['z_bmax']:.2f} (LOS {s_row['los_zbmax']})")
    if g_cfg != s_cfg:
        sav = g_row["travel"] - s_row["travel"]
        print(f"  >> 시스템 관점 채택 시 통행시간 {sav:+.1f}s 절약 (G→S)")

results_df = pd.DataFrame(results)
results_df.to_csv(OUT / "optimal_gate_count_v2.csv", index=False, encoding="utf-8-sig")

# =============================================================================
# 시각화 — 4-패널: gate_wait, esc_wait, travel(시스템 종속변수), Zone B LOS
# =============================================================================
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.3, height_ratios=[1, 1.1])

ps = sorted(agg["p"].unique())
cfgs = sorted(agg["config"].unique())

def heatmap(ax, vals, title, cmap="RdYlGn_r", vmin=None, vmax=None,
            fmt="{:.1f}", highlight_idx=None, highlight_color="blue"):
    arr = vals.values
    im = ax.imshow(arr, cmap=cmap, aspect="auto", origin="lower",
                   vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(cfgs)))
    ax.set_xticklabels([f"cfg{c}" for c in cfgs])
    ax.set_yticks(range(len(ps)))
    ax.set_yticklabels([f"p={p}" for p in ps])
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i,j]
            if not np.isnan(v):
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=9)
    if highlight_idx is not None:
        for i, j in highlight_idx:
            ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                                       edgecolor=highlight_color, lw=3))
    ax.set_title(title)
    plt.colorbar(im, ax=ax)

# (a) Gate wait — G optimal 표시 (파란)
ax1 = fig.add_subplot(gs[0, 0])
piv = agg.pivot(index="p", columns="config", values="gate_wait")
g_idx = []
for i, p in enumerate(ps):
    r = results_df[results_df.p==p].iloc[0]
    g_idx.append((i, list(cfgs).index(r["G_cfg"])))
heatmap(ax1, piv, "(a) avg_gate_wait (s)\n파란 테두리 = 게이트 관점 최적",
        highlight_idx=g_idx, highlight_color="blue")

# (b) Esc wait
ax2 = fig.add_subplot(gs[0, 1])
piv = agg.pivot(index="p", columns="config", values="esc_wait")
heatmap(ax2, piv, "(b) avg_esc_wait (s)")

# (c) Travel (총 통행시간) — S optimal 표시 (주황)
ax3 = fig.add_subplot(gs[0, 2])
piv = agg.pivot(index="p", columns="config", values="travel")
s_idx = []
for i, p in enumerate(ps):
    r = results_df[results_df.p==p].iloc[0]
    s_idx.append((i, list(cfgs).index(r["S_cfg"])))
heatmap(ax3, piv, "(c) 총 통행시간 (s) — 시스템 종속변수\n주황 테두리 = 시스템 관점 최적",
        highlight_idx=s_idx, highlight_color="orange")

# (d) Zone B max 평균 밀도 + LOS
ax4 = fig.add_subplot(gs[1, 0])
piv = agg.pivot(index="p", columns="config", values="z_bmax")
arr = piv.values
im = ax4.imshow(arr, cmap="RdYlGn_r", aspect="auto", origin="lower", vmin=0, vmax=2.5)
ax4.set_xticks(range(len(cfgs))); ax4.set_xticklabels([f"cfg{c}" for c in cfgs])
ax4.set_yticks(range(len(ps))); ax4.set_yticklabels([f"p={p}" for p in ps])
for i in range(arr.shape[0]):
    for j in range(arr.shape[1]):
        v = arr[i,j]
        if np.isnan(v): continue
        los = zone_grade("zone3b", v)
        col = "red" if v>2.0 else ("black")
        weight = "bold" if v>2.0 else "normal"
        ax4.text(j, i, f"{v:.2f}\n({los})", ha="center", va="center",
                 fontsize=8, color=col, fontweight=weight)
        if v > 2.0:
            ax4.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                                        edgecolor="red", lw=2, linestyle="--"))
# G/S 최적 모두 표시
for i, j in g_idx:
    ax4.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False, edgecolor="blue", lw=3))
for i, j in s_idx:
    ax4.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False, edgecolor="orange", lw=2, linestyle=":"))
ax4.set_title("(d) Zone B max 평균밀도 (ped/m²) + 보행로 LOS\n파:G최적 / 주황:S최적 / 빨강점선:LOS F 초과")
plt.colorbar(im, ax=ax4, label="ped/m²")

# (e) p별 G vs S 최적 비교 (총 통행시간)
ax5 = fig.add_subplot(gs[1, 1])
x = np.arange(len(ps))
w = 0.35
ax5.bar(x-w/2, [r["G_travel"] for r in results], w, color="#1F77B4", label="게이트 관점 최적 cfg의 travel time")
ax5.bar(x+w/2, [r["S_travel"] for r in results], w, color="#FF7F0E", label="시스템 관점 최적 cfg의 travel time")
for i, r in enumerate(results):
    ax5.text(x[i]-w/2, r["G_travel"]+0.5, f"cfg{r['G_cfg']}", ha="center", fontsize=8)
    ax5.text(x[i]+w/2, r["S_travel"]+0.5, f"cfg{r['S_cfg']}", ha="center", fontsize=8)
ax5.set_xticks(x); ax5.set_xticklabels([f"p={p}" for p in ps])
ax5.set_ylabel("평균 총 통행시간 (s)")
ax5.set_title("(e) G vs S: 총 통행시간 비교")
ax5.legend(fontsize=8)
ax5.grid(alpha=0.3, axis="y")

# (f) 각 관점 최적 cfg 의 Zone B 밀도 + LOS 등급
ax6 = fig.add_subplot(gs[1, 2])
g_dens = [r["G_z_bmax"] for r in results]
s_dens = [r["S_z_bmax"] for r in results]
g_los = [r["G_los_zbmax"] for r in results]
s_los = [r["S_los_zbmax"] for r in results]
ax6.bar(x-w/2, g_dens, w, color="#1F77B4", label="게이트 관점 최적 → Z_bmax")
ax6.bar(x+w/2, s_dens, w, color="#FF7F0E", label="시스템 관점 최적 → Z_bmax")
for i, r in enumerate(results):
    ax6.text(x[i]-w/2, g_dens[i]+0.05, f"{g_los[i]}", ha="center", fontsize=9, fontweight="bold")
    ax6.text(x[i]+w/2, s_dens[i]+0.05, f"{s_los[i]}", ha="center", fontsize=9, fontweight="bold")
ax6.axhline(2.0, color="red", linestyle="--", alpha=0.6, label="LOS F (보행로 >2.0)")
ax6.axhline(1.0, color="orange", linestyle="--", alpha=0.6, label="LOS D/E 경계 (1.0)")
ax6.set_xticks(x); ax6.set_xticklabels([f"p={p}" for p in ps])
ax6.set_ylabel("Zone B 평균밀도 (ped/m²)")
ax6.set_title("(f) 각 관점 최적 cfg의 Zone B LOS")
ax6.legend(fontsize=8)
ax6.grid(alpha=0.3, axis="y")

fig.suptitle("종속변수: 총 통행시간 (gate+esc) 기준 시스템 최적 cfg + Zone B LOS",
             fontsize=14, fontweight="bold", y=1.0)
plt.savefig(FIG / "optimal_gate_count_v2.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'optimal_gate_count_v2.png'}")

# =============================================================================
# 결론 요약
# =============================================================================
print("\n" + "=" * 90)
print("종합 결론")
print("=" * 90)
print(f"{'p':>4} | {'G cfg':>5} {'G travel':>8} {'G Z_bmax':>10} {'G LOS':>5} | "
      f"{'S cfg':>5} {'S travel':>8} {'S Z_bmax':>10} {'S LOS':>5} | binding")
for r in results:
    print(f"{r['p']:>4.1f} | {r['G_cfg']:>5} {r['G_travel']:>8.1f} {r['G_z_bmax']:>10.2f} {r['G_los_zbmax']:>5} | "
          f"{r['S_cfg']:>5} {r['S_travel']:>8.1f} {r['S_z_bmax']:>10.2f} {r['S_los_zbmax']:>5} | {r['binding']}")
