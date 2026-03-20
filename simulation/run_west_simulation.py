"""
성수역 서쪽 대합실 보행자 시뮬레이션 v5

변경 이력 (v4 → v5):
  1. 도착 모델: 균일 생성 → 열차 도착 군집(Platoon) 모델
     - 열차 간격 180초, 1회 하차 40명 (포아송 분포)
     - 계단에서 15초에 걸쳐 분산 도착
  2. 게이트 선택: 선행연구 기반 파라미터 (Haghani & Sarvi, 2016)
     - beta_dist = -0.25, beta_queue = -0.3
  3. 다단계 의사결정 모델 (핑퐁 효과 제거):
     - 관성(Inertia): 전환 비용 C_switch 추가
     - Lock-in: 게이트 3m 이내 진입 시 경로 변경 비활성화
     - 재평가 주기: 0.5초 → 3.0초
  4. 게이트 근처 time_gap 감소 (1.06 → 0.5): 바짝 붙어 서는 심리 반영

모델: CollisionFreeSpeedModelV2 (CFSM V2)
"""

import jupedsim as jps
import numpy as np
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely import Polygon

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from seongsu_west import (
    calculate_gate_positions, build_geometry,
    GATE_X, GATE_LENGTH, GATE_PASSAGE_WIDTH, GATE_HOUSING_WIDTH,
    BARRIER_Y_BOTTOM, BARRIER_Y_TOP,
    CONCOURSE_LENGTH, CONCOURSE_WIDTH, NOTCH_X, NOTCH_Y,
    STAIRS, EXITS, STRUCTURES, N_GATES,
)

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# =============================================================================
# 시뮬레이션 파라미터
# =============================================================================
SIM_TIME = 300.0        # 5분 (열차 1~2회 도착 관찰)
DT = 0.05

# =============================================================================
# 도착 모델 (열차 군집)
# =============================================================================
TRAIN_INTERVAL = 180.0   # 열차 도착 간격 (초) - 2호선 피크 약 2.5~3분
TRAIN_ALIGHTING = 40     # 1회 도착 하차 인원 (서쪽 계단 이용분)
PLATOON_SPREAD = 15.0    # 계단에서 대합실 진입까지 분산 시간 (초)
FIRST_TRAIN_TIME = 5.0   # 첫 열차 도착 시각

# =============================================================================
# CFSM V2 핵심 파라미터 (선행연구 기반)
# =============================================================================
PED_RADIUS = 0.225               # Weidmann 1993
PED_SPEED_MEAN = 1.34            # Weidmann 1993
PED_SPEED_STD = 0.26
PED_TIME_GAP = 1.06              # Tordeux et al. 2015
PED_TIME_GAP_QUEUE = 0.5         # 게이트 근처 대기열: 바짝 붙어 서는 심리
PED_STRENGTH_NEIGHBOR = 8.0      # Tordeux et al. 2015
PED_RANGE_NEIGHBOR = 0.1
PED_STRENGTH_GEOMETRY = 5.0
PED_RANGE_GEOMETRY = 0.02

# =============================================================================
# 서비스 시간 (태그 사용자)
# =============================================================================
SERVICE_MU = 0.35
SERVICE_SIGMA = 0.35

# =============================================================================
# 게이트 선택 모델 (Haghani & Sarvi, 2016 기반)
# =============================================================================
BETA_DIST = -0.25          # 거리 민감도 (선행연구: -0.21 ~ -0.31)
BETA_QUEUE = -0.3          # 대기열 민감도 (선행연구: -0.14 ~ -0.60)
VISION_RADIUS = 8.0        # 보행자 시야 반경 (m)

# 다단계 의사결정
C_SWITCH = 1.5             # 전환 비용 (관성): 새 게이트 효용이 이만큼 높아야 변경
LOCK_IN_DISTANCE = 3.0     # 게이트 이 거리 이내 → 경로 변경 비활성화 (m)
REROUTE_INTERVAL = 3.0     # 경로 재평가 주기 (초)

# 게이트 통과 구간
GATE_ZONE_X_START = GATE_X - 0.2
GATE_ZONE_X_END = GATE_X + GATE_LENGTH + 0.2

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# 도착 스케줄 생성
# =============================================================================
def generate_arrival_schedule(rng, sim_time):
    """
    열차 도착 군집 모델:
    - 열차가 TRAIN_INTERVAL 간격으로 도착
    - 각 열차에서 TRAIN_ALIGHTING명이 하차
    - 계단에서 PLATOON_SPREAD초에 걸쳐 분산 도착 (정규분포)
    """
    arrivals = []
    train_time = FIRST_TRAIN_TIME
    while train_time < sim_time:
        n_passengers = rng.poisson(TRAIN_ALIGHTING)
        # 계단 도착 시각: 열차 도착 후 정규분포로 분산
        for _ in range(n_passengers):
            arrival_t = train_time + abs(rng.normal(PLATOON_SPREAD / 2, PLATOON_SPREAD / 4))
            if arrival_t < sim_time:
                arrivals.append(arrival_t)
        train_time += TRAIN_INTERVAL
    arrivals.sort()
    return arrivals


# =============================================================================
# 서비스 시간 샘플링
# =============================================================================
def sample_service_time(rng):
    return np.clip(rng.lognormal(SERVICE_MU, SERVICE_SIGMA), 0.8, 5.0)


# =============================================================================
# 게이트 밀도 계산
# =============================================================================
def count_gate_density(sim, gates, agent_data):
    """각 게이트에 배정된 전체 대기 인원 (서비스 완료자 제외)"""
    density = [0] * len(gates)
    for agent in sim.agents():
        aid = agent.id
        if aid not in agent_data:
            continue
        if agent_data[aid]["serviced"]:
            continue
        gi = agent_data[aid]["gate_idx"]
        density[gi] += 1
    return density


# =============================================================================
# 게이트 선택 (Logit + 관성)
# =============================================================================
def choose_gate(agent_pos, gates, gate_density, vision_radius=None,
                current_gate=None):
    """
    효용함수: U(i) = beta_dist * dist(i) + beta_queue * queue(i)
    경로 변경 시: U(new) must exceed U(current) + C_switch
    """
    utilities = np.full(len(gates), -np.inf)
    for i, gate in enumerate(gates):
        dist = np.hypot(agent_pos[0] - gate["x"], agent_pos[1] - gate["y"])
        if vision_radius is not None and dist > vision_radius:
            continue
        utilities[i] = BETA_DIST * dist + BETA_QUEUE * gate_density[i]

    if np.all(np.isinf(utilities)):
        dists = [np.hypot(agent_pos[0] - g["x"], agent_pos[1] - g["y"])
                 for g in gates]
        return int(np.argmin(dists))

    # 경로 변경 시: 관성 적용
    if current_gate is not None:
        current_u = utilities[current_gate]
        if not np.isinf(current_u):
            best_new = np.max(utilities)
            # 새 게이트 효용이 현재 + 전환비용보다 높아야 변경
            if best_new <= current_u + C_SWITCH:
                return current_gate

    valid = ~np.isinf(utilities)
    utilities[valid] -= np.max(utilities[valid])
    exp_u = np.where(valid, np.exp(utilities), 0.0)
    probs = exp_u / exp_u.sum()
    return int(np.random.choice(len(gates), p=probs))


# =============================================================================
# 시뮬레이션 생성
# =============================================================================
def create_simulation():
    gates = calculate_gate_positions()
    # 시뮬레이션: 배리어 없는 열린 공간 (게이트 통과는 코드로 제어)
    walkable, obstacles, gate_openings = build_geometry(gates, include_barrier=False)
    # 시각화용: 배리어 포함
    _, vis_obstacles, _ = build_geometry(gates, include_barrier=True)

    model = jps.CollisionFreeSpeedModelV2()

    sim = jps.Simulation(
        model=model,
        geometry=walkable,
        dt=DT,
    )

    gate_x_end = GATE_X + GATE_LENGTH

    # 1단계: 접근 Waypoint (게이트 y좌표로 정렬, 줄 합류)
    approach_wp_ids = []
    for g in gates:
        wp_id = sim.add_waypoint_stage((8.0, g["y"]), 1.0)
        approach_wp_ids.append(wp_id)

    # 2단계: 게이트 입구 Waypoint (작은 반경 → 한 줄 대기)
    gate_wp_ids = []
    for g in gates:
        wp_id = sim.add_waypoint_stage((GATE_X, g["y"]), 0.4)
        gate_wp_ids.append(wp_id)

    # 3단계: 게이트 통과 후 Waypoint
    post_gate_wp_ids = []
    for g in gates:
        wp_id = sim.add_waypoint_stage((gate_x_end + 2.0, g["y"]), 1.0)
        post_gate_wp_ids.append(wp_id)

    # 출구
    exit_upper = sim.add_exit_stage(Polygon([
        (EXITS[0]["x_start"], EXITS[0]["y"] - 0.5),
        (EXITS[0]["x_end"],   EXITS[0]["y"] - 0.5),
        (EXITS[0]["x_end"],   EXITS[0]["y"] + 0.5),
        (EXITS[0]["x_start"], EXITS[0]["y"] + 0.5),
    ]))
    exit_lower = sim.add_exit_stage(Polygon([
        (EXITS[1]["x_start"], EXITS[1]["y"] - 0.5),
        (EXITS[1]["x_end"],   EXITS[1]["y"] - 0.5),
        (EXITS[1]["x_end"],   EXITS[1]["y"] + 0.5),
        (EXITS[1]["x_start"], EXITS[1]["y"] + 0.5),
    ]))

    # 게이트별 Journey (3단계: 접근 → 게이트 입구 → 통과 후 → 출구)
    journey_ids = []
    for i, g in enumerate(gates):
        target_exit = exit_upper if g["y"] > CONCOURSE_WIDTH / 2 else exit_lower
        journey = jps.JourneyDescription([
            approach_wp_ids[i], gate_wp_ids[i],
            post_gate_wp_ids[i], exit_upper, exit_lower
        ])
        journey.set_transition_for_stage(
            approach_wp_ids[i],
            jps.Transition.create_fixed_transition(gate_wp_ids[i])
        )
        journey.set_transition_for_stage(
            gate_wp_ids[i],
            jps.Transition.create_fixed_transition(post_gate_wp_ids[i])
        )
        journey.set_transition_for_stage(
            post_gate_wp_ids[i],
            jps.Transition.create_fixed_transition(target_exit)
        )
        jid = sim.add_journey(journey)
        journey_ids.append(jid)

    return (sim, gates, walkable, vis_obstacles, gate_openings,
            approach_wp_ids, gate_wp_ids, post_gate_wp_ids, journey_ids)


# =============================================================================
# 시뮬레이션 실행
# =============================================================================
def run_simulation():
    print("=" * 60)
    print("성수역 서쪽 대합실 시뮬레이션 v5 (CFSM V2)")
    print(f"  열차 간격: {TRAIN_INTERVAL}s, 하차: ~{TRAIN_ALIGHTING}명/회")
    print(f"  게이트 선택: beta_dist={BETA_DIST}, beta_queue={BETA_QUEUE}")
    print(f"  전환 비용(C_switch): {C_SWITCH}, Lock-in: {LOCK_IN_DISTANCE}m")
    print(f"  재평가 주기: {REROUTE_INTERVAL}s")
    print(f"  서비스시간: lognormal(mu={SERVICE_MU}, sigma={SERVICE_SIGMA})")
    print("=" * 60)

    (sim, gates, walkable, obstacles, gate_openings,
     approach_wp_ids, gate_wp_ids, post_gate_wp_ids, journey_ids) = create_simulation()

    rng = np.random.default_rng(42)
    total_steps = int(SIM_TIME / DT)
    reroute_step_interval = int(REROUTE_INTERVAL / DT)

    # 도착 스케줄 생성
    arrival_times = generate_arrival_schedule(rng, SIM_TIME)
    arrival_idx = 0
    print(f"  도착 스케줄: {len(arrival_times)}명 예정")

    agent_data = {}
    in_service = {}
    spawned_count = 0

    stats = {
        "gate_counts": [0] * N_GATES,
        "service_times": [],
        "queue_history": [],
        "reroute_count": 0,
    }

    gif_frames = []
    gif_interval = int(0.5 / DT)

    print("\n시뮬레이션 실행 중...")

    for step in range(total_steps):
        current_time = step * DT

        # ── 보행자 생성 (군집 도착) ──
        while (arrival_idx < len(arrival_times) and
               arrival_times[arrival_idx] <= current_time):
            stair = STAIRS[rng.integers(0, len(STAIRS))]
            spawn_x = stair["x"] + rng.uniform(0.3, 1.0)
            spawn_y = rng.uniform(stair["y_start"], stair["y_end"])
            desired_speed = np.clip(
                rng.normal(PED_SPEED_MEAN, PED_SPEED_STD), 0.5, 2.0)

            gate_density = count_gate_density(sim, gates, agent_data)
            gate_idx = choose_gate(
                (spawn_x, spawn_y), gates, gate_density, VISION_RADIUS)

            try:
                agent_id = sim.add_agent(
                    jps.CollisionFreeSpeedModelV2AgentParameters(
                        journey_id=journey_ids[gate_idx],
                        stage_id=approach_wp_ids[gate_idx],
                        position=(spawn_x, spawn_y),
                        desired_speed=desired_speed,
                        radius=PED_RADIUS,
                        time_gap=PED_TIME_GAP,
                        strength_neighbor_repulsion=PED_STRENGTH_NEIGHBOR,
                        range_neighbor_repulsion=PED_RANGE_NEIGHBOR,
                        strength_geometry_repulsion=PED_STRENGTH_GEOMETRY,
                        range_geometry_repulsion=PED_RANGE_GEOMETRY,
                    )
                )
                svc_time = sample_service_time(rng)
                agent_data[agent_id] = {
                    "gate_idx": gate_idx,
                    "spawn_time": current_time,
                    "service_time": svc_time,
                    "original_speed": desired_speed,
                    "serviced": False,
                    "locked_in": False,
                }
                spawned_count += 1
            except Exception:
                pass
            arrival_idx += 1

        # ── 게이트 점유 상태 파악 ──
        gate_occupied = [False] * N_GATES
        for aid_s, svc in in_service.items():
            gi = agent_data[aid_s]["gate_idx"]
            gate_occupied[gi] = True

        # ── 서비스 시간 + 대기열 제어 ──
        for agent in sim.agents():
            aid = agent.id
            if aid not in agent_data or agent_data[aid]["serviced"]:
                continue
            px, py = agent.position
            gi = agent_data[aid]["gate_idx"]

            # 게이트 구간 안에 있는 에이전트: 서비스 처리
            if GATE_ZONE_X_START <= px <= GATE_ZONE_X_END:
                if aid not in in_service:
                    agent.model.desired_speed = 0.3
                    in_service[aid] = {
                        "start": current_time,
                        "duration": agent_data[aid]["service_time"],
                    }
                    gate_occupied[gi] = True
                else:
                    elapsed = current_time - in_service[aid]["start"]
                    if elapsed >= in_service[aid]["duration"]:
                        agent.model.desired_speed = agent_data[aid]["original_speed"]
                        agent.model.time_gap = PED_TIME_GAP
                        agent_data[aid]["serviced"] = True
                        stats["gate_counts"][gi] += 1
                        stats["service_times"].append(in_service[aid]["duration"])
                        del in_service[aid]
                        gate_occupied[gi] = False
                continue

            # 게이트 구간 밖: 대기열 제어
            dist_to_gate = GATE_X - px
            if 0 < dist_to_gate < 5.0:
                agent.model.time_gap = PED_TIME_GAP_QUEUE
                # 내 게이트가 사용 중이면 → 완전 정지 (이동 욕구 제거)
                if gate_occupied[gi]:
                    agent.model.desired_speed = 0.0
                else:
                    agent.model.desired_speed = agent_data[aid]["original_speed"]

        # ── 동적 경로 변경 (다단계 의사결정) ──
        if step % reroute_step_interval == 0 and step > 0:
            gate_density = count_gate_density(sim, gates, agent_data)
            for agent in sim.agents():
                aid = agent.id
                if aid not in agent_data:
                    continue
                if agent_data[aid]["serviced"] or aid in in_service:
                    continue
                if agent_data[aid]["locked_in"]:
                    continue

                pos = agent.position

                # Lock-in: 게이트 3m 이내 → 경로 변경 비활성화
                dist_to_gate = GATE_X - pos[0]
                if dist_to_gate < LOCK_IN_DISTANCE:
                    agent_data[aid]["locked_in"] = True
                    continue

                current_gate = agent_data[aid]["gate_idx"]
                new_gate = choose_gate(
                    pos, gates, gate_density, VISION_RADIUS,
                    current_gate=current_gate  # 관성 적용
                )

                if new_gate != current_gate:
                    try:
                        sim.switch_agent_journey(
                            aid, journey_ids[new_gate], approach_wp_ids[new_gate])
                        agent_data[aid]["gate_idx"] = new_gate
                        stats["reroute_count"] += 1
                    except Exception:
                        pass

        # ── 통계 & 프레임 ──
        if step % int(1.0 / DT) == 0:
            gd = count_gate_density(sim, gates, agent_data)
            stats["queue_history"].append((current_time, gd.copy()))

        if step % gif_interval == 0:
            positions = [(a.position[0], a.position[1]) for a in sim.agents()]
            gif_frames.append((current_time, positions))

        sim.iterate()

        if step % int(30.0 / DT) == 0 and step > 0:
            print(f"  t={current_time:.0f}s | agents: {sim.agent_count()} "
                  f"| spawned: {spawned_count} | passed: {sum(stats['gate_counts'])} "
                  f"| re-route: {stats['reroute_count']}")

    # ── 결과 ──
    total_passed = sum(stats["gate_counts"])
    print(f"\n완료: {spawned_count}명 생성, {total_passed}명 통과, "
          f"{stats['reroute_count']}회 경로변경")
    print("\n게이트별 통과:")
    for i in range(N_GATES):
        print(f"  G{i+1}: {stats['gate_counts'][i]}명")

    if stats["service_times"]:
        st = np.array(stats["service_times"])
        print(f"\n서비스 시간: 평균 {st.mean():.2f}s, "
              f"중앙값 {np.median(st):.2f}s, 최대 {st.max():.2f}s")

    print(f"\n출력 생성...")
    create_snapshots(gif_frames, gates, obstacles, gate_openings)
    create_gif(gif_frames, gates, obstacles, gate_openings)
    plot_queue_history(stats["queue_history"])
    plot_service_time_dist(stats["service_times"])

    return stats


# =============================================================================
# 시각화
# =============================================================================
def draw_frame(ax, positions, gates, obstacles, gate_openings, time_sec):
    ax.clear()
    gate_x_end = GATE_X + GATE_LENGTH

    ax.axvspan(0, GATE_X, color='#E8F5E9', alpha=0.3)
    ax.axvspan(gate_x_end, 32, color='#FFF8E1', alpha=0.3)

    outer_x = [0, CONCOURSE_LENGTH, CONCOURSE_LENGTH, NOTCH_X, NOTCH_X, 0, 0]
    outer_y = [0, 0, CONCOURSE_WIDTH, CONCOURSE_WIDTH, NOTCH_Y, NOTCH_Y, 0]
    ax.plot(outer_x, outer_y, color='#E65100', linewidth=1.5)

    for obs in obstacles:
        if obs.geom_type == 'Polygon':
            ox, oy = obs.exterior.xy
            ax.fill(ox, oy, color='#546E7A', edgecolor='#263238', linewidth=0.3)
        elif obs.geom_type == 'MultiPolygon':
            for geom in obs.geoms:
                ox, oy = geom.exterior.xy
                ax.fill(ox, oy, color='#546E7A', edgecolor='#263238', linewidth=0.3)

    for opening in gate_openings:
        ox, oy = opening.exterior.xy
        ax.fill(ox, oy, color='#66BB6A', edgecolor='#2E7D32', linewidth=0.8, alpha=0.5)

    for g in gates:
        ax.text(g["x"] + GATE_LENGTH / 2, g["y"], str(g["id"] + 1),
                ha='center', va='center', fontsize=7, fontweight='bold', color='#1B5E20')

    for stair in STAIRS:
        ax.plot([stair["x"], stair["x"]],
                [stair["y_start"], stair["y_end"]],
                color='#E53935', linewidth=3, solid_capstyle='round')

    for exit_ in EXITS:
        ax.plot([exit_["x_start"], exit_["x_end"]],
                [exit_["y"], exit_["y"]],
                color='#1565C0', linewidth=3, solid_capstyle='round')

    for s in STRUCTURES:
        coords = s["coords"]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        ax.add_patch(mpatches.Rectangle(
            (min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys),
            linewidth=0.5, edgecolor='#E65100', facecolor='#FFE0B2',
            hatch='///', alpha=0.4))

    if positions:
        xs, ys = zip(*positions)
        ax.scatter(xs, ys, s=25, c='#0D47A1', edgecolors='white',
                   linewidths=0.3, alpha=0.85, zorder=5)

    ax.text(0.5, NOTCH_Y - 0.5,
            f't = {time_sec:.1f}s | {len(positions)} peds',
            fontsize=10, fontweight='bold', color='#333',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor='#999', alpha=0.9))

    ax.set_xlim(-0.5, 32)
    ax.set_ylim(-0.5, CONCOURSE_WIDTH + 0.5)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)', fontsize=9)
    ax.set_ylabel('y (m)', fontsize=9)


def create_snapshots(frames, gates, obstacles, gate_openings):
    """열차 도착 전후 스냅샷: 도착 직전, 피크, 해소 과정"""
    snap_times = [3, 10, 15, 25, 45, 90]

    fig, axes = plt.subplots(2, 3, figsize=(36, 22))
    axes = axes.flatten()

    for idx, target_t in enumerate(snap_times):
        best_i = min(range(len(frames)), key=lambda i: abs(frames[i][0] - target_t))
        t, positions = frames[best_i]
        draw_frame(axes[idx], positions, gates, obstacles, gate_openings, t)
        axes[idx].set_title(f't = {target_t}s ({len(positions)} agents)',
                            fontsize=12, fontweight='bold')

    fig.suptitle('성수역 서쪽 대합실 시뮬레이션 v5 (군집 도착 + 다단계 의사결정)',
                 fontsize=16, fontweight='bold')
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "snapshots_v5.png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  스냅샷: {OUTPUT_DIR / 'snapshots_v5.png'}")


def create_gif(frames, gates, obstacles, gate_openings):
    """첫 번째 열차 도착 구간(0~60s) GIF 생성"""
    from matplotlib.animation import FuncAnimation, PillowWriter

    # 0~60초 구간만 추출 (1초 간격으로 샘플링)
    target_frames = []
    for t, pos in frames:
        if t > 60:
            break
        target_frames.append((t, pos))
    # 1초 간격으로 다운샘플 (0.5초 간격 프레임 → 매 2번째)
    target_frames = target_frames[::2]

    if not target_frames:
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    def animate(i):
        t, positions = target_frames[i]
        draw_frame(ax, positions, gates, obstacles, gate_openings, t)
        ax.set_title(f'성수역 서쪽 v5 | t = {t:.1f}s | {len(positions)} agents',
                     fontsize=12, fontweight='bold')

    anim = FuncAnimation(fig, animate, frames=len(target_frames), interval=200)
    gif_path = OUTPUT_DIR / "simulation_v5.gif"
    anim.save(str(gif_path), writer=PillowWriter(fps=5), dpi=100)
    plt.close(fig)
    print(f"  GIF: {gif_path}")


def plot_queue_history(queue_history):
    if not queue_history:
        return
    times = [t for t, _ in queue_history]
    queues = np.array([q for _, q in queue_history])

    fig, ax = plt.subplots(figsize=(14, 5))
    for i in range(N_GATES):
        ax.plot(times, queues[:, i], label=f'G{i+1}', linewidth=1.5)

    # 열차 도착 시점 표시
    train_t = FIRST_TRAIN_TIME
    while train_t < SIM_TIME:
        ax.axvline(train_t, color='red', linestyle='--', alpha=0.3, linewidth=1)
        train_t += TRAIN_INTERVAL

    ax.set_xlabel('시간 (초)')
    ax.set_ylabel('게이트 앞 밀도 (명)')
    ax.set_title('게이트별 대기 밀도 변화 (v5) - 빨간 점선: 열차 도착')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "queue_history_v5.png", dpi=150)
    plt.close(fig)
    print(f"  대기열: {OUTPUT_DIR / 'queue_history_v5.png'}")


def plot_service_time_dist(service_times):
    if not service_times:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(service_times, bins=25, color='#42A5F5', edgecolor='#1565C0', alpha=0.8)
    ax.axvline(np.mean(service_times), color='red', linestyle='--',
               label=f'평균: {np.mean(service_times):.2f}s')
    ax.set_xlabel('서비스 시간 (초)')
    ax.set_ylabel('빈도')
    ax.set_title('개찰구 서비스 시간 분포 (태그 사용자)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "service_time_v5.png", dpi=150)
    plt.close(fig)
    print(f"  서비스시간: {OUTPUT_DIR / 'service_time_v5.png'}")


if __name__ == "__main__":
    run_simulation()
