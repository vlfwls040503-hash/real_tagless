"""
성수역 2F 대합실 게이트 구간 시뮬레이션 (JuPedSim)

실제 배치:
- 직사각형 대합실, 가로로 긴 형태
- 양쪽 끝에 게이트 7대씩 (총 14대)
- 가운데는 유료구역 (계단/에스컬레이터로 3F 승강장 연결)
- 왼쪽 출구 1,4 / 오른쪽 출구 2,3

구조 (위에서 본 평면도):
┌────────┬──────────────────────────────────┬────────┐
│ FREE   │G│         PAID ZONE              │G│ FREE   │
│ Exit   │A│    [Stair]    [Stair]          │A│ Exit   │
│ 1, 4   │T│      ↓          ↓             │T│ 2, 3   │
│        │E│   (from 3F platform)           │E│        │
│        │S│                                │S│        │
└────────┴──────────────────────────────────┴────────┘
         7대                                 7대
"""

import jupedsim as jps
import numpy as np
from shapely import Polygon
from shapely.ops import unary_union

# =============================================================================
# 1. 게이트 규격 (단위: m)
# =============================================================================
GATE_PASSAGE_WIDTH = 0.55       # 일반 게이트 통로 폭 (실제 치수)
GATE_HOUSING_WIDTH = 0.30       # 게이트 본체(칸막이) 폭
GATE_LENGTH = 1.50              # 게이트 본체 길이 - 시각화용
GATE_WALL_THICKNESS = 0.30      # 시뮬레이션 geometry 벽 두께 (플랩 병목 지점)

N_GATES_PER_GROUP = 7
N_GATE_GROUPS = 2
N_TOTAL_GATES = N_GATES_PER_GROUP * N_GATE_GROUPS  # 14

# =============================================================================
# 2. 대합실 기하구조
# =============================================================================
CONCOURSE_LENGTH = 80.0   # x방향 (동서)
CONCOURSE_WIDTH = 12.0    # y방향 (남북)

# 게이트 그룹 x좌표 (게이트 벽 중심)
LEFT_GATE_X = 12.0
RIGHT_GATE_X = 68.0

# 계단 위치 (유료구역 내, 3F에서 내려오는 지점)
STAIR_POSITIONS = [30.0, 50.0]


# =============================================================================
# 3. 게이트 위치 계산
# =============================================================================
def _gate_array_span():
    """7개 게이트 배열의 총 y방향 높이"""
    return (N_GATES_PER_GROUP * GATE_PASSAGE_WIDTH
            + (N_GATES_PER_GROUP + 1) * GATE_HOUSING_WIDTH)


def calculate_gate_positions():
    """각 게이트의 위치 계산 (양쪽 그룹)"""
    gates = []
    total_h = _gate_array_span()
    start_y = (CONCOURSE_WIDTH - total_h) / 2

    for group_idx, gate_x in enumerate([LEFT_GATE_X, RIGHT_GATE_X]):
        y = start_y + GATE_HOUSING_WIDTH
        for i in range(N_GATES_PER_GROUP):
            center_y = y + GATE_PASSAGE_WIDTH / 2
            gates.append({
                "id": group_idx * N_GATES_PER_GROUP + i,
                "group": "left" if group_idx == 0 else "right",
                "x": gate_x,
                "y": center_y,
                "passage_width": GATE_PASSAGE_WIDTH,
                "type": "normal",
            })
            y += GATE_PASSAGE_WIDTH + GATE_HOUSING_WIDTH

    return gates


# =============================================================================
# 4. 기하구조 생성
# =============================================================================
def build_geometry(gates):
    """
    walkable area 생성: 대합실 - 게이트 벽체(장애물)
    게이트 벽은 x방향으로 GATE_WALL_THICKNESS 두께 (시뮬레이션용, 얇은 벽)
    시각화에서는 GATE_LENGTH로 표현
    """
    concourse = Polygon([
        (0, 0), (CONCOURSE_LENGTH, 0),
        (CONCOURSE_LENGTH, CONCOURSE_WIDTH), (0, CONCOURSE_WIDTH)
    ])

    obstacles = []

    for gate_x in [LEFT_GATE_X, RIGHT_GATE_X]:
        group_gates = [g for g in gates if g["x"] == gate_x]
        wall_left = gate_x - GATE_WALL_THICKNESS / 2
        wall_right = gate_x + GATE_WALL_THICKNESS / 2

        total_h = _gate_array_span()
        start_y = (CONCOURSE_WIDTH - total_h) / 2

        # 게이트 배열 아래쪽 벽 (y=0 ~ 배열 시작)
        if start_y > 0.01:
            obstacles.append(Polygon([
                (wall_left, 0), (wall_right, 0),
                (wall_right, start_y), (wall_left, start_y)
            ]))

        # housing 세그먼트들 (게이트 사이 칸막이)
        y = start_y
        for i in range(N_GATES_PER_GROUP + 1):
            h_bot = y
            h_top = y + GATE_HOUSING_WIDTH
            obstacles.append(Polygon([
                (wall_left, h_bot), (wall_right, h_bot),
                (wall_right, h_top), (wall_left, h_top)
            ]))
            y = h_top
            if i < N_GATES_PER_GROUP:
                y += GATE_PASSAGE_WIDTH  # 통로 건너뜀

        # 게이트 배열 위쪽 벽 (배열 끝 ~ y=CONCOURSE_WIDTH)
        end_y = start_y + total_h
        if end_y < CONCOURSE_WIDTH - 0.01:
            obstacles.append(Polygon([
                (wall_left, end_y), (wall_right, end_y),
                (wall_right, CONCOURSE_WIDTH), (wall_left, CONCOURSE_WIDTH)
            ]))

    # walkable = 대합실 - 장애물
    walkable = concourse
    for obs in obstacles:
        if obs.is_valid and obs.area > 0:
            walkable = walkable.difference(obs)

    return walkable, obstacles
