"""
태그리스 게이트 시뮬레이션 데모
- 복도 끝에 게이트 3개 배치
- 태그 이용자 (통과시간 2~3초) vs 태그리스 이용자 (통과시간 ~1초)
- 겸용 운영 vs 분리 운영 비교
"""

import jupedsim as jps
import numpy as np
from shapely import Polygon, GeometryCollection
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.animation import FuncAnimation
import random

# ============================================================
# 1. 기하구조 설정 (단순화된 개찰구 구역)
# ============================================================
# 복도: 20m x 10m
# 게이트 3개가 x=15m 라인에 위치 (폭 0.6m, 간격 2m)

CORRIDOR_LENGTH = 20.0
CORRIDOR_WIDTH = 10.0

# 게이트 위치 (y 좌표 중심)
GATE_POSITIONS = [3.0, 5.0, 7.0]
GATE_WIDTH = 0.6
WALL_THICKNESS = 0.3
GATE_X = 15.0

# walkable area 정의: 복도 전체에서 게이트 벽 부분을 뚫어줌
# 게이트 벽: x=15 라인에 벽이 있고, 게이트 위치만 통과 가능

# 왼쪽 영역 (게이트 전)
left_area = Polygon([
    (0, 0), (GATE_X, 0), (GATE_X, CORRIDOR_WIDTH), (0, CORRIDOR_WIDTH)
])

# 오른쪽 영역 (게이트 후)
right_area = Polygon([
    (GATE_X + WALL_THICKNESS, 0),
    (CORRIDOR_LENGTH, 0),
    (CORRIDOR_LENGTH, CORRIDOR_WIDTH),
    (GATE_X + WALL_THICKNESS, CORRIDOR_WIDTH)
])

# 게이트 통로 (벽 사이 좁은 통로)
gate_passages = []
for gy in GATE_POSITIONS:
    passage = Polygon([
        (GATE_X, gy - GATE_WIDTH / 2),
        (GATE_X + WALL_THICKNESS, gy - GATE_WIDTH / 2),
        (GATE_X + WALL_THICKNESS, gy + GATE_WIDTH / 2),
        (GATE_X, gy + GATE_WIDTH / 2),
    ])
    gate_passages.append(passage)

# 전체 walkable area = 왼쪽 + 오른쪽 + 게이트 통로
from shapely.ops import unary_union
walkable_area = unary_union([left_area, right_area] + gate_passages)

# ============================================================
# 2. 시뮬레이션 파라미터
# ============================================================
NUM_PEDESTRIANS = 60
TAGLESS_RATIO = 0.4  # 태그리스 이용자 비율
SIM_DT = 0.01  # 시뮬레이션 타임스텝

# 태그 통과시간: 2~3초 (게이트 앞에서 정지)
TAG_SERVICE_TIME = 2.5
# 태그리스 통과시간: ~1초 (감속만)
TAGLESS_SERVICE_TIME = 0.8

# ============================================================
# 3. 시뮬레이션 설정
# ============================================================
print("=" * 50)
print("태그리스 게이트 시뮬레이션 데모")
print("=" * 50)
print(f"보행자 수: {NUM_PEDESTRIANS}")
print(f"태그리스 비율: {TAGLESS_RATIO * 100:.0f}%")
print(f"게이트 수: {len(GATE_POSITIONS)}")
print()

# 시뮬레이션 생성
simulation = jps.Simulation(
    model=jps.CollisionFreeSpeedModelV2(),
    geometry=walkable_area,
    dt=SIM_DT,
)

# 출구 설정 (게이트 통과 후 오른쪽 끝)
exit_area = Polygon([
    (CORRIDOR_LENGTH - 0.5, 0),
    (CORRIDOR_LENGTH, 0),
    (CORRIDOR_LENGTH, CORRIDOR_WIDTH),
    (CORRIDOR_LENGTH - 0.5, CORRIDOR_WIDTH),
])
exit_id = simulation.add_exit_stage(exit_area)

# 게이트 앞 대기 포인트 설정 (웨이포인트)
gate_waypoints = []
for gy in GATE_POSITIONS:
    wp = simulation.add_waypoint_stage(
        position=(GATE_X - 0.5, gy),
        distance=0.5,
    )
    gate_waypoints.append(wp)

# 여정 설정: 각 게이트별 여정
gate_journeys = []
for wp in gate_waypoints:
    journey = jps.JourneyDescription(stage_ids=[wp, exit_id])
    journey_id = simulation.add_journey(journey)
    gate_journeys.append(journey_id)

# ============================================================
# 4. 보행자 생성 (태그/태그리스 구분)
# ============================================================
agent_types = {}  # agent_id -> "tag" or "tagless"
agent_gate_times = {}  # agent_id -> 게이트 도착 시간
agent_exit_times = {}  # agent_id -> 게이트 통과 완료 시간
agent_waiting = {}  # agent_id -> 대기 중 여부

random.seed(42)
np.random.seed(42)

# 그리드 기반 배치로 겹침 방지
spacing = 0.6
cols = int(12.0 / spacing)  # x: 1~13m
rows = int((CORRIDOR_WIDTH - 2.0) / spacing)  # y: 1~9m
grid_positions = []
for r in range(rows):
    for c in range(cols):
        grid_positions.append((1.0 + c * spacing, 1.0 + r * spacing))
random.shuffle(grid_positions)

for i in range(NUM_PEDESTRIANS):
    start_x, start_y = grid_positions[i]

    # 태그리스 여부
    is_tagless = random.random() < TAGLESS_RATIO

    # 가장 가까운 게이트 선택 (단순 거리 기반)
    distances = [abs(start_y - gy) for gy in GATE_POSITIONS]
    chosen_gate_idx = distances.index(min(distances))

    # 보행 속도 설정
    if is_tagless:
        speed = random.uniform(1.2, 1.5)  # 태그리스: 빠르게 통과
    else:
        speed = random.uniform(0.8, 1.2)  # 태그: 일반 보행

    agent_id = simulation.add_agent(
        jps.CollisionFreeSpeedModelV2AgentParameters(
            journey_id=gate_journeys[chosen_gate_idx],
            stage_id=gate_waypoints[chosen_gate_idx],
            position=(start_x, start_y),
            desired_speed=speed,
            radius=0.2,
        )
    )

    agent_types[agent_id] = "tagless" if is_tagless else "tag"

print(f"태그 이용자: {sum(1 for v in agent_types.values() if v == 'tag')}명")
print(f"태그리스 이용자: {sum(1 for v in agent_types.values() if v == 'tagless')}명")

# ============================================================
# 5. 시뮬레이션 실행
# ============================================================
print("\n시뮬레이션 실행 중...")

positions_history = []
types_history = []
max_iterations = 10000

for step in range(max_iterations):
    agents = list(simulation.agents())
    if len(agents) == 0:
        print(f"모든 보행자 통과 완료! (시간: {simulation.elapsed_time():.1f}초)")
        break

    # 현재 프레임 위치 저장 (10스텝마다)
    if step % 10 == 0:
        frame_pos = []
        frame_types = []
        for agent in agents:
            frame_pos.append(agent.position)
            frame_types.append(agent_types.get(agent.id, "tag"))
        positions_history.append(frame_pos)
        types_history.append(frame_types)

    simulation.iterate()

total_time = simulation.elapsed_time()
print(f"총 시뮬레이션 시간: {total_time:.1f}초")

# ============================================================
# 6. 결과 시각화 (정적 스냅샷)
# ============================================================
print("\n시각화 생성 중...")

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 스냅샷 시점: 초기, 중간, 후반
snapshot_indices = [
    0,
    len(positions_history) // 3,
    2 * len(positions_history) // 3,
]
snapshot_labels = ["초기 상태", "중간 상태", "후반 상태"]

for ax, idx, label in zip(axes, snapshot_indices, snapshot_labels):
    if idx >= len(positions_history):
        idx = len(positions_history) - 1

    # 배경: 복도
    ax.set_xlim(-0.5, CORRIDOR_LENGTH + 0.5)
    ax.set_ylim(-0.5, CORRIDOR_WIDTH + 0.5)

    # 벽 그리기
    ax.fill_between(
        [GATE_X, GATE_X + WALL_THICKNESS],
        0, CORRIDOR_WIDTH,
        color="gray", alpha=0.5, label="벽"
    )
    # 게이트 통로 표시
    for gy in GATE_POSITIONS:
        rect = Rectangle(
            (GATE_X, gy - GATE_WIDTH / 2),
            WALL_THICKNESS, GATE_WIDTH,
            color="white", zorder=3
        )
        ax.add_patch(rect)
        ax.plot(
            [GATE_X, GATE_X + WALL_THICKNESS],
            [gy, gy],
            "g--", linewidth=2, zorder=4
        )

    # 보행자 그리기
    positions = positions_history[idx]
    types = types_history[idx]

    for pos, ptype in zip(positions, types):
        color = "red" if ptype == "tag" else "blue"
        ax.scatter(pos[0], pos[1], c=color, s=30, zorder=5, alpha=0.7)

    ax.set_title(label, fontsize=14)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

# 범례
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='태그 이용자'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='태그리스 이용자'),
]
fig.legend(handles=legend_elements, loc='upper center', ncol=2, fontsize=12)
plt.suptitle(
    f"태그리스 게이트 시뮬레이션 (보행자 {NUM_PEDESTRIANS}명, 태그리스 비율 {TAGLESS_RATIO*100:.0f}%)",
    fontsize=16, y=1.02
)
plt.tight_layout()
plt.savefig("C:/Users/aaron/tagless/demo_result.png", dpi=150, bbox_inches="tight")
print("결과 저장: ~/tagless/demo_result.png")
plt.show()
print("\n데모 완료!")
