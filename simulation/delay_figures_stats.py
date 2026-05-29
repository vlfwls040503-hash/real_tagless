"""Make figures + stats for CFSM delay analysis.

Inputs:
  - results_cfsm_latest/delay_analysis.csv
  - results_cfsm_latest/agent_level_delay.csv

Outputs:
  - figures/delay_breakdown.png
  - figures/optimal_cfg_delay_based.png
  - results_cfsm_latest/delay_stats.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from scipy import stats

for fname in ["Malgun Gothic", "NanumGothic", "AppleGothic"]:
    if any(fname in f.name for f in matplotlib.font_manager.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = fname
        break
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
RDIR = ROOT / "results_cfsm_latest"
FIG_DIR = ROOT / "figures"

P_LEVELS = [0.1, 0.3, 0.5, 0.7, 0.8]
CFG_LEVELS = [1, 2, 3, 4]

COLORS = {1: "#1f77b4", 2: "#2ca02c", 3: "#ff7f0e", 4: "#d62728"}


def main():
    df = pd.read_csv(RDIR / "delay_analysis.csv")

    # Aggregate mean per (p, cfg)
    agg = df.groupby(["p", "config"]).agg(
        gate_delay=("avg_gate_delay", "mean"),
        post_gate_delay=("avg_post_gate_delay", "mean"),
        total_delay=("avg_total_delay", "mean"),
        gate_delay_sd=("avg_gate_delay", "std"),
        total_delay_sd=("avg_total_delay", "std"),
        post_share=("post_gate_delay_share", "mean"),
        n_analyzed=("n_analyzed", "mean"),
        n_serviced=("n_serviced", "mean"),
    ).reset_index()

    # ─────────────── Figure 1: delay_breakdown ───────────────
    fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
    n_p = len(P_LEVELS)
    width = 0.2
    x_base = np.arange(n_p)

    for i, cfg in enumerate(CFG_LEVELS):
        offset = (i - 1.5) * width
        sub = agg[agg["config"] == cfg].sort_values("p").reset_index(drop=True)
        gate_vals = sub["gate_delay"].values
        post_vals = sub["post_gate_delay"].values
        positions = x_base + offset
        # stacked
        ax.bar(positions, gate_vals, width, color=COLORS[cfg], alpha=0.85,
               label=f"cfg {cfg} — gate")
        ax.bar(positions, post_vals, width, bottom=gate_vals,
               color=COLORS[cfg], alpha=0.4, hatch="//",
               label=f"cfg {cfg} — post-gate")

    ax.set_xticks(x_base)
    ax.set_xticklabels([f"p={p}" for p in P_LEVELS])
    ax.set_ylabel("Avg delay per agent (s)")
    ax.set_title("Delay breakdown: gate (solid) + post-gate (hatched) by config")
    ax.legend(ncol=4, fontsize=7, loc="upper left")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "delay_breakdown.png", dpi=100)
    plt.close()
    print(f"Wrote {FIG_DIR / 'delay_breakdown.png'}")

    # ─────────────── Figure 2: optimal_cfg_delay_based ───────────────
    # For each p, find cfg that minimizes gate_delay vs total_delay
    rows = []
    for p in P_LEVELS:
        sub = agg[agg["p"] == p]
        gate_opt = sub.loc[sub["gate_delay"].idxmin()]
        sys_opt = sub.loc[sub["total_delay"].idxmin()]
        rows.append({
            "p": p,
            "gate_opt_cfg": int(gate_opt["config"]),
            "gate_opt_gate_delay": gate_opt["gate_delay"],
            "gate_opt_total_delay": gate_opt["total_delay"],
            "sys_opt_cfg": int(sys_opt["config"]),
            "sys_opt_gate_delay": sys_opt["gate_delay"],
            "sys_opt_total_delay": sys_opt["total_delay"],
        })
    opt = pd.DataFrame(rows)
    print("\nOptimal cfg comparison:")
    print(opt.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=100)
    # Left: gate-opt vs sys-opt config chosen
    ax = axes[0]
    ax.plot(opt["p"], opt["gate_opt_cfg"], "o-", lw=2, markersize=10,
            color="tab:blue", label="게이트 관점 최적 cfg")
    ax.plot(opt["p"], opt["sys_opt_cfg"], "s--", lw=2, markersize=10,
            color="tab:red", label="시스템 관점 최적 cfg")
    for _, r in opt.iterrows():
        if r["gate_opt_cfg"] != r["sys_opt_cfg"]:
            ax.axvspan(r["p"] - 0.04, r["p"] + 0.04, alpha=0.15, color="red")
    ax.set_xlabel("p (태그리스 이용률)")
    ax.set_ylabel("optimal config")
    ax.set_yticks([1, 2, 3, 4])
    ax.set_title("관점별 최적 cfg (빨간 영역: 불일치)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Right: delay at each optimal
    ax = axes[1]
    x = np.arange(len(P_LEVELS))
    w = 0.35
    ax.bar(x - w/2, opt["gate_opt_total_delay"], w, color="tab:blue",
           alpha=0.7, label="gate-opt cfg의 총 delay")
    ax.bar(x + w/2, opt["sys_opt_total_delay"], w, color="tab:red",
           alpha=0.7, label="sys-opt cfg의 총 delay")
    ax.set_xticks(x)
    ax.set_xticklabels([f"p={p}" for p in P_LEVELS])
    ax.set_ylabel("Avg total delay per agent (s)")
    ax.set_title("관점별 최적 cfg의 총 delay 비교")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    for i, (g, s) in enumerate(zip(opt["gate_opt_total_delay"], opt["sys_opt_total_delay"])):
        ax.text(i - w/2, g + 0.5, f"{g:.1f}", ha="center", fontsize=8)
        ax.text(i + w/2, s + 0.5, f"{s:.1f}", ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "optimal_cfg_delay_based.png", dpi=100)
    plt.close()
    print(f"Wrote {FIG_DIR / 'optimal_cfg_delay_based.png'}")

    # ─────────────── Paired t-test for mismatched p ───────────────
    stats_out = {"opt_comparison": opt.to_dict("records"), "paired_tests": []}
    for _, r in opt.iterrows():
        p = r["p"]
        g_cfg = r["gate_opt_cfg"]
        s_cfg = r["sys_opt_cfg"]
        if g_cfg == s_cfg:
            continue
        # Paired: match seeds
        g_rows = df[(df["p"] == p) & (df["config"] == g_cfg)].sort_values("seed")
        s_rows = df[(df["p"] == p) & (df["config"] == s_cfg)].sort_values("seed")
        merged = g_rows.merge(s_rows, on="seed", suffixes=("_gateopt", "_sysopt"))
        delta = merged["avg_total_delay_gateopt"] - merged["avg_total_delay_sysopt"]
        t, pval = stats.ttest_rel(
            merged["avg_total_delay_gateopt"],
            merged["avg_total_delay_sysopt"]
        )
        d = delta.mean() / (delta.std(ddof=1) if delta.std(ddof=1) > 0 else 1)
        ci = stats.t.interval(0.95, df=len(delta) - 1,
                              loc=delta.mean(),
                              scale=delta.std(ddof=1) / np.sqrt(len(delta)))
        print(f"\n[p={p}] Paired t-test: cfg {g_cfg} (gate-opt) total_delay vs cfg {s_cfg} (sys-opt)")
        print(f"  n={len(delta)}, t={t:.3f}, p-value={pval:.4f}, Cohen's d={d:.3f}")
        print(f"  mean diff = {delta.mean():+.3f}s, 95% CI = [{ci[0]:+.3f}, {ci[1]:+.3f}]")
        print(f"  interpretation: gate-opt cfg {g_cfg}에서 시스템 delay가 "
              f"{delta.mean():+.1f}s 만큼 {'더 큼' if delta.mean()>0 else '더 작음'}")
        stats_out["paired_tests"].append({
            "p": float(p), "gate_opt_cfg": int(g_cfg), "sys_opt_cfg": int(s_cfg),
            "n": int(len(delta)), "t": float(t), "p_value": float(pval),
            "cohen_d": float(d), "mean_diff_s": float(delta.mean()),
            "ci_95": [float(ci[0]), float(ci[1])],
        })

    # ─────────────── Bottleneck transfer metric ───────────────
    print("\n=== 병목 전이 (post_gate_delay_share by p, cfg) ===")
    share_tbl = agg.pivot(index="p", columns="config", values="post_share")
    print(share_tbl.round(3))
    stats_out["post_gate_share_table"] = share_tbl.round(4).to_dict()

    # Save stats
    with open(RDIR / "delay_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats_out, f, indent=2, default=str, ensure_ascii=False)
    print(f"\nWrote {RDIR / 'delay_stats.json'}")

    # Print full summary table
    print("\n=== Full scenario summary (mean over 5 seeds) ===")
    print(agg.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
