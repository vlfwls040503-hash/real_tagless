"""
에스컬레이터 진입부 암묵적 병목 — 최소 재현 시나리오

목적: CFSM V2 기반 시뮬에서 agent가 좁은 에스컬레이터 입구로
수렴할 때 발생하는 **진동/엉킴 현상**을 정량 관측하고, 여러
해결 전략(깔때기 기하, 국소 속도 저하, AVM 교체 등)을 비교하기
위한 공통 테스트 베드.

설계:
  공간: 10m × 10m
  진입부: 한쪽 벽(x=10)의 중앙에 폭 1.0m 개구 (y=4.5~5.5)
  스폰: 반대쪽 벽(x=0~1)에서 에이전트 연속 유입
  목표: 개구(exit) 중심으로 전원 이동
  CFSM V2 기본 파라미터 (성수역 시뮬과 동일)

사용법:
  from scenario_setup import build_scenario, run_once
  result = run_once(strategy="baseline", arrival_rate=2.0,
                    sim_time=60.0, seed=0)

  result는 dict:
    - trajectories: [(agent_id, t, x, y, vx, vy), ...]
    - config: 실험 파라미터
    - meta: 소요 시간, 총 에이전트 수, 빠져나간 수 등
"""

from __future__ import annotations

import sys
import time as timer
import numpy as np
import pathlib
from dataclasses import dataclass, field
from typing import Callable, Optional

import jupedsim as jps
from shapely import Polygon


# =============================================================================
# 시나리오 공간 (10m × 10m 대합실 + 1m 폭 × 3m 연장 통로)
# =============================================================================
WIDTH = 10.0          # 대합실 x 방향 길이
HEIGHT = 10.0         # 대합실 y 방향 길이
EXIT_WIDTH = 1.0      # 에스컬레이터 진입부 폭
EXIT_Y_CENTER = 5.0   # 개구 중심 y
EXIT_X = 10.0         # 개구는 x=10 오른쪽 벽

EXIT_Y_LOW = EXIT_Y_CENTER - EXIT_WIDTH / 2
EXIT_Y_HIGH = EXIT_Y_CENTER + EXIT_WIDTH / 2

# 에스컬레이터 통로 (개구 뒤 연장)
CORRIDOR_LEN = 3.0
CORRIDOR_END = WIDTH + CORRIDOR_LEN  # = 13.0
EXIT_STAGE_X_MIN = CORRIDOR_END - 0.5
EXIT_STAGE_X_MAX = CORRIDOR_END

SPAWN_X = 0.5         # 스폰 x 위치
SPAWN_Y_RANGE = (2.5, 7.5)  # 스폰 y 범위 (폭 5m — 넓게 유입)

# =============================================================================
# CFSM V2 기본 파라미터 (성수역 시뮬과 동일)
# =============================================================================
CFSM_TIME_GAP = 0.80
CFSM_RADIUS = 0.15
CFSM_V0_MEAN = 1.34
CFSM_V0_STD = 0.26
CFSM_V0_MIN = 0.8
CFSM_V0_MAX = 1.5

CFSM_STRENGTH_NEIGHBOR = 8.0
CFSM_RANGE_NEIGHBOR = 0.1
CFSM_STRENGTH_GEOMETRY = 5.0
CFSM_RANGE_GEOMETRY = 0.02

DT_DEFAULT = 0.05


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass
class StrategyConfig:
    """전략별 파라미터를 담는 구조체."""
    name: str = "baseline"
    dt: float = DT_DEFAULT
    time_gap: float = CFSM_TIME_GAP
    radius: float = CFSM_RADIUS
    v0_mean: float = CFSM_V0_MEAN
    strength_neighbor: float = CFSM_STRENGTH_NEIGHBOR
    range_neighbor: float = CFSM_RANGE_NEIGHBOR
    # 전략 A: 깔때기 벽 좌표 (Polygon 리스트). 빈 리스트면 비활성.
    funnel_obstacles: list = field(default_factory=list)
    # 전략 B: 국소 속도 감소 함수. 신호: (x, y) -> v_scaled.
    speed_modifier: Optional[Callable[[float, float], float]] = None
    # 전략 D: 모델 선택 ("CFSM" | "AVM")
    model: str = "CFSM"

    def label(self) -> str:
        return self.name


@dataclass
class RunResult:
    """한 번의 시뮬 실행 결과."""
    config_label: str
    arrival_rate: float
    sim_time: float
    seed: int
    trajectories: np.ndarray  # (N, 6): [id, t, x, y, vx, vy]
    spawned: int
    exited: int
    wall_time: float


# =============================================================================
# 기하구조
# =============================================================================
def build_geometry(extra_obstacles: list | None = None):
    """
    10m x 10m 영역, 오른쪽 벽에 폭 1m 개구(y=4.5~5.5).
    extra_obstacles: 전략 A 깔때기 벽 등 추가 장애물.

    반환:
      walkable: Shapely Polygon (JuPedSim geometry용)
      exit_polygon: Shapely Polygon (exit_stage용, 개구 안쪽 1m 깊이)
    """
    # 대합실(10x10) + 에스컬레이터 통로(1m × 3m) ㄷ자 형태
    outer = Polygon([
        (0, 0),
        (WIDTH, 0),
        (WIDTH, EXIT_Y_LOW),
        (CORRIDOR_END, EXIT_Y_LOW),
        (CORRIDOR_END, EXIT_Y_HIGH),
        (WIDTH, EXIT_Y_HIGH),
        (WIDTH, HEIGHT),
        (0, HEIGHT),
    ])

    walkable = outer
    if extra_obstacles:
        for obs in extra_obstacles:
            if obs.is_valid and obs.area > 0:
                walkable = walkable.difference(obs)

    # Exit Polygon: 통로 끝 (x=12.5~13.0)
    exit_polygon = Polygon([
        (EXIT_STAGE_X_MIN, EXIT_Y_LOW + 0.01),
        (EXIT_STAGE_X_MAX, EXIT_Y_LOW + 0.01),
        (EXIT_STAGE_X_MAX, EXIT_Y_HIGH - 0.01),
        (EXIT_STAGE_X_MIN, EXIT_Y_HIGH - 0.01),
    ])

    return walkable, exit_polygon


# =============================================================================
# 에이전트 파라미터
# =============================================================================
def sample_v0(rng):
    v = rng.normal(CFSM_V0_MEAN, CFSM_V0_STD)
    return float(np.clip(v, CFSM_V0_MIN, CFSM_V0_MAX))


def spawn_agent(sim, journey_id, stage_id, rng, cfg: StrategyConfig):
    """
    스폰 영역 내 임의 위치에 에이전트 1명 추가.
    실패 시 None 반환.
    """
    y = rng.uniform(*SPAWN_Y_RANGE)
    x = SPAWN_X + rng.uniform(-0.2, 0.2)
    v0 = sample_v0(rng)

    if cfg.model == "AVM":
        # AVM agent 파라미터 (JuPedSim 1.3.x API)
        try:
            params = jps.AnticipationVelocityModelAgentParameters(
                position=(x, y),
                journey_id=journey_id,
                stage_id=stage_id,
                desired_speed=v0,
                radius=cfg.radius,
            )
        except Exception:
            # 버전 호환 fallback
            return None
    else:
        params = jps.CollisionFreeSpeedModelV2AgentParameters(
            position=(x, y),
            journey_id=journey_id,
            stage_id=stage_id,
            desired_speed=v0,
            radius=cfg.radius,
            time_gap=cfg.time_gap,
            strength_neighbor_repulsion=cfg.strength_neighbor,
            range_neighbor_repulsion=cfg.range_neighbor,
            strength_geometry_repulsion=CFSM_STRENGTH_GEOMETRY,
            range_geometry_repulsion=CFSM_RANGE_GEOMETRY,
        )
    try:
        return sim.add_agent(params)
    except Exception:
        return None


# =============================================================================
# 시뮬레이션 1회 실행
# =============================================================================
def run_once(cfg: StrategyConfig,
             arrival_rate: float = 2.0,
             sim_time: float = 60.0,
             seed: int = 0,
             quiet: bool = True) -> RunResult:
    """한 개 전략 × 유입률 × 시드에 대한 시뮬 1회 실행."""
    t0 = timer.time()
    rng = np.random.default_rng(seed)

    walkable, exit_poly = build_geometry(extra_obstacles=cfg.funnel_obstacles)

    # 모델 선택
    if cfg.model == "AVM":
        try:
            model = jps.AnticipationVelocityModel()
        except Exception as e:
            raise RuntimeError(f"AVM not available in this JuPedSim: {e}")
    else:
        model = jps.CollisionFreeSpeedModelV2()

    sim = jps.Simulation(model=model, geometry=walkable, dt=cfg.dt)

    # Exit stage
    exit_id = sim.add_exit_stage(exit_poly)
    journey = jps.JourneyDescription([exit_id])
    journey_id = sim.add_journey(journey)

    # 도착 스케줄 (Poisson)
    total_arrivals = int(arrival_rate * sim_time)
    arrival_gaps = rng.exponential(1.0 / arrival_rate, size=total_arrivals)
    arrival_times = np.cumsum(arrival_gaps)
    arrival_times = arrival_times[arrival_times < sim_time]

    arrival_idx = 0
    total_steps = int(sim_time / cfg.dt)

    trajectories = []  # (id, t, x, y, vx, vy)
    spawned = 0
    exited = 0
    prev_positions = {}  # id -> (x, y)

    for step in range(total_steps):
        t = step * cfg.dt

        # 에이전트 스폰
        while arrival_idx < len(arrival_times) and arrival_times[arrival_idx] <= t:
            aid = spawn_agent(sim, journey_id, exit_id, rng, cfg)
            if aid is not None:
                spawned += 1
            arrival_idx += 1

        # 전략 B: 국소 속도 조정 (매 스텝)
        if cfg.speed_modifier is not None:
            for agent in sim.agents():
                px, py = agent.position
                scale = cfg.speed_modifier(px, py)
                base_v = agent.desired_speed
                # 원래 v0 저장이 없으므로 scale factor를 agent.model에 직접 주입
                try:
                    agent.model.desired_speed = base_v * scale
                except Exception:
                    pass  # 일부 버전은 read-only — 이 경우 알림만

        # 이전 위치 스냅샷
        current_positions = {}
        for agent in sim.agents():
            current_positions[agent.id] = agent.position

        sim.iterate()

        # 궤적 기록
        for agent in sim.agents():
            aid = agent.id
            px, py = agent.position
            prev = prev_positions.get(aid)
            if prev is not None:
                vx = (px - prev[0]) / cfg.dt
                vy = (py - prev[1]) / cfg.dt
            else:
                vx, vy = 0.0, 0.0
            trajectories.append((aid, t, px, py, vx, vy))
            prev_positions[aid] = (px, py)

        # exit 처리: JuPedSim은 자동 remove하지만 count 갱신 필요
        exited = spawned - len(list(sim.agents()))

    wall_time = timer.time() - t0

    traj_array = np.array(trajectories, dtype=float)

    result = RunResult(
        config_label=cfg.label(),
        arrival_rate=arrival_rate,
        sim_time=sim_time,
        seed=seed,
        trajectories=traj_array,
        spawned=spawned,
        exited=exited,
        wall_time=wall_time,
    )

    if not quiet:
        print(f"[{cfg.label()}] rate={arrival_rate} seed={seed} "
              f"spawned={spawned} exited={exited} "
              f"wall_time={wall_time:.1f}s")

    return result


# =============================================================================
# CLI 테스트용
# =============================================================================
if __name__ == "__main__":
    cfg = StrategyConfig(name="baseline")
    res = run_once(cfg, arrival_rate=2.0, sim_time=30.0, seed=0, quiet=False)
    print(f"Trajectory rows: {len(res.trajectories)}")
