"""
베이스라인 + 전략 A~F 일괄 실행 및 지표 비교.

실행: py -3.12 run_experiments.py [--strategies A,B,C,D,E,F] [--fast]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time as timer

import numpy as np
from shapely import Polygon

from scenario_setup import (
    StrategyConfig, run_once,
    WIDTH, HEIGHT, EXIT_X, EXIT_Y_CENTER, EXIT_Y_LOW, EXIT_Y_HIGH, EXIT_WIDTH,
    CFSM_STRENGTH_NEIGHBOR, CFSM_RANGE_NEIGHBOR,
)
from metrics import compute_metrics, summarize, format_summary


HERE = pathlib.Path(__file__).parent
OUT_DIR = HERE / "results"
OUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# 공통 실험 파라미터
# =============================================================================
ARRIVAL_RATES = [2.0, 4.0, 6.0]  # 저/중/고 혼잡
SEEDS = [0, 1, 2]                # 반복 3회
SIM_TIME = 30.0                  # 짧은 런 (베이스라인 재현용)


# =============================================================================
# 전략 정의
# =============================================================================
def build_strategies():
    strategies = []

    # -------------------------------------------------------------------------
    # 기본(베이스라인)
    # -------------------------------------------------------------------------
    strategies.append(StrategyConfig(name="baseline"))

    # -------------------------------------------------------------------------
    # 전략 A: 깔때기 (funnel)
    # 입구(x=10) 앞에 비대칭 벽을 두어 agent를 정렬.
    # 깔때기 시작 거리(장벽 x) × 각도(깔때기 기울기)를 두 수준씩.
    # -------------------------------------------------------------------------
    def funnel_walls(depth, angle_deg):
        """
        depth: 깔때기 시작 x (작을수록 멀리서 시작)
              예: depth=3 → 벽이 x=7부터 시작해서 x=10까지.
        angle_deg: 깔때기 각도 (좌우 대칭).
              벽 끝 y간격 = EXIT_WIDTH=1m 유지, 벽 시작 y간격은
              EXIT_WIDTH + 2 * depth * tan(angle_deg).
        """
        half_end = EXIT_WIDTH / 2
        extra = depth * np.tan(np.radians(angle_deg))
        half_start = half_end + extra

        y_start_upper = EXIT_Y_CENTER + half_start
        y_start_lower = EXIT_Y_CENTER - half_start

        # 상단 벽 (두께 0.1m)
        upper = Polygon([
            (WIDTH - depth, y_start_upper),
            (WIDTH, EXIT_Y_HIGH),
            (WIDTH, HEIGHT),
            (WIDTH - depth, HEIGHT),
        ])
        # 하단 벽
        lower = Polygon([
            (WIDTH - depth, 0),
            (WIDTH, 0),
            (WIDTH, EXIT_Y_LOW),
            (WIDTH - depth, y_start_lower),
        ])
        return [upper, lower]

    strategies.append(StrategyConfig(
        name="A_funnel_3m_15deg",
        funnel_obstacles=funnel_walls(depth=3.0, angle_deg=15.0),
    ))
    strategies.append(StrategyConfig(
        name="A_funnel_5m_15deg",
        funnel_obstacles=funnel_walls(depth=5.0, angle_deg=15.0),
    ))
    strategies.append(StrategyConfig(
        name="A_funnel_3m_30deg",
        funnel_obstacles=funnel_walls(depth=3.0, angle_deg=30.0),
    ))

    # -------------------------------------------------------------------------
    # 전략 B: 국소 desired_speed 감소
    # -------------------------------------------------------------------------
    def make_speed_modifier_linear(center_x, center_y, r_inner, r_outer, v_min_scale):
        """중심에서 r_inner 이내: v_min_scale, r_outer 이상: 1.0, 사이 선형."""
        def modifier(x, y):
            r = np.hypot(x - center_x, y - center_y)
            if r >= r_outer:
                return 1.0
            if r <= r_inner:
                return v_min_scale
            frac = (r_outer - r) / (r_outer - r_inner)
            return 1.0 - frac * (1.0 - v_min_scale)
        return modifier

    strategies.append(StrategyConfig(
        name="B_speed_linear_1to3m_0.4",
        speed_modifier=make_speed_modifier_linear(
            EXIT_X, EXIT_Y_CENTER, r_inner=1.0, r_outer=3.0, v_min_scale=0.4),
    ))
    strategies.append(StrategyConfig(
        name="B_speed_linear_2to4m_0.5",
        speed_modifier=make_speed_modifier_linear(
            EXIT_X, EXIT_Y_CENTER, r_inner=2.0, r_outer=4.0, v_min_scale=0.5),
    ))

    # -------------------------------------------------------------------------
    # 전략 C: neighbor repulsion 재캘리브레이션
    # 현재 strength=8.0, range=0.1 기준 ±50%
    # -------------------------------------------------------------------------
    for mult in [0.5, 1.5, 2.0]:
        strategies.append(StrategyConfig(
            name=f"C_strength_x{mult}",
            strength_neighbor=CFSM_STRENGTH_NEIGHBOR * mult,
        ))
    for mult in [0.5, 2.0]:
        strategies.append(StrategyConfig(
            name=f"C_range_x{mult}",
            range_neighbor=CFSM_RANGE_NEIGHBOR * mult,
        ))

    # -------------------------------------------------------------------------
    # 전략 D: AVM 모델 교체
    # -------------------------------------------------------------------------
    strategies.append(StrategyConfig(name="D_AVM", model="AVM"))

    # -------------------------------------------------------------------------
    # 전략 E: dt 감소
    # -------------------------------------------------------------------------
    strategies.append(StrategyConfig(name="E_dt_0.025", dt=0.025))

    # -------------------------------------------------------------------------
    # 전략 F: 조합 (예비 — 최종은 비교 후 선정)
    # -------------------------------------------------------------------------
    strategies.append(StrategyConfig(
        name="F_funnel3m15_plus_dt0025",
        funnel_obstacles=funnel_walls(depth=3.0, angle_deg=15.0),
        dt=0.025,
    ))

    return strategies


# =============================================================================
# 실행
# =============================================================================
def run_strategy(cfg: StrategyConfig, rates, seeds, sim_time):
    all_summaries = []
    for rate in rates:
        metrics_list = []
        for seed in seeds:
            try:
                res = run_once(cfg, arrival_rate=rate, sim_time=sim_time, seed=seed)
            except Exception as e:
                print(f"  [FAIL] {cfg.label()} rate={rate} seed={seed}: {e}")
                continue
            m = compute_metrics(res)
            metrics_list.append(m)
        if metrics_list:
            s = summarize(metrics_list)
            all_summaries.append(s)
            print(format_summary(s))
            print("-" * 40)
    return all_summaries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default=None,
                    help="comma-separated filter e.g. baseline,A_funnel_3m_15deg")
    ap.add_argument("--fast", action="store_true",
                    help="seed 1개, sim_time 15s (빠른 확인용)")
    args = ap.parse_args()

    strategies = build_strategies()
    if args.strategies:
        want = set(s.strip() for s in args.strategies.split(","))
        strategies = [s for s in strategies if s.name in want]

    rates = ARRIVAL_RATES
    seeds = SEEDS
    sim_time = SIM_TIME
    if args.fast:
        seeds = [0]
        sim_time = 15.0

    all_results = {}
    t0 = timer.time()
    for cfg in strategies:
        print("=" * 60)
        print(f"STRATEGY: {cfg.label()} (model={cfg.model}, dt={cfg.dt})")
        print("=" * 60)
        summaries = run_strategy(cfg, rates, seeds, sim_time)
        all_results[cfg.label()] = summaries

    total_wall = timer.time() - t0
    print(f"\n전체 실행 시간: {total_wall:.1f}s")

    # Save JSON
    out_json = OUT_DIR / "summary.json"
    serializable = {}
    for label, summaries in all_results.items():
        serializable[label] = summaries
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"  저장: {out_json}")


if __name__ == "__main__":
    main()
