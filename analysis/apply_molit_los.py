"""
100 시나리오 + p=0 baseline 에 국토부 LOS 기준 적용.
시뮬 출력 zone_density (평균/최대) 를 MOLIT 표 2.2/2.3 기준으로 재분류.

결과:
- results/molit_los_100scenarios.csv: 시나리오별 LOS 등급
- results/molit_los_baseline.csv: p=0 baseline
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import (
    zone_grade, los_threshold, ZONE_CATEGORY,
)

OUT = ROOT / "results" / "molit"
OUT.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 1. 100 시나리오 요약 읽기
# =============================================================================
summary = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
print(f"[100 시나리오] rows={len(summary)}, p={sorted(summary['p'].unique())}, "
      f"config={sorted(summary['config'].unique())}, seeds={sorted(summary['seed'].unique())}")

# Zone 유형별 LOS 적용. MOLIT은 첨두 1분 평균 단위 → 시뮬의 avg_density 사용.
# (max_density 는 순간 피크라 기준과 맞지 않음 — 참고용만 병기)
zones = ["zone1", "zone2", "zone3a", "zone3b", "zone3c", "zone4a", "zone4b", "zone4c"]
records = []
for _, row in summary.iterrows():
    rec = {
        "scenario_id": row["scenario_id"],
        "p": row["p"], "config": row["config"], "seed": row["seed"],
        "avg_gate_wait": row["avg_gate_wait"],
        "p95_gate_wait": row["p95_gate_wait"],
        "avg_esc_wait": row["avg_esc_wait_precise"],
    }
    for z in zones:
        d_avg = row[f"{z}_avg_density"]
        d_max = row[f"{z}_max_density"]
        rec[f"{z}_density_avg"] = d_avg
        rec[f"{z}_density_max"] = d_max
        rec[f"{z}_los_avg"] = zone_grade(z, d_avg)
        rec[f"{z}_los_max"] = zone_grade(z, d_max)
        rec[f"{z}_category"] = ZONE_CATEGORY[z][0]
    records.append(rec)

df100 = pd.DataFrame(records)
df100.to_csv(OUT / "molit_los_100scenarios.csv", index=False, encoding="utf-8-sig")
print(f"  저장: {OUT / 'molit_los_100scenarios.csv'}")

# 시나리오 배합별 LOS 분포 요약 (seed 5개 평균)
agg = df100.groupby(["p", "config"]).agg(
    gate_wait=("avg_gate_wait", "mean"),
    esc_wait=("avg_esc_wait", "mean"),
    # 관심 Zone: 3b/4b (에스컬 앞), 2 (게이트 앞)
    z2_avg=("zone2_density_avg", "mean"),
    z2_max=("zone2_density_max", "mean"),
    z3b_avg=("zone3b_density_avg", "mean"),
    z3b_max=("zone3b_density_max", "mean"),
    z4b_avg=("zone4b_density_avg", "mean"),
    z4b_max=("zone4b_density_max", "mean"),
).reset_index()

# 평균 밀도 기준 LOS
for col_prefix, zone_id in [("z2", "zone2"), ("z3b", "zone3b"), ("z4b", "zone4b")]:
    agg[f"{col_prefix}_los_avg"] = agg[f"{col_prefix}_avg"].apply(lambda d: zone_grade(zone_id, d))
    agg[f"{col_prefix}_los_max"] = agg[f"{col_prefix}_max"].apply(lambda d: zone_grade(zone_id, d))

agg.to_csv(OUT / "molit_los_agg_pxcfg.csv", index=False, encoding="utf-8-sig")
print(f"  저장: {OUT / 'molit_los_agg_pxcfg.csv'}")

# =============================================================================
# 2. p=0 baseline
# =============================================================================
p0_file = ROOT / "results_baseline" / "p0_summary.json"
if p0_file.exists():
    p0 = json.loads(p0_file.read_text(encoding="utf-8"))
    # p0_summary 구조 확인
    print(f"\n[p=0 baseline] keys: {list(p0.keys())[:10]}")
    # seed별 데이터
    if "seeds" in p0:
        baseline_rows = []
        for s_key, s_data in p0["seeds"].items():
            row = {"seed": s_key}
            for k, v in s_data.items():
                row[k] = v
            baseline_rows.append(row)
        df0 = pd.DataFrame(baseline_rows)
        df0.to_csv(OUT / "molit_los_baseline_p0.csv", index=False, encoding="utf-8-sig")
        print(f"  저장: {OUT / 'molit_los_baseline_p0.csv'}")
    # aggregate (여러 키 구조 대비)
    summary_p0 = {"p=0_baseline": True}
    for k, v in p0.items():
        if isinstance(v, (int, float)):
            summary_p0[k] = v
        elif isinstance(v, dict) and not isinstance(next(iter(v.values())), (list, dict)):
            for kk, vv in v.items():
                if isinstance(vv, (int, float)):
                    summary_p0[f"{k}_{kk}"] = vv
    (OUT / "molit_los_baseline_p0.json").write_text(
        json.dumps(summary_p0, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  저장: {OUT / 'molit_los_baseline_p0.json'}")

# =============================================================================
# 3. 간단 요약 출력
# =============================================================================
print("\n===== Zone B (에스컬 앞) 평균 밀도 + LOS (보행로 기준) =====")
print("열: z3b_avg / z3b_los_avg / z4b_avg / z4b_los_avg / gate_wait")
for _, r in agg.iterrows():
    print(f"p={r['p']:.1f} cfg={int(r['config'])}: "
          f"z3b={r['z3b_avg']:.2f}/{r['z3b_los_avg']} "
          f"z4b={r['z4b_avg']:.2f}/{r['z4b_los_avg']} "
          f"gate_wait={r['gate_wait']:.1f}s")

print("\n===== Zone 2 (게이트 앞) 평균 밀도 + LOS (대기공간 기준) =====")
for _, r in agg.iterrows():
    print(f"p={r['p']:.1f} cfg={int(r['config'])}: "
          f"z2={r['z2_avg']:.2f}/{r['z2_los_avg']} "
          f"max={r['z2_max']:.2f}/{r['z2_los_max']}")

# MOLIT 보행로 LOS F 임계(2.0) 위반 시나리오
print(f"\n===== MOLIT 보행로 LOS F (>2.0 ped/m²) 위반 (평균 밀도) =====")
violations_avg_3b = agg[agg["z3b_avg"] > 2.0]
violations_avg_4b = agg[agg["z4b_avg"] > 2.0]
print(f"Zone 3B 위반: {len(violations_avg_3b)}개")
print(f"Zone 4B 위반: {len(violations_avg_4b)}개")
