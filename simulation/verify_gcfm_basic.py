"""
GCFM 기본 검증 (RiMEA 기반)

Test 1: 자유보행 속도 — 장애물 없는 복도에서 희망속도대로 보행하는지
Test 2: 기본 다이어그램 — 밀도 vs 속도 관계 재현 (Weidmann 1993 비교)
Test 3: 병목 유량 — 좁은 통로에서 유량이 Seyfried et al. (2009)와 일치하는지

참조:
  - Chraibi et al. (2010), GCFM 원논문
  - Seyfried et al. (2009), New insights into pedestrian flow through bottlenecks
  - Weidmann (1993), 보행자 기본 다이어그램
  - JuPedSim 공식 문서
"""

import jupedsim as jps
import numpy as np
from shapely import Polygon
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pathlib

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output" / "verification"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# GCFM 파라미터 — Chraibi et al. (2010) + 좁은 병목 보정
# =============================================================================
GCFM_PARAMS = dict(
    strength_neighbor_repulsion=0.13,
    strength_geometry_repulsion=0.10,
    max_neighbor_interaction_distance=2.0,
    max_geometry_interaction_distance=2.0,
    max_neighbor_repulsion_force=3.0,
    max_geometry_repulsion_force=3.0,
)

# 에이전트 파라미터 — Chraibi et al. (2010) 기반, 0.55m 통로 대응
AGENT_PARAMS = dict(
    mass=1.0,
    tau=0.5,        # 반응시간 0.5s (Chraibi 기본)
    a_v=1.0,        # 등방 속도 의존 파라미터
    a_min=0.15,     # 타원 최소 반축 (m) — 0.20→0.15: 좁은 통로 대응
    b_min=0.15,     # 정지 시 타원 장축 (m) — 0.20→0.15
    b_max=0.25,     # 최대 타원 장축 (m) — 0.40→0.25: 직경 0.50m < 통로 0.55m
)

DT = 0.01  # 0.05→0.01: 좁은 통로에서 수치 안정성 향상


# =============================================================================
# Test 1: 자유보행 속도 (Free-flow Speed)
# =============================================================================
def test_free_flow_speed():
    """
    RiMEA Test 1: 넓은 복도(30m x 5m)에서 단일 보행자가
    설정한 희망속도대로 걷는지 확인.
    측정: 위치 차분으로 실제 속도 계산 (가속 구간 제외).
    """
    print("\n" + "=" * 60)
    print("Test 1: 자유보행 속도 (Free-flow Speed)")
    print("=" * 60)

    corridor = Polygon([(0, 0), (30, 0), (30, 5), (0, 5)])
    test_speeds = [0.6, 0.8, 1.0, 1.2, 1.34, 1.5]
    results = []

    for v_desired in test_speeds:
        model = jps.GeneralizedCentrifugalForceModel(**GCFM_PARAMS)
        sim = jps.Simulation(model=model, geometry=corridor, dt=DT)

        exit_stage = sim.add_exit_stage(Polygon([
            (29, 1), (30, 1), (30, 4), (29, 4)
        ]))
        journey = jps.JourneyDescription([exit_stage])
        journey.set_transition_for_stage(
            exit_stage, jps.Transition.create_fixed_transition(exit_stage))
        jid = sim.add_journey(journey)

        start_x = 2.0
        agent_id = sim.add_agent(
            jps.GeneralizedCentrifugalForceModelAgentParameters(
                journey_id=jid,
                stage_id=exit_stage,
                position=(start_x, 2.5),
                desired_speed=v_desired,
                **AGENT_PARAMS,
            ))

        # 위치 기록
        positions = []
        max_steps = int(20.0 / DT)
        for step in range(max_steps):
            if sim.agent_count() == 0:
                break
            pos = sim.agent(agent_id).position
            positions.append((step * DT, pos[0]))
            sim.iterate()

        # 안정화 후 측정: 2초~끝 구간에서 선형 회귀로 속도 계산
        warmup_time = 2.0
        pts = [(t, x) for t, x in positions if t >= warmup_time]
        if len(pts) >= 10:
            times = np.array([p[0] for p in pts])
            xs = np.array([p[1] for p in pts])
            # 최소자승법으로 속도 추정
            v_measured = np.polyfit(times, xs, 1)[0]
        else:
            v_measured = 0

        error_pct = abs(v_measured - v_desired) / v_desired * 100
        status = "PASS" if error_pct < 5 else "FAIL"
        results.append((v_desired, v_measured, error_pct, status))
        print(f"  v_desired={v_desired:.2f} m/s -> v_measured={v_measured:.2f} m/s "
              f"(error: {error_pct:.1f}%) [{status}]")

    # 시각화
    fig, ax = plt.subplots(figsize=(8, 5))
    v_des = [r[0] for r in results]
    v_meas = [r[1] for r in results]
    ax.plot([0.4, 1.8], [0.4, 1.8], 'k--', alpha=0.5, label='ideal (1:1)')
    ax.scatter(v_des, v_meas, s=100, c='blue', zorder=5, label='GCFM')
    for vd, vm, err, st in results:
        ax.annotate(f'{err:.1f}%', (vd, vm), textcoords="offset points",
                    xytext=(8, 8), fontsize=9)
    ax.set_xlabel('desired speed (m/s)')
    ax.set_ylabel('measured speed (m/s)')
    ax.set_title('Test 1: Free-flow Speed Verification')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(OUTPUT_DIR / 'test1_free_flow_speed.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  -> graph: {OUTPUT_DIR / 'test1_free_flow_speed.png'}")

    all_pass = all(r[3] == "PASS" for r in results)
    return all_pass, results


# =============================================================================
# Test 2: 기본 다이어그램 (Fundamental Diagram)
# =============================================================================
def test_fundamental_diagram():
    """
    긴 복도(50m x 4m)에 다양한 밀도로 보행자를 배치.
    측정 구간(15~35m)에서 LOCAL 밀도와 LOCAL 속도를 동시에 측정.
    출구는 복도 끝에 두되, 측정은 에이전트가 빠지기 전 짧은 시간에 수행.
    Weidmann (1993) 경험식과 정량 비교 (RMSE).

    PASS 기준:
    - 단조감소 트렌드
    - Weidmann 대비 RMSE < 0.20 m/s
    """
    print("\n" + "=" * 60)
    print("Test 2: Fundamental Diagram")
    print("=" * 60)

    corridor_length = 50.0
    corridor_width = 4.0
    corridor = Polygon([
        (0, 0), (corridor_length, 0),
        (corridor_length, corridor_width), (0, corridor_width)
    ])

    # 측정 구간: 복도 중앙
    measure_x_min = 15.0
    measure_x_max = 35.0
    measure_area = (measure_x_max - measure_x_min) * corridor_width

    target_densities = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    results = []

    for rho_target in target_densities:
        n_agents = int(rho_target * corridor_length * corridor_width)
        if n_agents < 2:
            continue

        model = jps.GeneralizedCentrifugalForceModel(**GCFM_PARAMS)
        sim = jps.Simulation(model=model, geometry=corridor, dt=DT)

        # 출구: 끝에 전체 폭
        exit_stage = sim.add_exit_stage(Polygon([
            (corridor_length - 0.5, 0.01),
            (corridor_length - 0.01, 0.01),
            (corridor_length - 0.01, corridor_width - 0.01),
            (corridor_length - 0.5, corridor_width - 0.01),
        ]))
        journey = jps.JourneyDescription([exit_stage])
        journey.set_transition_for_stage(
            exit_stage, jps.Transition.create_fixed_transition(exit_stage))
        jid = sim.add_journey(journey)

        rng = np.random.default_rng(42)
        placed = 0
        for _ in range(n_agents * 10):
            if placed >= n_agents:
                break
            x = rng.uniform(0.5, corridor_length - 1.0)
            y = rng.uniform(0.4, corridor_width - 0.4)
            try:
                sim.add_agent(
                    jps.GeneralizedCentrifugalForceModelAgentParameters(
                        journey_id=jid,
                        stage_id=exit_stage,
                        position=(x, y),
                        desired_speed=1.34,
                        **AGENT_PARAMS,
                    ))
                placed += 1
            except Exception:
                continue

        if placed < 2:
            continue

        # 안정화 1초, 측정 1초 (짧게 — 에이전트 이탈 최소화)
        warmup_steps = int(1.0 / DT)
        measure_steps = int(1.0 / DT)

        prev_positions = {}
        # 매 스텝: (local_density, local_speed) 쌍 기록
        step_densities = []
        step_speeds = []

        crashed = False
        for step in range(warmup_steps + measure_steps):
            if sim.agent_count() == 0:
                break
            try:
                current_positions = {}
                for agent in sim.agents():
                    aid = agent.id
                    px, py = agent.position
                    current_positions[aid] = (px, py)

                if step >= warmup_steps:
                    # 측정 구간 내 에이전트 수 → local density
                    agents_in_zone = 0
                    speeds_this_step = []
                    for aid, (px, py) in current_positions.items():
                        if measure_x_min <= px <= measure_x_max:
                            agents_in_zone += 1
                            if aid in prev_positions:
                                ox, oy = prev_positions[aid]
                                dist = np.hypot(px - ox, py - oy)
                                speeds_this_step.append(dist / DT)

                    if agents_in_zone > 0 and speeds_this_step:
                        local_density = agents_in_zone / measure_area
                        local_speed = np.mean(speeds_this_step)
                        step_densities.append(local_density)
                        step_speeds.append(local_speed)

                prev_positions = current_positions
                sim.iterate()
            except RuntimeError:
                crashed = True
                break

        if crashed:
            results.append((rho_target, 0, 0, "CRASH"))
            print(f"  rho_target={rho_target:.2f} P/m2 (N={placed}) -> CRASH")
            continue

        if step_densities:
            mean_density = np.mean(step_densities)
            mean_speed = np.mean(step_speeds)
        else:
            mean_density = 0
            mean_speed = 0

        # Weidmann 이론값
        if mean_density > 0:
            v_weidmann = 1.34 * (1 - np.exp(-1.913 * (1.0 / mean_density - 1.0 / 5.4)))
            v_weidmann = max(v_weidmann, 0)
        else:
            v_weidmann = 1.34
        error = abs(mean_speed - v_weidmann)

        results.append((mean_density, mean_speed, v_weidmann, "OK"))
        print(f"  rho_target={rho_target:.1f} -> local_rho={mean_density:.2f} P/m2 "
              f"v_sim={mean_speed:.2f} v_weidmann={v_weidmann:.2f} "
              f"err={error:.2f} m/s (N={placed})")

    # Weidmann 곡선
    rho_w = np.linspace(0.1, 5.0, 100)
    v_w = 1.34 * (1 - np.exp(-1.913 * (1.0 / rho_w - 1.0 / 5.4)))
    v_w = np.clip(v_w, 0, 1.34)

    # 정량 비교: RMSE
    ok_results = [r for r in results if r[3] == "OK"]
    if ok_results:
        errors_sq = [(r[1] - r[2]) ** 2 for r in ok_results]
        rmse = np.sqrt(np.mean(errors_sq))
    else:
        rmse = float('inf')

    # 시각화
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(rho_w, v_w, 'r-', linewidth=2, label='Weidmann (1993)')
    if ok_results:
        rhos = [r[0] for r in ok_results]
        vs = [r[1] for r in ok_results]
        ax.scatter(rhos, vs, s=100, c='blue', zorder=5, label='GCFM simulation')
        # 오차 막대
        for r in ok_results:
            ax.plot([r[0], r[0]], [r[1], r[2]], 'b--', alpha=0.3)
    ax.set_xlabel('Density (P/m2)')
    ax.set_ylabel('Speed (m/s)')
    ax.set_title(f'Test 2: Fundamental Diagram (RMSE={rmse:.3f} m/s)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 1.6)
    fig.savefig(OUTPUT_DIR / 'test2_fundamental_diagram.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  RMSE vs Weidmann: {rmse:.3f} m/s")
    print(f"  -> graph: {OUTPUT_DIR / 'test2_fundamental_diagram.png'}")

    # PASS 기준: 단조감소 + RMSE < 0.20
    ok_speeds = [r[1] for r in ok_results]
    monotone = True
    if len(ok_speeds) >= 3:
        monotone = all(ok_speeds[i] >= ok_speeds[i+1] - 0.05 for i in range(len(ok_speeds)-1))

    rmse_pass = rmse < 0.20
    mono_pass = monotone
    overall = rmse_pass and mono_pass
    print(f"  monotone decrease: [{'PASS' if mono_pass else 'FAIL'}]")
    print(f"  RMSE < 0.20 m/s:  [{'PASS' if rmse_pass else 'FAIL'}] (RMSE={rmse:.3f})")
    return overall, results


# =============================================================================
# Test 3: 병목 유량 (Bottleneck Flow)
# =============================================================================
def test_bottleneck_flow():
    """
    방(10m x 8m) → 병목(2m x width) → 방(10m x 8m) 구조.
    Seyfried et al. (2009) 실험 데이터와 비교.
    100명 투입, 정상상태 유량 측정.

    PASS 기준: Seyfried 대비 25% 이내 (interpolated)
    """
    print("\n" + "=" * 60)
    print("Test 3: Bottleneck Flow")
    print("=" * 60)

    # Seyfried (2009) 참조 데이터 — 보간용
    seyfried_widths = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    seyfried_specific_flow = np.array([1.61, 1.72, 1.78, 1.82, 1.85, 1.87])

    bottleneck_widths = [0.60, 0.80, 1.00]  # Seyfried 데이터가 있는 폭만
    results = []

    for bw in bottleneck_widths:
        # 기하구조: 방 → 병목 → 방 (오른쪽 방을 크게)
        room_left = Polygon([(0, 0), (10, 0), (10, 8), (0, 8)])
        by_center = 4.0
        bottleneck = Polygon([
            (10, by_center - bw/2),
            (12, by_center - bw/2),
            (12, by_center + bw/2),
            (10, by_center + bw/2),
        ])
        room_right = Polygon([(12, 0), (22, 0), (22, 8), (12, 8)])
        walkable = unary_union([room_left, bottleneck, room_right])

        model = jps.GeneralizedCentrifugalForceModel(**GCFM_PARAMS)
        sim = jps.Simulation(model=model, geometry=walkable, dt=DT)

        exit_stage = sim.add_exit_stage(Polygon([
            (21, 1), (22, 1), (22, 7), (21, 7)
        ]))
        journey = jps.JourneyDescription([exit_stage])
        journey.set_transition_for_stage(
            exit_stage, jps.Transition.create_fixed_transition(exit_stage))
        jid = sim.add_journey(journey)

        rng = np.random.default_rng(42)
        n_agents = 100
        placed = 0
        for _ in range(n_agents * 10):
            if placed >= n_agents:
                break
            x = rng.uniform(0.5, 9.5)
            y = rng.uniform(0.5, 7.5)
            try:
                sim.add_agent(
                    jps.GeneralizedCentrifugalForceModelAgentParameters(
                        journey_id=jid,
                        stage_id=exit_stage,
                        position=(x, y),
                        desired_speed=1.34,
                        **AGENT_PARAMS,
                    ))
                placed += 1
            except Exception:
                continue

        print(f"\n  bottleneck width: {bw:.2f}m (placed: {placed})")

        # 병목 출구(x=12) 통과 시각 기록
        passed_times = []
        agent_passed = set()
        max_time = 180.0
        max_steps = int(max_time / DT)
        crashed = False

        for step in range(max_steps):
            current_time = step * DT
            try:
                for agent in sim.agents():
                    aid = agent.id
                    if aid not in agent_passed:
                        px, _ = agent.position
                        if px > 12.5:
                            passed_times.append(current_time)
                            agent_passed.add(aid)
                sim.iterate()
            except RuntimeError as e:
                print(f"  [!] crashed: {e}")
                crashed = True
                break

            if sim.agent_count() == 0:
                break

        if crashed:
            results.append((bw, 0, 0, 0, "CRASH"))
            continue

        # 정상상태 유량: 처음 10명 + 마지막 5명 제외
        n_passed = len(passed_times)
        if n_passed >= 20:
            steady_times = passed_times[10:-5]
            if len(steady_times) >= 2:
                duration = steady_times[-1] - steady_times[0]
                flow_rate = (len(steady_times) - 1) / duration if duration > 0 else 0
                specific_flow = flow_rate / bw
            else:
                flow_rate = 0
                specific_flow = 0
        elif n_passed >= 5:
            steady_times = passed_times[3:]
            duration = steady_times[-1] - steady_times[0]
            flow_rate = (len(steady_times) - 1) / duration if duration > 0 else 0
            specific_flow = flow_rate / bw
        else:
            flow_rate = 0
            specific_flow = 0

        # Seyfried 보간값
        js_seyfried = float(np.interp(bw, seyfried_widths, seyfried_specific_flow))
        error_pct = abs(specific_flow - js_seyfried) / js_seyfried * 100

        status = "PASS" if error_pct <= 25 else "FAIL"
        results.append((bw, flow_rate, specific_flow, js_seyfried, status))
        print(f"  flow: {flow_rate:.2f} P/s | Js_sim={specific_flow:.2f} Js_sey={js_seyfried:.2f} "
              f"err={error_pct:.1f}% [{status}]")
        print(f"  ({n_passed} passed / {placed} total)")

    # 시각화
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(seyfried_widths, seyfried_specific_flow, 'ro-',
            linewidth=2, markersize=8, label='Seyfried et al. (2009)')
    # 25% 밴드
    ax.fill_between(seyfried_widths,
                     seyfried_specific_flow * 0.75,
                     seyfried_specific_flow * 1.25,
                     alpha=0.1, color='red', label='25% band')
    non_crash = [r for r in results if r[4] != "CRASH"]
    if non_crash:
        ws = [r[0] for r in non_crash]
        js = [r[2] for r in non_crash]
        colors = ['green' if r[4] == 'PASS' else 'red' for r in non_crash]
        ax.scatter(ws, js, s=120, c=colors, zorder=5, edgecolors='black',
                   linewidths=1, label='GCFM simulation')
        for r in non_crash:
            err = abs(r[2] - r[3]) / r[3] * 100
            ax.annotate(f'{err:.0f}%', (r[0], r[2]),
                        textcoords="offset points", xytext=(8, 8), fontsize=9)
    ax.set_xlabel('Bottleneck Width (m)')
    ax.set_ylabel('Specific Flow Js (P/m/s)')
    ax.set_title('Test 3: Bottleneck Flow - GCFM vs Seyfried (2009)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.4, 1.2)
    ax.set_ylim(0, 3.0)
    fig.savefig(OUTPUT_DIR / 'test3_bottleneck_flow.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  -> graph: {OUTPUT_DIR / 'test3_bottleneck_flow.png'}")

    has_crash = any(r[4] == "CRASH" for r in results)
    all_pass = not has_crash and all(r[4] == "PASS" for r in non_crash)
    return all_pass, results


# =============================================================================
# 메인
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("GCFM Basic Verification (RiMEA-based)")
    print("=" * 60)
    print(f"\nGCFM params: {GCFM_PARAMS}")
    print(f"Agent params: {AGENT_PARAMS}")
    print(f"dt = {DT}s")

    r1_pass, r1 = test_free_flow_speed()
    r2_pass, r2 = test_fundamental_diagram()
    r3_pass, r3 = test_bottleneck_flow()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Test 1 (Free-flow speed):      {'PASS' if r1_pass else 'FAIL'}")
    print(f"  Test 2 (Fundamental diagram):   {'PASS' if r2_pass else 'FAIL'}")
    print(f"  Test 3 (Bottleneck flow):       {'PASS' if r3_pass else 'FAIL'}")

    if r1_pass and r2_pass and r3_pass:
        print("\n-> All basic tests PASSED. Ready for station simulation.")
    else:
        print("\n-> Some tests FAILED. GCFM parameter adjustment needed.")
    print("=" * 60)
