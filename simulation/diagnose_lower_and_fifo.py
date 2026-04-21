"""
1) lower 에스컬 실패 에이전트 궤적 분석 (벽에 비비는 패턴)
2) 에스컬 탑승 순서 FIFO 위반 패턴 확인
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
TRAJ = ROOT / "output" / "trajectories_escalator.csv"
FIG = ROOT / "figures" / "bottleneck" / "lower_failure_fifo.png"

df = pd.read_csv(TRAJ).sort_values(["agent_id", "time"]).reset_index(drop=True)
sim_end = df["time"].max()

# 각 에이전트 첫/마지막 위치
first = df.groupby("agent_id").head(1).rename(columns={"x": "x0", "y": "y0", "time": "t0"})
last = df.groupby("agent_id").tail(1).rename(columns={"x": "xL", "y": "yL", "time": "tL"})
ag = first[["agent_id", "x0", "y0", "t0"]].merge(
    last[["agent_id", "xL", "yL", "tL"]], on="agent_id"
)

# 게이트 통과 후 목적지: y<12.5 → lower, y>12.5 → upper (게이트 y 기준)
# 게이트 x=12 통과 = serviced. post-gate y로 sides 판별.
# 여기선 spawn 위치 y로 보자 (계단 spawn: upper y=15~18, lower y=8~11)
ag["origin"] = ag["y0"].apply(lambda y: "upper_stair" if y > 12.5 else "lower_stair")
# 탑승 여부 (마지막 x > 30 이면 에스컬 근접 = 탑승)
ag["boarded"] = (ag["tL"] < sim_end - 0.2) & (ag["xL"] > 30)
# 끝 위치 기준 side (에스컬 y 기준)
ag["end_side"] = ag["yL"].apply(lambda y: "upper" if y > 12.5 else "lower")

print("=" * 60)
print("[1] 에이전트 경로별 결과")
print("=" * 60)
crosstab = pd.crosstab([ag["origin"], ag["end_side"]], ag["boarded"])
print(crosstab)

# lower escalator 탑승 성공 / 실패 구분
lower_attempts = ag[ag["end_side"] == "lower"]
print(f"\nlower side 도달: {len(lower_attempts)}명")
print(f"  탑승 성공: {(lower_attempts['boarded']).sum()}")
print(f"  실패 (벽에 비빔 등): {(~lower_attempts['boarded']).sum()}")

# 실패 에이전트 궤적 관찰
failed = lower_attempts[~lower_attempts["boarded"]]
print(f"\n실패 에이전트 끝 위치 분포:")
print(failed[["xL", "yL"]].describe())

# 벽 비빔: 끝 위치가 corridor 경계 (y=0 또는 y=-1, x=28~33 근처) 또는 funnel 벽
# Corridor: x=28~40, y=-1~0
# funnel 대각 벽: x=24.8~27.9, y=0.3~3.2 (lower)
# 즉 y=0 선을 따라 x=28 근처에서 정체하는 에이전트

# 실패한 에이전트 샘플 궤적 추출
failed_ids = failed["agent_id"].head(8).tolist()
lower_success_ids = lower_attempts[lower_attempts["boarded"]]["agent_id"].head(4).tolist()

# 2) FIFO 분석: staging 진입 시간 vs 탑승 시간 비교
# boarded agent의 tL = escalator 탑승 시각 (시뮬에서 remove된 시각)
# upper 에스컬 탑승자 중 t_arrive (approach 근처 도달) 순서 vs t_board(탑승) 순서
# t_arrive = 에이전트가 x>=25 에 처음 도달한 시각 (approach 근처 = 병목 진입)
approach_arrival = df[df["x"] >= 28].groupby("agent_id").head(1)[["agent_id", "time"]].rename(columns={"time": "t_arr"})
ag = ag.merge(approach_arrival, on="agent_id", how="left")

# upper escalator 탑승자만 비교
up_boarded = ag[(ag["boarded"]) & (ag["end_side"] == "upper")].copy()
up_boarded = up_boarded.sort_values("tL").reset_index(drop=True)
up_boarded["board_rank"] = up_boarded.index + 1
up_boarded = up_boarded.sort_values("t_arr").reset_index(drop=True)
up_boarded["arrive_rank"] = up_boarded.index + 1
up_boarded["rank_diff"] = up_boarded["board_rank"] - up_boarded["arrive_rank"]

print("\n" + "=" * 60)
print("[2] FIFO 위반 분석 (upper 에스컬 탑승자)")
print("=" * 60)
print(f"총 탑승자: {len(up_boarded)}")
print(f"도착 순서와 탑승 순서 차이 분포:")
print(up_boarded["rank_diff"].describe())
print(f"\nFIFO 완벽 일치 (|diff|=0): {(up_boarded['rank_diff'].abs() == 0).sum()}")
print(f"순위 3위 이상 역전: {(up_boarded['rank_diff'].abs() >= 3).sum()}")
print(f"순위 5위 이상 역전: {(up_boarded['rank_diff'].abs() >= 5).sum()}")
print(f"최대 역전: {up_boarded['rank_diff'].abs().max()}위")

# 예시: 가장 많이 "새치기" 당한 에이전트
overtaken = up_boarded[up_boarded["rank_diff"] > 0].sort_values("rank_diff", ascending=False).head(5)
print(f"\n가장 많이 밀린 에이전트 (도착 빨랐지만 늦게 탑승):")
print(overtaken[["agent_id", "t_arr", "tL", "arrive_rank", "board_rank", "rank_diff"]].to_string(index=False))

# 3) 시각화
fig, axes = plt.subplots(2, 2, figsize=(13, 10))

# (a) lower 실패 궤적
ax = axes[0, 0]
for aid in failed_ids:
    g = df[df["agent_id"] == aid]
    ax.plot(g["x"], g["y"], "-", alpha=0.5, linewidth=1.0)
    ax.scatter(g["x"].iloc[0], g["y"].iloc[0], s=20, marker=">", color="green", zorder=3)
    ax.scatter(g["x"].iloc[-1], g["y"].iloc[-1], s=40, marker="X", color="red", zorder=3)
# 벽 표시
ax.axhline(0, color="black", linewidth=2, alpha=0.3)
ax.axhline(-1, color="black", linewidth=1, alpha=0.3)
# funnel 대각
ax.plot([24.8, 27.7], [3.2, 0.3], "k-", linewidth=2, alpha=0.4)
# 에스컬 wp
ax.scatter([33], [-0.5], s=100, marker="*", color="red", zorder=5, label="에스컬 lower")
# capture
ax.axvspan(31.5, 33, ymin=0, ymax=0.2, color="blue", alpha=0.15, label="capture")
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(a) lower 에스컬 실패 궤적 8명 (빨강=끝 위치)")
ax.set_xlim(20, 35)
ax.set_ylim(-2, 10)
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (b) lower 성공 궤적 (비교)
ax = axes[0, 1]
for aid in lower_success_ids:
    g = df[df["agent_id"] == aid]
    ax.plot(g["x"], g["y"], "-", alpha=0.6, linewidth=1.2)
    ax.scatter(g["x"].iloc[0], g["y"].iloc[0], s=20, marker=">", color="green", zorder=3)
    ax.scatter(g["x"].iloc[-1], g["y"].iloc[-1], s=40, marker="X", color="blue", zorder=3)
ax.axhline(0, color="black", linewidth=2, alpha=0.3)
ax.axhline(-1, color="black", linewidth=1, alpha=0.3)
ax.plot([24.8, 27.7], [3.2, 0.3], "k-", linewidth=2, alpha=0.4)
ax.scatter([33], [-0.5], s=100, marker="*", color="red", zorder=5)
ax.axvspan(31.5, 33, ymin=0, ymax=0.2, color="blue", alpha=0.15)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(b) lower 에스컬 성공 궤적 4명")
ax.set_xlim(20, 35)
ax.set_ylim(-2, 10)
ax.grid(alpha=0.3)

# (c) FIFO 위반 (탑승 순위 vs 도착 순위)
ax = axes[1, 0]
ax.scatter(up_boarded["arrive_rank"], up_boarded["board_rank"],
           s=15, alpha=0.6)
ax.plot([0, len(up_boarded)], [0, len(up_boarded)], "r--", alpha=0.5, label="완벽 FIFO")
ax.set_xlabel("approach 도착 순위")
ax.set_ylabel("에스컬 탑승 순위")
ax.set_title(f"(c) upper 탑승 FIFO 분석 (최대 역전 {up_boarded['rank_diff'].abs().max()}위)")
ax.legend()
ax.grid(alpha=0.3)

# (d) rank_diff 분포
ax = axes[1, 1]
ax.hist(up_boarded["rank_diff"], bins=20, color="steelblue", alpha=0.7, edgecolor="black")
ax.axvline(0, color="red", linestyle="--", label="FIFO")
ax.set_xlabel("탑승순위 - 도착순위 (+: 새치기당함, -: 새치기함)")
ax.set_ylabel("에이전트 수")
ax.set_title("(d) 순위 차이 분포")
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(FIG, dpi=100)
plt.close()
print(f"\n그림: {FIG}")
