"""
성수역 2F 대합실 게이트 구간 시뮬레이션 (JuPedSim)

범위: 계단/에스컬레이터 출구 → 대합실 → 개찰구 통과
방향: 하차 승객이 플랫폼(3F)에서 계단을 내려와 대합실(2F)을 거쳐 개찰구를 통과하여 나가는 동선

게이트 규격 (실제 지하철 표준):
- 일반 턴스타일 통로 폭: 550mm
- 우대용 게이트 통로 폭: 900mm
- 게이트 본체(housing) 폭: 300mm
- 게이트 본체 길이: 1500mm

성수역 게이트 현황:
- 턴스타일 개집표기: 31대
- 우대자용 개집표기: 8대
- 합계: 39대
"""

import jupedsim as jps
import pedpy
import pathlib
import numpy as np
from shapely import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm

# 한글 폰트 설정 (Windows)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# =============================================================================
# 1. 게이트 규격 (단위: m)
# =============================================================================
GATE_PASSAGE_WIDTH = 0.55       # 일반 게이트 통로 폭
GATE_WIDE_PASSAGE_WIDTH = 0.90  # 우대용 게이트 통로 폭
GATE_HOUSING_WIDTH = 0.30       # 게이트 본체(칸막이) 폭
GATE_LENGTH = 1.50              # 게이트 본체 길이 (통과 방향)

N_NORMAL_GATES = 31             # 일반 턴스타일
N_WIDE_GATES = 8                # 우대용
N_TOTAL_GATES = N_NORMAL_GATES + N_WIDE_GATES  # 39

# =============================================================================
# 2. 성수역 2F 대합실 기하구조 정의
# =============================================================================
# 성수역 안내도 기반 대합실 레이아웃 (간략화)
#
# 이미지 분석 결과:
# - 대합실은 동서 방향으로 긴 직사각형 형태
# - 게이트는 대합실 중앙에 동서 방향으로 일렬 배치
# - 계단/에스컬레이터는 대합실 양쪽 끝에 위치
# - 출구 1,4는 서쪽(뚝섬방면), 출구 2,3은 동쪽(건대입구방면)
#
# 좌표계: x = 동서방향(길이), y = 남북방향(폭)
# 원점: 대합실 서쪽 끝 하단

# 대합실 크기 추정 (성수역 규모 기반)
CONCOURSE_LENGTH = 80.0   # 대합실 길이 (m) - 동서
CONCOURSE_WIDTH = 16.0    # 대합실 폭 (m) - 남북

# 게이트 라인 위치 (대합실 중앙 부근, y방향 중심)
GATE_LINE_Y = CONCOURSE_WIDTH / 2  # 게이트 중심선 y좌표 = 8.0m
GATE_LINE_X_START = 10.0           # 게이트 배열 시작 x좌표
# 게이트 배열 끝은 자동 계산

# =============================================================================
# 3. 게이트 위치 계산
# =============================================================================
def calculate_gate_positions():
    """각 게이트의 중심 x좌표, 통로 폭, 유형을 계산"""
    gates = []
    x = GATE_LINE_X_START

    # 게이트 배치: 좌측부터 일반 + 우대용 혼합 배치
    # 실제 성수역 배치를 근사: 우대용 게이트는 양 끝에 분산 배치
    gate_types = []

    # 우대용 게이트를 균등 분산 배치 (약 5개마다 1개)
    wide_positions = set()
    interval = N_TOTAL_GATES // N_WIDE_GATES
    for i in range(N_WIDE_GATES):
        pos = i * interval
        if pos >= N_TOTAL_GATES:
            pos = N_TOTAL_GATES - 1
        wide_positions.add(pos)

    for i in range(N_TOTAL_GATES):
        if i in wide_positions:
            gate_types.append("wide")
        else:
            gate_types.append("normal")

    # 각 게이트 위치 계산
    for i, gtype in enumerate(gate_types):
        passage_w = GATE_WIDE_PASSAGE_WIDTH if gtype == "wide" else GATE_PASSAGE_WIDTH

        if i == 0:
            # 첫 게이트: 시작 위치 + 본체 반폭 + 통로 반폭
            x = GATE_LINE_X_START + GATE_HOUSING_WIDTH + passage_w / 2
        else:
            # 이전 게이트 통로 반폭 + 본체 폭 + 현재 통로 반폭
            prev_pw = gates[-1]["passage_width"]
            x = gates[-1]["x"] + prev_pw / 2 + GATE_HOUSING_WIDTH + passage_w / 2

        gates.append({
            "id": i,
            "x": x,
            "type": gtype,
            "passage_width": passage_w,
        })

    return gates


def build_geometry(gates):
    """
    대합실 walkable area를 생성 (게이트 본체를 장애물로 배치)

    구조:
    ┌─────────────────────────────────────────────────────┐
    │                  유료구역 (게이트 북쪽)                │  y=16
    │   [계단A]                              [계단B]       │
    │                                                     │  y=GATE_LINE_Y + GATE_LENGTH/2 + passage
    │  ║G1║G2║G3║ ... ║G38║G39║   ← 게이트 라인            │  y=GATE_LINE_Y
    │                                                     │  y=GATE_LINE_Y - GATE_LENGTH/2 - passage
    │   [출구1,4]                            [출구2,3]     │
    │                  무료구역 (게이트 남쪽)                │  y=0
    └─────────────────────────────────────────────────────┘
    """
    # 대합실 외곽
    concourse = Polygon([
        (0, 0),
        (CONCOURSE_LENGTH, 0),
        (CONCOURSE_LENGTH, CONCOURSE_WIDTH),
        (0, CONCOURSE_WIDTH),
    ])

    # 게이트 본체(housing)를 장애물로 생성
    # 각 게이트 사이의 칸막이 + 양 끝 벽
    obstacles = []

    # 게이트 라인의 y범위
    gate_y_bottom = GATE_LINE_Y - GATE_LENGTH / 2
    gate_y_top = GATE_LINE_Y + GATE_LENGTH / 2

    # 첫 게이트 왼쪽 벽 (게이트 시작점까지)
    first_gate = gates[0]
    wall_left = Polygon([
        (0, gate_y_bottom),
        (first_gate["x"] - first_gate["passage_width"] / 2, gate_y_bottom),
        (first_gate["x"] - first_gate["passage_width"] / 2, gate_y_top),
        (0, gate_y_top),
    ])
    obstacles.append(wall_left)

    # 게이트 사이의 칸막이(housing)
    for i in range(len(gates) - 1):
        g_curr = gates[i]
        g_next = gates[i + 1]

        housing_x_left = g_curr["x"] + g_curr["passage_width"] / 2
        housing_x_right = g_next["x"] - g_next["passage_width"] / 2

        housing = Polygon([
            (housing_x_left, gate_y_bottom),
            (housing_x_right, gate_y_bottom),
            (housing_x_right, gate_y_top),
            (housing_x_left, gate_y_top),
        ])
        obstacles.append(housing)

    # 마지막 게이트 오른쪽 벽 (게이트 끝부터 대합실 끝까지)
    last_gate = gates[-1]
    wall_right = Polygon([
        (last_gate["x"] + last_gate["passage_width"] / 2, gate_y_bottom),
        (CONCOURSE_LENGTH, gate_y_bottom),
        (CONCOURSE_LENGTH, gate_y_top),
        (last_gate["x"] + last_gate["passage_width"] / 2, gate_y_top),
    ])
    obstacles.append(wall_right)

    # walkable area = 대합실 - 장애물
    walkable = concourse
    for obs in obstacles:
        if obs.is_valid and obs.area > 0:
            walkable = walkable.difference(obs)

    return walkable, obstacles


# =============================================================================
# 4. 시각화
# =============================================================================
def plot_station(walkable, gates, obstacles, save_path=None):
    """성수역 대합실 레이아웃 시각화"""
    fig, ax = plt.subplots(1, 1, figsize=(22, 10))

    gate_y_bottom = GATE_LINE_Y - GATE_LENGTH / 2
    gate_y_top = GATE_LINE_Y + GATE_LENGTH / 2

    # ── 배경: 유료/무료 구역 구분 ──
    # 유료구역 (게이트 위쪽 = 승강장 쪽)
    paid_zone = mpatches.Rectangle(
        (0, gate_y_top), CONCOURSE_LENGTH, CONCOURSE_WIDTH - gate_y_top,
        facecolor='#E3F2FD', edgecolor='#1565C0', linewidth=1.5, linestyle='--'
    )
    ax.add_patch(paid_zone)

    # 무료구역 (게이트 아래쪽 = 출구 쪽)
    free_zone = mpatches.Rectangle(
        (0, 0), CONCOURSE_LENGTH, gate_y_bottom,
        facecolor='#FFF3E0', edgecolor='#E65100', linewidth=1.5, linestyle='--'
    )
    ax.add_patch(free_zone)

    # ── 게이트 본체 (칸막이) = 회색 직사각형 ──
    for obs in obstacles:
        ox, oy = obs.exterior.xy
        ax.fill(ox, oy, color='#616161', edgecolor='#212121', linewidth=0.5)

    # ── 게이트 통로 = 사람이 지나가는 틈 ──
    for g in gates:
        is_wide = g["type"] == "wide"
        color = '#FF9800' if is_wide else '#4CAF50'
        edge = '#E65100' if is_wide else '#1B5E20'

        rect = mpatches.Rectangle(
            (g["x"] - g["passage_width"] / 2, gate_y_bottom),
            g["passage_width"], GATE_LENGTH,
            linewidth=1, edgecolor=edge, facecolor=color, alpha=0.5
        )
        ax.add_patch(rect)

    # ── 게이트 번호 (위에 표시) ──
    for g in gates:
        gid = g["id"] + 1
        if gid == 1 or gid % 5 == 0 or gid == N_TOTAL_GATES:
            ax.text(g["x"], gate_y_top + 0.4, f'{gid}',
                    ha='center', va='bottom', fontsize=7, fontweight='bold', color='#333')

    # ── 계단/에스컬레이터 (승강장에서 내려오는 지점) ──
    stair_specs = [
        {"x": 15, "label": "Stair/ESC A\n(Exit 1,4)"},
        {"x": 35, "label": "Stair/ESC B\n(Center)"},
        {"x": 65, "label": "Stair/ESC C\n(Exit 2,3)"},
    ]
    stair_y = 13.0
    stair_w, stair_h = 4.0, 2.0

    for s in stair_specs:
        stair_rect = mpatches.FancyBboxPatch(
            (s["x"] - stair_w / 2, stair_y - stair_h / 2), stair_w, stair_h,
            boxstyle="round,pad=0.2", facecolor='#EF5350', edgecolor='#B71C1C',
            linewidth=1.5, alpha=0.8
        )
        ax.add_patch(stair_rect)
        ax.text(s["x"], stair_y, s["label"],
                ha='center', va='center', fontsize=7, fontweight='bold', color='white')

        # 화살표: 계단 → 게이트 방향
        ax.annotate('', xy=(s["x"], gate_y_top + 0.3),
                    xytext=(s["x"], stair_y - stair_h / 2 - 0.2),
                    arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2))

    # ── 출구 표시 (무료구역 아래) ──
    exit_specs = [
        {"x": 15, "label": "Exit 1, 4"},
        {"x": 65, "label": "Exit 2, 3"},
    ]
    exit_y = 2.5

    for e in exit_specs:
        exit_rect = mpatches.FancyBboxPatch(
            (e["x"] - 3, exit_y - 1), 6, 2,
            boxstyle="round,pad=0.2", facecolor='#AB47BC', edgecolor='#6A1B9A',
            linewidth=1.5, alpha=0.8
        )
        ax.add_patch(exit_rect)
        ax.text(e["x"], exit_y, e["label"],
                ha='center', va='center', fontsize=8, fontweight='bold', color='white')

        # 화살표: 게이트 → 출구 방향
        ax.annotate('', xy=(e["x"], exit_y + 1.2),
                    xytext=(e["x"], gate_y_bottom - 0.3),
                    arrowprops=dict(arrowstyle='->', color='#E65100', lw=2))

    # ── 보행 동선 큰 화살표 (전체 흐름) ──
    ax.annotate('',
                xy=(CONCOURSE_LENGTH / 2, gate_y_bottom - 0.5),
                xytext=(CONCOURSE_LENGTH / 2, gate_y_top + 2.5),
                arrowprops=dict(arrowstyle='->', color='#0D47A1', lw=3, alpha=0.4))
    ax.text(CONCOURSE_LENGTH / 2 + 3, GATE_LINE_Y + 3,
            'Pedestrian Flow\n(Platform -> Gate -> Exit)',
            ha='left', va='center', fontsize=9, color='#0D47A1', fontstyle='italic')

    # ── 구역 라벨 ──
    ax.text(3, CONCOURSE_WIDTH - 1.5,
            'PAID ZONE (Platform side)',
            ha='left', va='center', fontsize=11, color='#1565C0', fontweight='bold')
    ax.text(3, 1,
            'FREE ZONE (Exit side)',
            ha='left', va='center', fontsize=11, color='#E65100', fontweight='bold')

    # ── 게이트 라인 설명 ──
    # 확대도 (오른쪽에 작은 박스로 게이트 구조 설명)
    inset_x, inset_y = CONCOURSE_LENGTH - 22, CONCOURSE_WIDTH - 5.5
    inset_w, inset_h = 20, 5

    inset_bg = mpatches.FancyBboxPatch(
        (inset_x, inset_y), inset_w, inset_h,
        boxstyle="round,pad=0.3", facecolor='white', edgecolor='#333',
        linewidth=1, alpha=0.95
    )
    ax.add_patch(inset_bg)

    # 확대도 내용
    ax.text(inset_x + inset_w / 2, inset_y + inset_h - 0.5,
            'Gate Structure (Top View)', ha='center', va='top',
            fontsize=9, fontweight='bold', color='#333')

    # 미니 게이트 그림
    mini_y = inset_y + 1.2
    mini_scale = 3.0  # 확대 배율

    for i in range(4):
        # 칸막이 (housing)
        hx = inset_x + 2 + i * (0.55 + 0.30) * mini_scale
        hw = 0.30 * mini_scale
        hh = 1.5 * mini_scale * 0.3
        h_rect = mpatches.Rectangle((hx, mini_y), hw, hh,
                                     facecolor='#616161', edgecolor='#212121', linewidth=1)
        ax.add_patch(h_rect)

        # 통로 (passage)
        if i < 3:
            px = hx + hw
            pw = 0.55 * mini_scale
            p_rect = mpatches.Rectangle((px, mini_y), pw, hh,
                                         facecolor='#4CAF50', edgecolor='#1B5E20',
                                         linewidth=1, alpha=0.5)
            ax.add_patch(p_rect)

    # 확대도 라벨
    ax.annotate('Housing\n(30cm)', xy=(inset_x + 2.3, mini_y - 0.1),
                ha='center', va='top', fontsize=6, color='#616161')
    ax.annotate('Passage\n(55cm)', xy=(inset_x + 4.5, mini_y - 0.1),
                ha='center', va='top', fontsize=6, color='#1B5E20')

    # ── 범례 ──
    legend_items = [
        mpatches.Patch(color='#4CAF50', alpha=0.5,
                       label=f'Normal Gate: {N_NORMAL_GATES}ea (passage {GATE_PASSAGE_WIDTH*100:.0f}cm)'),
        mpatches.Patch(color='#FF9800', alpha=0.5,
                       label=f'Wide Gate: {N_WIDE_GATES}ea (passage {GATE_WIDE_PASSAGE_WIDTH*100:.0f}cm)'),
        mpatches.Patch(color='#616161', alpha=0.8,
                       label=f'Gate Housing (barrier {GATE_HOUSING_WIDTH*100:.0f}cm)'),
        mpatches.Patch(color='#EF5350', alpha=0.8, label='Stair / Escalator'),
        mpatches.Patch(color='#AB47BC', alpha=0.8, label='Exit'),
    ]
    ax.legend(handles=legend_items, loc='lower right', fontsize=8,
              framealpha=0.95, edgecolor='#333')

    # ── 축 설정 ──
    ax.set_xlim(-2, CONCOURSE_LENGTH + 2)
    ax.set_ylim(-2, CONCOURSE_WIDTH + 2)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)', fontsize=10)
    ax.set_ylabel('y (m)', fontsize=10)
    ax.set_title('Seongsu Station 2F Concourse - Gate Layout (39 Gates)',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.2, linestyle=':')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {save_path}")

    return fig, ax


# =============================================================================
# 5. 메인 실행
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("성수역 2F 대합실 게이트 구간 기하구조 생성")
    print("=" * 60)

    # 게이트 위치 계산
    gates = calculate_gate_positions()

    # 게이트 배치 요약
    print(f"\n게이트 총 {len(gates)}대:")
    print(f"  일반 턴스타일: {sum(1 for g in gates if g['type'] == 'normal')}대 (통로 {GATE_PASSAGE_WIDTH*100:.0f}cm)")
    print(f"  우대용: {sum(1 for g in gates if g['type'] == 'wide')}대 (통로 {GATE_WIDE_PASSAGE_WIDTH*100:.0f}cm)")

    first_x = gates[0]["x"] - gates[0]["passage_width"] / 2 - GATE_HOUSING_WIDTH
    last_x = gates[-1]["x"] + gates[-1]["passage_width"] / 2
    total_gate_span = last_x - first_x
    print(f"\n게이트 배열 범위: {first_x:.1f}m ~ {last_x:.1f}m (총 {total_gate_span:.1f}m)")

    # 기하구조 생성
    walkable, obstacles = build_geometry(gates)
    print(f"\nWalkable area: {walkable.area:.1f} m²")
    print(f"장애물 수: {len(obstacles)}개")

    # JuPedSim 시뮬레이션 생성 테스트
    print("\nJuPedSim 시뮬레이션 객체 생성 테스트...")
    try:
        simulation = jps.Simulation(
            model=jps.CollisionFreeSpeedModel(),
            geometry=walkable,
        )
        print("성공! JuPedSim이 이 기하구조를 정상 인식합니다.")
    except Exception as e:
        print(f"오류: {e}")

    # 시각화
    output_dir = pathlib.Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    fig, ax = plot_station(walkable, gates, obstacles,
                           save_path=str(output_dir / "seongsu_gate_layout.png"))
    print("\n완료!")
    plt.show()
