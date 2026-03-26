"""
CFSM V2 기본 검증 (RiMEA 기반)

Test 1: 자유보행 속도 — 희망속도대로 보행하는지
Test 2: 기본 다이어그램 — 밀도 vs 속도 (Weidmann 1993)
Test 3: 병목 유량 — Seyfried et al. (2009) 비교

참조:
  - Tordeux et al. (2016), CFSM 원논문
  - Xu et al. (2019), CFSM V2
  - Seyfried et al. (2009), 병목 유량
  - Weidmann (1993), 기본 다이어그램
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
# CFSM V2 파라미터 — Tordeux et al. (2016)
# =============================================================================
CFSM_AGENT_PARAMS = dict(
    time_gap=0.80,
    radius=0.15,
    strength_neighbor_repulsion=8.0,
    range_neighbor_repulsion=0.1,
    strength_geometry_repulsion=5.0,
    range_geometry_repulsion=0.02,
)

DT = 0.01


# =============================================================================
# Test 1: 자유보행 속도
# =============================================================================
def test_free_flow_speed():
    print("\n" + "=" * 60)
    print("Test 1: Free-flow Speed (CFSM V2)")
    print("=" * 60)

    corridor = Polygon([(0, 0), (30, 0), (30, 5), (0, 5)])
    test_speeds = [0.6, 0.8, 1.0, 1.2, 1.34, 1.5]
    results = []

    for v_desired in test_speeds:
        model = jps.CollisionFreeSpeedModelV2()
        sim = jps.Simulation(model=model, geometry=corridor, dt=DT)

        exit_stage = sim.add_exit_stage(Polygon([
            (29, 1), (30, 1), (30, 4), (29, 4)
        ]))
        journey = jps.JourneyDescription([exit_stage])
        journey.set_transition_for_stage(
            exit_stage, jps.Transition.create_fixed_transition(exit_stage))
        jid = sim.add_journey(journey)

        agent_id = sim.add_agent(
            jps.CollisionFreeSpeedModelV2AgentParameters(
                journey_id=jid,
                stage_id=exit_stage,
                position=(2.0, 2.5),
                desired_speed=v_desired,
                **CFSM_AGENT_PARAMS,
            ))

        positions = []
        max_steps = int(20.0 / DT)
        for step in range(max_steps):
            if sim.agent_count() == 0:
                break
            pos = sim.agent(agent_id).position
            positions.append((step * DT, pos[0]))
            sim.iterate()

        warmup_time = 2.0
        pts = [(t, x) for t, x in positions if t >= warmup_time]
        if len(pts) >= 10:
            times = np.array([p[0] for p in pts])
            xs = np.array([p[1] for p in pts])
            v_measured = np.polyfit(times, xs, 1)[0]
        else:
            v_measured = 0

        error_pct = abs(v_measured - v_desired) / v_desired * 100
        status = "PASS" if error_pct < 5 else "FAIL"
        results.append((v_desired, v_measured, error_pct, status))
        print(f"  v_desired={v_desired:.2f} -> v_measured={v_measured:.2f} "
              f"(error: {error_pct:.1f}%) [{status}]")

    # 시각화
    fig, ax = plt.subplots(figsize=(8, 5))
    v_des = [r[0] for r in results]
    v_meas = [r[1] for r in results]
    ax.plot([0.4, 1.8], [0.4, 1.8], 'k--', alpha=0.5, label='ideal (1:1)')
    ax.scatter(v_des, v_meas, s=100, c='blue', zorder=5, label='CFSM V2')
    for vd, vm, err, st in results:
        ax.annotate(f'{err:.1f}%', (vd, vm), textcoords="offset points",
                    xytext=(8, 8), fontsize=9)
    ax.set_xlabel('desired speed (m/s)')
    ax.set_ylabel('measured speed (m/s)')
    ax.set_title('Test 1: Free-flow Speed (CFSM V2)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(OUTPUT_DIR / 'cfsm_test1_free_flow_speed.png', dpi=150, bbox_inches='tight')
    plt.close()

    all_pass = all(r[3] == "PASS" for r in results)
    return all_pass, results


# =============================================================================
# Test 2: 기본 다이어그램
# =============================================================================
def test_fundamental_diagram():
    print("\n" + "=" * 60)
    print("Test 2: Fundamental Diagram (CFSM V2)")
    print("=" * 60)

    corridor_length = 50.0
    corridor_width = 4.0
    corridor = Polygon([
        (0, 0), (corridor_length, 0),
        (corridor_length, corridor_width), (0, corridor_width)
    ])

    measure_x_min = 15.0
    measure_x_max = 35.0
    measure_area = (measure_x_max - measure_x_min) * corridor_width

    target_densities = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    results = []

    for rho_target in target_densities:
        n_agents = int(rho_target * corridor_length * corridor_width)
        if n_agents < 2:
            continue

        model = jps.CollisionFreeSpeedModelV2()
        sim = jps.Simulation(model=model, geometry=corridor, dt=DT)

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
                    jps.CollisionFreeSpeedModelV2AgentParameters(
                        journey_id=jid, stage_id=exit_stage,
                        position=(x, y), desired_speed=1.34,
                        **CFSM_AGENT_PARAMS,
                    ))
                placed += 1
            except Exception:
                continue

        if placed < 2:
            continue

        warmup_steps = int(1.0 / DT)
        measure_steps = int(1.0 / DT)
        prev_positions = {}
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
                        step_densities.append(agents_in_zone / measure_area)
                        step_speeds.append(np.mean(speeds_this_step))

                prev_positions = current_positions
                sim.iterate()
            except RuntimeError:
                crashed = True
                break

        if crashed or not step_densities:
            results.append((rho_target, 0, 0, "CRASH"))
            print(f"  rho_target={rho_target:.2f} -> CRASH")
            continue

        mean_density = np.mean(step_densities)
        mean_speed = np.mean(step_speeds)

        if mean_density > 0:
            v_weidmann = 1.34 * (1 - np.exp(-1.913 * (1.0 / mean_density - 1.0 / 5.4)))
            v_weidmann = max(v_weidmann, 0)
        else:
            v_weidmann = 1.34

        results.append((mean_density, mean_speed, v_weidmann, "OK"))
        print(f"  rho={rho_target:.1f} -> local_rho={mean_density:.2f} "
              f"v_sim={mean_speed:.2f} v_weidmann={v_weidmann:.2f} (N={placed})")

    # RMSE
    ok_results = [r for r in results if r[3] == "OK"]
    if ok_results:
        rmse = np.sqrt(np.mean([(r[1] - r[2])**2 for r in ok_results]))
    else:
        rmse = float('inf')

    # 시각화
    rho_w = np.linspace(0.1, 5.0, 100)
    v_w = 1.34 * (1 - np.exp(-1.913 * (1.0 / rho_w - 1.0 / 5.4)))
    v_w = np.clip(v_w, 0, 1.34)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(rho_w, v_w, 'r-', linewidth=2, label='Weidmann (1993)')
    if ok_results:
        ax.scatter([r[0] for r in ok_results], [r[1] for r in ok_results],
                   s=100, c='blue', zorder=5, label='CFSM V2')
    ax.set_xlabel('Density (P/m2)')
    ax.set_ylabel('Speed (m/s)')
    ax.set_title(f'Test 2: Fundamental Diagram CFSM V2 (RMSE={rmse:.3f})')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 1.6)
    fig.savefig(OUTPUT_DIR / 'cfsm_test2_fundamental_diagram.png', dpi=150, bbox_inches='tight')
    plt.close()

    ok_speeds = [r[1] for r in ok_results]
    monotone = all(ok_speeds[i] >= ok_speeds[i+1] - 0.05
                   for i in range(len(ok_speeds)-1)) if len(ok_speeds) >= 3 else True
    overall = rmse < 0.20 and monotone
    print(f"\n  RMSE: {rmse:.3f} m/s [{'PASS' if rmse < 0.20 else 'FAIL'}]")
    print(f"  Monotone: [{'PASS' if monotone else 'FAIL'}]")
    return overall, results


# =============================================================================
# Test 3: 병목 유량
# =============================================================================
def test_bottleneck_flow():
    print("\n" + "=" * 60)
    print("Test 3: Bottleneck Flow (CFSM V2)")
    print("=" * 60)

    seyfried_widths = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    seyfried_js = np.array([1.61, 1.72, 1.78, 1.82, 1.85, 1.87])

    bottleneck_widths = [0.60, 0.80, 1.00]
    results = []

    for bw in bottleneck_widths:
        room_left = Polygon([(0, 0), (10, 0), (10, 8), (0, 8)])
        by_center = 4.0
        bottleneck = Polygon([
            (10, by_center - bw/2), (12, by_center - bw/2),
            (12, by_center + bw/2), (10, by_center + bw/2),
        ])
        room_right = Polygon([(12, 0), (22, 0), (22, 8), (12, 8)])
        walkable = unary_union([room_left, bottleneck, room_right])

        model = jps.CollisionFreeSpeedModelV2()
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
                    jps.CollisionFreeSpeedModelV2AgentParameters(
                        journey_id=jid, stage_id=exit_stage,
                        position=(x, y), desired_speed=1.34,
                        **CFSM_AGENT_PARAMS,
                    ))
                placed += 1
            except Exception:
                continue

        print(f"\n  bottleneck width: {bw:.2f}m (placed: {placed})")

        passed_times = []
        agent_passed = set()
        max_time = 180.0
        max_steps = int(max_time / DT)

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
            except RuntimeError:
                break
            if sim.agent_count() == 0:
                break

        n_passed = len(passed_times)
        if n_passed >= 20:
            steady = passed_times[10:-5]
            if len(steady) >= 2:
                duration = steady[-1] - steady[0]
                flow = (len(steady) - 1) / duration if duration > 0 else 0
                specific_flow = flow / bw
            else:
                specific_flow = 0
        else:
            specific_flow = 0

        js_seyfried = float(np.interp(bw, seyfried_widths, seyfried_js))
        error_pct = abs(specific_flow - js_seyfried) / js_seyfried * 100
        status = "PASS" if error_pct <= 10 else "FAIL"
        results.append((bw, specific_flow, js_seyfried, error_pct, status))
        print(f"  Js_sim={specific_flow:.2f} Js_sey={js_seyfried:.2f} "
              f"err={error_pct:.1f}% [{status}] ({n_passed}/{placed} passed)")

    # 시각화
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(seyfried_widths, seyfried_js, 'ro-', linewidth=2, markersize=8,
            label='Seyfried et al. (2009)')
    ax.fill_between(seyfried_widths, seyfried_js * 0.90, seyfried_js * 1.10,
                     alpha=0.1, color='red', label='10% band')
    non_crash = [r for r in results if r[4] != "CRASH"]
    if non_crash:
        ws = [r[0] for r in non_crash]
        js = [r[1] for r in non_crash]
        colors = ['green' if r[4] == 'PASS' else 'red' for r in non_crash]
        ax.scatter(ws, js, s=120, c=colors, zorder=5, edgecolors='black',
                   linewidths=1, label='CFSM V2')
    ax.set_xlabel('Bottleneck Width (m)')
    ax.set_ylabel('Specific Flow Js (P/m/s)')
    ax.set_title('Test 3: Bottleneck Flow - CFSM V2 vs Seyfried (2009)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.4, 1.2)
    ax.set_ylim(0, 3.0)
    fig.savefig(OUTPUT_DIR / 'cfsm_test3_bottleneck_flow.png', dpi=150, bbox_inches='tight')
    plt.close()

    all_pass = all(r[4] == "PASS" for r in results)
    return all_pass, results


# =============================================================================
# 겹침 체크 (V6 대응)
# =============================================================================
def test_overlap_check():
    print("\n" + "=" * 60)
    print("V6: Overlap Check (CFSM V2)")
    print("=" * 60)

    corridor = Polygon([(0, 0), (20, 0), (20, 4), (0, 4)])
    n_agents = int(1.5 * 20 * 4)
    r_agent = CFSM_AGENT_PARAMS["radius"]

    model = jps.CollisionFreeSpeedModelV2()
    sim = jps.Simulation(model=model, geometry=corridor, dt=DT)

    exit_stage = sim.add_exit_stage(Polygon([
        (19, 0.5), (20, 0.5), (20, 3.5), (19, 3.5)
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
        x = rng.uniform(0.5, 18.5)
        y = rng.uniform(0.5, 3.5)
        try:
            sim.add_agent(
                jps.CollisionFreeSpeedModelV2AgentParameters(
                    journey_id=jid, stage_id=exit_stage,
                    position=(x, y), desired_speed=1.34,
                    **CFSM_AGENT_PARAMS,
                ))
            placed += 1
        except Exception:
            continue

    print(f"  Placed {placed}/{n_agents} agents")

    max_overlap = 0.0
    overlap_count = 0
    total_checks = 0

    warmup_steps = int(2.0 / DT)
    max_steps = int(7.0 / DT)

    for step in range(max_steps):
        try:
            if step >= warmup_steps and step % 100 == 0 and sim.agent_count() >= 2:
                positions = np.array([a.position for a in sim.agents()])
                n = len(positions)
                for i in range(n):
                    for j in range(i + 1, n):
                        d = np.hypot(positions[i][0] - positions[j][0],
                                     positions[i][1] - positions[j][1])
                        overlap = max(0, 2 * r_agent - d)
                        total_checks += 1
                        if overlap > 0:
                            overlap_count += 1
                        if overlap > max_overlap:
                            max_overlap = overlap
            sim.iterate()
        except RuntimeError:
            break

    overlap_rate = overlap_count / total_checks * 100 if total_checks > 0 else 0
    print(f"  Total checks: {total_checks}")
    print(f"  Overlaps: {overlap_count} ({overlap_rate:.2f}%)")
    print(f"  Max overlap: {max_overlap*100:.1f} cm")

    if max_overlap < 0.01:
        print(f"  Result: PASS (collision-free)")
    elif max_overlap < 0.05:
        print(f"  Result: Level A (< 5cm)")
    else:
        print(f"  Result: Level C ({max_overlap*100:.1f}cm)")

    return max_overlap < 0.05, {"max_overlap": max_overlap, "overlap_count": overlap_count}


# =============================================================================
# 메인
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CFSM V2 Basic Verification")
    print("=" * 60)
    print(f"Agent params: {CFSM_AGENT_PARAMS}")
    print(f"dt = {DT}s")

    r1_pass, r1 = test_free_flow_speed()
    r2_pass, r2 = test_fundamental_diagram()
    r3_pass, r3 = test_bottleneck_flow()
    r6_pass, r6 = test_overlap_check()

    print("\n" + "=" * 60)
    print("CFSM V2 Verification Summary")
    print("=" * 60)
    print(f"  V1 (Free-flow speed):      {'PASS' if r1_pass else 'FAIL'}")
    print(f"  V2 (Fundamental diagram):   {'PASS' if r2_pass else 'FAIL'}")
    print(f"  V3 (Bottleneck flow):       {'PASS' if r3_pass else 'FAIL'}")
    print(f"  V6 (Overlap check):         {'PASS' if r6_pass else 'FAIL'}")

    all_pass = r1_pass and r2_pass and r3_pass and r6_pass
    if all_pass:
        print("\n-> All tests PASSED.")
    else:
        failed = []
        if not r1_pass: failed.append("V1")
        if not r2_pass: failed.append("V2")
        if not r3_pass: failed.append("V3")
        if not r6_pass: failed.append("V6")
        print(f"\n-> FAILED: {', '.join(failed)}")
    print("=" * 60)
