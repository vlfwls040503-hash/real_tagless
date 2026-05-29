"""
3가지 종속변수/제약 조합으로 최적 cfg 도출 + p=0 baseline 포함

(G)  게이트 관점:        min avg_gate_wait
(S1) 시스템 + LOS E 제약: Z_bmax ≤ 2.0 (지침 권장) → min avg_travel_time
(S2) 시스템 + LOS D 제약: Z_bmax ≤ 1.0 (엄격)     → min avg_travel_time
"""
from __future__ import annotations
from pathlib import Path
import sys, json
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

# ── 100 시나리오 + cfg5,6 모두 로드 ─────────────────────────────
df = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
# cfg1-4 는 SKIP 처리되어 spawned/passed 메타 누락. 신뢰도 OK 가정 (이전 검증).
# cfg5,6 만 pass_rate <90% 시 제외 (시뮬 시간 부족 → 정상상태 미도달)
df["pass_rate"] = df["passed"] / df["spawned"]
keep_mask = (df["config"].isin([1,2,3,4])) | (df["pass_rate"] > 0.9)
df_keep = df[keep_mask].copy()
n_excl = len(df) - len(df_keep)
print(f"전체 시나리오: {len(df)}, 사용: {len(df_keep)} (제외 {n_excl}: cfg5,6 시뮬 시간 부족)")
# cfg5,6은 이미 cfg1-4와 동등한 SIM_TIME 600s 등으로 재실행 필요 (현재 300s)

df_keep["z_bmax"] = df_keep[["zone3b_avg_density","zone4b_avg_density"]].max(axis=1)
agg = df_keep.groupby(["p","config"]).agg(
    gate_wait=("avg_gate_wait","mean"),
    esc_wait=("avg_esc_wait_precise","mean"),
    travel=("avg_travel_time","mean"),
    z3b=("zone3b_avg_density","mean"),
    z4b=("zone4b_avg_density","mean"),
    z_bmax=("z_bmax","mean"),
    n_seeds=("seed","count"),
).reset_index()
agg["los_zbmax"] = agg["z_bmax"].apply(lambda d: zone_grade("zone3b", d))

# ── p=0 baseline ──────────────────────────────────────────────
p0 = json.load(open(ROOT/"results_baseline"/"p0_summary.json", encoding="utf-8"))["aggregated"]
def m(k): return p0[k]["mean"]
p0_z4b = m("z4b_avg")
p0_z3b = m("z3b_avg")
p0_zbmax = max(p0_z4b, p0_z3b)
p0_los = zone_grade("zone3b", p0_zbmax)
p0_gate = m("avg_gate_wait")
p0_esc  = m("avg_esc_wait_precise")
p0_travel = m("avg_travel_time")

# ── 분석 ──────────────────────────────────────────────────────
print("\n" + "="*100)
print(f"{'p':>4} | {'baseline':>20s} | {'(G) 게이트만 최적':>30s} | "
      f"{'(S1) LOS E ≤2.0':>30s} | {'(S2) LOS D ≤1.0':>30s}")
print("="*100)

# p=0 row
print(f"{0.0:>4.1f} | "
      f"travel={p0_travel:.1f}s Z_bmax={p0_zbmax:.2f}({p0_los}) | "
      f"{'(baseline)':>30s} | {'(baseline)':>30s} | {'(baseline)':>30s}")

records = [{
    "p": 0.0,
    "G_cfg": None, "G_gate": p0_gate, "G_travel": p0_travel, "G_zbmax": p0_zbmax, "G_los": p0_los,
    "S1_cfg": None, "S1_gate": p0_gate, "S1_travel": p0_travel, "S1_zbmax": p0_zbmax, "S1_los": p0_los, "S1_feasible": p0_zbmax<=2.0,
    "S2_cfg": None, "S2_gate": p0_gate, "S2_travel": p0_travel, "S2_zbmax": p0_zbmax, "S2_los": p0_los, "S2_feasible": p0_zbmax<=1.0,
}]

for p_val in sorted(agg["p"].unique()):
    sub = agg[agg["p"]==p_val]
    # G
    g_idx = sub["gate_wait"].idxmin()
    g = sub.loc[g_idx]
    # S1: LOS E (≤2.0)
    s1 = sub[sub["z_bmax"] <= 2.0]
    if len(s1) > 0:
        s1_idx = s1["travel"].idxmin()
        s1r = s1.loc[s1_idx]
        s1_feasible = True
    else:
        s1r = sub.loc[sub["travel"].idxmin()]
        s1_feasible = False
    # S2: LOS D (≤1.0)
    s2 = sub[sub["z_bmax"] <= 1.0]
    if len(s2) > 0:
        s2_idx = s2["travel"].idxmin()
        s2r = s2.loc[s2_idx]
        s2_feasible = True
    else:
        s2r = sub.loc[sub["travel"].idxmin()]
        s2_feasible = False

    print(f"{p_val:>4.1f} | "
          f"{'':>20s} | "
          f"cfg{int(g.config)} gw={g.gate_wait:.1f} tr={g.travel:.1f} Z={g.z_bmax:.2f}({g.los_zbmax}) | "
          f"cfg{int(s1r.config) if s1_feasible else '-'} tr={s1r.travel:.1f} Z={s1r.z_bmax:.2f}({s1r.los_zbmax}){'' if s1_feasible else '*불가'} | "
          f"cfg{int(s2r.config) if s2_feasible else '-'} tr={s2r.travel:.1f} Z={s2r.z_bmax:.2f}({s2r.los_zbmax}){'' if s2_feasible else '*불가'}")

    records.append({
        "p": p_val,
        "G_cfg": int(g.config), "G_gate": g.gate_wait, "G_travel": g.travel, "G_zbmax": g.z_bmax, "G_los": g.los_zbmax,
        "S1_cfg": int(s1r.config) if s1_feasible else None, "S1_gate": s1r.gate_wait, "S1_travel": s1r.travel, "S1_zbmax": s1r.z_bmax, "S1_los": s1r.los_zbmax, "S1_feasible": s1_feasible,
        "S2_cfg": int(s2r.config) if s2_feasible else None, "S2_gate": s2r.gate_wait, "S2_travel": s2r.travel, "S2_zbmax": s2r.z_bmax, "S2_los": s2r.los_zbmax, "S2_feasible": s2_feasible,
    })

results_df = pd.DataFrame(records)
results_df.to_csv(OUT / "optimal_gate_count_v3.csv", index=False, encoding="utf-8-sig")

# ── 시각화 ────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
ps = results_df["p"].tolist()
x = np.arange(len(ps))
w = 0.27

# (a) 최적 cfg 비교
ax = axes[0]
ax.bar(x-w, [r if r else 0 for r in results_df["G_cfg"]], w,
       color="#1F77B4", label="(G) 게이트만")
ax.bar(x,   [r if r else 0 for r in results_df["S1_cfg"]], w,
       color="#FF7F0E", label="(S1) +LOS E ≤2.0")
ax.bar(x+w, [r if r else 0 for r in results_df["S2_cfg"]], w,
       color="#9467BD", label="(S2) +LOS D ≤1.0")
for i, r in results_df.iterrows():
    ax.text(x[i]-w, (r["G_cfg"] or 0)+0.05, f"{r['G_cfg'] or '-'}", ha="center", fontsize=8)
    ax.text(x[i],   (r["S1_cfg"] or 0)+0.05, f"{r['S1_cfg'] or 'X'}", ha="center", fontsize=8,
            color="red" if not r["S1_feasible"] else "black")
    ax.text(x[i]+w, (r["S2_cfg"] or 0)+0.05, f"{r['S2_cfg'] or 'X'}", ha="center", fontsize=8,
            color="red" if not r["S2_feasible"] else "black")
ax.set_xticks(x); ax.set_xticklabels([f"p={p}" for p in ps])
ax.set_ylabel("최적 cfg (전용 게이트 수)")
ax.set_title("(a) p별 최적 cfg")
ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")

# (b) 총 통행시간 비교
ax = axes[1]
ax.bar(x-w, results_df["G_travel"], w, color="#1F77B4", label="(G)")
ax.bar(x,   results_df["S1_travel"], w, color="#FF7F0E", label="(S1)")
ax.bar(x+w, results_df["S2_travel"], w, color="#9467BD", label="(S2)")
for i, r in results_df.iterrows():
    ax.text(x[i]-w, r["G_travel"]+0.5, f"{r['G_travel']:.1f}", ha="center", fontsize=7)
ax.set_xticks(x); ax.set_xticklabels([f"p={p}" for p in ps])
ax.set_ylabel("평균 총 통행시간 (s)")
ax.set_title("(b) 통행시간 비교")
ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")

# (c) Zone B 밀도 + LOS 임계
ax = axes[2]
ax.bar(x-w, results_df["G_zbmax"], w, color="#1F77B4", label="(G)")
ax.bar(x,   results_df["S1_zbmax"], w, color="#FF7F0E", label="(S1)")
ax.bar(x+w, results_df["S2_zbmax"], w, color="#9467BD", label="(S2)")
ax.axhline(2.0, color="red", linestyle="--", label="LOS E 상한 (보행로)")
ax.axhline(1.0, color="orange", linestyle="--", label="LOS D 상한")
for i, r in results_df.iterrows():
    ax.text(x[i]-w, r["G_zbmax"]+0.05, r["G_los"], ha="center", fontsize=7, fontweight="bold")
    ax.text(x[i]+w, r["S2_zbmax"]+0.05, r["S2_los"], ha="center", fontsize=7, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([f"p={p}" for p in ps])
ax.set_ylabel("Zone B max 평균밀도 (ped/m²)")
ax.set_title("(c) Z_bmax + LOS 임계")
ax.legend(fontsize=7); ax.grid(alpha=0.3, axis="y")

fig.suptitle("3관점 비교: 게이트만 vs +LOS E vs +LOS D (cfg5,6 제외)",
             fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(FIG / "optimal_3perspectives.png", dpi=110, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'optimal_3perspectives.png'}")
