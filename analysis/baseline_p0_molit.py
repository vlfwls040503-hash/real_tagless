"""
p=0 baseline 을 MOLIT 기준으로 재측정.
results_baseline/p0_summary.json 의 zone 평균 밀도를 국토부 LOS 등급에 매핑.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.molit_los import zone_grade, ZONE_CATEGORY

OUT = ROOT / "results" / "molit"
OUT.mkdir(parents=True, exist_ok=True)

p0 = json.loads((ROOT / "results_baseline" / "p0_summary.json").read_text(encoding="utf-8"))
agg = p0["aggregated"]
config = p0["config"]

print("=" * 70)
print("p=0 baseline (100% 태그 이용자)")
print("=" * 70)
print(f"조건: {config}")
print(f"시뮬 시간: {config['sim_time']}s, 열차 하차: {config['train_alighting']}명, "
      f"열차 간격: {config['train_interval']}s")

# Zone 통계
def m(key):
    return agg[key]["mean"]
def s(key):
    return agg[key]["std"]

zones_data = {
    "zone1":  ("Z1", "대합실_전체",   m("z1_avg"),  m("z1_max")),
    "zone2":  ("Z2", "게이트_앞",     m("z2_avg"),  m("z2_max")),
    "zone3a": ("Z3A","exit1_접근",     m("z3a_avg"), m("z3a_max")),
    "zone3b": ("Z3B","exit1_대기",     m("z3b_avg"), m("z3b_max")),
    "zone3c": ("Z3C","exit1_corridor", m("z3c_avg"), m("z3c_max")),
    "zone4a": ("Z4A","exit4_접근",     m("z4a_avg"), m("z4a_max")),
    "zone4b": ("Z4B","exit4_대기",     m("z4b_avg"), m("z4b_max")),
    "zone4c": ("Z4C","exit4_corridor", m("z4c_avg"), m("z4c_max")),
}

rows = []
print(f"\n{'Zone':6s} {'이름':18s} {'유형':8s} {'평균':>8s} {'LOS(평균)':10s} "
      f"{'최대':>8s} {'LOS(최대)':10s}")
print("-" * 80)
for zkey, (zid, zname, d_avg, d_max) in zones_data.items():
    cat, _ = ZONE_CATEGORY[zkey]
    los_avg = zone_grade(zkey, d_avg)
    los_max = zone_grade(zkey, d_max)
    cat_k = "보행로" if cat=="walkway" else "대기"
    print(f"{zid:6s} {zname:18s} {cat_k:8s} {d_avg:>8.3f} {los_avg:10s} "
          f"{d_max:>8.3f} {los_max:10s}")
    rows.append({
        "zone": zid, "name": zname, "category": cat,
        "density_avg": d_avg, "los_avg": los_avg,
        "density_max": d_max, "los_max": los_max,
    })

pd.DataFrame(rows).to_csv(OUT / "baseline_p0_molit_los.csv", index=False, encoding="utf-8-sig")

print(f"\n게이트 평균 대기시간: {m('avg_gate_wait'):.2f} s (std {s('avg_gate_wait'):.2f})")
print(f"에스컬 평균 대기시간: {m('avg_esc_wait_precise'):.2f} s")
print(f"평균 통행시간:       {m('avg_travel_time'):.2f} s")
print(f"exit1:exit4 비율:     {m('exit1_share'):.2f} : {1-m('exit1_share'):.2f}")

# 핵심 해석
print("\n" + "=" * 70)
print("p=0 baseline 핵심 해석")
print("=" * 70)
z4b_avg = m("z4b_avg")
z4b_max = m("z4b_max")
z2_avg = m("z2_avg")
z2_max = m("z2_max")
print(f"- Zone 4B (upper 에스컬 앞): 평균 {z4b_avg:.2f} ped/m² -> 보행로 LOS "
      f"{zone_grade('zone4b', z4b_avg)} / 최대 {z4b_max:.2f} -> LOS {zone_grade('zone4b', z4b_max)}")
print(f"  보행로 LOS F 임계값 2.0 대비: 평균 {'초과' if z4b_avg>2.0 else '이하'}, "
      f"최대 {'초과' if z4b_max>2.0 else '이하'}")
print(f"- Zone 2 (게이트 앞 대기): 평균 {z2_avg:.2f} ped/m² -> 대기공간 LOS "
      f"{zone_grade('zone2', z2_avg)} / 최대 {z2_max:.2f} -> LOS {zone_grade('zone2', z2_max)}")
print(f"  대기공간 LOS F 임계값 5.0 대비: 평균 {'초과' if z2_avg>5.0 else '이하'}, "
      f"최대 {'초과' if z2_max>5.0 else '이하'}")
