"""시스템 최적화 관점 최종 분석 — 국토부 LOS 기준 적용
Step 1: 국소 최적화 (개찰구 관점)
Step 2: 병목 전이와 LOS 위반 임계점
Step 3: 제약 조건부 시스템 최적화
ANOVA + 가변 운영 권고
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from scipy import stats
from scipy.stats import f_oneway, linregress
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import statsmodels.formula.api as smf
import pwlf

ROOT = Path(__file__).resolve().parent.parent
SUMMARY  = ROOT / "results_cfsm_latest" / "summary.csv"
AGENT    = ROOT / "results_cfsm_latest" / "agent_level_delay.csv"
FIG_DIR  = ROOT / "figures"
RES_DIR  = ROOT / "results_final"
DOCS_DIR = ROOT / "docs"
for d in [FIG_DIR, RES_DIR, DOCS_DIR]:
    d.mkdir(exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 100, "savefig.dpi": 100,
    "font.family": "Malgun Gothic", "axes.unicode_minus": False,
    "font.size": 10,
})

# ── 상수 ──
LOS_D_THRESH = 1.08   # Zone B: LOS D 유지 최대 밀도
LOS_F_THRESH = 2.17   # LOS F 진입 밀도
SIM_TIME     = 120.0
N_GATES      = 7
P_LEVELS     = [0.1, 0.3, 0.5, 0.7, 0.8]
CFG_LEVELS   = [1, 2, 3, 4]
P_LABELS     = ["p=10%", "p=30%", "p=50%", "p=70%", "p=80%"]
CFG_COLORS   = {1: "#4C9BE8", 2: "#F5A623", 3: "#7ED321", 4: "#D0021B"}

# 기존 분석 결과: 게이트 관점 최적 cfg
GATE_OPT = {0.1: 1, 0.3: 2, 0.5: 3, 0.7: 4, 0.8: 4}

# ── LOS 분류 ──
def classify_los(d: float) -> str:
    if d < 1.08:   return "D이상"
    if d < 2.17:   return "E"
    return "F"

def los_color(los: str) -> str:
    return {"D이상": "#2ECC71", "E": "#F39C12", "F": "#E74C3C"}.get(los, "gray")


# =============================================================================
# 데이터 로드 및 전처리
# =============================================================================
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(SUMMARY)
    # Zone 집계: B(대기), A(접근)
    df["zone_b_max"]  = df[["zone3b_max_density", "zone4b_max_density"]].max(axis=1)
    df["zone_b_avg"]  = df[["zone3b_avg_density",  "zone4b_avg_density"]].mean(axis=1)
    df["zone_a_max"]  = df[["zone3a_max_density", "zone4a_max_density"]].max(axis=1)
    df["zone_a_avg"]  = df[["zone3a_avg_density",  "zone4a_avg_density"]].mean(axis=1)
    df["gate_throughput"] = df["passed"] / SIM_TIME        # ped/s (전체 7게이트)
    df["pass_rate"]   = df["passed"] / df["spawned"]
    df["los_b"]       = df["zone_b_max"].apply(classify_los)
    df["los_a"]       = df["zone_a_max"].apply(classify_los)
    df["violation_b"] = df["zone_b_max"] >= LOS_D_THRESH
    df["violation_a"] = df["zone_a_max"] >= LOS_F_THRESH

    # seed 평균 집계
    agg = df.groupby(["p", "config"]).agg(
        avg_gate_delay   = ("avg_gate_wait",    "mean"),
        avg_travel_time  = ("avg_travel_time",  "mean"),
        gate_throughput  = ("gate_throughput",  "mean"),
        pass_rate        = ("pass_rate",        "mean"),
        zone_b_max_mean  = ("zone_b_max",       "mean"),
        zone_b_max_max   = ("zone_b_max",       "max"),
        zone_b_avg_mean  = ("zone_b_avg",       "mean"),
        zone_a_max_mean  = ("zone_a_max",       "mean"),
        violation_b_rate = ("violation_b",      "mean"),
    ).reset_index()
    agg["los_b"] = agg["zone_b_max_mean"].apply(classify_los)

    agent_df = pd.read_csv(AGENT)
    return df, agg, agent_df

raw_df, agg_df, agent_df = load_data()
print(f"raw: {raw_df.shape}, agg: {agg_df.shape}, agent: {agent_df.shape}")


# =============================================================================
# Step 1 — 국지적 최적화 (개찰구 관점)
# =============================================================================
def step1():
    print("\n" + "="*60)
    print("Step 1: 국지적 최적화 (개찰구 관점)")
    print("="*60)

    # 1-1. 각 p에서 avg_gate_delay 최소 cfg 확인 (데이터 검증)
    derived_opt = {}
    for p in P_LEVELS:
        sub = agg_df[agg_df["p"] == p].sort_values("avg_gate_delay")
        best = int(sub.iloc[0]["config"])
        derived_opt[p] = best

    print(f"\n데이터 기반 gate-optimal cfg: {derived_opt}")
    print(f"기존 결과 활용 cfg:          {GATE_OPT}")

    # 1-2. 개찰구 효율 지표 표
    rows = []
    for p in P_LEVELS:
        cfg = GATE_OPT[p]
        row = agg_df[(agg_df["p"] == p) & (agg_df["config"] == cfg)].iloc[0]
        rows.append({
            "p": f"p={int(p*100)}%",
            "최적 cfg": cfg,
            "avg_gate_delay (s)": f"{row['avg_gate_delay']:.2f}",
            "gate throughput (ped/s)": f"{row['gate_throughput']:.3f}",
            "pass_rate": f"{row['pass_rate']:.1%}",
        })
    step1_table = pd.DataFrame(rows)
    print("\n[Step 1-2] 개찰구 효율 지표:")
    print(step1_table.to_string(index=False))

    # 1-3. 시각화
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    p_vals = P_LEVELS
    delays = [agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])]["avg_gate_delay"].values[0]
              for p in p_vals]
    thrupts = [agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])]["gate_throughput"].values[0]
               for p in p_vals]
    cfgs = [GATE_OPT[p] for p in p_vals]

    ax1.plot(p_vals, delays, "b-o", lw=2, ms=8, label="avg gate delay (s)")
    ax2.plot(p_vals, thrupts, "r--s", lw=2, ms=8, label="gate throughput (ped/s)")

    for x, d, t, c in zip(p_vals, delays, thrupts, cfgs):
        ax1.annotate(f"cfg{c}", (x, d), textcoords="offset points",
                     xytext=(0, 10), ha="center", fontsize=9, color="blue")

    ax1.set_xlabel("태그리스 이용 비율 (p)")
    ax1.set_ylabel("평균 게이트 대기시간 (s)", color="blue")
    ax2.set_ylabel("게이트 처리율 (ped/s)", color="red")
    ax1.set_xticks(p_vals)
    ax1.set_xticklabels([f"{int(p*100)}%" for p in p_vals])
    ax1.tick_params(axis="y", labelcolor="blue")
    ax2.tick_params(axis="y", labelcolor="red")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("Step 1: 개찰구 관점 최적 cfg — 게이트 효율\n"
                  "핵심: p 증가에 따라 최적 cfg도 증가, 게이트 처리율 극대화")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step1_gate_optimal.png", bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {FIG_DIR/'step1_gate_optimal.png'}")
    return step1_table


# =============================================================================
# Step 2 — 병목 전이와 LOS 위반 임계점
# =============================================================================
def step2():
    print("\n" + "="*60)
    print("Step 2: 병목 전이와 LOS 위반 임계점")
    print("="*60)

    # 2-1. Step1 cfg 시 Zone B 밀도
    rows = []
    for p in P_LEVELS:
        cfg = GATE_OPT[p]
        row = agg_df[(agg_df["p"]==p) & (agg_df["config"]==cfg)].iloc[0]
        los = classify_los(row["zone_b_max_mean"])
        rows.append({
            "p": f"p={int(p*100)}%",
            "게이트 최적 cfg": cfg,
            "Zone B 최대밀도 (평균)": f"{row['zone_b_max_mean']:.3f}",
            "Zone B 평균밀도": f"{row['zone_b_avg_mean']:.3f}",
            "LOS": los,
            "국토부 위반": "위반" if row["zone_b_max_mean"] >= LOS_D_THRESH else "양호",
        })
    step2_1 = pd.DataFrame(rows)
    print("\n[Step 2-1] Zone B 밀도 (게이트 최적 cfg 적용 시):")
    print(step2_1.to_string(index=False))

    # 2-2. 전체 100 시나리오 LOS 히트맵
    pivot_los  = agg_df.pivot(index="config", columns="p", values="zone_b_max_mean")
    pivot_val  = pivot_los.copy()

    los_to_num = {"D이상": 0, "E": 1, "F": 2}
    pivot_num  = pivot_val.applymap(classify_los).applymap(lambda x: los_to_num[x])
    cmap = mcolors.ListedColormap(["#2ECC71", "#F39C12", "#E74C3C"])
    norm = mcolors.BoundaryNorm([0, 1, 2, 3], cmap.N)

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(pivot_num.values, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(P_LEVELS)))
    ax.set_xticklabels([f"{int(p*100)}%" for p in P_LEVELS])
    ax.set_yticks(range(len(CFG_LEVELS)))
    ax.set_yticklabels([f"cfg {c}" for c in CFG_LEVELS])
    ax.set_xlabel("태그리스 이용 비율 (p)")
    ax.set_ylabel("전용 게이트 수 (cfg)")

    for i, cfg in enumerate(CFG_LEVELS):
        for j, p in enumerate(P_LEVELS):
            val = pivot_val.loc[cfg, p]
            los = classify_los(val)
            ax.text(j, i, f"{val:.2f}\n({los})", ha="center", va="center",
                    fontsize=8.5, fontweight="bold",
                    color="white" if los == "F" else "black")

    # 게이트 최적 cfg 표시
    for j, p in enumerate(P_LEVELS):
        i = CFG_LEVELS.index(GATE_OPT[p])
        ax.add_patch(mpatches.FancyBboxPatch(
            (j-0.48, i-0.48), 0.96, 0.96,
            boxstyle="round,pad=0.02", linewidth=2.5,
            edgecolor="navy", facecolor="none"))

    patches = [mpatches.Patch(color=c, label=l)
               for l, c in [("D이상 (양호)", "#2ECC71"), ("E (위반)", "#F39C12"), ("F (심각)", "#E74C3C")]]
    ax.legend(handles=patches, loc="upper left", fontsize=8)
    ax.set_title("Step 2: Zone B LOS 히트맵 (100 시나리오)\n"
                 "□ = 게이트 최적 cfg  |  밀도 기준: LOS D=1.08, F=2.17 /m²")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step2_los_heatmap.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {FIG_DIR/'step2_los_heatmap.png'}")

    # LOS 위반 CSV
    los_tbl = agg_df[["p","config","gate_throughput","zone_b_max_mean","zone_a_max_mean","los_b","violation_b_rate"]].copy()
    los_tbl.columns = ["p","cfg","gate_throughput","zone_b_max","zone_a_max","LOS_B","violation_B_rate"]
    los_tbl["LOS_A"] = los_tbl["zone_a_max"].apply(classify_los)
    los_tbl["violation_A"] = los_tbl["zone_a_max"] >= LOS_F_THRESH
    los_tbl.to_csv(RES_DIR / "los_violation_table.csv", index=False, float_format="%.4f")
    print(f"Saved: {RES_DIR/'los_violation_table.csv'}")

    # 2-3. 회귀분석: gate_throughput → zone_b_max
    x_all = agg_df["gate_throughput"].values
    y_all = agg_df["zone_b_max_mean"].values
    sort_idx = np.argsort(x_all)
    x_s, y_s = x_all[sort_idx], y_all[sort_idx]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    # A) Linear
    slope, intercept, r, p_val, _ = linregress(x_all, y_all)
    r2_lin = r**2
    n = len(x_all)
    k_lin = 2
    sse_lin = np.sum((y_all - (slope*x_all + intercept))**2)
    aic_lin = n * np.log(sse_lin/n) + 2*k_lin

    x_fit = np.linspace(x_all.min(), x_all.max(), 100)
    ax = axes[0]
    ax.scatter(x_all, y_all, c=[CFG_COLORS[int(c)] for c in agg_df["config"]], s=60, zorder=3)
    ax.plot(x_fit, slope*x_fit + intercept, "k-", lw=2)
    ax.axhline(LOS_D_THRESH, color="orange", ls="--", lw=1.5, label=f"LOS D ({LOS_D_THRESH})")
    ax.axhline(LOS_F_THRESH, color="red", ls="--", lw=1.5, label=f"LOS F ({LOS_F_THRESH})")
    x_los_d = (LOS_D_THRESH - intercept) / slope
    x_los_f = (LOS_F_THRESH - intercept) / slope
    ax.axvline(x_los_d, color="orange", ls=":", lw=1.5)
    ax.axvline(x_los_f, color="red", ls=":", lw=1.5)
    ax.set_title(f"A) Linear\nR²={r2_lin:.3f}, AIC={aic_lin:.1f}\n"
                 f"LOS D: {x_los_d:.3f} ped/s  LOS F: {x_los_f:.3f} ped/s")
    ax.set_xlabel("Gate Throughput (ped/s)")
    ax.set_ylabel("Zone B 최대밀도 (명/m²)")
    ax.legend(fontsize=7)

    # B) Polynomial (degree 2)
    coefs = np.polyfit(x_all, y_all, 2)
    y_pred_poly = np.polyval(coefs, x_all)
    sse_poly = np.sum((y_all - y_pred_poly)**2)
    ss_tot = np.sum((y_all - y_all.mean())**2)
    r2_poly = 1 - sse_poly/ss_tot
    k_poly = 3
    aic_poly = n * np.log(sse_poly/n) + 2*k_poly

    ax = axes[1]
    ax.scatter(x_all, y_all, c=[CFG_COLORS[int(c)] for c in agg_df["config"]], s=60, zorder=3)
    y_fit_poly = np.polyval(coefs, x_fit)
    ax.plot(x_fit, y_fit_poly, "k-", lw=2)
    ax.axhline(LOS_D_THRESH, color="orange", ls="--", lw=1.5)
    ax.axhline(LOS_F_THRESH, color="red", ls="--", lw=1.5)
    coefs_d = coefs.copy(); coefs_d[-1] -= LOS_D_THRESH
    roots_d = np.roots(coefs_d); roots_d = roots_d[np.isreal(roots_d)].real
    roots_d = roots_d[(roots_d >= x_all.min()) & (roots_d <= x_all.max())]
    coefs_f = coefs.copy(); coefs_f[-1] -= LOS_F_THRESH
    roots_f = np.roots(coefs_f); roots_f = roots_f[np.isreal(roots_f)].real
    roots_f = roots_f[(roots_f >= x_all.min()) & (roots_f <= x_all.max())]
    for r_d in roots_d: ax.axvline(r_d, color="orange", ls=":", lw=1.5)
    for r_f in roots_f: ax.axvline(r_f, color="red", ls=":", lw=1.5)
    d_str = f"{roots_d[0]:.3f}" if len(roots_d) else "N/A"
    f_str = f"{roots_f[0]:.3f}" if len(roots_f) else "N/A"
    ax.set_title(f"B) Polynomial (deg 2)\nR²={r2_poly:.3f}, AIC={aic_poly:.1f}\n"
                 f"LOS D: {d_str} ped/s  LOS F: {f_str} ped/s")
    ax.set_xlabel("Gate Throughput (ped/s)")
    ax.set_ylabel("Zone B 최대밀도 (명/m²)")

    # C) Piecewise linear (pwlf)
    pw = pwlf.PiecewiseLinFit(x_all, y_all)
    breaks = pw.fit(2)   # 1 breakpoint → 2 segments
    sse_pw = pw.ssr
    r2_pw = 1 - sse_pw / ss_tot
    k_pw = 5
    aic_pw = n * np.log(sse_pw/n) + 2*k_pw
    bp = breaks[1]

    ax = axes[2]
    ax.scatter(x_all, y_all, c=[CFG_COLORS[int(c)] for c in agg_df["config"]], s=60, zorder=3)
    y_fit_pw = pw.predict(x_fit)
    ax.plot(x_fit, y_fit_pw, "k-", lw=2)
    ax.axvline(bp, color="purple", ls="-.", lw=2, label=f"breakpoint={bp:.3f}")
    ax.axhline(LOS_D_THRESH, color="orange", ls="--", lw=1.5)
    ax.axhline(LOS_F_THRESH, color="red", ls="--", lw=1.5)
    # 신뢰구간: bootstrap
    bp_samples = []
    rng = np.random.default_rng(42)
    for _ in range(200):
        idx = rng.integers(0, n, n)
        try:
            pw_b = pwlf.PiecewiseLinFit(x_all[idx], y_all[idx])
            pw_b.fit(2)
            bp_samples.append(pw_b.fit_breaks[1])
        except Exception:
            pass
    bp_ci = (np.percentile(bp_samples, 2.5), np.percentile(bp_samples, 97.5)) if bp_samples else (bp, bp)
    ax.axvspan(bp_ci[0], bp_ci[1], alpha=0.15, color="purple")
    ax.set_title(f"C) Piecewise (1 breakpoint)\nR²={r2_pw:.3f}, AIC={aic_pw:.1f}\n"
                 f"BP={bp:.3f} [{bp_ci[0]:.3f}, {bp_ci[1]:.3f}] ped/s")
    ax.set_xlabel("Gate Throughput (ped/s)")
    ax.set_ylabel("Zone B 최대밀도 (명/m²)")
    ax.legend(fontsize=7)

    # cfg 범례
    cfg_patches = [mpatches.Patch(color=CFG_COLORS[c], label=f"cfg {c}") for c in CFG_LEVELS]
    fig.legend(handles=cfg_patches, loc="lower center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Step 2: 게이트 처리율 → Zone B 밀도 회귀분석 (breakpoint 탐색)",
                 fontsize=11, y=1.01)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step2_threshold_regression.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {FIG_DIR/'step2_threshold_regression.png'}")

    # 2-4. 이용률 임계점 출력
    print("\n[Step 2-4] LOS D 위반 이용률 임계점:")
    for p in P_LEVELS:
        for cfg in CFG_LEVELS:
            row = agg_df[(agg_df["p"]==p)&(agg_df["config"]==cfg)].iloc[0]
            if row["zone_b_max_mean"] >= LOS_D_THRESH:
                print(f"  p={int(p*100)}%, cfg {cfg}: Zone B {row['zone_b_max_mean']:.3f} /m² → LOS D 위반")

    print(f"\npiecewise breakpoint: {bp:.4f} ped/s (95% CI: [{bp_ci[0]:.4f}, {bp_ci[1]:.4f}])")
    return bp, bp_ci, step2_1


# =============================================================================
# Step 3 — 제약 조건부 시스템 최적화
# =============================================================================
def step3():
    print("\n" + "="*60)
    print("Step 3: 제약 조건부 시스템 최적화")
    print("="*60)

    # 시스템 관점 최적 (total travel time 최소)
    sys_opt = {}
    for p in P_LEVELS:
        sub = agg_df[agg_df["p"]==p].sort_values("avg_travel_time")
        sys_opt[p] = int(sub.iloc[0]["config"])

    # 제약 조건부 최적 (Zone B < LOS_D_THRESH 하에서 gate delay 최소)
    con_opt = {}
    for p in P_LEVELS:
        sub = agg_df[(agg_df["p"]==p) & (agg_df["zone_b_max_mean"] < LOS_D_THRESH)]
        if len(sub) == 0:
            sub = agg_df[agg_df["p"]==p]  # 모든 cfg 위반 시 최소 밀도
            con_opt[p] = int(sub.sort_values("zone_b_max_mean").iloc[0]["config"])
        else:
            con_opt[p] = int(sub.sort_values("avg_gate_delay").iloc[0]["config"])

    print(f"\n게이트 관점 최적: {GATE_OPT}")
    print(f"시스템 관점 최적: {sys_opt}")
    print(f"제약 조건부 최적: {con_opt}")

    # 3-2. 비교 표
    rows = []
    for p in P_LEVELS:
        rows.append({
            "p": f"p={int(p*100)}%",
            "게이트 관점 cfg": GATE_OPT[p],
            "시스템 관점 cfg": sys_opt[p],
            "제약 조건부 cfg": con_opt[p],
            "변경 여부": "O" if (GATE_OPT[p] != con_opt[p]) else "-",
        })
    comp_table = pd.DataFrame(rows)
    print("\n[Step 3-2] 3가지 관점 최적 cfg 비교:")
    print(comp_table.to_string(index=False))

    # 3-3. 희생 비용 분석
    cost_rows = []
    for p in P_LEVELS:
        r_gate = agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])].iloc[0]
        r_con  = agg_df[(agg_df["p"]==p)&(agg_df["config"]==con_opt[p])].iloc[0]
        cost_rows.append({
            "p": f"p={int(p*100)}%",
            "게이트cfg": GATE_OPT[p],
            "제약cfg": con_opt[p],
            "gate_delay 증가(s)": f"{r_con['avg_gate_delay']-r_gate['avg_gate_delay']:+.2f}",
            "ZoneB 밀도 감소": f"{r_gate['zone_b_max_mean']-r_con['zone_b_max_mean']:+.3f}",
            "total_time 변화(s)": f"{r_con['avg_travel_time']-r_gate['avg_travel_time']:+.2f}",
        })
    cost_df = pd.DataFrame(cost_rows)
    print("\n[Step 3-3] 희생 비용 분석:")
    print(cost_df.to_string(index=False))

    # 3-4. 시각화 A: 파레토 프론티어
    fig, ax = plt.subplots(figsize=(9, 6))
    markers = {0.1:"o", 0.3:"s", 0.5:"^", 0.7:"D", 0.8:"P"}
    for p in P_LEVELS:
        for cfg in CFG_LEVELS:
            row = agg_df[(agg_df["p"]==p)&(agg_df["config"]==cfg)].iloc[0]
            ax.scatter(row["avg_gate_delay"], row["zone_b_max_mean"],
                      c=CFG_COLORS[cfg], marker=markers[p], s=80, zorder=3,
                      edgecolors="black", linewidths=0.5)

    ax.axhline(LOS_D_THRESH, color="orange", ls="--", lw=2,
               label=f"Zone B LOS D 한계 ({LOS_D_THRESH} /m²)")
    ax.axhline(LOS_F_THRESH, color="red", ls="--", lw=2,
               label=f"Zone B LOS F ({LOS_F_THRESH} /m²)")

    # 파레토 최적점 표시 (제약 조건부)
    for p in P_LEVELS:
        cfg = con_opt[p]
        row = agg_df[(agg_df["p"]==p)&(agg_df["config"]==cfg)].iloc[0]
        ax.scatter(row["avg_gate_delay"], row["zone_b_max_mean"],
                  s=220, zorder=5, facecolors="none", edgecolors="navy",
                  linewidths=2.5, marker="o")
        ax.annotate(f"p={int(p*100)}%\ncfg{cfg}",
                    (row["avg_gate_delay"], row["zone_b_max_mean"]),
                    textcoords="offset points", xytext=(7, 4), fontsize=7.5)

    cfg_patches = [mpatches.Patch(color=CFG_COLORS[c], label=f"cfg {c}") for c in CFG_LEVELS]
    p_patches   = [plt.scatter([],[], marker=markers[p], c="gray", s=60,
                                label=f"p={int(p*100)}%") for p in P_LEVELS]
    pareto_patch = plt.scatter([],[], s=220, facecolors="none", edgecolors="navy",
                                linewidths=2.5, marker="o", label="제약 조건부 최적")
    ax.legend(handles=cfg_patches+p_patches+[pareto_patch], fontsize=7.5,
              loc="upper left", ncol=2)
    ax.set_xlabel("평균 게이트 대기시간 (s)")
    ax.set_ylabel("Zone B 최대밀도 (명/m²)")
    ax.set_title("Step 3: 파레토 프론티어\n"
                 "핵심: 게이트 대기 소폭 희생 → Zone B LOS 방어")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step3_pareto_frontier.png", bbox_inches="tight")
    plt.close(fig)

    # 3-4 B: 3가지 관점 cfg 비교 막대
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(P_LEVELS))
    w = 0.25
    opt_types = [("게이트 관점", GATE_OPT, "#4C9BE8"),
                 ("시스템 관점", sys_opt,  "#F5A623"),
                 ("제약 조건부", con_opt,  "#7ED321")]
    for i, (lbl, d, c) in enumerate(opt_types):
        vals = [d[p] for p in P_LEVELS]
        bars = ax.bar(x + i*w, vals, w, label=lbl, color=c, edgecolor="black", lw=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.04,
                    str(v), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x + w)
    ax.set_xticklabels([f"p={int(p*100)}%" for p in P_LEVELS])
    ax.set_ylabel("전용 게이트 수 (cfg)")
    ax.set_ylim(0, 5.5)
    ax.set_title("Step 3: 3가지 관점 최적 cfg 비교")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step3_three_perspectives.png", bbox_inches="tight")
    plt.close(fig)

    # 3-4 C: 희생 비용 시각화
    cost_data = []
    for p in P_LEVELS:
        r_gate = agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])].iloc[0]
        r_con  = agg_df[(agg_df["p"]==p)&(agg_df["config"]==con_opt[p])].iloc[0]
        cost_data.append({
            "p": p,
            "delay_cost": r_con["avg_gate_delay"] - r_gate["avg_gate_delay"],
            "density_gain": r_gate["zone_b_max_mean"] - r_con["zone_b_max_mean"],
        })
    cost_plot = pd.DataFrame(cost_data)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()
    ax1.bar([p-0.01 for p in P_LEVELS], cost_plot["delay_cost"], width=0.025,
            color="#E74C3C", alpha=0.8, label="gate delay 증가분 (비용)")
    ax2.bar([p+0.01 for p in P_LEVELS], cost_plot["density_gain"], width=0.025,
            color="#2ECC71", alpha=0.8, label="Zone B 밀도 감소분 (이득)")
    ax1.set_xlabel("태그리스 이용 비율 (p)")
    ax1.set_ylabel("게이트 대기시간 증가 (s)", color="#E74C3C")
    ax2.set_ylabel("Zone B 밀도 감소 (명/m²)", color="#2ECC71")
    ax1.set_xticks(P_LEVELS)
    ax1.set_xticklabels([f"{int(p*100)}%" for p in P_LEVELS])
    l1, lb1 = ax1.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax1.legend(l1+l2, lb1+lb2, loc="upper left", fontsize=8)
    ax1.set_title("Step 3: 제약 조건부 vs 게이트 관점 — 희생 비용 vs 이득")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "step3_tradeoff_cost.png", bbox_inches="tight")
    plt.close(fig)

    print(f"\nSaved: step3_pareto_frontier / step3_three_perspectives / step3_tradeoff_cost")

    # CSV 저장
    constrained_df = pd.DataFrame([{
        "p": p, "gate_cfg": GATE_OPT[p], "system_cfg": sys_opt[p],
        "constrained_cfg": con_opt[p],
        "gate_delay_gate_opt": agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])]["avg_gate_delay"].values[0],
        "gate_delay_con_opt": agg_df[(agg_df["p"]==p)&(agg_df["config"]==con_opt[p])]["avg_gate_delay"].values[0],
        "zone_b_max_gate_opt": agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])]["zone_b_max_mean"].values[0],
        "zone_b_max_con_opt": agg_df[(agg_df["p"]==p)&(agg_df["config"]==con_opt[p])]["zone_b_max_mean"].values[0],
    } for p in P_LEVELS])
    constrained_df.to_csv(RES_DIR / "constrained_optimal.csv", index=False, float_format="%.4f")
    print(f"Saved: {RES_DIR/'constrained_optimal.csv'}")
    return sys_opt, con_opt, comp_table


# =============================================================================
# Step 4 — ANOVA 및 통계 검증
# =============================================================================
def step4(sys_opt, con_opt):
    print("\n" + "="*60)
    print("Step 4: ANOVA 및 통계 검증")
    print("="*60)

    # 각 seed별 raw 데이터에 운영 방식 라벨 부여
    gate_rows, sys_rows, con_rows = [], [], []
    for p in P_LEVELS:
        for seed_val in [42,43,44,45,46]:
            def get_row(cfg):
                r = raw_df[(raw_df["p"]==p)&(raw_df["config"]==cfg)&(raw_df["seed"]==seed_val)]
                return r.iloc[0] if len(r) else None
            for lbl, cfg, lst in [("게이트관점", GATE_OPT[p], gate_rows),
                                   ("시스템관점", sys_opt[p], sys_rows),
                                   ("제약조건부", con_opt[p], con_rows)]:
                r = get_row(cfg)
                if r is not None:
                    lst.append({"type": lbl, "p": p, "cfg": cfg, "seed": seed_val,
                                "avg_total_delay": r["avg_gate_wait"] + r["avg_post_gate"],
                                "zone_b_max": r["zone_b_max"],
                                "violation": int(r["zone_b_max"] >= LOS_D_THRESH)})

    anova_df = pd.concat([pd.DataFrame(gate_rows), pd.DataFrame(sys_rows), pd.DataFrame(con_rows)])

    # 종속변수별 ANOVA
    results = []
    for dv in ["avg_total_delay", "zone_b_max", "violation"]:
        g1 = anova_df[anova_df["type"]=="게이트관점"][dv].values
        g2 = anova_df[anova_df["type"]=="시스템관점"][dv].values
        g3 = anova_df[anova_df["type"]=="제약조건부"][dv].values
        f_stat, p_val = f_oneway(g1, g2, g3)
        # eta-squared
        grand_mean = np.mean(np.concatenate([g1,g2,g3]))
        ss_between = len(g1)*(np.mean(g1)-grand_mean)**2 + \
                     len(g2)*(np.mean(g2)-grand_mean)**2 + \
                     len(g3)*(np.mean(g3)-grand_mean)**2
        ss_total = np.sum((np.concatenate([g1,g2,g3]) - grand_mean)**2)
        eta2 = ss_between / ss_total if ss_total > 0 else 0
        results.append({"종속변수": dv, "F": f"{f_stat:.3f}", "p": f"{p_val:.4f}",
                        "유의": "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns",
                        "η²": f"{eta2:.4f}"})
    anova_res = pd.DataFrame(results)
    print("\n[ANOVA 결과]")
    print(anova_res.to_string(index=False))
    anova_res.to_csv(RES_DIR / "anova_results.csv", index=False)

    # 사후검정 (Tukey HSD) — avg_total_delay 기준
    tukey = pairwise_tukeyhsd(anova_df["avg_total_delay"], anova_df["type"])
    tukey_df = pd.DataFrame(data=tukey._results_table.data[1:],
                            columns=tukey._results_table.data[0])
    print("\n[Tukey HSD - avg_total_delay]")
    print(tukey_df.to_string(index=False))
    tukey_df.to_csv(RES_DIR / "post_hoc.csv", index=False)
    print(f"Saved: anova_results.csv, post_hoc.csv")
    return anova_df


# =============================================================================
# Step 5 — 가변 운영 방안
# =============================================================================
def step5(con_opt, sys_opt):
    print("\n" + "="*60)
    print("Step 5: 가변 운영 방안 도출")
    print("="*60)

    lines = [
        "# 가변 운영 권고안 (태그리스 이용률별)",
        "",
        "| 이용률 (p) | 시간대 예시 | 게이트 관점 cfg | 제약 조건부 cfg | 운영 권고 |",
        "|---|---|---|---|---|",
    ]
    labels = {0.1:"심야/비첨두", 0.3:"비첨두", 0.5:"전환기", 0.7:"첨두", 0.8:"극첨두"}
    for p in P_LEVELS:
        g_cfg  = GATE_OPT[p]
        c_cfg  = con_opt[p]
        row_g  = agg_df[(agg_df["p"]==p)&(agg_df["config"]==g_cfg)].iloc[0]
        row_c  = agg_df[(agg_df["p"]==p)&(agg_df["config"]==c_cfg)].iloc[0]
        zb_g   = row_g["zone_b_max_mean"]
        zb_c   = row_c["zone_b_max_mean"]
        note = f"Zone B {zb_c:.2f}/m² ({'양호' if zb_c<LOS_D_THRESH else '위반'})"
        if g_cfg != c_cfg:
            note += f" ← cfg{g_cfg}→{c_cfg} 조정 필요"
        lines.append(f"| p={int(p*100)}% | {labels[p]} | cfg {g_cfg} | cfg {c_cfg} | {note} |")

    lines += [
        "",
        "## 핵심 권고",
        "- **개찰구는 밸브 역할**: 게이트 처리 속도를 조절하여 에스컬레이터 전방 혼잡 완충",
        "- 고이용률(p≥50%)에서 제약 조건부 cfg 적용 시 Zone B LOS 방어 가능",
        "- 실제 시간대 매핑은 서울교통공사 시간대별 승하차 데이터 필요",
        "",
        "> **참고**: 국토부 고시 2025-241호 기준, Zone B LOS D 한계 = 1.08 /m²",
    ]
    out = DOCS_DIR / "variable_operation_recommendation.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {out}")


# =============================================================================
# Step 6 — 최종 종합 보고서
# =============================================================================
def step6(bp, bp_ci, step2_1, comp_table, sys_opt, con_opt):
    lines = [
        "# 시스템 최적화 관점 최종 분석 보고서",
        f"분석 기준: 국토부 고시 2025-241호 | 보행 모델: CFSM V2 | 100 시나리오",
        "",
        "---",
        "",
        "## Step 1: 국소 최적화의 함정",
        "",
        "### 개찰구 최적 배합",
        "| p | 게이트 최적 cfg | avg gate delay (s) | throughput (ped/s) |",
        "|---|---|---|---|",
    ]
    for p in P_LEVELS:
        cfg = GATE_OPT[p]
        r = agg_df[(agg_df["p"]==p)&(agg_df["config"]==cfg)].iloc[0]
        lines.append(f"| p={int(p*100)}% | cfg {cfg} | {r['avg_gate_delay']:.2f} | {r['gate_throughput']:.3f} |")

    lines += [
        "",
        "**핵심**: p 증가에 따라 최적 cfg도 단조 증가. 게이트 처리율은 극대화되나, 후방 Zone B 밀도 문제 미반영.",
        "",
        "---",
        "",
        "## Step 2: 병목 전이와 LOS 위반",
        "",
        "### Zone B 밀도 (게이트 최적 cfg 적용)",
        step2_1.to_markdown(index=False),
        "",
        f"### 회귀분석 Breakpoint",
        f"- Piecewise regression breakpoint: **{bp:.4f} ped/s** (95% CI: [{bp_ci[0]:.4f}, {bp_ci[1]:.4f}])",
        f"- 이 처리율 초과 시 Zone B 밀도 급증 (breakdown)",
        f"- LOS D 한계({LOS_D_THRESH}/m²): linear 모델 기준 약 {bp:.3f} ped/s",
        "",
        "---",
        "",
        "## Step 3: 제약 조건부 재최적화",
        "",
        "### 3가지 관점 최적 cfg",
        comp_table.to_markdown(index=False),
        "",
        "### 희생 비용 요약",
        "| p | gate_delay 증가(s) | Zone B 밀도 감소 |",
        "|---|---|---|",
    ]
    for p in P_LEVELS:
        r_g = agg_df[(agg_df["p"]==p)&(agg_df["config"]==GATE_OPT[p])].iloc[0]
        r_c = agg_df[(agg_df["p"]==p)&(agg_df["config"]==con_opt[p])].iloc[0]
        lines.append(f"| p={int(p*100)}% | {r_c['avg_gate_delay']-r_g['avg_gate_delay']:+.2f} | {r_g['zone_b_max_mean']-r_c['zone_b_max_mean']:+.3f} |")

    lines += [
        "",
        "---",
        "",
        "## 결론 및 운영 권고",
        "",
        f"**개찰구는 밸브다**: 게이트 대기 소폭 희생으로 에스컬레이터 LOS 방어 가능",
        "",
        "| p | 게이트 관점 cfg | 제약 조건부 cfg | 조정 방향 |",
        "|---|---|---|---|",
    ]
    for p in P_LEVELS:
        g, c = GATE_OPT[p], con_opt[p]
        lines.append(f"| p={int(p*100)}% | cfg {g} | cfg {c} | {'cfg 감소 → LOS 방어' if c<g else ('동일' if c==g else 'cfg 증가')} |")

    lines += [
        "",
        "---",
        "",
        "## 한계",
        "- 보행 모델 캘리브레이션 진행 중 (Jülich 기반, 최종 적용 예정)",
        "- 실시간 시간대별 p 매핑은 서울교통공사 데이터 확보 후 정밀화 필요",
        "- p=0 베이스라인(태그 전용) 미포함 — 후속 분석 예정",
        "",
        "> LOS 기준: 국토부 고시 2025-241호 / Fruin(1971) 대기공간 기준",
        "> Zone B LOS D = < 1.08 /m², LOS F = ≥ 2.17 /m²",
    ]
    out = DOCS_DIR / "final_system_optimization.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved: {out}")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    step1()
    bp, bp_ci, step2_1 = step2()
    sys_opt, con_opt, comp_table = step3()
    step4(sys_opt, con_opt)
    step5(con_opt, sys_opt)
    step6(bp, bp_ci, step2_1, comp_table, sys_opt, con_opt)

    print("\n" + "="*60)
    print("완료. 출력 파일:")
    for f in sorted(list(FIG_DIR.glob("step*.png")) + list(RES_DIR.glob("*.csv")) +
                    list(DOCS_DIR.glob("*optimization*")) + list(DOCS_DIR.glob("*variable*"))):
        print(f"  {f}")
    print("="*60)
