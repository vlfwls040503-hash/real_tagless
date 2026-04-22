"""
국토부 지침 최소 권장 LOS 기준에 따른 결과 재해석.

지침 원문 (2.2.3 (2)):
> 첨두시간대를 기준으로
> 승강장 및 내·외부 계단의 서비스수준을 D 이상,
> 환승통로에서의 서비스수준을 E 이상으로 한다.

대합실은 명시 없으나, '보행공간(보행로)' 으로 분류 → 환승통로 기준 (LOS E 이상) 적용.
더 엄격한 기준 (계단/승강장 수준 LOS D) 도 병기.

기준 임계값 (보행로, 표 2.3):
- LOS D 이상 (엄격): ≤ 1.0 ped/m²
- LOS E 이상 (지침 권장): ≤ 2.0 ped/m²
"""
from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import zone_grade

OUT = ROOT / "results" / "molit"
OUT.mkdir(parents=True, exist_ok=True)

# 100 시나리오 raw + agg
df = pd.read_csv(OUT / "molit_los_100scenarios.csv")
df["z_bmax"] = df[["zone3b_density_avg", "zone4b_density_avg"]].max(axis=1)

agg = df.groupby(["p","config"]).agg(
    z3b=("zone3b_density_avg", "mean"),
    z4b=("zone4b_density_avg", "mean"),
    z_bmax=("z_bmax", "mean"),
    z2=("zone2_density_avg", "mean"),
    z3a=("zone3a_density_avg", "mean"),
    z4a=("zone4a_density_avg", "mean"),
).reset_index()

# Baseline p=0
import json
p0 = json.load(open(ROOT / "results_baseline" / "p0_summary.json", encoding="utf-8"))["aggregated"]

# =============================================================================
# 1. 기준별 위반 시나리오 카운트 (보행로 기준 적용 zone들)
# =============================================================================
print("=" * 70)
print("국토부 권장 LOS 기준 위반 분석 (100 시나리오, 보행공간)")
print("=" * 70)

# 보행공간 적용 zone: 3a, 3b, 4a, 4b (대기공간인 zone2 제외)
walkway_zones = {
    "Zone 3A (exit1 접근)": "z3a",
    "Zone 3B (exit1 대기)": "z3b",
    "Zone 4A (exit4 접근)": "z4a",
    "Zone 4B (exit4 대기)": "z4b",
    "Zone B max (시스템)":   "z_bmax",
}

print(f"\n{'Zone':<25s} {'평균밀도 max':>12s} {'LOS E (>2.0) 위반':>18s} {'LOS D (>1.0) 위반':>18s}")
print("-" * 80)
for zname, zcol in walkway_zones.items():
    max_d = agg[zcol].max()
    los_e_violations = (agg[zcol] > 2.0).sum()
    los_d_violations = (agg[zcol] > 1.0).sum()
    print(f"{zname:<25s} {max_d:>12.3f} {los_e_violations:>10d}/{len(agg)} {los_d_violations:>10d}/{len(agg)}")

# =============================================================================
# 2. 기준 만족 cfg 개수 (p별)
# =============================================================================
print("\n" + "=" * 70)
print("p별 기준 만족 cfg 수 (Z_bmax 기준)")
print("=" * 70)
print(f"{'p':>4} | {'LOS E 만족 (≤2.0) cfg':>30s} | {'LOS D 만족 (≤1.0) cfg':>30s}")
print("-" * 80)
for p_val in sorted(agg["p"].unique()):
    sub = agg[agg["p"] == p_val]
    los_e_ok = sub[sub["z_bmax"] <= 2.0]["config"].tolist()
    los_d_ok = sub[sub["z_bmax"] <= 1.0]["config"].tolist()
    print(f"{p_val:>4.1f} | {str(los_e_ok):>30s} | {str(los_d_ok):>30s}")

# =============================================================================
# 3. baseline p=0 vs LOS 기준
# =============================================================================
print("\n" + "=" * 70)
print("p=0 baseline LOS 평가 (지침 기준)")
print("=" * 70)
def m(k): return p0[k]["mean"]
print(f"Zone 4B avg (이용 우세 측):  {m('z4b_avg'):.3f} ped/m^2 -> "
      f"LOS {zone_grade('zone4b', m('z4b_avg'))}")
print(f"  지침 LOS E (>2.0) 위반: {'O' if m('z4b_avg')>2.0 else 'X'}")
print(f"  지침 LOS D (>1.0) 위반: {'O' if m('z4b_avg')>1.0 else 'X'} (1.60 > 1.0)")
print(f"Zone 4B max:                {m('z4b_max'):.3f} ped/m^2 -> "
      f"LOS {zone_grade('zone4b', m('z4b_max'))}")
print(f"Zone 2 (게이트 앞 대기):     평균 {m('z2_avg'):.3f}, 최대 {m('z2_max'):.3f}")
print(f"  대기공간 기준 LOS F (>5.0): 평균 {'X' if m('z2_avg')<5 else 'O'}, "
      f"최대 {'X' if m('z2_max')<5 else 'O'}")

# =============================================================================
# 4. 종합 결과
# =============================================================================
print("\n" + "=" * 70)
print("종합 (지침 적합성)")
print("=" * 70)
print("- 지침 권장: 환승통로(보행로) LOS E 이상 (≤2.0 ped/m²)")
print("- 더 엄격한 기준: 승강장/계단 수준 LOS D 이상 (≤1.0 ped/m²)")
print()
print("결과:")
los_e_total = (agg["z_bmax"] <= 2.0).sum()
los_d_total = (agg["z_bmax"] <= 1.0).sum()
print(f"  100 시나리오 중 LOS E 만족: {los_e_total}/{len(agg)} ({los_e_total/len(agg)*100:.0f}%)")
print(f"  100 시나리오 중 LOS D 만족: {los_d_total}/{len(agg)} ({los_d_total/len(agg)*100:.0f}%)")
print()
print("판단:")
print("- 지침 권장 (LOS E) 기준은 거의 모든 시나리오에서 만족")
print("- 더 엄격한 기준 (LOS D) 은 상당수 시나리오에서 위반")
print("- baseline (p=0) Z4B 평균 1.60 → 이미 LOS D 초과 (LOS E 등급)")
print("  → 현 성수역 2F 대합실 서쪽은 'LOS D 이상' 기준에서는 본래 부적합")

# 저장
out_summary = {
    "criteria": {
        "los_e_threshold": 2.0,
        "los_d_threshold": 1.0,
        "source": "국토부 고시 제2025-241호 표 2.3 (보행로)",
        "zone_classification": "대합실=보행공간, Z2=대기공간",
    },
    "100_scenarios": {
        "total": len(agg),
        "los_e_satisfied": int(los_e_total),
        "los_d_satisfied": int(los_d_total),
    },
    "baseline_p0": {
        "z4b_avg": m("z4b_avg"),
        "z4b_avg_los": zone_grade("zone4b", m("z4b_avg")),
        "z4b_max": m("z4b_max"),
        "z4b_max_los": zone_grade("zone4b", m("z4b_max")),
        "los_d_violation_avg": m("z4b_avg") > 1.0,
        "los_e_violation_avg": m("z4b_avg") > 2.0,
    },
}
import json as _j
(OUT / "molit_minimum_criteria.json").write_text(
    _j.dumps(out_summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n저장: {OUT / 'molit_minimum_criteria.json'}")
