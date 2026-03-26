"""
성수역 보행자 시뮬레이션 - GIF 생성
양쪽 끝 게이트 7대씩, 가운데 유료구역에서 출발
게이트별 waypoint 스테이지로 개찰구 통과 의사결정 구현
"""

import matplotlib
matplotlib.use('Agg')

import jupedsim as jps
import numpy as np
import pathlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, PillowWriter
from shapely import Polygon

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from seongsu_station import (
    calculate_gate_positions, build_geometry,
    CONCOURSE_LENGTH, CONCOURSE_WIDTH, GATE_LENGTH,
    LEFT_GATE_X, RIGHT_GATE_X, STAIR_POSITIONS,
    GATE_PASSAGE_WIDTH, GATE_HOUSING_WIDTH,
    N_GATES_PER_GROUP, _gate_array_span,
)

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# =============================================================================
N_PEDESTRIANS = 500
SIM_TIME = 180.0
DT = 0.05
GIF_INTERVAL = 0.25
AGENT_RADIUS = 0.12    # 에이전트 반경 (0.55m 통로 통과 가능하도록)
OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def create_simulation():
    gates = calculate_gate_positions()
    walkable, obstacles = build_geometry(gates)

    sim = jps.Simulation(
        model=jps.CollisionFreeSpeedModel(),
        geometry=walkable,
        dt=DT,
    )

    # ── 1) 출구 스테이지 ──
    left_exit = Polygon([(0, 0), (2, 0), (2, CONCOURSE_WIDTH), (0, CONCOURSE_WIDTH)])
    right_exit = Polygon([
        (CONCOURSE_LENGTH - 2, 0), (CONCOURSE_LENGTH, 0),
        (CONCOURSE_LENGTH, CONCOURSE_WIDTH), (CONCOURSE_LENGTH - 2, CONCOURSE_WIDTH)
    ])
    left_exit_id = sim.add_exit_stage(left_exit)
    right_exit_id = sim.add_exit_stage(right_exit)

    # ── 2) 각 게이트에 접근 waypoint + 통과 waypoint 생성 ──
    # 접근 wp: 게이트 앞(유료구역 쪽)에서 정렬
    # 통과 wp: 게이트 뒤(무료구역 쪽)로 끌어당김
    gate_journeys = {}  # gate_id -> (journey_id, first_stage_id)

    for g in gates:
        gx, gy = g["x"], g["y"]
        if g["group"] == "left":
            # 유료구역(오른쪽) → 게이트 → 무료구역(왼쪽)
            approach_x = gx + GATE_LENGTH / 2 + 1.0   # 게이트 앞 1m
            through_x = gx - GATE_LENGTH / 2 - 1.0    # 게이트 뒤 1m
            exit_id = left_exit_id
        else:
            # 유료구역(왼쪽) → 게이트 → 무료구역(오른쪽)
            approach_x = gx - GATE_LENGTH / 2 - 1.0
            through_x = gx + GATE_LENGTH / 2 + 1.0
            exit_id = right_exit_id

        approach_id = sim.add_waypoint_stage((approach_x, gy), 0.8)
        through_id = sim.add_waypoint_stage((through_x, gy), 0.8)

        journey = jps.JourneyDescription([approach_id, through_id, exit_id])
        journey.set_transition_for_stage(
            approach_id, jps.Transition.create_fixed_transition(through_id)
        )
        journey.set_transition_for_stage(
            through_id, jps.Transition.create_fixed_transition(exit_id)
        )
        journey_id = sim.add_journey(journey)
        gate_journeys[g["id"]] = (journey_id, approach_id)

    # ── 4) 보행자 스폰 ──
    paid_x_min = LEFT_GATE_X + GATE_LENGTH / 2 + 0.5
    paid_x_max = RIGHT_GATE_X - GATE_LENGTH / 2 - 0.5
    paid_y_min = 1.0
    paid_y_max = CONCOURSE_WIDTH - 1.0

    left_gates = [g for g in gates if g["group"] == "left"]
    right_gates = [g for g in gates if g["group"] == "right"]

    rng = np.random.default_rng(42)
    spawned = 0

    for i in range(N_PEDESTRIANS):
        stair_x = rng.choice(STAIR_POSITIONS)
        px = stair_x + rng.normal(0, 5.0)
        px = np.clip(px, paid_x_min, paid_x_max)
        py = rng.uniform(paid_y_min, paid_y_max)
        speed = max(0.5, min(2.0, rng.normal(1.34, 0.26)))

        # 가까운 방향의 게이트 그룹 선택
        mid_x = (LEFT_GATE_X + RIGHT_GATE_X) / 2
        if px < mid_x:
            group_gates = left_gates
        else:
            group_gates = right_gates

        # 그룹 내에서 y좌표가 가장 가까운 게이트 선택
        best_gate = min(group_gates, key=lambda g: abs(g["y"] - py))
        j_id, first_stage = gate_journeys[best_gate["id"]]

        try:
            sim.add_agent(jps.CollisionFreeSpeedModelAgentParameters(
                journey_id=j_id,
                stage_id=first_stage,
                position=(px, py),
                desired_speed=speed,
                radius=AGENT_RADIUS,
            ))
            spawned += 1
        except Exception:
            pass

    print(f"Spawned {spawned}/{N_PEDESTRIANS} pedestrians")
    return sim, gates, walkable, obstacles


def draw_frame(ax, gates, obstacles, time_sec, positions):
    ax.clear()

    # 바닥 색
    ax.set_facecolor('#FAFAFA')
    # 유료구역
    ax.add_patch(mpatches.Rectangle(
        (LEFT_GATE_X + GATE_LENGTH / 2, 0),
        RIGHT_GATE_X - LEFT_GATE_X - GATE_LENGTH, CONCOURSE_WIDTH,
        facecolor='#E8F5E9', edgecolor='none', zorder=0))
    # 무료구역 (왼쪽)
    ax.add_patch(mpatches.Rectangle(
        (0, 0), LEFT_GATE_X - GATE_LENGTH / 2, CONCOURSE_WIDTH,
        facecolor='#FFF8E1', edgecolor='none', zorder=0))
    # 무료구역 (오른쪽)
    ax.add_patch(mpatches.Rectangle(
        (RIGHT_GATE_X + GATE_LENGTH / 2, 0),
        CONCOURSE_LENGTH - RIGHT_GATE_X - GATE_LENGTH / 2, CONCOURSE_WIDTH,
        facecolor='#FFF8E1', edgecolor='none', zorder=0))

    # 게이트 벽체
    for obs in obstacles:
        ox, oy = obs.exterior.xy
        ax.fill(ox, oy, color='#37474F', edgecolor='#263238', linewidth=0.5, zorder=3)

    # 게이트 통로
    for g in gates:
        gx, gy = g["x"], g["y"]
        pw = g["passage_width"]
        xl = gx - GATE_LENGTH / 2
        yl = gy - pw / 2
        ax.add_patch(mpatches.Rectangle(
            (xl, yl), GATE_LENGTH, pw,
            facecolor='#C8E6C9', edgecolor='#2E7D32', linewidth=0.5, zorder=2))

    # 게이트 번호
    for g in gates:
        gx, gy = g["x"], g["y"]
        label = str(g["id"] + 1)
        offset_x = GATE_LENGTH / 2 + 0.3
        if g["group"] == "left":
            ax.text(gx - offset_x, gy, label, ha='right', va='center',
                    fontsize=5.5, fontweight='bold', color='#455A64', zorder=5)
        else:
            ax.text(gx + offset_x, gy, label, ha='left', va='center',
                    fontsize=5.5, fontweight='bold', color='#455A64', zorder=5)

    # 계단
    for sx in STAIR_POSITIONS:
        sw, sh = 4.0, 2.0
        sy = CONCOURSE_WIDTH / 2 - sh / 2
        ax.add_patch(mpatches.FancyBboxPatch(
            (sx - sw / 2, sy), sw, sh,
            boxstyle="round,pad=0.15", facecolor='#E53935',
            edgecolor='#B71C1C', linewidth=1, alpha=0.8, zorder=4))
        ax.text(sx, CONCOURSE_WIDTH / 2, 'STAIR', ha='center', va='center',
                fontsize=6, fontweight='bold', color='white', zorder=5)

    # 출구
    for ex, label in [(3, 'EXIT 1,4'), (CONCOURSE_LENGTH - 3, 'EXIT 2,3')]:
        ew, eh = 4, 2
        ax.add_patch(mpatches.FancyBboxPatch(
            (ex - ew / 2, CONCOURSE_WIDTH / 2 - eh / 2), ew, eh,
            boxstyle="round,pad=0.15", facecolor='#7B1FA2',
            edgecolor='#4A148C', linewidth=1, alpha=0.8, zorder=4))
        ax.text(ex, CONCOURSE_WIDTH / 2, label, ha='center', va='center',
                fontsize=5.5, fontweight='bold', color='white', zorder=5)

    # 구역 라벨
    ax.text(LEFT_GATE_X / 2, CONCOURSE_WIDTH - 0.5, 'FREE ZONE',
            ha='center', fontsize=7, color='#E65100', fontweight='bold', alpha=0.6)
    ax.text((LEFT_GATE_X + RIGHT_GATE_X) / 2, CONCOURSE_WIDTH - 0.5, 'PAID ZONE',
            ha='center', fontsize=7, color='#2E7D32', fontweight='bold', alpha=0.6)
    ax.text((RIGHT_GATE_X + CONCOURSE_LENGTH) / 2, CONCOURSE_WIDTH - 0.5, 'FREE ZONE',
            ha='center', fontsize=7, color='#E65100', fontweight='bold', alpha=0.6)

    # 보행자
    for px, py in positions:
        ax.add_patch(plt.Circle((px, py), AGENT_RADIUS, facecolor='#1565C0',
                                edgecolor='white', linewidth=0.3, zorder=6, alpha=0.9))

    # 정보 박스
    ax.text(CONCOURSE_LENGTH - 1, CONCOURSE_WIDTH + 0.3,
            f't = {time_sec:.1f}s | {len(positions)} peds',
            ha='right', va='bottom', fontsize=9, fontweight='bold', color='#333',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor='#999', alpha=0.9), zorder=7)

    ax.set_xlim(-1, CONCOURSE_LENGTH + 1)
    ax.set_ylim(-1, CONCOURSE_WIDTH + 1)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)', fontsize=8)
    ax.set_ylabel('y (m)', fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title('Seongsu Station - Pedestrian Simulation (Gate Waypoint Routing)',
                 fontsize=11, fontweight='bold')


def run_and_save():
    sim, gates, walkable, obstacles = create_simulation()
    total_steps = int(SIM_TIME / DT)
    gif_step_interval = int(GIF_INTERVAL / DT)

    print("Running simulation...")
    frames = []
    for step in range(total_steps):
        if sim.agent_count() == 0:
            print(f"  All exited at t={step * DT:.1f}s")
            break
        if step % gif_step_interval == 0:
            positions = [(a.position[0], a.position[1]) for a in sim.agents()]
            frames.append((step * DT, positions))
        sim.iterate()
    print(f"  Collected {len(frames)} frames")

    print(f"Creating GIF ({len(frames)} frames)...")
    fig, ax = plt.subplots(1, 1, figsize=(16, 4.5))

    def animate(i):
        t, positions = frames[i]
        draw_frame(ax, gates, obstacles, t, positions)
        if (i + 1) % 20 == 0:
            print(f"  Frame {i + 1}/{len(frames)}...")

    anim = FuncAnimation(fig, animate, frames=len(frames), interval=80)
    gif_path = OUTPUT_DIR / "pedestrian_simulation.gif"
    anim.save(str(gif_path), writer=PillowWriter(fps=12))
    plt.close(fig)
    print(f"  GIF saved: {gif_path}")
    print("Done!")


if __name__ == "__main__":
    run_and_save()
