"""
v12 궤적 기반 에스컬레이터 병목 분석 + 율리히 4D090 비교
- 1단계: v12 궤적에서 병목 특성 추출 (밀도·속도·처리율)
- 2단계: 율리히 4D090 (폭=100cm) 벤치마크와 비교 → 보정 필요 지점 식별
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
V12_TRAJ = ROOT / "output" / "trajectories_escalator.csv"
JULICH_4D090 = ROOT / "data" / "julich" / "4D090_trajectory.csv"
OUT_DIR = ROOT / "docs" / "bottleneck_analysis"
FIG_DIR = ROOT / "figures" / "bottleneck"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# v12 에스컬레이터 병목 앞 구역
# capture_zone: x=26.5~28.0, escalator_wp: (28.0, 25.5) upper / (28.0, -0.5) lower
# 병목 형성 관찰 구역: x=20~28, y ∈ upper: 22~26, lower: -1~3
ESC_UPPER_X = (20.0, 28.0)
ESC_UPPER_Y = (22.0, 26.0)
ESC_LOWER_X = (20.0, 28.0)
ESC_LOWER_Y = (-1.0, 3.0)

CAPTURE_X_EDGE = 26.5  # 큐 흡수 시작 지점
WP_X = 28.0           # 탑승 waypoint

# -----------------------------
# 1) v12 궤적 로드
# -----------------------------
print("[1/4] v12 궤적 로드 중...")
v12 = pd.read_csv(V12_TRAJ)
print(f"  총 {len(v12):,} rows, {v12['agent_id'].nunique()} agents, t={v12['time'].min():.1f}-{v12['time'].max():.1f}s")

# 속도 계산 (dt=0.1s 가정, 매 0.1초마다 기록)
v12 = v12.sort_values(["agent_id", "time"]).reset_index(drop=True)
v12["dx"] = v12.groupby("agent_id")["x"].diff()
v12["dy"] = v12.groupby("agent_id")["y"].diff()
v12["dt"] = v12.groupby("agent_id")["time"].diff()
v12["speed"] = np.sqrt(v12["dx"]**2 + v12["dy"]**2) / v12["dt"].replace(0, np.nan)
v12 = v12.dropna(subset=["speed"])
v12 = v12[v12["speed"] < 3.0]  # 텔레포트 제외

# -----------------------------
# 2) 에스컬레이터 앞 구역 추출 (upper/lower 통합)
# -----------------------------
print("[2/4] 에스컬레이터 앞 밀도/속도 분석 중...")

def in_esc_zone(df, x_range, y_range):
    return df[(df["x"] >= x_range[0]) & (df["x"] <= x_range[1]) &
              (df["y"] >= y_range[0]) & (df["y"] <= y_range[1])].copy()

upper = in_esc_zone(v12, ESC_UPPER_X, ESC_UPPER_Y)
lower = in_esc_zone(v12, ESC_LOWER_X, ESC_LOWER_Y)
upper["side"] = "upper"
lower["side"] = "lower"
esc = pd.concat([upper, lower], ignore_index=True)

# 2a) x축 구간별 평균 속도 (병목 앞 감속 패턴)
bins_x = np.arange(20, 28.5, 0.5)
esc["x_bin"] = pd.cut(esc["x"], bins_x, include_lowest=True)
speed_by_x = esc.groupby(["side", "x_bin"], observed=True)["speed"].agg(["mean", "std", "count"]).reset_index()
speed_by_x["x_center"] = speed_by_x["x_bin"].apply(lambda b: float((b.left + b.right) / 2)).astype(float)

# 2b) 구역별 순간 밀도 (0.5초 bin, 6m² waiting area)
esc["t_bin"] = (esc["time"] // 0.5) * 0.5
capture_zone_area = 1.5 * 3.0  # capture zone approx (x=26.5~28.0, y=+-1.5)
# 각 side별 시간 binning
density_series = {}
for side, sub in [("upper", upper), ("lower", lower)]:
    # capture zone 내 에이전트 수 (0.5초 간격)
    cap = sub[sub["x"] >= CAPTURE_X_EDGE].copy()
    cap["t_bin"] = (cap["time"] // 0.5) * 0.5
    cnt = cap.groupby("t_bin")["agent_id"].nunique().reset_index()
    cnt["density"] = cnt["agent_id"] / capture_zone_area
    density_series[side] = cnt

# 2c) 에스컬레이터 실효 처리율 (탑승 시점 간격)
# 에이전트의 마지막 궤적 위치가 에스컬 capture zone 내(x>=24)면 탑승으로 간주
v12_full = pd.read_csv(V12_TRAJ).sort_values(["agent_id", "time"])
last_frame = v12_full.groupby("agent_id").tail(1).copy()
sim_end = v12_full["time"].max()
boarded = last_frame[(last_frame["time"] < sim_end - 0.2) & (last_frame["x"] >= 24)].copy()
boarded["side"] = boarded["y"].apply(lambda y: "upper" if y > 12 else "lower")
arrivals = boarded.rename(columns={"time": "t_arr", "y": "y_arr"})[["agent_id", "t_arr", "y_arr", "side"]]
throughput = {}
for side in ["upper", "lower"]:
    arr = arrivals[arrivals["side"] == side].sort_values("t_arr")
    if len(arr) < 2:
        continue
    gaps = arr["t_arr"].diff().dropna()
    # steady-state: 40~100s
    arr_ss = arr[(arr["t_arr"] >= 40) & (arr["t_arr"] <= 100)]
    gaps_ss = arr_ss["t_arr"].diff().dropna()
    throughput[side] = {
        "n_arrivals": int(len(arr)),
        "mean_gap": float(gaps.mean()),
        "median_gap": float(gaps.median()),
        "effective_rate_ped_per_s": float(1.0 / gaps.median()) if gaps.median() > 0 else 0.0,
        "median_gap_ss": float(gaps_ss.median()) if len(gaps_ss) > 0 else float("nan"),
        "rate_ss": float(1.0 / gaps_ss.median()) if len(gaps_ss) > 0 and gaps_ss.median() > 0 else 0.0,
    }

# -----------------------------
# 3) 율리히 4D090 (폭 100cm) 로드 & 분석
# -----------------------------
print("[3/4] 율리히 4D090 분석 중...")
jul = pd.read_csv(JULICH_4D090)
jul["dx"] = jul.groupby("agent_id")["x"].diff()
jul["dy"] = jul.groupby("agent_id")["y"].diff()
jul["dt"] = jul.groupby("agent_id")["time"].diff()
jul["speed"] = np.sqrt(jul["dx"]**2 + jul["dy"]**2) / jul["dt"].replace(0, np.nan)
jul = jul.dropna(subset=["speed"])
jul = jul[jul["speed"] < 3.0]

# 4D090: 병목 x=0 에 있음 (footprint: x_edges -2~0)
# 병목 앞 대기 구역: x ∈ -2~0
jul_zone = jul[(jul["x"] >= -2.0) & (jul["x"] <= 0.0)].copy()
bins_jx = np.arange(-2.0, 0.01, 0.2)
jul_zone["x_bin"] = pd.cut(jul_zone["x"], bins_jx, include_lowest=True)
jul_speed_by_x = jul_zone.groupby("x_bin", observed=True)["speed"].agg(["mean", "std", "count"]).reset_index()
jul_speed_by_x["x_center"] = jul_speed_by_x["x_bin"].apply(lambda b: float((b.left + b.right) / 2)).astype(float)

# 율리히 병목 통과율 (x=0 통과)
jul_arrivals = jul[jul["x"] >= -0.1].groupby("agent_id").agg(t_arr=("time", "min")).reset_index()
jul_arrivals = jul_arrivals.sort_values("t_arr")
jul_gaps = jul_arrivals["t_arr"].diff().dropna()
# steady-state만: 10~60초 구간
jul_arrivals_ss = jul_arrivals[(jul_arrivals["t_arr"] >= 10) & (jul_arrivals["t_arr"] <= 60)]
jul_gaps_ss = jul_arrivals_ss["t_arr"].diff().dropna()
jul_throughput = {
    "n_passages": int(len(jul_arrivals)),
    "mean_gap": float(jul_gaps.mean()),
    "median_gap_ss": float(jul_gaps_ss.median()),
    "rate_ped_per_s_ss": float(1.0 / jul_gaps_ss.median()),
}

# 율리히 병목 앞 밀도 (capture zone 상응: x ∈ -1.5~0, y ∈ -1~1)
jul_cap = jul[(jul["x"] >= -1.5) & (jul["x"] <= 0.0) & (jul["y"] >= -1.0) & (jul["y"] <= 1.0)].copy()
jul_cap["t_bin"] = (jul_cap["time"] // 0.5) * 0.5
jul_density = jul_cap.groupby("t_bin")["agent_id"].nunique().reset_index()
jul_area = 1.5 * 2.0
jul_density["density"] = jul_density["agent_id"] / jul_area

# -----------------------------
# 4) 시각화 & 보고서
# -----------------------------
print("[4/4] 시각화 중...")

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# (a) 병목 앞 x-속도 프로파일 비교
ax = axes[0, 0]
for side in ["upper", "lower"]:
    d = speed_by_x[speed_by_x["side"] == side]
    ax.plot(d["x_center"], d["mean"], "-o", label=f"v12 {side}", markersize=4)
# 율리히는 x=-2~0이 우리 x=26~28에 대응
jul_scaled_x = jul_speed_by_x["x_center"] + 28.0
ax.plot(jul_scaled_x, jul_speed_by_x["mean"], "--s", color="gray", label="율리히 4D090 (x 평행이동)", markersize=4)
ax.axvline(CAPTURE_X_EDGE, color="red", linestyle=":", alpha=0.5, label="capture zone edge")
ax.axvline(WP_X, color="black", linestyle="--", alpha=0.5, label="WP(탑승)")
ax.set_xlabel("x 위치 (m)")
ax.set_ylabel("평균 속도 (m/s)")
ax.set_title("(a) 병목 앞 감속 프로파일")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (b) 시간별 capture zone 밀도
ax = axes[0, 1]
for side in ["upper", "lower"]:
    if side in density_series:
        d = density_series[side]
        ax.plot(d["t_bin"], d["density"], alpha=0.7, label=f"v12 {side}")
ax.plot(jul_density["t_bin"], jul_density["density"], color="gray", alpha=0.7, label="율리히 4D090")
ax.axhline(1.33, color="orange", linestyle="--", alpha=0.5, label="보행 LOS F 경계")
ax.axhline(2.17, color="red", linestyle="--", alpha=0.5, label="대기 LOS F 경계")
ax.set_xlabel("시간 (s)")
ax.set_ylabel("밀도 (ped/m²)")
ax.set_title("(b) 병목 앞 밀도 시계열")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (c) 기본다이어그램 (v12 vs 율리히)
ax = axes[1, 0]
# v12: 0.5초 bin 내 평균밀도 vs 평균속도 상관
# 각 sub-bin (side x t_bin) 의 mean speed 와 density 매칭
for side, sub_cap in [("upper", upper), ("lower", lower)]:
    cap = sub_cap[sub_cap["x"] >= CAPTURE_X_EDGE].copy()
    cap["t_bin"] = (cap["time"] // 0.5) * 0.5
    g = cap.groupby("t_bin").agg(density=("agent_id", "nunique"), speed=("speed", "mean")).reset_index()
    g["density"] = g["density"] / capture_zone_area
    ax.scatter(g["density"], g["speed"], s=6, alpha=0.4, label=f"v12 {side}")
# 율리히
jg = jul_cap.copy()
jg["t_bin"] = (jg["time"] // 0.5) * 0.5
jg = jg.groupby("t_bin").agg(density=("agent_id", "nunique"), speed=("speed", "mean")).reset_index()
jg["density"] = jg["density"] / jul_area
ax.scatter(jg["density"], jg["speed"], s=6, alpha=0.4, color="gray", label="율리히 4D090")
ax.set_xlabel("밀도 (ped/m²)")
ax.set_ylabel("평균 속도 (m/s)")
ax.set_title("(c) 기본다이어그램 (density-speed)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# (d) 에스컬레이터 도달 간격 분포
ax = axes[1, 1]
for side, thr in throughput.items():
    arr = arrivals[arrivals["side"] == side].sort_values("t_arr")
    gaps = arr["t_arr"].diff().dropna()
    ax.hist(gaps, bins=20, alpha=0.5, label=f"v12 {side} (n={len(gaps)})", density=True)
ax.hist(jul_gaps_ss, bins=20, alpha=0.5, color="gray", label=f"율리히 ss (n={len(jul_gaps_ss)})", density=True)
ax.axvline(0.85, color="red", linestyle="--", alpha=0.5, label="목표 0.85s/ped")
ax.set_xlabel("도달 간격 (s)")
ax.set_ylabel("밀도")
ax.set_title("(d) 탑승 간격 분포")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)
ax.set_xlim(0, 4)

plt.tight_layout()
fig_path = FIG_DIR / "bottleneck_v12_vs_julich.png"
plt.savefig(fig_path, dpi=100)
plt.close()

# -----------------------------
# 5) 보고서 생성
# -----------------------------
report = OUT_DIR / "v12_bottleneck_report.md"
lines = []
lines.append("# v12 에스컬레이터 병목 분석 보고서\n")
lines.append(f"분석일: 2026-04-22 | 궤적: `{V12_TRAJ.name}` | 율리히 벤치마크: `4D090_trajectory.csv` (폭 100cm)\n")

lines.append("## 1. v12 실효 처리율 (에스컬레이터 탑승)\n")
lines.append("| Side | 도달 수 | 평균 간격(s) | 중앙값(s) | 실효 처리율(ped/s) |")
lines.append("|---|---|---|---|---|")
for side, thr in throughput.items():
    lines.append(f"| {side} | {thr['n_arrivals']} | {thr['mean_gap']:.2f} | {thr['median_gap']:.2f} | {thr['effective_rate_ped_per_s']:.2f} |")
lines.append(f"\n목표값: 1.17 ped/s (Cheung & Lam 2002, 30m/min × 1.0m 폭)")
lines.append(f"문헌 일반값: 1.5–2.0 ped/s (CIBSE Guide D)\n")

lines.append("## 2. 율리히 4D090 벤치마크 (폭 100cm 정적 병목)\n")
lines.append(f"- 총 통과 {jul_throughput['n_passages']}명 / 75.16s")
lines.append(f"- 정상상태(10-60s) 중앙 간격: {jul_throughput['median_gap_ss']:.2f}s → **{jul_throughput['rate_ped_per_s_ss']:.2f} ped/s**")
lines.append(f"- 병목 앞 (x=-1.5~0) 피크 밀도: {jul_density['density'].max():.2f} ped/m²\n")

lines.append("## 3. v12 vs 율리히 비교\n")
v12_upper_rate = throughput.get("upper", {}).get("effective_rate_ped_per_s", 0)
v12_lower_rate = throughput.get("lower", {}).get("effective_rate_ped_per_s", 0)
lines.append(f"| 지표 | v12 upper | v12 lower | 율리히 4D090 | 갭 |")
lines.append(f"|---|---|---|---|---|")
lines.append(f"| 실효 처리율 (ped/s) | {v12_upper_rate:.2f} | {v12_lower_rate:.2f} | {jul_throughput['rate_ped_per_s_ss']:.2f} | {jul_throughput['rate_ped_per_s_ss']-max(v12_upper_rate,v12_lower_rate):+.2f} |")
up_peak = density_series.get("upper", pd.DataFrame({"density":[0]}))["density"].max()
lo_peak = density_series.get("lower", pd.DataFrame({"density":[0]}))["density"].max()
lines.append(f"| 피크 밀도 (ped/m²) | {up_peak:.2f} | {lo_peak:.2f} | {jul_density['density'].max():.2f} | — |\n")

lines.append("## 4. 보정 방향\n")
avg_rate = (v12_upper_rate + v12_lower_rate) / 2
target_rate = 1.17  # Cheung & Lam 2002
gap = target_rate - avg_rate
if gap > 0.1:
    lines.append(f"**v12 처리율이 목표보다 {gap:.2f} ped/s 낮음** → 서비스시간 단축 필요")
    lines.append(f"- 현재 ESCALATOR_SERVICE_TIME = 0.85s → 실효 {1/avg_rate:.2f}s 수준으로 밀림")
    lines.append(f"- 큐 흡수 로직 병목: QUEUE_ENTRY_MIN_GAP, ease-in 지연이 누적되어 처리율 저하")
    lines.append(f"- 제안: 에스컬레이터 큐 흡수 간격 하한 완화 + capture_zone 확장 테스트")
else:
    lines.append("처리율은 목표 근접. 피크 밀도 비교로 수렴 구간 검토 필요.")
lines.append("")
lines.append("## 5. 한계\n")
lines.append("- v12는 단일 런 (5 seeds 필요 시 재실행)")
lines.append("- 율리히 4D090은 정적 병목(문) 실험 → 에스컬레이터 특유의 '탑승 한 명씩' 동역학과 완전 일치하진 않음")
lines.append("- 하지만 수렴 구간 밀도·속도 프로파일은 직접 비교 가능\n")

lines.append(f"![bottleneck analysis]({fig_path.relative_to(ROOT)})\n")

report.write_text("\n".join(lines), encoding="utf-8")

# 요약 JSON도 저장
summary = {
    "v12_throughput": throughput,
    "julich_4D090_throughput": jul_throughput,
    "v12_peak_density_upper": float(up_peak),
    "v12_peak_density_lower": float(lo_peak),
    "julich_peak_density": float(jul_density["density"].max()),
    "target_rate_ped_per_s": 1.17,
    "gap_ped_per_s": float(target_rate - avg_rate),
}
(OUT_DIR / "v12_bottleneck_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n완료:")
print(f"  그림: {fig_path}")
print(f"  보고서: {report}")
print(f"  요약: {OUT_DIR / 'v12_bottleneck_summary.json'}")
