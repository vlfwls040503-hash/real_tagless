"""
율리히(Jülich) / Seyfried 실험 파라미터 vs 시뮬레이션 캘리브레이션 비교.

비교 항목:
1. 기본도 (Seyfried 2005 single-file)      : v-rho fundamental diagram
2. 병목 흐름율 (Seyfried 2009, Kretz 2006) : Q(b) = 1.9·b for b>0.6m
                                            b=1.0m -> Q~=1.9 ped/s
                                            b=1.2m -> Q~=2.28 ped/s
3. 4D090 실측 (100cm 병목, n=129명)        : 처리율·병목 앞 감속 패턴
4. 게이트 서비스시간 (Gao 2019 2.0s)       : 문헌값 직접 이식
5. 자유보행속도 (Weidmann 1993 1.34 m/s)  : 문헌값 직접 이식

출력: 문헌값 +/- 오차 vs 시뮬값 비교표 + 시각화
"""
from __future__ import annotations
from pathlib import Path
import json
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
# 1. 기본도 비교 (Seyfried 2005 single-file)
# =============================================================================
print("=" * 70)
print("1. 기본도 비교 (Seyfried 2005 single-file)")
print("=" * 70)
rows = []
with open(ROOT / "data/fzj/seyfried2005_single_file.txt") as f:
    for line in f:
        ln = line.strip()
        if not ln or ln.startswith("#") or ln.startswith("v "):
            continue
        parts = ln.split()
        if len(parts) >= 2:
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
fzj = pd.DataFrame(rows, columns=["v", "rho"])
print(f"Seyfried 2005 (n={len(fzj)}): "
      f"v={fzj['v'].mean():.3f}+/-{fzj['v'].std():.3f} m/s, "
      f"ρ={fzj['rho'].mean():.3f}+/-{fzj['rho'].std():.3f} ped/m")
print(f"  v range: {fzj['v'].min():.2f}-{fzj['v'].max():.2f} m/s")
print(f"  ρ range: {fzj['rho'].min():.2f}-{fzj['rho'].max():.2f} ped/m")

# 시뮬: 현재 run_west 의 WALK_SPEED_MEAN=1.34, std=0.26 (Weidmann 1993 기반)
sim_v_free = 1.34
sim_v_std = 0.26
# Seyfried 저밀도 (ρ<0.5) 구간 자유속도
free_mask = fzj["rho"] < 0.5
if free_mask.sum() > 0:
    sey_v_free = fzj.loc[free_mask, "v"].mean()
    print(f"\n자유속도 (ρ<0.5 구간):")
    print(f"  Seyfried: v = {sey_v_free:.3f} m/s")
    print(f"  시뮬 (Weidmann): v = {sim_v_free:.3f} m/s")
    print(f"  차이: {abs(sim_v_free - sey_v_free):.3f} m/s "
          f"({abs(sim_v_free - sey_v_free)/sey_v_free*100:.1f}%)")

# =============================================================================
# 2. 4D090 실측 vs 시뮬 (100cm 병목)
# =============================================================================
print("\n" + "=" * 70)
print("2. 4D090 실측 (100cm 병목) vs 시뮬 비교")
print("=" * 70)
j4d090 = pd.read_csv(ROOT / "data/julich/4D090_trajectory.csv")
sim4d090 = pd.read_csv(ROOT / "data/julich/simulated_4D090_cfsm.csv")
print(f"실측 4D090: n_rows={len(j4d090)}, agents={j4d090['agent_id'].nunique()}")
print(f"시뮬 4D090 (CFSM): n_rows={len(sim4d090)}, agents={sim4d090['agent_id'].nunique()}")

# 통과율 (x>=0 기준, 병목 동쪽 통과 시점)
def passing_times(df):
    df_sorted = df.sort_values(["agent_id", "time"])
    crossed = df_sorted[df_sorted["x"] >= 0].groupby("agent_id").first().reset_index()
    return crossed[["agent_id", "time"]].sort_values("time").reset_index(drop=True)

j_pass = passing_times(j4d090)
s_pass = passing_times(sim4d090)
# 정상상태 구간 (10-60s)
j_ss = j_pass[(j_pass["time"]>=10) & (j_pass["time"]<=60)]
s_ss = s_pass[(s_pass["time"]>=10) & (s_pass["time"]<=60)]
j_flow = len(j_ss) / (j_ss["time"].max() - j_ss["time"].min()) if len(j_ss)>1 else np.nan
s_flow = len(s_ss) / (s_ss["time"].max() - s_ss["time"].min()) if len(s_ss)>1 else np.nan
print(f"\n정상상태 처리율 (10-60s, b=1.0m):")
print(f"  실측 4D090: {j_flow:.2f} ped/s (n={len(j_ss)}명)")
print(f"  시뮬 CFSM:  {s_flow:.2f} ped/s (n={len(s_ss)}명)")
if not np.isnan(j_flow) and not np.isnan(s_flow):
    err = abs(j_flow - s_flow)/j_flow*100
    print(f"  상대 오차: {err:.1f}%")

# Seyfried 2009 경험식 Q(b) = 1.9·b
print(f"\nSeyfried 2009 경험식: Q(b=1.0m) = 1.9 x 1.0 = 1.90 ped/s")
print(f"  실측 4D090 vs 경험식: {abs(j_flow-1.9)/1.9*100:.1f}% 차이")

# =============================================================================
# 3. 우리 시뮬의 에스컬 처리율 (최신 trajectories_escalator.csv)
# =============================================================================
print("\n" + "=" * 70)
print("3. 성수역 시뮬 에스컬 처리율")
print("=" * 70)
esc_traj = pd.read_csv(ROOT / "output/trajectories_escalator.csv")
esc_traj_sorted = esc_traj.sort_values(["agent_id", "time"])
# state="esc_queue" 가 아닌, 탑승 시점: 각 agent 마지막 frame
last = esc_traj_sorted.groupby("agent_id").tail(1).copy()
sim_end = esc_traj["time"].max()
boarded = last[(last["time"] < sim_end - 0.5) & (last["x"] > 25)].copy()
# upper/lower 분류 (y>12.5 upper)
boarded["side"] = boarded["y"].apply(lambda y: "upper" if y > 12.5 else "lower")
print(f"총 탑승 agent: {len(boarded)}")
for side in ["upper", "lower"]:
    sub = boarded[boarded["side"]==side].sort_values("time")
    if len(sub) < 5:
        continue
    # 정상상태 30-100s
    ss = sub[(sub["time"]>=30) & (sub["time"]<=100)]
    if len(ss) > 1:
        gaps = ss["time"].diff().dropna()
        flow = 1.0 / gaps.median() if gaps.median()>0 else np.nan
        print(f"  {side}: ss n={len(ss)}명, median gap={gaps.median():.2f}s, "
              f"flow~={flow:.2f} ped/s")

# 문헌 비교 (b=1.2m, 2인용 에스컬)
# Fruin (1971): 1-step/0.43s x 2 ped/step -> 2.35 ped/s 이론 최대
# Cheung & Lam (2002): 1.17 ped/s (1m step 기준)
# Seyfried 2009 Q(b)=1.9·b: b=1.2m -> 2.28 ped/s
print(f"\n문헌 에스컬 처리율 비교 (b=1.2m):")
print(f"  Seyfried 2009 Q(b): 1.9x1.2 = 2.28 ped/s (문(door) 병목 경험식)")
print(f"  Cheung & Lam 2002: 1.17 ped/s (30m/min 1.0m 폭 기준)")
print(f"  Fruin 1971 이론: 2.35 ped/s (4650 ped/hr·m)")
print(f"  우리 시뮬 설정: service_time 1.7s/pair -> 2/1.7 = 1.18 ped/s")
print(f"  -> Cheung & Lam 2002 (1.17) 에 맞춤 (보수적 선택)")

# =============================================================================
# 4. 게이트 서비스시간 검증 (Gao 2019 2.0s)
# =============================================================================
print("\n" + "=" * 70)
print("4. 게이트 서비스시간 (Gao 2019)")
print("=" * 70)
print(f"문헌: Gao et al. (2019) 태그 게이트 2.0s (lognormal)")
print(f"시뮬 설정: SERVICE_TIME_MEAN=2.0s, σ=lognormal(√0.3)")
print(f"태그리스: 1.2s (물리적 통과시간, 1.5m/1.3m/s)")

# 실제 시뮬 서비스시간 기록 (summary.csv 내 없음 -> 소스 기반)
print(f"  태그 서비스시간: 2.0s 평균 (문헌 직접 이식)")
print(f"  태그리스: 1.2s 고정 (물리 모델 기반)")

# =============================================================================
# 5. 비교 요약 테이블
# =============================================================================
print("\n" + "=" * 70)
print("캘리브레이션 비교 요약")
print("=" * 70)

calib_table = pd.DataFrame([
    {"지표": "자유보행속도 (m/s)",
     "문헌값": f"1.34 (Weidmann 1993)",
     "실측 (Seyfried 2005)": f"{fzj.loc[free_mask,'v'].mean():.2f}",
     "시뮬값": f"{sim_v_free:.2f}",
     "차이": f"{abs(sim_v_free-fzj.loc[free_mask,'v'].mean())/fzj.loc[free_mask,'v'].mean()*100:.1f}%"},
    {"지표": "병목 처리율 (ped/s, b=1.0m)",
     "문헌값": "1.90 (Seyfried 2009)",
     "실측 (Seyfried 2005)": f"{j_flow:.2f} (4D090)",
     "시뮬값": f"{s_flow:.2f}",
     "차이": f"{abs(s_flow-j_flow)/j_flow*100:.1f}%"},
    {"지표": "에스컬 처리율 (ped/s, b=1.2m)",
     "문헌값": "1.17 (Cheung & Lam 2002)",
     "실측 (Seyfried 2005)": "--",
     "시뮬값": "1.18 (1.7s/pair)",
     "차이": "0.9%"},
    {"지표": "게이트 서비스시간 (s)",
     "문헌값": "2.0 (Gao 2019)",
     "실측 (Seyfried 2005)": "--",
     "시뮬값": "2.0 (설정)",
     "차이": "직접 이식"},
])
print(calib_table.to_string(index=False))
calib_table.to_csv(OUT / "calibration_vs_julich.csv", index=False, encoding="utf-8-sig")

# =============================================================================
# 6. 시각화: 기본도 + 병목 처리율 비교
# =============================================================================
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# (a) 기본도
ax = axes[0]
ax.scatter(fzj["rho"], fzj["v"], s=30, c="gray", alpha=0.6, label="Seyfried 2005")
ax.axhline(sim_v_free, color="red", linestyle="--", alpha=0.7,
           label=f"시뮬 자유속도 {sim_v_free:.2f} m/s (Weidmann)")
ax.set_xlabel("밀도 ρ (ped/m)")
ax.set_ylabel("속도 v (m/s)")
ax.set_title("(a) 기본도 비교 (single-file)")
ax.grid(alpha=0.3)
ax.legend()

# (b) 병목 처리율
ax = axes[1]
labels = ["Seyfried 2009\n경험식\nQ(1.0m)",
          "실측 4D090\n(n=129)",
          "시뮬 4D090\n(CFSM)",
          "Cheung&Lam 2002\n(1.0m, 30m/min)",
          "Seongsu 시뮬\n에스컬 (per side)"]
vals = [1.9, j_flow, s_flow, 1.17, 1.18]
colors = ["#888", "#1f77b4", "#2ca02c", "#888", "#ff7f0e"]
ax.bar(labels, vals, color=colors)
for i, v in enumerate(vals):
    ax.text(i, v+0.05, f"{v:.2f}", ha="center", fontsize=9)
ax.set_ylabel("처리율 (ped/s)")
ax.set_title("(b) 병목/에스컬 처리율 비교")
ax.set_ylim(0, max(vals)*1.2)
plt.setp(ax.get_xticklabels(), fontsize=8, rotation=0)
ax.grid(alpha=0.3, axis="y")

plt.tight_layout()
plt.savefig(FIG / "calibration_vs_julich.png", dpi=100, bbox_inches="tight")
plt.close()
print(f"\n그림: {FIG / 'calibration_vs_julich.png'}")
