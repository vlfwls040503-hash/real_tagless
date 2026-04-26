"""
2.7s vs 2.09s 비교 — G 최적화 cfg / S 최적화 cfg (LOS E 제약) 모두 표시.

표:
  표 1. G 최적화 cfg 비교 (게이트 대기시간 최소)
  표 2. S 최적화 cfg 비교 (LOS E 제약 + 통행시간 최소)
  표 3. 최종 채택 cfg 비교
"""
from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import WALKWAY_LOS, grade

DENS_27 = ROOT / "results" / "molit" / "density_union.csv"
DENS_209 = ROOT / "results_service_209" / "density_209.csv"
OUT = ROOT / "results_service_209" / "COMPARE_27_VS_209.txt"

PASS_RATE_MIN = 0.9
LOS_E_MAX = 1.0


def los(d):
    return grade(d, WALKWAY_LOS)


def load(path, w2_avg_col, w2_pk_col):
    df = pd.read_csv(path)
    df = df[df["pass_rate"] >= PASS_RATE_MIN]
    df = df[df["config"].isin([1, 2, 3, 4, 5, 6])]
    return df.groupby(["p", "config"]).agg(
        travel=("avg_travel_time", "mean"),
        gate_wait=("avg_gate_wait", "mean"),
        W2_avg=(w2_avg_col, "mean"),
        W2_pk=(w2_pk_col, "mean"),
        n=("seed", "count"),
    ).reset_index()


def best_g(sub):
    """게이트 대기 최소 cfg (제약 없음)."""
    return sub.loc[sub["gate_wait"].idxmin()]


def best_s_los(sub):
    """LOS E 제약 하 통행시간 최소 cfg. None 이면 후보 없음."""
    feas = sub[sub["W2_pk"] <= LOS_E_MAX]
    if len(feas) == 0:
        return None
    return feas.loc[feas["travel"].idxmin()]


def main():
    a27 = load(DENS_27, "W1_avg_density", "W1_peak_density")  # 잠시 임시 (W2)
    # 실제 W2 컬럼: W2_avg_density / W2_peak_density
    a27 = load(DENS_27, "W2_avg_density", "W2_peak_density")
    a209 = load(DENS_209, "W2_avg", "W2_pk")

    out = []
    add = out.append
    add("=" * 130)
    add("SERVICE_TIME 2.7s vs 2.09s 비교 — G 최적 / S 최적 (LOS E 제약)")
    add("=" * 130)
    add("")
    add("정의:")
    add("  G 최적 cfg = 게이트 대기시간 (gate_wait) 최소 cfg (LOS 제약 없음)")
    add("  S 최적 cfg = 통행시간 (travel) 최소 cfg, 단 W2 peak ≤ 1.0 (LOS E) 만족")
    add("  '없음' = LOS E 만족하는 cfg 없음 (시설 부족)")

    p_list = sorted(a27["p"].unique())

    # ──────────────── 표 1: G 최적 cfg 비교 ────────────────
    add("\n" + "=" * 130)
    add("[표 1] G 최적 cfg 비교 — 게이트 대기시간 최소 (LOS 제약 없음)")
    add("=" * 130)
    add("")
    add(f"  {'p':>4} | "
        f"{'2.7s G cfg':>10} | {'gate_wait':>9} | {'travel':>7} | {'W2pk':>6} {'LOS':>4} | "
        f"{'2.09s G cfg':>11} | {'gate_wait':>9} | {'travel':>7} | {'W2pk':>6} {'LOS':>4} | "
        f"{'cfg 변화':>9}")
    add("  " + "-" * 130)
    for p_val in p_list:
        s27 = a27[a27["p"] == p_val]
        s209 = a209[a209["p"] == p_val]
        r27 = best_g(s27); r209 = best_g(s209)
        cfg27, cfg209 = int(r27["config"]), int(r209["config"])
        change = "동일" if cfg27 == cfg209 else f"cfg{cfg27}→cfg{cfg209}"
        add(f"  {p_val:>4.1f} | "
            f"{'cfg'+str(cfg27):>10s} | {r27['gate_wait']:>7.1f}s | "
            f"{r27['travel']:>5.1f}s | {r27['W2_pk']:>5.2f}  {los(r27['W2_pk']):>3} | "
            f"{'cfg'+str(cfg209):>11s} | {r209['gate_wait']:>7.1f}s | "
            f"{r209['travel']:>5.1f}s | {r209['W2_pk']:>5.2f}  {los(r209['W2_pk']):>3} | "
            f"{change:>9s}")

    # ──────────────── 표 2: S 최적 cfg (LOS E 제약) 비교 ────────────────
    add("\n" + "=" * 130)
    add("[표 2] S 최적 cfg 비교 — LOS E (W2pk ≤ 1.0) 제약 + 통행시간 최소")
    add("=" * 130)
    add("")
    add(f"  {'p':>4} | "
        f"{'2.7s S cfg':>10} | {'gate_wait':>9} | {'travel':>7} | {'W2pk':>6} {'LOS':>4} | "
        f"{'2.09s S cfg':>11} | {'gate_wait':>9} | {'travel':>7} | {'W2pk':>6} {'LOS':>4} | "
        f"{'cfg 변화':>9}")
    add("  " + "-" * 130)
    for p_val in p_list:
        s27 = a27[a27["p"] == p_val]
        s209 = a209[a209["p"] == p_val]
        r27 = best_s_los(s27); r209 = best_s_los(s209)
        def fmt(r):
            if r is None:
                return ("없음", "-", "-", "-", "-")
            return (f"cfg{int(r['config'])}",
                    f"{r['gate_wait']:.1f}s",
                    f"{r['travel']:.1f}s",
                    f"{r['W2_pk']:.2f}",
                    los(r["W2_pk"]))
        c27, gw27, tr27, w27, l27 = fmt(r27)
        c209, gw209, tr209, w209, l209 = fmt(r209)
        if r27 is None or r209 is None:
            change = "-"
        elif int(r27["config"]) == int(r209["config"]):
            change = "동일"
        else:
            change = f"{c27}→{c209}"
        add(f"  {p_val:>4.1f} | "
            f"{c27:>10s} | {gw27:>9s} | {tr27:>7s} | {w27:>6s} {l27:>4s} | "
            f"{c209:>11s} | {gw209:>9s} | {tr209:>7s} | {w209:>6s} {l209:>4s} | "
            f"{change:>9s}")

    # ──────────────── 표 3: 최종 채택 cfg 비교 ────────────────
    add("\n" + "=" * 130)
    add("[표 3] 최종 채택 cfg 비교 — 결정 규칙 적용 (G≠S면 S 채택, G/S 둘 다 위반이면 LOS 통과 중 travel 최저)")
    add("=" * 130)
    add("")
    add(f"  {'p':>4} | {'2.7s 채택':>10} | {'travel':>7} | {'gate_wait':>9} | {'W2pk':>6} {'LOS':>4} | "
        f"{'2.09s 채택':>11} | {'travel':>7} | {'gate_wait':>9} | {'W2pk':>6} {'LOS':>4} | "
        f"{'travel 변화':>11}")
    add("  " + "-" * 130)

    def decide(sub):
        rg = best_g(sub); rs = sub.loc[sub["travel"].idxmin()]
        g_eq_s = (int(rg["config"]) == int(rs["config"]))
        s_ok = rs["W2_pk"] <= LOS_E_MAX
        if g_eq_s and s_ok:
            return rs
        if g_eq_s and not s_ok:
            feas = sub[sub["W2_pk"] <= LOS_E_MAX]
            if len(feas) == 0: return None
            return feas.loc[feas["travel"].idxmin()]
        # G ≠ S
        if s_ok:
            return rs
        feas = sub[sub["W2_pk"] <= LOS_E_MAX]
        if len(feas) == 0: return None
        return feas.loc[feas["travel"].idxmin()]

    for p_val in p_list:
        s27 = a27[a27["p"] == p_val]
        s209 = a209[a209["p"] == p_val]
        r27 = decide(s27); r209 = decide(s209)
        def fmt2(r):
            if r is None: return ("없음", "-", "-", "-", "-")
            return (f"cfg{int(r['config'])}",
                    f"{r['travel']:.1f}s",
                    f"{r['gate_wait']:.1f}s",
                    f"{r['W2_pk']:.2f}",
                    los(r["W2_pk"]))
        c27, tr27, gw27, w27, l27 = fmt2(r27)
        c209, tr209, gw209, w209, l209 = fmt2(r209)
        if r27 is None or r209 is None:
            change = "-"
        else:
            change = f"{r209['travel'] - r27['travel']:+.1f}s"
        add(f"  {p_val:>4.1f} | "
            f"{c27:>10s} | {tr27:>7s} | {gw27:>9s} | {w27:>6s} {l27:>4s} | "
            f"{c209:>11s} | {tr209:>7s} | {gw209:>9s} | {w209:>6s} {l209:>4s} | "
            f"{change:>11s}")

    # 요약
    add("\n" + "=" * 130)
    add("[요약]")
    add("=" * 130)
    add("")
    add("- 2.09s (게이트 빠른 시나리오) 채택 cfg 가 전반적으로 더 큰 쪽 (cfg2→cfg3/4) 으로 이동")
    add("- 통행시간 단축 효과: 거의 모든 p 에서 -2~6s")
    add("- 게이트 대기시간 큰 폭 단축")
    add("- LOS 위반 cfg 분포가 바뀌어 같은 cfg2가 2.7s에선 LOS E 통과, 2.09s에선 LOS F 위반 (p=0.3)")

    text = "\n".join(out)
    print(text)
    OUT.write_text(text, encoding="utf-8")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
