"""
v12 궤적 개별 문제점 진단
1) 역행 에이전트 (backward movement)
2) 측방향 퍼짐 (lateral spread / 옆으로 새기)
3) 에스컬 진입 각도 변화 (직선→꺾기 vs 완만한 곡선)
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
FIG_DIR = ROOT / "figures" / "bottleneck"
FIG_DIR.mkdir(parents=True, exist_ok=True)

print("[로드 중]")
df = pd.read_csv(TRAJ).sort_values(["agent_id", "time"]).reset_index(drop=True)

# 속도·방향 계산
df["dx"] = df.groupby("agent_id")["x"].diff()
df["dy"] = df.groupby("agent_id")["y"].diff()
df["dt"] = df.groupby("agent_id")["time"].diff()
df["speed"] = np.sqrt(df["dx"]**2 + df["dy"]**2) / df["dt"].replace(0, np.nan)

# -----------------------------
# 1) 역행 분석
# -----------------------------
# 에이전트는 x+ 방향으로 이동해야 함 (게이트 통과 후 에스컬 쪽)
# dx < 0 인 프레임 = 역행
backward = df[df["dx"] < -0.05].copy()  # 프레임당 5cm 이상 후퇴
forward_all = df[df["dx"].notna()].copy()

print(f"\n[1] 역행 분석")
print(f"  총 dx 프레임: {len(forward_all):,}")
print(f"  역행 프레임: {len(backward):,} ({len(backward)/len(forward_all)*100:.1f}%)")

# 에이전트별 역행량 집계
backward_by_agent = backward.groupby("agent_id").agg(
    n_backward=("dx", "count"),
    total_backward_dist=("dx", lambda s: -s.sum()),
    mean_x=("x", "mean"),
    mean_y=("y", "mean"),
).reset_index()
backward_by_agent = backward_by_agent.sort_values("total_backward_dist", ascending=False)

# 심각한 역행 에이전트 (후퇴 거리 > 0.5m)
severe_backward = backward_by_agent[backward_by_agent["total_backward_dist"] > 0.5]
print(f"  심각 역행 에이전트 (>0.5m): {len(severe_backward)}명")
print(f"  상위 10명:")
print(severe_backward.head(10).to_string(index=False))

# -----------------------------
# 2) 측방향 퍼짐 (lateral spread)
# -----------------------------
# 각 에이전트의 y 표준편차 (진로 안정성)
# 단방향 하차이므로 이상적으로는 y가 크게 변하지 않아야 함
lateral = df.groupby("agent_id").agg(
    y_std=("y", "std"),
    y_range=("y", lambda s: s.max() - s.min()),
    x_mean=("x", "mean"),
    n_frames=("time", "count"),
).reset_index()
# approach zone (x=20~26) 에서 측방향 흔들림 측정
approach = df[(df["x"] >= 20) & (df["x"] <= 26)].copy()
lateral_approach = approach.groupby("agent_id").agg(
    y_std_approach=("y", "std"),
    y_range_approach=("y", lambda s: s.max() - s.min()),
).reset_index()
lateral = lateral.merge(lateral_approach, on="agent_id", how="left")

print(f"\n[2] 측방향 퍼짐 (approach zone x=20~26)")
print(f"  평균 y 범위: {lateral['y_range_approach'].mean():.2f} m")
print(f"  90퍼센타일 y 범위: {lateral['y_range_approach'].quantile(0.9):.2f} m")
big_spread = lateral[lateral["y_range_approach"] > 2.0]
print(f"  큰 측방향 이동 (>2m): {len(big_spread)}명")

# -----------------------------
# 3) 에스컬 진입 각도 (꺾임 vs 곡선)
# -----------------------------
# capture zone 근처 (x=24~27) 에서 방향 변화
# 곡률: 인접 3프레임의 방향 변화 각도
near_esc = df[(df["x"] >= 24) & (df["x"] <= 27)].copy()
near_esc = near_esc.sort_values(["agent_id", "time"])
near_esc["dx2"] = near_esc.groupby("agent_id")["x"].diff()
near_esc["dy2"] = near_esc.groupby("agent_id")["y"].diff()
near_esc["heading"] = np.arctan2(near_esc["dy2"], near_esc["dx2"])
near_esc["heading_prev"] = near_esc.groupby("agent_id")["heading"].shift(1)
# 각도 차이 (절댓값, wrap-around 고려)
def angle_diff(a, b):
    d = a - b
    return np.arctan2(np.sin(d), np.cos(d))
near_esc["turn"] = np.abs(angle_diff(near_esc["heading"], near_esc["heading_prev"]))
# 급격한 꺾임 (프레임당 >30도)
sharp_turns = near_esc[near_esc["turn"] > np.pi / 6].copy()
print(f"\n[3] 에스컬 진입 구간 (x=24~27) 꺾임")
print(f"  분석 프레임 수: {near_esc['turn'].notna().sum():,}")
print(f"  급격 꺾임 (>30°): {len(sharp_turns):,} ({len(sharp_turns)/near_esc['turn'].notna().sum()*100:.1f}%)")
# 에이전트별 최대 꺾임
max_turn_by_agent = near_esc.groupby("agent_id")["turn"].max().reset_index()
max_turn_deg = np.degrees(max_turn_by_agent["turn"])
print(f"  에이전트당 최대 꺾임 평균: {max_turn_deg.mean():.1f}°")
print(f"  90퍼센타일: {max_turn_deg.quantile(0.9):.1f}°")

# -----------------------------
# 4) 시각화
# -----------------------------
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# (a) 역행 히트맵
ax = axes[0, 0]
if len(backward) > 0:
    h, xedges, yedges = np.histogram2d(backward["x"], backward["y"], bins=[40, 30])
    ax.imshow(h.T, extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
              origin="lower", aspect="auto", cmap="Reds")
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title(f"(a) 역행 발생 위치 히트맵 (n={len(backward):,})")
ax.axvspan(26.5, 28, alpha=0.2, color="blue", label="capture zone")
ax.legend()
ax.grid(alpha=0.3)

# (b) 심각 역행 에이전트 궤적 (상위 5명)
ax = axes[0, 1]
top_bw = severe_backward.head(5)["agent_id"].tolist()
for aid in top_bw:
    g = df[df["agent_id"] == aid]
    ax.plot(g["x"], g["y"], "-", alpha=0.6, linewidth=1.2, label=f"#{aid}")
    ax.scatter(g["x"].iloc[0], g["y"].iloc[0], s=30, marker=">", zorder=3)
    ax.scatter(g["x"].iloc[-1], g["y"].iloc[-1], s=50, marker="X", zorder=3)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(b) 심각 역행 에이전트 궤적 (상위 5명)")
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

# (c) y 변화 (측방향 퍼짐) 분포
ax = axes[1, 0]
ax.hist(lateral["y_range_approach"].dropna(), bins=30, color="steelblue", alpha=0.7)
ax.axvline(2.0, color="red", linestyle="--", label="큰 퍼짐 기준 (2m)")
ax.set_xlabel("approach zone 내 y 범위 (m)")
ax.set_ylabel("에이전트 수")
ax.set_title(f"(c) 측방향 흔들림 분포 (>2m: {len(big_spread)}명)")
ax.legend()
ax.grid(alpha=0.3)

# (d) 에스컬 진입 경로 샘플 (꺾임 큰 에이전트 vs 정상)
ax = axes[1, 1]
# 꺾임 큰 에이전트 상위 5명
top_turn = max_turn_by_agent.sort_values("turn", ascending=False).head(5)["agent_id"].tolist()
for aid in top_turn:
    g = df[(df["agent_id"] == aid) & (df["x"] >= 20)]
    if len(g) > 0:
        ax.plot(g["x"], g["y"], "-", alpha=0.7, linewidth=1.5, label=f"꺾임 #{aid}")
# 에스컬 waypoint
ax.scatter([28], [25.5], s=80, marker="*", color="red", zorder=5, label="에스컬 upper")
ax.scatter([28], [-0.5], s=80, marker="*", color="red", zorder=5)
ax.axvline(26.5, color="gray", linestyle=":", alpha=0.5)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("(d) 에스컬 진입 급꺾임 상위 5명")
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

plt.tight_layout()
fig_path = FIG_DIR / "trajectory_issues_diagnosis.png"
plt.savefig(fig_path, dpi=100)
plt.close()

# -----------------------------
# 5) 수치 요약 저장
# -----------------------------
summary = {
    "역행": {
        "total_frames": len(forward_all),
        "backward_frames": len(backward),
        "backward_ratio_pct": len(backward) / len(forward_all) * 100,
        "severe_backward_agents": len(severe_backward),
        "top5_agent_ids": severe_backward.head(5)["agent_id"].tolist(),
    },
    "측방향 퍼짐 (approach x=20~26)": {
        "mean_y_range": float(lateral["y_range_approach"].mean()),
        "p90_y_range": float(lateral["y_range_approach"].quantile(0.9)),
        "big_spread_over_2m": int(len(big_spread)),
    },
    "에스컬 진입 꺾임 (x=24~27)": {
        "sharp_turn_frames_pct": len(sharp_turns) / near_esc["turn"].notna().sum() * 100,
        "max_turn_mean_deg": float(max_turn_deg.mean()),
        "max_turn_p90_deg": float(max_turn_deg.quantile(0.9)),
    },
}
import json
(FIG_DIR.parent.parent / "docs" / "bottleneck_analysis" / "trajectory_issues_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)

print(f"\n완료: {fig_path}")
print(f"      {FIG_DIR.parent.parent / 'docs' / 'bottleneck_analysis' / 'trajectory_issues_summary.json'}")
