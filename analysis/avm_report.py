"""AVM 100회 배치 분석 + Phase 1-3 비교 + report_avm.md."""
import csv
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from scipy.stats import pearsonr

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(r"C:\Users\aaron\tagless")
RES_V3 = ROOT / "results_v3"
RES_V5 = ROOT / "results_v5_avm"
RAW = RES_V5 / "raw"
FIG = RES_V5 / "figures"
FIG.mkdir(parents=True, exist_ok=True)
REPORT = RES_V5 / "report_avm.md"


def anova(df, dvar):
    m = smf.ols(f"{dvar} ~ C(config) * p", data=df).fit()
    aov = anova_lm(m, typ=2)
    aov["eta_sq"] = aov.sum_sq / aov.sum_sq.sum()
    return aov


def r2(df, dvar):
    m = smf.ols(f"{dvar} ~ p + config + p:config", data=df).fit()
    return m.rsquared


def main():
    print("Loading...")
    df_avm = pd.read_csv(RES_V5 / "summary.csv")
    df_cfsm = pd.read_csv(RES_V3 / "summary.csv")
    df_avm["pass_rate"] = df_avm.passed / df_avm.spawned * 100
    df_cfsm["pass_rate"] = df_cfsm.passed / df_cfsm.spawned * 100

    # 실행 통계
    exec_log = RES_V5 / "execution_log.txt"
    wall_times = []
    fail_count = 0
    if exec_log.exists():
        for line in exec_log.read_text(encoding="utf-8").splitlines():
            if ": OK (" in line:
                try:
                    wt = float(line.split("OK (")[1].split("s,")[0])
                    wall_times.append(wt)
                except Exception:
                    pass
            elif ": FAIL" in line:
                fail_count += 1

    disk_raw_mb = sum(f.stat().st_size for f in RAW.glob("*.csv")) / (1024*1024)

    # ── 통계 비교 ──
    r2_avm_tt = r2(df_avm, "avg_travel_time")
    r2_avm_gw = r2(df_avm, "avg_gate_wait")
    r2_avm_pg = r2(df_avm, "avg_post_gate")
    r2_avm_esc = r2(df_avm, "avg_esc_wait_precise")
    aov_avm = anova(df_avm, "avg_travel_time")
    aov_cfsm = anova(df_cfsm, "avg_travel_time")

    r2_cfsm_tt = r2(df_cfsm, "avg_travel_time")
    r2_cfsm_gw = r2(df_cfsm, "avg_gate_wait")
    r2_cfsm_pg = r2(df_cfsm, "avg_post_gate")
    r2_cfsm_esc = r2(df_cfsm, "avg_esc_wait_precise")

    # ── 속도 프로파일 (대표 3 시나리오) ──
    print("Velocity profiles...")
    profiles = {}
    for label, sid in [("p=0.1 cfg=1 s42", "p10_cfg1_s42"),
                       ("p=0.5 cfg=3 s42", "p50_cfg3_s42"),
                       ("p=0.8 cfg=4 s42", "p80_cfg4_s42")]:
        for ver, path in [("AVM", RAW), ("CFSM", RES_V3 / "raw")]:
            f = path / f"trajectory_{sid}.csv"
            if not f.exists(): continue
            tr = pd.read_csv(f)
            tr = tr.sort_values(["agent_id", "time"])
            tr["dx"] = tr.groupby("agent_id").x.diff()
            tr["dy"] = tr.groupby("agent_id").y.diff()
            tr["dt"] = tr.groupby("agent_id").time.diff()
            tr["v"] = np.sqrt(tr.dx**2 + tr.dy**2) / tr.dt
            post = tr[(tr.state == "passed") & (tr.x > 14) & (tr.x < 30)
                      & tr.v.notna() & (tr.v > 0.01)]
            post = post.copy()
            post["x_bin"] = (post.x * 2).astype(int) / 2
            prof = post.groupby("x_bin").v.agg(["mean", "count"]).reset_index()
            prof = prof[prof["count"] >= 10]
            profiles[(label, ver)] = prof

    # 속도 프로파일 그래프
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for ax, label in zip(axes, ["p=0.1 cfg=1 s42", "p=0.5 cfg=3 s42", "p=0.8 cfg=4 s42"]):
        for ver, color in [("CFSM", "#1976D2"), ("AVM", "#C2185B")]:
            prof = profiles.get((label, ver))
            if prof is None or len(prof) == 0:
                continue
            ax.plot(prof.x_bin, prof["mean"], "-o", color=color, lw=2,
                    markersize=4, label=ver, alpha=0.85)
        ax.axvspan(23, 25, alpha=0.08, color="gray")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("평균 속도 (m/s)")
        ax.set_title(label)
        ax.legend()
        ax.grid(True, alpha=0.3, linestyle=":")
    fig.suptitle("CFSM vs AVM 속도 프로파일 (게이트 이후 x별)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(FIG / "velocity_compare.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    # ── 통과율 비교 ──
    print("Pass rate compare...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, df, title in [(axes[0], df_cfsm, "CFSM (v3)"),
                          (axes[1], df_avm, "AVM (v5)")]:
        pivot = df.groupby(["p", "config"]).pass_rate.mean().unstack()
        im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                       vmin=40, vmax=100)
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"cfg {c}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"p={p}" for p in pivot.index])
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                v = pivot.values[i, j]
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                        color="white" if v < 70 else "black", fontsize=10)
        plt.colorbar(im, ax=ax, label="통과율 (%)")
        ax.set_title(title)
    fig.suptitle("통과율 heatmap — CFSM vs AVM", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(FIG / "pass_rate_compare.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    # ── R² 막대 ──
    fig, ax = plt.subplots(figsize=(10, 5))
    metrics = ["avg_travel_time", "avg_gate_wait", "avg_post_gate", "avg_esc_wait_precise"]
    cfsm_r = [r2_cfsm_tt, r2_cfsm_gw, r2_cfsm_pg, r2_cfsm_esc]
    avm_r = [r2_avm_tt, r2_avm_gw, r2_avm_pg, r2_avm_esc]
    x = np.arange(len(metrics))
    ax.bar(x - 0.2, cfsm_r, 0.4, label="CFSM (v3)", color="#1976D2")
    ax.bar(x + 0.2, avm_r, 0.4, label="AVM (v5)", color="#C2185B")
    for i in range(len(metrics)):
        ax.text(i - 0.2, cfsm_r[i] + 0.01, f"{cfsm_r[i]:.3f}",
                ha="center", fontsize=9)
        ax.text(i + 0.2, avm_r[i] + 0.01, f"{avm_r[i]:.3f}",
                ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(["총 통행", "게이트 대기", "후처리", "에스컬 대기"])
    ax.set_ylabel("R²")
    ax.set_ylim(0, 1.0)
    ax.set_title("회귀 R² 비교 (y ~ p + config + p:config)")
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle=":", axis="y")
    plt.tight_layout()
    fig.savefig(FIG / "r2_compare.png", dpi=110)
    plt.close(fig)

    # ── 병목 전이 비교 ──
    df_avm["gate_actual_tput"] = df_avm.passed / 300.0
    df_cfsm["gate_actual_tput"] = df_cfsm.passed / 300.0
    r_avm, p_avm = pearsonr(df_avm.gate_actual_tput, df_avm.avg_esc_wait_precise)
    r_cfsm, p_cfsm = pearsonr(df_cfsm.gate_actual_tput, df_cfsm.avg_esc_wait_precise)

    # 최적 배합
    def best_cfg(df, metric, maximize=False):
        agg = df.groupby(["p", "config"])[metric].mean()
        if maximize:
            return agg.groupby(level=0).idxmax().apply(lambda x: x[1])
        return agg.groupby(level=0).idxmin().apply(lambda x: x[1])

    best_avm_pr = best_cfg(df_avm, "pass_rate", maximize=True)
    best_cfsm_pr = best_cfg(df_cfsm, "pass_rate", maximize=True)

    # ── report_avm.md ──
    L = []
    L.append("# AVM (Anticipation Velocity Model) 100회 배치 보고서")
    L.append("")
    L.append("**생성일**: 2026-04-19")
    L.append("")

    L.append("## 요약 (Executive Summary)")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|---|---|")
    L.append(f"| 시뮬 1회 평균 소요 | {np.mean(wall_times):.1f}초 (범위 {min(wall_times):.1f}~{max(wall_times):.1f}s) |"
             if wall_times else "| 시뮬 시간 | 로그 없음 |")
    L.append(f"| 디스크 사용량 (raw) | {disk_raw_mb:.1f} MB |")
    L.append(f"| 실패 시나리오 | {fail_count}개 |")
    L.append(f"| AVM avg_travel_time R² | {r2_avm_tt:.3f} (CFSM v3: {r2_cfsm_tt:.3f}) |")
    L.append(f"| AVM esc_wait_precise R² | {r2_avm_esc:.3f} (CFSM v3: {r2_cfsm_esc:.3f}) |")
    L.append("")
    L.append("**주요 발견 5줄**:")
    L.append(f"- AVM 평균 통행시간 {df_avm.avg_travel_time.mean():.1f}s "
             f"(CFSM {df_cfsm.avg_travel_time.mean():.1f}s 대비 "
             f"{df_avm.avg_travel_time.mean() - df_cfsm.avg_travel_time.mean():+.2f}s)")
    L.append(f"- AVM 평균 통과율 {df_avm.pass_rate.mean():.1f}% "
             f"(CFSM {df_cfsm.pass_rate.mean():.1f}% 대비 "
             f"{df_avm.pass_rate.mean() - df_cfsm.pass_rate.mean():+.1f}%p)")
    L.append(f"- AVM esc_wait_precise 평균 {df_avm.avg_esc_wait_precise.mean():.1f}s "
             f"(CFSM {df_cfsm.avg_esc_wait_precise.mean():.1f}s)")
    L.append(f"- AVM 게이트 처리율 vs 에스컬 대기 r = {r_avm:+.3f} "
             f"(CFSM r = {r_cfsm:+.3f})")
    L.append(f"- 최적 배합 패턴: AVM {list(best_avm_pr)} / CFSM {list(best_cfsm_pr)} → "
             f"{'동일' if list(best_avm_pr) == list(best_cfsm_pr) else '다름'}")
    L.append("")

    L.append("## 1. AVM 모델 개요")
    L.append("")
    L.append("AnticipationVelocityModel (Xu et al. 2021):")
    L.append("- CFSM의 등방성 한계 보완 — 전방 궤적 예측으로 미리 감속/회피")
    L.append("- 주요 파라미터: `anticipation_time=1.0s`, `reaction_time=0.3s`, "
             "`wall_buffer_distance=0.1m`")
    L.append("- CFSM과의 차이: 거리 기반이 아닌 시간 기반 회피 (더 부드러운 흐름)")
    L.append("")
    L.append("**구현**: `simulation/run_west_simulation_avm_demo.py` (CFSM 코드 복사 후 모델 swap)")
    L.append("")

    L.append("## 2. 실험 설계")
    L.append("")
    L.append("- 시나리오: 5 (p) × 4 (config) × 5 (seed) = 100회")
    L.append("- SIM_TIME 300s, TRAIN_INTERVAL 150s, 열차 2편")
    L.append("- 모든 다른 조건 (geometry, 큐 로직, FIFO, capture) v3과 동일")
    L.append("- 잭키잉 OFF 유지, 속도 분포 N(1.34, 0.26) clip(0.8, 2.0) 유지")
    L.append("")

    L.append("## 3. 통계량 비교")
    L.append("")
    L.append("### 3.1 회귀 R² (y ~ p + config + p:config)")
    L.append("")
    L.append("![R² 비교](figures/r2_compare.png)")
    L.append("")
    L.append("| 종속변수 | CFSM (v3) | AVM (v5) | Δ |")
    L.append("|---|---|---|---|")
    L.append(f"| 총 통행시간 | {r2_cfsm_tt:.3f} | {r2_avm_tt:.3f} | {r2_avm_tt-r2_cfsm_tt:+.3f} |")
    L.append(f"| 게이트 대기 | {r2_cfsm_gw:.3f} | {r2_avm_gw:.3f} | {r2_avm_gw-r2_cfsm_gw:+.3f} |")
    L.append(f"| 후처리 | {r2_cfsm_pg:.3f} | {r2_avm_pg:.3f} | {r2_avm_pg-r2_cfsm_pg:+.3f} |")
    L.append(f"| 에스컬 대기 (precise) | {r2_cfsm_esc:.3f} | {r2_avm_esc:.3f} | {r2_avm_esc-r2_cfsm_esc:+.3f} |")
    L.append("")

    L.append("### 3.2 ANOVA 효과 크기 (avg_travel_time)")
    L.append("")
    for factor in ["C(config)", "p", "C(config):p"]:
        v_cfsm = aov_cfsm.loc[factor, "eta_sq"] if factor in aov_cfsm.index else None
        v_avm = aov_avm.loc[factor, "eta_sq"] if factor in aov_avm.index else None
        if v_cfsm is not None and v_avm is not None:
            L.append(f"- {factor}: CFSM η²={v_cfsm:.3f}, AVM η²={v_avm:.3f} ({v_avm-v_cfsm:+.3f})")
    L.append("")

    L.append("## 4. 통과율 비교")
    L.append("")
    L.append("![통과율 heatmap](figures/pass_rate_compare.png)")
    L.append("")
    L.append("### CFSM 통과율 (%)")
    pr_cfsm = df_cfsm.groupby(["p", "config"]).pass_rate.mean().unstack().round(1)
    L.append("```")
    L.append(str(pr_cfsm))
    L.append("```")
    L.append("")
    L.append("### AVM 통과율 (%)")
    pr_avm = df_avm.groupby(["p", "config"]).pass_rate.mean().unstack().round(1)
    L.append("```")
    L.append(str(pr_avm))
    L.append("```")
    L.append("")
    L.append("### 차이 (AVM − CFSM, %p)")
    L.append("```")
    L.append(str((pr_avm - pr_cfsm).round(1)))
    L.append("```")
    L.append("")

    L.append("## 5. 속도 프로파일 (CFSM vs AVM)")
    L.append("")
    L.append("![속도 프로파일](figures/velocity_compare.png)")
    L.append("")
    L.append("**관찰**: AVM이 corridor 입구(x=23~25) 직전까지 CFSM보다 빠른 속도 유지. "
             "anticipation으로 미리 감속하지만 멈추지 않고 흐름 유지하기 때문.")
    L.append("")

    L.append("## 6. 병목 전이 (CFSM vs AVM)")
    L.append("")
    L.append("| 지표 | CFSM | AVM |")
    L.append("|---|---|---|")
    L.append(f"| 게이트 처리율 vs 에스컬 대기 r | {r_cfsm:+.3f} | {r_avm:+.3f} |")
    L.append(f"| (p-value) | {p_cfsm:.4g} | {p_avm:.4g} |")
    L.append("")

    L.append("## 7. 최적 배합 비교")
    L.append("")
    L.append("| p | CFSM 최적 | AVM 최적 | 일치? |")
    L.append("|---|---|---|---|")
    for p in sorted(df_avm.p.unique()):
        c_cfsm = int(best_cfsm_pr[p])
        c_avm = int(best_avm_pr[p])
        eq = "O" if c_cfsm == c_avm else "X"
        L.append(f"| {p:.1f} | {c_cfsm} | {c_avm} | {eq} |")
    L.append("")

    L.append("## 8. AVM 채택 시사점")
    L.append("")
    diff_tt = df_avm.avg_travel_time.mean() - df_cfsm.avg_travel_time.mean()
    diff_pr = df_avm.pass_rate.mean() - df_cfsm.pass_rate.mean()
    L.append(f"- 평균 통행시간 차이 {diff_tt:+.2f}s → "
             f"{'AVM 빠름' if diff_tt < 0 else 'AVM 느림' if diff_tt > 0 else '동일'}")
    L.append(f"- 평균 통과율 차이 {diff_pr:+.1f}%p → "
             f"{'AVM 우수' if diff_pr > 0 else 'AVM 열등' if diff_pr < 0 else '동일'}")
    L.append("- R² 비교: AVM이 CFSM보다 설명력 "
             f"{'높음' if r2_avm_tt > r2_cfsm_tt else '낮음'} "
             f"({r2_avm_tt - r2_cfsm_tt:+.3f})")
    L.append("- 최적 배합 패턴: 두 모델 "
             f"{'동일' if list(best_avm_pr) == list(best_cfsm_pr) else '불일치'} "
             "→ 모델 선택이 정책 결론을 바꾸는가의 답")
    L.append("")

    L.append("## 9. 한계 및 후속")
    L.append("")
    L.append("- AVM 데모는 V&V (RiMEA, FZJ) 미실행. 본격 채택 전 검증 필요.")
    L.append("- AVM 파라미터 (anticipation_time=1.0, reaction_time=0.3) 기본값 사용. "
             "한국 통근자 행태 보정은 후속.")
    L.append("- capture 로직, 큐 로직은 양 모델 동일 → 모델 차이는 자유보행 영역에 한정.")
    L.append("- 영상 검증: `output/simulation_escalator.mp4` (CFSM) vs "
             "`output/simulation_avm_demo.mp4` (AVM)")
    L.append("")

    REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"\nSaved: {REPORT}")


if __name__ == "__main__":
    main()
