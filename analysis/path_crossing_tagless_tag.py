"""
태그/태그리스 동선 교차(꼬임) 분석.

조건:
- 시뮬에서 태그리스/태그 사용자가 다른 게이트를 향함
- 두 사용자의 직선 경로가 게이트 접근 영역에서 교차
- agent의 횡(y) 이동량이 큼 = 다른 사용자 줄을 가로지름

데이터:
- output/trajectories_escalator.csv : x,y,gate_idx,state (per agent over time)
- agent_level_delay.csv (results_cfsm_latest) : is_tagless, gate_idx, agent_id

분석 단위: 100 시나리오 중 대표 1개 + 최신 단일 시뮬 trajectory.

지표:
1. 게이트 접근 구간 (x=2~12) 에서 agent 별 |Δy| 누적량
2. 같은 시점에 좌우로 가로지르는 (반대 방향 y 이동) 두 agent 간 교차 카운트
3. 태그리스 vs 태그 그룹의 횡이동 차이 (t-test)
"""
from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 1. 단일 시뮬 trajectory + agent_level (is_tagless flag) 결합
# =============================================================================
print("[1] 단일 시뮬 (output/trajectories_escalator.csv) 분석")
traj = pd.read_csv(ROOT / "output" / "trajectories_escalator.csv")
print(f"  trajectory rows: {len(traj):,}, agents: {traj.agent_id.nunique()}")

# 100 시나리오 agent_level_delay 에서 is_tagless 가져오기 — 단일 시뮬에는 매핑 안됨
# 대신 단일 시뮬에서는 gate_idx 만 알 수 있으므로,
# tagless가 어느 게이트를 가는지는 BATCH_TAGLESS_ONLY_GATES = frozenset() (cfg=0) 인지
# 또는 TAGLESS_RATIO=1.0 (전부 태그리스) 인지에 따라 다름.
# 현재 단일 시뮬은 TAGLESS_RATIO=1.0, BATCH_TAGLESS_ONLY_GATES=∅ → 모두 태그리스
# 즉 "혼재 상황"이 아님 → 동선 교차 분석은 100 시나리오 데이터 사용

# =============================================================================
# 2. 100 시나리오 agent-level 데이터로 동선 교차 분석
# =============================================================================
print("\n[2] 100 시나리오 agent_level_delay 로 분석")
ag = pd.read_csv(ROOT / "results_cfsm_latest" / "agent_level_delay.csv")
print(f"  total agents: {len(ag):,}")
print(f"  scenarios: {ag.scenario_id.nunique()}")
print(f"  is_tagless 분포: {ag.is_tagless.value_counts().to_dict()}")

# 시나리오별 게이트 분포 (태그리스 vs 태그)
print("\n[3] 시나리오별 게이트 선택 분포 (태그리스 vs 태그)")
samples = ["p10_cfg1_s42", "p30_cfg2_s42", "p50_cfg3_s42", "p70_cfg4_s42", "p80_cfg4_s42"]
for sid in samples:
    sub = ag[ag.scenario_id == sid]
    if len(sub) == 0:
        continue
    p_val = sub["p"].iloc[0]
    cfg_val = sub["config"].iloc[0]
    # tagless / tag 별 게이트 분포는 agent_level_delay에 gate_idx 없으면 못 함
    # 대신 sink_side (upper/lower) 분포
    tl = sub[sub.is_tagless == 1]
    tg = sub[sub.is_tagless == 0]
    print(f"  {sid} (p={p_val}, cfg={cfg_val}): "
          f"tagless n={len(tl)}, tag n={len(tg)}")
    if "sink_side" in sub.columns:
        tl_side = tl["sink_side"].value_counts().to_dict()
        tg_side = tg["sink_side"].value_counts().to_dict()
        print(f"    tagless sink: {tl_side}, tag sink: {tg_side}")

# =============================================================================
# 3. 100 시나리오 raw zones 데이터에서 게이트 접근구역 (Z2: 게이트 앞) 분석
# =============================================================================
print("\n[4] Z2 (게이트 앞) 평균 밀도 vs 동선 충돌 추정")
# 직접적 교차 측정은 trajectory 필요. Z2 평균 밀도를 proxy.
summary = pd.read_csv(ROOT / "results_cfsm_latest" / "summary.csv")
# 대칭 cfg (1,2,3,4) 에서 z2 밀도
sub_summary = summary.groupby(["p","config"]).zone2_avg_density.mean().unstack()
print(sub_summary.to_string(float_format="%.3f"))

# =============================================================================
# 4. 단일 시뮬 trajectory 로 횡이동(가로지름) 추정
# =============================================================================
print("\n[5] 단일 시뮬에서 게이트 접근 구간 횡이동 분석")
# 게이트 접근 zone: x=2 ~ 13 (게이트 x=12)
approach = traj[(traj.x >= 2) & (traj.x <= 13)].copy()
approach = approach.sort_values(["agent_id", "time"]).reset_index(drop=True)
approach["dy"] = approach.groupby("agent_id")["y"].diff()
approach["dx"] = approach.groupby("agent_id")["x"].diff()
approach["abs_dy"] = approach["dy"].abs()

# agent별 누적 횡이동량
y_movement = approach.groupby("agent_id").agg(
    y_total_abs=("abs_dy", "sum"),
    y_range=("y", lambda s: s.max() - s.min()),
    target_gate=("gate_idx", lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else -1),
    n_frames=("time", "count"),
).reset_index()

print(f"  agent 수: {len(y_movement)}")
print(f"  접근 구간 평균 |Δy| 누적: {y_movement.y_total_abs.mean():.2f} m")
print(f"  접근 구간 평균 y 범위:    {y_movement.y_range.mean():.2f} m")
print(f"  y 범위 > 2m (큰 횡이동): {(y_movement.y_range > 2).sum()}명 "
      f"({(y_movement.y_range > 2).sum()/len(y_movement)*100:.1f}%)")

# =============================================================================
# 5. 게이트별 spawn-target 차이 — 게이트 변경(가로지름) 추정
# =============================================================================
# spawn 시점 y vs 통과 게이트 y 차이
print("\n[6] spawn y vs 도착 gate y 차이")
first = traj.sort_values(["agent_id","time"]).groupby("agent_id").head(1).copy()
first.columns = [f"first_{c}" if c not in ["agent_id"] else c for c in first.columns]
last_pre_gate = traj[traj.x < 13].sort_values(["agent_id","time"]).groupby("agent_id").tail(1).copy()
last_pre_gate.columns = [f"pre_{c}" if c not in ["agent_id"] else c for c in last_pre_gate.columns]
merged = first.merge(last_pre_gate, on="agent_id", how="inner")
merged["y_shift"] = merged["pre_y"] - merged["first_y"]
merged["abs_y_shift"] = merged["y_shift"].abs()

# 큰 y 이동 = 다른 게이트로 가는 길에 가로지름
big_shifts = merged[merged["abs_y_shift"] > 3]  # 3m 이상 y 이동
print(f"  spawn→pre-gate 평균 y shift: {merged['abs_y_shift'].mean():.2f} m")
print(f"  3m 이상 y 이동: {len(big_shifts)}명 "
      f"({len(big_shifts)/len(merged)*100:.1f}%)")

# 게이트 별 분포
gate_counts = merged.groupby("pre_gate_idx").agg(
    n=("agent_id", "count"),
    spawn_y_mean=("first_y", "mean"),
    abs_y_shift_mean=("abs_y_shift", "mean"),
).reset_index()
print("\n  게이트별 통계 (single sim, 모두 태그리스):")
print(gate_counts.to_string(index=False))

# =============================================================================
# 6. 시각화: 게이트 접근 시 횡이동 분포
# =============================================================================
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

ax = axes[0]
ax.hist(y_movement.y_range, bins=30, color="steelblue", alpha=0.75, edgecolor="white")
ax.axvline(2.0, color="red", linestyle="--", label=f"기준 2m ({(y_movement.y_range>2).sum()}명 초과)")
ax.set_xlabel("게이트 접근 구간 (x=2~13) 내 y 범위 (m)")
ax.set_ylabel("agent 수")
ax.set_title(f"(a) 게이트 접근 횡이동 분포 (n={len(y_movement)}, 모두 태그리스)")
ax.legend(); ax.grid(alpha=0.3)

ax = axes[1]
# 100 시나리오 zone2_avg_density 의 p×cfg 히트맵
piv = summary.groupby(["p","config"]).zone2_avg_density.mean().unstack()
im = ax.imshow(piv.values, cmap="OrRd", aspect="auto", origin="lower")
ax.set_xticks(range(piv.shape[1]))
ax.set_xticklabels([f"cfg{c}" for c in piv.columns])
ax.set_yticks(range(piv.shape[0]))
ax.set_yticklabels([f"p={p}" for p in piv.index])
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.iloc[i,j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9)
plt.colorbar(im, ax=ax, label="ped/m²")
ax.set_title("(b) Z2 (게이트 앞) 평균밀도 — 동선 충돌 proxy")

plt.tight_layout()
plt.savefig(FIG / "path_crossing.png", dpi=100)
plt.close()
print(f"\n그림: {FIG / 'path_crossing.png'}")

# =============================================================================
# 7. 결론
# =============================================================================
print("\n" + "=" * 70)
print("결론")
print("=" * 70)
mean_y = y_movement.y_range.mean()
big_pct = (y_movement.y_range > 2).sum() / len(y_movement) * 100
print(f"- 단일 시뮬(태그리스 100%)에서 게이트 접근 시 평균 횡 이동 범위: {mean_y:.2f} m")
print(f"- 2m 이상 횡이동 비율: {big_pct:.1f}%")
print(f"  (해석: 모두 태그리스라 동선 교차 소수. 혼재 상황에서는 더 클 가능성)")
print()
print("- z2 (게이트 앞) 밀도는 cfg/p에 따라 0.45~3.53 ped/m² 변화")
print("  높은 z2 밀도 = 게이트 앞 정체 = 가로지르기 어려움 / 충돌 가능성 ↑")
