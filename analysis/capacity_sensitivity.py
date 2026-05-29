"""Capacity sensitivity 분석 — SVC 5단계 (0.5, 0.85, 1.5, 2.0, 3.0)."""
import os, sys
os.environ["PYTHONIOENCODING"] = "utf-8"
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(r"C:\Users\aaron\tagless")
SCAN = ROOT / "results_v6_cap"
BASELINE = ROOT / "results_v5_avm"
FIG = SCAN / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# SVC 레벨 매핑
LEVELS = [
    (0.5, SCAN / "cap_0p5" / "summary.csv", "SVC=0.5 (1.25 ped/s 이론)"),
    (0.85, BASELINE / "summary.csv", "SVC=0.85 (baseline)"),
    (1.5, SCAN / "cap_1p5" / "summary.csv", "SVC=1.5"),
    (2.0, SCAN / "cap_2p0" / "summary.csv", "SVC=2.0"),
    (3.0, SCAN / "cap_3p0" / "summary.csv", "SVC=3.0 (극단)"),
]


def load_all():
    dfs = []
    for svc, path, label in LEVELS:
        if not path.exists():
            print(f"SKIP (missing): {path}")
            continue
        df = pd.read_csv(path)
        df["svc"] = svc
        df["label"] = label
        df["pass_rate"] = df.passed / df.spawned * 100
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def best_per_svc_p(df, metric, maximize=False):
    """각 (svc, p)에서 최적 cfg."""
    out = {}
    for (svc, p), sub in df.groupby(["svc", "p"]):
        agg = sub.groupby("config")[metric].mean()
        out[(svc, p)] = int(agg.idxmax() if maximize else agg.idxmin())
    return out


def plot_optimal_drift(df):
    """SVC 변화에 따른 p별 최적 cfg 변화."""
    best = best_per_svc_p(df, "avg_travel_time")
    svcs = sorted(df.svc.unique())
    ps = sorted(df.p.unique())
    mat = np.zeros((len(ps), len(svcs)))
    for i, p in enumerate(ps):
        for j, svc in enumerate(svcs):
            mat[i, j] = best.get((svc, p), np.nan)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(mat, cmap="RdYlGn_r", aspect="auto", vmin=1, vmax=4)
    ax.set_xticks(range(len(svcs)))
    ax.set_xticklabels([f"SVC={s:.2f}\n({1/s*2:.2f} ped/s)" for s in svcs])
    ax.set_yticks(range(len(ps)))
    ax.set_yticklabels([f"p={p}" for p in ps])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isnan(v): continue
            ax.text(j, i, f"cfg {int(v)}", ha="center", va="center",
                    fontsize=11, fontweight="bold")
    plt.colorbar(im, ax=ax, label="최적 cfg (travel_time 기준)")
    ax.set_title("에스컬 용량 변화 × 태그리스 이용률 → 최적 cfg 이동",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("에스컬 service time (초) / 이론 처리율 (상한, 2개 합산)", fontsize=11)
    ax.set_ylabel("태그리스 이용률 p", fontsize=11)
    plt.tight_layout()
    fig.savefig(FIG / "optimal_cfg_drift.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("Saved optimal_cfg_drift.png")


def plot_cfg_compare_by_svc(df):
    """각 SVC별 p=0.7에서 cfg별 avg_travel_time 비교."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, p_fix, title in [(axes[0], 0.5, "p=0.5"),
                              (axes[1], 0.7, "p=0.7")]:
        for svc in sorted(df.svc.unique()):
            sub = df[(df.svc == svc) & (df.p == p_fix)]
            agg = sub.groupby("config").avg_travel_time.agg(["mean", "std"])
            if len(agg) == 0: continue
            ax.errorbar(agg.index, agg["mean"], yerr=agg["std"]/np.sqrt(5),
                        marker="o", lw=2, capsize=3, label=f"SVC={svc}")
        ax.set_xlabel("cfg (전용 게이트 수)")
        ax.set_ylabel("평균 travel_time (s)")
        ax.set_title(f"{title} — SVC별 cfg vs travel_time")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, linestyle=":")
        ax.set_xticks([1, 2, 3, 4])
    plt.tight_layout()
    fig.savefig(FIG / "cfg_travel_time_by_svc.png", dpi=110)
    plt.close(fig)
    print("Saved cfg_travel_time_by_svc.png")


def plot_pass_rate_heatmap(df):
    """각 SVC의 pass_rate heatmap (p × cfg)."""
    svcs = sorted(df.svc.unique())
    fig, axes = plt.subplots(1, len(svcs), figsize=(4*len(svcs), 5),
                              sharey=True)
    if len(svcs) == 1: axes = [axes]
    for ax, svc in zip(axes, svcs):
        sub = df[df.svc == svc]
        pivot = sub.groupby(["p", "config"]).pass_rate.mean().unstack()
        im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                       vmin=50, vmax=100)
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"cfg {c}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"p={p}" for p in pivot.index])
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                v = pivot.values[i, j]
                ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                        color="white" if v < 75 else "black", fontsize=9)
        ax.set_title(f"SVC={svc}")
    fig.suptitle("통과율 (%) heatmap — SVC별",
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(FIG / "pass_rate_by_svc.png", dpi=110)
    plt.close(fig)
    print("Saved pass_rate_by_svc.png")


def find_threshold(df):
    """cfg 4가 cfg 3보다 travel_time이 나빠지는 임계 SVC 찾기."""
    rows = []
    for p in sorted(df.p.unique()):
        for svc in sorted(df.svc.unique()):
            sub = df[(df.svc == svc) & (df.p == p)]
            tt3 = sub[sub.config == 3].avg_travel_time.mean()
            tt4 = sub[sub.config == 4].avg_travel_time.mean()
            pr3 = sub[sub.config == 3].pass_rate.mean()
            pr4 = sub[sub.config == 4].pass_rate.mean()
            rows.append({"p": p, "svc": svc,
                         "tt_cfg3": tt3, "tt_cfg4": tt4,
                         "tt_diff_4minus3": tt4 - tt3,
                         "pr_cfg3": pr3, "pr_cfg4": pr4,
                         "pr_diff_4minus3": pr4 - pr3,
                         "cfg4_better_tt": tt4 < tt3,
                         "cfg4_better_pr": pr4 > pr3})
    return pd.DataFrame(rows)


def write_report(df, thresh_df):
    L = []
    L.append("# Capacity Sensitivity 분석 보고서")
    L.append("")
    L.append("**생성일**: 2026-04-20")
    L.append("**모델**: AVM")
    L.append("**스캔**: ESCALATOR_SERVICE_TIME = [0.5, 0.85, 1.5, 2.0, 3.0] 초")
    L.append("")

    L.append("## 1. 실험 조건")
    L.append("")
    L.append("| SVC | 이론 처리율 (한 쪽, ped/s) | 양쪽 합산 | 유입(1.33)과 비교 |")
    L.append("|---|---|---|---|")
    for svc, _, _ in LEVELS:
        single = 1 / svc
        total = single * 2
        sat = "포화 이하" if total > 1.33 else "포화 경계" if abs(total - 1.33) < 0.3 else "포화"
        L.append(f"| {svc} | {single:.2f} | {total:.2f} | {sat} |")
    L.append("")

    L.append("## 2. SVC별 실효 처리율 (실측)")
    L.append("")
    actual = df.groupby("svc").agg(
        actual_tput=("passed", lambda x: x.mean() / 300)).round(2)
    L.append("```")
    L.append(str(actual))
    L.append("```")
    L.append("")

    L.append("## 3. SVC별 최적 cfg (travel_time 기준)")
    L.append("")
    best = best_per_svc_p(df, "avg_travel_time")
    svcs = sorted(df.svc.unique())
    ps = sorted(df.p.unique())
    L.append("| p |" + " | ".join(f"SVC={s}" for s in svcs) + " |")
    L.append("|---|" + "---|"*len(svcs))
    for p in ps:
        row = [f"p={p}"] + [f"cfg {best.get((s, p), '-')}" for s in svcs]
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("![최적 cfg 이동](figures/optimal_cfg_drift.png)")
    L.append("")

    L.append("## 4. 임계점 분석 — cfg 3 vs cfg 4")
    L.append("")
    L.append("같은 (SVC, p)에서 cfg 4가 cfg 3보다 travel_time이 긴지 비교:")
    L.append("")
    L.append("| p | SVC | tt_cfg3 | tt_cfg4 | Δ (cfg4-cfg3) | cfg4가 나쁨? |")
    L.append("|---|---|---|---|---|---|")
    for _, r in thresh_df.iterrows():
        sign = "O (역전)" if r["tt_diff_4minus3"] > 0 else ""
        L.append(f"| {r['p']} | {r['svc']} | {r['tt_cfg3']:.1f} | {r['tt_cfg4']:.1f} | "
                 f"{r['tt_diff_4minus3']:+.2f} | {sign} |")
    L.append("")

    L.append("## 5. 통과율 변화")
    L.append("")
    L.append("![통과율 heatmap](figures/pass_rate_by_svc.png)")
    L.append("")

    L.append("## 6. 해석")
    L.append("")
    # 어느 SVC에서 최적 cfg 변화?
    baseline_best = {p: best.get((0.85, p)) for p in ps}
    changes = []
    for p in ps:
        for svc in svcs:
            if svc == 0.85: continue
            c = best.get((svc, p))
            if c and c != baseline_best[p]:
                changes.append((p, svc, baseline_best[p], c))
    if changes:
        L.append("### 최적 cfg가 baseline과 달라지는 구간:")
        for p, svc, bc, nc in changes:
            L.append(f"- p={p}, SVC={svc}: baseline cfg {bc} → cfg {nc}")
    else:
        L.append("- 모든 SVC 수준에서 최적 cfg가 baseline과 동일.")
        L.append("- 즉 에스컬 용량 변화가 최적 배합 선택을 바꾸지 않음.")
    L.append("")

    # 임계 SVC 추정
    L.append("### 임계 SVC 추정")
    cfg4_worse_cases = thresh_df[thresh_df.tt_diff_4minus3 > 0]
    if len(cfg4_worse_cases) > 0:
        first_svc = cfg4_worse_cases.svc.min()
        L.append(f"- cfg 4가 cfg 3보다 나빠지는 최소 SVC: **{first_svc}s**")
        L.append(f"- 해당 이론 처리율 (양쪽): {2/first_svc:.2f} ped/s")
        L.append(f"- 실측 처리율: 약 {df[df.svc == first_svc].passed.mean()/300:.2f} ped/s")
    else:
        L.append("- 현재 SVC 범위 (0.5~3.0)에서는 cfg 4가 여전히 cfg 3 이상.")
        L.append("- 즉 **에스컬 용량을 3배 늘려도 최적 배합 선택 불변**.")
    L.append("")

    L.append("## 7. 결론")
    L.append("")
    if len(cfg4_worse_cases) > 0:
        L.append(f"- **임계 SVC = {cfg4_worse_cases.svc.min()}초** 에서 병목 전이가 최적 배합 선택을 뒤집음.")
        L.append("- 이 이상의 용량 저하 시 cfg 3 (중간 배합)이 안전.")
        L.append("- 우이신설선 실측 SVC가 이 값을 넘으면 현재 정책 (cfg 단조 증가) 재검토 필요.")
    else:
        L.append("- 현재 스캔 범위에서 최적 배합 불변 → **병목 전이가 실재하나 정책 결정엔 영향 안 줌**.")
        L.append("- 단 SVC=3.0의 극단 조건에서도 cfg 4 유지되는 건 의외 — SIM_TIME 300s 한계로 포화 못 본 가능성.")
    L.append("")

    out = SCAN / "report_capacity.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"Saved: {out}")


def main():
    df = load_all()
    print(f"Loaded: {len(df)} rows, {df.svc.nunique()} SVC levels")
    plot_optimal_drift(df)
    plot_cfg_compare_by_svc(df)
    plot_pass_rate_heatmap(df)
    thresh = find_threshold(df)
    thresh.to_csv(SCAN / "threshold_table.csv", index=False, encoding="utf-8-sig")
    write_report(df, thresh)


if __name__ == "__main__":
    main()
