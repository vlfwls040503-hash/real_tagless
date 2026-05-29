"""
Voronoi 기반 격자 보행밀도 계산 모듈.

학술 표준 (Steffen & Seyfried 2010):
- 매 프레임 Voronoi tessellation
- 각 셀 밀도 = 1 / (셀 면적), max_density 로 클리핑
- 격자에 nearest-neighbor 매핑 (= Voronoi 셀 정의)
- 시간 평균 + 가우시안 스무딩
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import Voronoi, cKDTree
from scipy.ndimage import gaussian_filter
from shapely.geometry import Polygon, box


def voronoi_density_frame(positions: np.ndarray, bbox: tuple,
                          grid_res: float = 0.1,
                          max_density: float = 6.0) -> tuple:
    """단일 프레임의 Voronoi 기반 격자 밀도.

    positions : (N, 2) array — 보행자 좌표
    bbox      : (xmin, xmax, ymin, ymax)
    grid_res  : 격자 크기 (m)
    max_density : 셀 밀도 클리핑 상한 (ped/m²)

    Returns: (density_grid, x_edges, y_edges)
    """
    xmin, xmax, ymin, ymax = bbox
    xs = np.arange(xmin, xmax + grid_res, grid_res)
    ys = np.arange(ymin, ymax + grid_res, grid_res)
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    grid_pts = np.column_stack([XX.ravel(), YY.ravel()])
    grid_density = np.zeros(grid_pts.shape[0])

    if len(positions) < 4:
        return grid_density.reshape(YY.shape), xs, ys

    bbox_poly = box(xmin, ymin, xmax, ymax)
    try:
        vor = Voronoi(positions)
    except Exception:
        return grid_density.reshape(YY.shape), xs, ys

    cell_density = np.zeros(len(positions))  # default 0 (무한/빈 영역)
    for i, region_idx in enumerate(vor.point_region):
        region = vor.regions[region_idx]
        if -1 in region or len(region) == 0:
            continue  # 무한 영역 → 0 (가장자리)
        try:
            poly = Polygon([vor.vertices[v] for v in region])
            clipped = poly.intersection(bbox_poly)
            area = clipped.area
            if area > 1e-6:
                cell_density[i] = min(1.0 / area, max_density)
        except Exception:
            pass

    # 격자 점에 nearest neighbor → 너무 멀면 0 (빈 영역 투명)
    tree = cKDTree(positions)
    distances, nearest = tree.query(grid_pts)
    grid_density = cell_density[nearest]
    grid_density[distances > 1.5] = 0.0  # 1.5m 이상 멀면 빈 영역
    return grid_density.reshape(YY.shape), xs, ys


def time_averaged_density(traj_df: pd.DataFrame, bbox: tuple,
                          start_time: float, end_time: float,
                          grid_res: float = 0.1,
                          max_density: float = 6.0,
                          smooth_sigma_m: float = 0.3) -> tuple:
    """정상상태 시간 윈도우의 Voronoi 밀도 시간평균 + 가우시안 스무딩.

    traj_df: columns [time, agent_id, x, y]
    bbox: (xmin, xmax, ymin, ymax)
    Returns: (smoothed_density, x_edges, y_edges)
    """
    sub = traj_df[(traj_df["time"] >= start_time) &
                  (traj_df["time"] <= end_time)]
    times = sorted(sub["time"].unique())
    sum_grid = None
    n = 0
    for t in times:
        frame = sub[sub["time"] == t]
        positions = frame[["x", "y"]].values
        grid, xs, ys = voronoi_density_frame(
            positions, bbox, grid_res, max_density)
        if sum_grid is None:
            sum_grid = np.zeros_like(grid)
        sum_grid += grid
        n += 1

    avg = sum_grid / max(n, 1)
    sigma_grid = smooth_sigma_m / grid_res
    smoothed = gaussian_filter(avg, sigma=sigma_grid)
    return smoothed, xs, ys
