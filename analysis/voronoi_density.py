"""
PedPy (Voronoi) 기반 보행밀도 측정.

학술/실측 표준 (Steffen & Seyfried 2010, 율리히 PedPy):
- 각 보행자 주변에 Voronoi 셀 생성 → ρ_i = 1/(셀 면적)
- 측정 영역의 시공간 평균 = mean over (time, agent in zone)

비교 대상:
1. 현재 방식 (직사각형 21m² 평균) — Z_3B / Z_4B
2. Voronoi 방식 — 같은 영역 내

결과:
- output/molit/voronoi_vs_classical.csv
- figures/molit/voronoi_vs_classical.png
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pedpy
from shapely.geometry import Polygon

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
TRAJ = ROOT / "output" / "trajectories_escalator.csv"
OUT = ROOT / "results" / "molit"
FIG = ROOT / "figures" / "molit"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

print("[1] Trajectory 로딩")
df = pd.read_csv(TRAJ)
# PedPy 입력 형식: id, frame, x, y
fps = 10  # DT=0.1s 가정
df["frame"] = (df["time"] * fps).round().astype(int)
df_pp = df.rename(columns={"agent_id": "id"})[["id", "frame", "x", "y"]].copy()
df_pp = df_pp.drop_duplicates(subset=["id", "frame"]).sort_values(["frame", "id"])
print(f"  rows: {len(df_pp):,}, agents: {df_pp.id.nunique()}, frames: {df_pp.frame.nunique()}")

# PedPy TrajectoryData 객체 생성
traj_data = pedpy.TrajectoryData(data=df_pp, frame_rate=fps)

# 측정 영역 (Z_4B = exit4 대기, x=28~33, y=22~26.2)
zones = {
    "Z3B (exit1 대기)": Polygon([(28, -1.2), (33, -1.2), (33, 3), (28, 3)]),
    "Z4B (exit4 대기)": Polygon([(28, 22), (33, 22), (33, 26.2), (28, 26.2)]),
}

print("\n[2] Voronoi 밀도 계산 중...")
results = {}
for zname, zpoly in zones.items():
    measurement_area = pedpy.MeasurementArea(zpoly)
    # individual density via Voronoi
    individual = pedpy.compute_individual_voronoi_polygons(
        traj_data=traj_data,
        walkable_area=pedpy.WalkableArea(Polygon([(0,0),(50,0),(50,28),(0,28)])),
    )
    # density in measurement area (시공간 평균)
    density_voronoi = pedpy.compute_voronoi_density(
        individual_voronoi_data=individual,
        measurement_area=measurement_area,
    )
    # 결과: tuple (density_per_frame: DataFrame, individual_in_area: DataFrame)
    if isinstance(density_voronoi, tuple):
        density_df = density_voronoi[0]
    else:
        density_df = density_voronoi

    # 평균 / 최대
    if "density" in density_df.columns:
        d_mean = density_df["density"].mean()
        d_max = density_df["density"].max()
    else:
        # 컬럼명이 다를 수 있음
        col = [c for c in density_df.columns if c != "frame"][0]
        d_mean = density_df[col].mean()
        d_max = density_df[col].max()

    # Classical (고전 방식: agent 수 / 면적)
    area = zpoly.area
    pos_in_zone = []
    for fr in df_pp.frame.unique():
        sub = df_pp[df_pp.frame == fr]
        in_zone = sub[(sub.x>=zpoly.bounds[0]) & (sub.x<=zpoly.bounds[2]) &
                      (sub.y>=zpoly.bounds[1]) & (sub.y<=zpoly.bounds[3])]
        pos_in_zone.append(len(in_zone) / area)
    classical = pd.Series(pos_in_zone)

    print(f"\n[{zname}] (영역 {area:.1f} m²)")
    print(f"  classical 평균: {classical.mean():.3f} ped/m^2 (max {classical.max():.3f})")
    print(f"  Voronoi 평균: {d_mean:.3f} ped/m^2 (max {d_max:.3f})")
    print(f"  비율 V/C: {d_mean/classical.mean() if classical.mean()>0 else 0:.2f}x")

    results[zname] = {
        "area": area,
        "classical_mean": classical.mean(),
        "classical_max": classical.max(),
        "voronoi_mean": float(d_mean),
        "voronoi_max": float(d_max),
        "n_frames": len(classical),
    }

# 저장
import json as _j
(OUT / "voronoi_vs_classical.json").write_text(
    _j.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n저장: {OUT / 'voronoi_vs_classical.json'}")
