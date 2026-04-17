"""
진동/엉킴 정량 지표 계산.

scenario_setup.run_once() 가 반환한 RunResult.trajectories 를 받아
네 가지 지표를 계산한다:

  1. 방향 변화 빈도  (heading change rate, deg/s)
  2. 역방향 이동 비율 (backward velocity ratio)
  3. 평균 속도 (단순 지표; FD 편차는 density bin이 필요)
  4. 에스컬레이터 앞 1m × 3m 영역의 밀도 시계열

출력:
  dict 혹은 pandas-free summary (dataclass).
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict

from scenario_setup import EXIT_X, EXIT_Y_CENTER, RunResult


# =============================================================================
# 측정 영역 (에스컬레이터 앞)
# =============================================================================
# 1m × 3m 영역: x = 7.0~10.0 (에스컬레이터 앞 3m 깊이),
#               y = 4.0~6.0 (개구 주변 2m)
# 실제 prompt는 "1m × 3m" 라 했음. 여기서는 depth=3m, width=2m로 해석.
ZONE_X_MIN, ZONE_X_MAX = 7.0, 10.0
ZONE_Y_MIN, ZONE_Y_MAX = 4.0, 6.0
ZONE_AREA = (ZONE_X_MAX - ZONE_X_MIN) * (ZONE_Y_MAX - ZONE_Y_MIN)  # 6.0 m²


@dataclass
class Metrics:
    config_label: str
    arrival_rate: float
    seed: int

    # 1. heading change (deg/s per agent, then averaged)
    heading_change_rate_mean: float = 0.0
    heading_change_rate_p90: float = 0.0

    # 2. backward motion
    backward_ratio_mean: float = 0.0

    # 3. 평균 속도 (m/s, 전 에이전트 전 시간)
    speed_mean: float = 0.0
    speed_in_zone_mean: float = 0.0  # 측정 영역 안에서의 평균 속도 (FD 편차 참고)

    # 4. 밀도 시계열 (측정 영역)
    density_series_times: np.ndarray = field(default_factory=lambda: np.array([]))
    density_series_values: np.ndarray = field(default_factory=lambda: np.array([]))
    density_mean: float = 0.0
    density_max: float = 0.0

    # 메타
    n_agents: int = 0
    spawned: int = 0
    exited: int = 0
    wall_time: float = 0.0


# =============================================================================
# 지표 계산
# =============================================================================
def _unit_vec(vx, vy):
    mag = np.sqrt(vx * vx + vy * vy)
    if mag < 1e-6:
        return 0.0, 0.0, 0.0
    return vx / mag, vy / mag, mag


def compute_metrics(result: RunResult) -> Metrics:
    traj = result.trajectories  # (N, 6): [id, t, x, y, vx, vy]

    if len(traj) == 0:
        return Metrics(
            config_label=result.config_label,
            arrival_rate=result.arrival_rate,
            seed=result.seed,
            spawned=result.spawned,
            exited=result.exited,
            wall_time=result.wall_time,
        )

    ids = traj[:, 0].astype(int)
    ts = traj[:, 1]
    xs = traj[:, 2]
    ys = traj[:, 3]
    vxs = traj[:, 4]
    vys = traj[:, 5]

    # ---------------------------------------------------------------------
    # 1. 방향 변화율 (agent별 heading 변화 총각/총시간, deg/s)
    # ---------------------------------------------------------------------
    heading_rates = []
    for aid in np.unique(ids):
        mask = ids == aid
        t_a = ts[mask]
        vx_a = vxs[mask]
        vy_a = vys[mask]
        if len(t_a) < 3:
            continue
        # 속도가 0이 아닌 시점만
        valid = np.sqrt(vx_a ** 2 + vy_a ** 2) > 0.05
        if valid.sum() < 3:
            continue
        vx_v = vx_a[valid]
        vy_v = vy_a[valid]
        t_v = t_a[valid]
        headings = np.arctan2(vy_v, vx_v)  # rad
        dheading = np.diff(np.unwrap(headings))
        dt = np.diff(t_v)
        dt[dt < 1e-6] = np.nan
        rate_deg_per_s = np.abs(np.degrees(dheading) / dt)
        rate_deg_per_s = rate_deg_per_s[np.isfinite(rate_deg_per_s)]
        if len(rate_deg_per_s) > 0:
            heading_rates.append(np.mean(rate_deg_per_s))

    heading_rates = np.array(heading_rates) if heading_rates else np.array([0.0])
    heading_change_rate_mean = float(np.mean(heading_rates))
    heading_change_rate_p90 = float(np.percentile(heading_rates, 90))

    # ---------------------------------------------------------------------
    # 2. 역방향 이동 비율
    #    desired direction: agent -> exit center (EXIT_X, EXIT_Y_CENTER)
    #    actual velocity . desired < 0 인 시간 비율
    # ---------------------------------------------------------------------
    dx_goal = EXIT_X - xs
    dy_goal = EXIT_Y_CENTER - ys
    goal_mag = np.sqrt(dx_goal ** 2 + dy_goal ** 2)
    goal_mag[goal_mag < 1e-6] = 1e-6
    dot = (vxs * dx_goal + vys * dy_goal) / goal_mag  # scalar projection
    speed = np.sqrt(vxs ** 2 + vys ** 2)
    # 속도 정지(<0.05 m/s) 제외, desired 방향 반대 이동 기준
    moving = speed > 0.05
    backward_ratio_mean = float(np.mean((dot < 0)[moving])) if moving.any() else 0.0

    # ---------------------------------------------------------------------
    # 3. 평균 속도
    # ---------------------------------------------------------------------
    speed_mean = float(np.mean(speed[speed > 0.01])) if (speed > 0.01).any() else 0.0

    in_zone = (
        (xs >= ZONE_X_MIN) & (xs <= ZONE_X_MAX) &
        (ys >= ZONE_Y_MIN) & (ys <= ZONE_Y_MAX)
    )
    if in_zone.any():
        speed_in_zone_mean = float(np.mean(speed[in_zone & (speed > 0.01)]))
    else:
        speed_in_zone_mean = 0.0

    # ---------------------------------------------------------------------
    # 4. 측정 영역 밀도 시계열
    # ---------------------------------------------------------------------
    unique_t = np.unique(ts)
    density_values = []
    for t in unique_t:
        mask = (ts == t) & in_zone
        count = int(mask.sum())
        density_values.append(count / ZONE_AREA)
    density_values = np.array(density_values)

    density_mean = float(np.mean(density_values))
    density_max = float(np.max(density_values)) if len(density_values) else 0.0

    return Metrics(
        config_label=result.config_label,
        arrival_rate=result.arrival_rate,
        seed=result.seed,
        heading_change_rate_mean=heading_change_rate_mean,
        heading_change_rate_p90=heading_change_rate_p90,
        backward_ratio_mean=backward_ratio_mean,
        speed_mean=speed_mean,
        speed_in_zone_mean=speed_in_zone_mean,
        density_series_times=unique_t,
        density_series_values=density_values,
        density_mean=density_mean,
        density_max=density_max,
        n_agents=len(np.unique(ids)),
        spawned=result.spawned,
        exited=result.exited,
        wall_time=result.wall_time,
    )


def summarize(metrics_list: list) -> Dict:
    """여러 시드의 평균 요약."""
    if not metrics_list:
        return {}
    return {
        "config_label": metrics_list[0].config_label,
        "arrival_rate": metrics_list[0].arrival_rate,
        "n_seeds": len(metrics_list),
        "heading_change_mean": float(np.mean([m.heading_change_rate_mean for m in metrics_list])),
        "heading_change_p90": float(np.mean([m.heading_change_rate_p90 for m in metrics_list])),
        "backward_ratio": float(np.mean([m.backward_ratio_mean for m in metrics_list])),
        "speed_mean": float(np.mean([m.speed_mean for m in metrics_list])),
        "speed_in_zone": float(np.mean([m.speed_in_zone_mean for m in metrics_list])),
        "density_mean": float(np.mean([m.density_mean for m in metrics_list])),
        "density_max": float(np.mean([m.density_max for m in metrics_list])),
        "wall_time_mean": float(np.mean([m.wall_time for m in metrics_list])),
        "spawned_mean": float(np.mean([m.spawned for m in metrics_list])),
        "exited_mean": float(np.mean([m.exited for m in metrics_list])),
    }


def format_summary(summary: Dict) -> str:
    if not summary:
        return "(empty)"
    return (
        f"[{summary['config_label']}] rate={summary['arrival_rate']} "
        f"seeds={summary['n_seeds']}\n"
        f"  heading_change: mean={summary['heading_change_mean']:.1f} deg/s, "
        f"p90={summary['heading_change_p90']:.1f}\n"
        f"  backward_ratio: {summary['backward_ratio']:.3f}\n"
        f"  speed: global={summary['speed_mean']:.3f} m/s, "
        f"zone={summary['speed_in_zone']:.3f} m/s\n"
        f"  density (zone): mean={summary['density_mean']:.2f}, "
        f"max={summary['density_max']:.2f} ped/m^2\n"
        f"  flow: spawned={summary['spawned_mean']:.1f}, "
        f"exited={summary['exited_mean']:.1f}\n"
        f"  wall_time: {summary['wall_time_mean']:.1f}s"
    )


if __name__ == "__main__":
    from scenario_setup import StrategyConfig, run_once

    cfg = StrategyConfig(name="baseline")
    res = run_once(cfg, arrival_rate=2.0, sim_time=30.0, seed=0, quiet=False)
    m = compute_metrics(res)
    print(format_summary(summarize([m])))
