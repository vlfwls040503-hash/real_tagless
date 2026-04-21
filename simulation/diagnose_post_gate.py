"""
Post-gate trajectory only analysis
- pre-gate agents (spawn x<10) 제외, post-gate agents (첫 x=13.5 근처) 만 분석
- 벽 관통 여부 검사 (채널 벽 y=23.4~23.8 / y=1.2~1.6)
- 에스컬 접근 경로 품질
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
FIG = ROOT / "figures" / "bottleneck" / "post_gate_analysis.png"

df = pd.read_csv(TRAJ).sort_values(["agent_id", "time"]).reset_index(drop=True)
sim_end = df["time"].max()

# 각 agent 의 첫 위치 — post-gate agents 는 x=13.5~14 에서 시작
first = df.groupby("agent_id").head(1).copy()
# pre-gate: 계단 spawn (x=1.5~3.5) 또는 게이트 앞 대기 (x<13)
# post-gate: 게이트 통과 직후 spawn (x=13.5~14)
first["type"] = first["x"].apply(lambda x: "pre_gate" if x < 13 else ("post_gate" if 13 <= x <= 14.5 else "other"))
print(f"Agent 수 분류:")
print(first["type"].value_counts())

post_ids = first[first["type"] == "post_gate"]["agent_id"].tolist()
print(f"\npost-gate agents: {len(post_ids)}")
post = df[df["agent_id"].isin(post_ids)].copy()

# 끝 위치
last = post.groupby("agent_id").tail(1).copy()
print(f"\npost-gate 끝 x 분포:")
print(last.x.describe())

# 탑승 분류: 끝 위치 x > 25 = 에스컬 근처 도달
print(f"\n끝 x>25 (에스컬 근처): {(last.x>25).sum()}")
print(f"끝 x>28 (corridor 진입): {(last.x>28).sum()}")
print(f"끝 x>30: {(last.x>30).sum()}")
print(f"끝 x<20 (중간에서 멈춤): {(last.x<20).sum()}")

# 벽 관통 검사
# 채널 upper 벽: y=23.4~23.8, x=18~28
# 채널 lower 벽: y=1.2~1.6, x=18~28
# 이 벽 내부 좌표를 기록한 적이 있는가?
wall_penetration = post[
    ((post["x"] >= 18) & (post["x"] <= 28)) &
    (((post["y"] >= 23.4) & (post["y"] <= 23.8)) |
     ((post["y"] >= 1.2) & (post["y"] <= 1.6)))
]
print(f"\n채널 벽 관통 프레임: {len(wall_penetration)} ({len(wall_penetration)/len(post)*100:.2f}%)")
if len(wall_penetration) > 0:
    print(f"관통 agent 수: {wall_penetration['agent_id'].nunique()}")
    print(f"관통 위치 분포:")
    print(wall_penetration[["x","y"]].describe())

# 대합실 북쪽 경계 관통 (y=25 at x=12~28)
boundary_cross = post[
    ((post["x"] >= 12) & (post["x"] <= 28)) &
    ((post["y"] >= 25.0) & (post["y"] <= 25.1))
]
print(f"\n대합실 북쪽 경계(y=25, x=12~28) 관통 프레임: {len(boundary_cross)}")

# 시각화
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# (a) 샘플 궤적 10개
ax = axes[0, 0]
sample_ids = last.sort_values("time").head(20)["agent_id"].tolist()[:10]
for aid in sample_ids:
    g = post[post["agent_id"] == aid]
    ax.plot(g["x"], g["y"], "-", alpha=0.5, linewidth=1.0)
    ax.scatter(g["x"].iloc[0], g["y"].iloc[0], s=20, marker=">", color="green", zorder=3)
    ax.scatter(g["x"].iloc[-1], g["y"].iloc[-1], s=30, marker="X", color="red", zorder=3)
# 채널 벽 표시
ax.add_patch(plt.Rectangle((18, 23.4), 10, 0.4, color="gray", alpha=0.5, label="채널 벽"))
ax.add_patch(plt.Rectangle((18,  1.2), 10, 0.4, color="gray", alpha=0.5))
# corridor
ax.add_patch(plt.Rectangle((28, 25), 12, 1.2, color="lightblue", alpha=0.3, label="corridor"))
ax.add_patch(plt.Rectangle((28, -1.2), 12, 1.2, color="lightblue", alpha=0.3))
# 에스컬 wp
ax.scatter([33], [25.6], s=100, marker="*", color="red", zorder=5)
ax.scatter([33], [-0.6], s=100, marker="*", color="red", zorder=5)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(a) Post-gate 궤적 샘플 10개")
ax.set_xlim(12, 35)
ax.set_ylim(-3, 28)
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (b) 전체 끝 위치 히트맵
ax = axes[0, 1]
h, xe, ye = np.histogram2d(last.x, last.y, bins=[30, 30])
ax.imshow(h.T, origin="lower", extent=[xe[0], xe[-1], ye[0], ye[-1]],
          aspect="auto", cmap="hot")
ax.add_patch(plt.Rectangle((18, 23.4), 10, 0.4, edgecolor="cyan", fill=False, lw=1.5))
ax.add_patch(plt.Rectangle((18,  1.2), 10, 0.4, edgecolor="cyan", fill=False, lw=1.5))
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(b) Post-gate 끝 위치 히트맵")
ax.grid(alpha=0.3)

# (c) x 시간 vs 진행 (몇 명 선택)
ax = axes[1, 0]
for aid in sample_ids:
    g = post[post["agent_id"] == aid]
    ax.plot(g["time"], g["x"], alpha=0.5, linewidth=1.0)
ax.axhline(28, color="red", linestyle="--", alpha=0.5, label="corridor 시작 x=28")
ax.axhline(31.5, color="orange", linestyle="--", alpha=0.5, label="capture zone x=31.5")
ax.set_xlabel("시간 (s)")
ax.set_ylabel("x (m)")
ax.set_title("(c) 시간별 x 진행")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (d) 채널 안에서의 밀도 — 시간별 채널 내 agent 수
ax = axes[1, 1]
post["in_channel_upper"] = (post["x"]>=18) & (post["x"]<=28) & (post["y"]>=23.8) & (post["y"]<=25)
post["in_channel_lower"] = (post["x"]>=18) & (post["x"]<=28) & (post["y"]>=0) & (post["y"]<=1.2)
post["in_corridor_upper"] = (post["x"]>=28) & (post["x"]<=40) & (post["y"]>=25) & (post["y"]<=26.2)
post["in_corridor_lower"] = (post["x"]>=28) & (post["x"]<=40) & (post["y"]>=-1.2) & (post["y"]<=0)
post["t_bin"] = (post["time"] // 1.0) * 1.0
ct = post.groupby("t_bin").agg(
    ch_u=("in_channel_upper", "sum"),
    ch_l=("in_channel_lower", "sum"),
    co_u=("in_corridor_upper", "sum"),
    co_l=("in_corridor_lower", "sum"),
).reset_index()
ax.plot(ct["t_bin"], ct["ch_u"], label="채널 upper")
ax.plot(ct["t_bin"], ct["ch_l"], label="채널 lower")
ax.plot(ct["t_bin"], ct["co_u"], label="corridor upper", linestyle="--")
ax.plot(ct["t_bin"], ct["co_l"], label="corridor lower", linestyle="--")
ax.set_xlabel("시간 (s)")
ax.set_ylabel("구역 내 agent 수")
ax.set_title("(d) 시간별 구역 내 agent 수")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(FIG, dpi=100)
plt.close()
print(f"\n그림: {FIG}")
