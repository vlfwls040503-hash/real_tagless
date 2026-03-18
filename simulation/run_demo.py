"""
성수역 보행자 이동 데모 시뮬레이션
- 계단에서 보행자가 내려와서 게이트를 통과하여 출구로 나가는 모습
- 게이트 구간 줌인 시각화 + GIF 애니메이션
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
    GATE_LINE_Y, GATE_LENGTH, CONCOURSE_LENGTH, CONCOURSE_WIDTH,
    GATE_PASSAGE_WIDTH, GATE_WIDE_PASSAGE_WIDTH, GATE_HOUSING_WIDTH,
    N_NORMAL_GATES, N_WIDE_GATES, N_TOTAL_GATES
)

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# =============================================================================
N_PEDESTRIANS = 200
SIM_TIME = 60.0
DT = 0.05
OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def create_simulation():
    gates = calculate_gate_positions()
    walkable, obstacles = build_geometry(gates)

    gate_y_bottom = GATE_LINE_Y - GATE_LENGTH / 2
    gate_y_top = GATE_LINE_Y + GATE_LENGTH / 2

    sim = jps.Simulation(
        model=jps.CollisionFreeSpeedModel(),
        geometry=walkable,
        dt=DT,
    )

    exit_area = Polygon([
        (0, 0), (CONCOURSE_LENGTH, 0),
        (CONCOURSE_LENGTH, 1.0), (0, 1.0)
    ])
    exit_id = sim.add_exit_stage(exit_area)
    journey = jps.JourneyDescription([exit_id])
    journey_id = sim.add_journey(journey)

    # 게이트 전체 범위에 걸쳐 분산 스폰
    # 실제로는 계단 3곳에서 내려오지만, 대합실에서 퍼지므로 넓게 분포
    first_gate_x = gates[0]["x"]
    last_gate_x = gates[-1]["x"]
    spawn_x_min = first_gate_x - 1.0
    spawn_x_max = last_gate_x + 1.0
    spawn_y_min = gate_y_top + 0.5
    spawn_y_max = CONCOURSE_WIDTH - 0.5

    # 계단 위치 기반 가우시안 mixture (3개 계단에서 퍼지는 형태)
    stair_centers = [15.0, 35.0, 65.0]
    stair_spread = 10.0  # 각 계단에서 퍼지는 표준편차

    rng = np.random.default_rng(42)
    spawned = 0

    for i in range(N_PEDESTRIANS):
        # 3개 계단 중 하나 선택 후 넓게 퍼뜨림
        stair_x = rng.choice(stair_centers)
        px = stair_x + rng.normal(0, stair_spread)
        # 게이트 범위 안으로 클램핑
        px = np.clip(px, spawn_x_min, spawn_x_max)
        py = rng.uniform(spawn_y_min, spawn_y_max)
        desired_speed = max(0.5, min(2.0, rng.normal(1.34, 0.26)))

        try:
            sim.add_agent(
                jps.CollisionFreeSpeedModelAgentParameters(
                    journey_id=journey_id,
                    stage_id=exit_id,
                    position=(px, py),
                    desired_speed=desired_speed,
                )
            )
            spawned += 1
        except Exception:
            pass

    print(f"Spawned {spawned}/{N_PEDESTRIANS} pedestrians")
    return sim, gates, walkable, obstacles


def draw_frame(ax, sim, gates, obstacles, time_sec, view='full'):
    """
    view='full': 전체 대합실
    view='zoom': 게이트 중심 확대
    """
    ax.clear()

    gate_y_bottom = GATE_LINE_Y - GATE_LENGTH / 2
    gate_y_top = GATE_LINE_Y + GATE_LENGTH / 2

    # ── 뷰 범위 결정 ──
    if view == 'zoom':
        # 게이트 중심부 15대 정도 보이도록 줌인
        vx_min, vx_max = 18, 48
        vy_min, vy_max = 2, 14
    else:
        vx_min, vx_max = -1, CONCOURSE_LENGTH + 1
        vy_min, vy_max = -1, CONCOURSE_WIDTH + 1

    # ── 바닥 ──
    # 유료구역 (위)
    ax.axhspan(gate_y_top, CONCOURSE_WIDTH, color='#E8F5E9', zorder=0)
    # 무료구역 (아래)
    ax.axhspan(0, gate_y_bottom, color='#FFF8E1', zorder=0)
    # 게이트 구간 바닥
    ax.axhspan(gate_y_bottom, gate_y_top, color='#ECEFF1', zorder=0)

    # ── 게이트 본체 (칸막이) ──
    for obs in obstacles:
        ox, oy = obs.exterior.xy
        ax.fill(ox, oy, color='#37474F', edgecolor='#263238', linewidth=0.8, zorder=3)

    # ── 게이트 통로 ──
    for g in gates:
        is_wide = g["type"] == "wide"
        pw = g["passage_width"]
        gx = g["x"]

        # 통로 바닥 (밝은 색)
        passage_color = '#FFE0B2' if is_wide else '#C8E6C9'
        ax.add_patch(mpatches.Rectangle(
            (gx - pw / 2, gate_y_bottom), pw, GATE_LENGTH,
            facecolor=passage_color, edgecolor='none', zorder=2
        ))

        # 통로 양쪽 플랩 (게이트 날개)
        flap_len = GATE_LENGTH * 0.35
        flap_y_top_start = gate_y_top - flap_len
        flap_y_bot_end = gate_y_bottom + flap_len
        flap_color = '#FF8F00' if is_wide else '#2E7D32'

        # 위쪽 플랩 (왼쪽)
        ax.plot([gx - pw / 2, gx - pw / 2], [gate_y_top, flap_y_top_start],
                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)
        # 위쪽 플랩 (오른쪽)
        ax.plot([gx + pw / 2, gx + pw / 2], [gate_y_top, flap_y_top_start],
                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)
        # 아래쪽 플랩 (왼쪽)
        ax.plot([gx - pw / 2, gx - pw / 2], [gate_y_bottom, flap_y_bot_end],
                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)
        # 아래쪽 플랩 (오른쪽)
        ax.plot([gx + pw / 2, gx + pw / 2], [gate_y_bottom, flap_y_bot_end],
                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)

        # 통로 중심에 통과 방향 화살표
        ax.annotate('', xy=(gx, gate_y_bottom + 0.15),
                    xytext=(gx, gate_y_top - 0.15),
                    arrowprops=dict(arrowstyle='->', color='#90A4AE', lw=0.8),
                    zorder=2)

    # ── 게이트 번호 ──
    for g in gates:
        gid = g["id"] + 1
        gx = g["x"]
        # 줌인 뷰에선 모든 번호, 전체 뷰에선 5개마다
        show = (view == 'zoom') or (gid == 1 or gid % 5 == 0 or gid == N_TOTAL_GATES)
        if show and vx_min <= gx <= vx_max:
            fontsize = 7 if view == 'zoom' else 5
            ax.text(gx, gate_y_top + 0.25, str(gid),
                    ha='center', va='bottom', fontsize=fontsize,
                    fontweight='bold', color='#455A64', zorder=5)

    # ── 구역 경계선 ──
    ax.axhline(gate_y_top, color='#1565C0', linewidth=1, linestyle='--', alpha=0.5, zorder=1)
    ax.axhline(gate_y_bottom, color='#E65100', linewidth=1, linestyle='--', alpha=0.5, zorder=1)

    # ── 계단/에스컬레이터 ──
    for sx in [15, 35, 65]:
        if vx_min - 5 <= sx <= vx_max + 5:
            sw, sh = 5, 1.8
            stair = mpatches.FancyBboxPatch(
                (sx - sw / 2, 13), sw, sh,
                boxstyle="round,pad=0.2", facecolor='#E53935', edgecolor='#B71C1C',
                linewidth=1.2, alpha=0.85, zorder=4)
            ax.add_patch(stair)
            ax.text(sx, 13 + sh / 2, 'STAIR', ha='center', va='center',
                    fontsize=7, fontweight='bold', color='white', zorder=5)

    # ── 출구 표시 ──
    for ex, label in [(15, 'EXIT 1,4'), (65, 'EXIT 2,3')]:
        if vx_min - 5 <= ex <= vx_max + 5:
            ew, eh = 5, 1.2
            exit_r = mpatches.FancyBboxPatch(
                (ex - ew / 2, 1), ew, eh,
                boxstyle="round,pad=0.15", facecolor='#7B1FA2', edgecolor='#4A148C',
                linewidth=1.2, alpha=0.85, zorder=4)
            ax.add_patch(exit_r)
            ax.text(ex, 1 + eh / 2, label, ha='center', va='center',
                    fontsize=6.5, fontweight='bold', color='white', zorder=5)

    # ── 보행자 ──
    for agent in sim.agents():
        px, py = agent.position
        if vx_min <= px <= vx_max and vy_min <= py <= vy_max:
            # 보행자 = 원 + 이동 방향
            circle = plt.Circle((px, py), 0.2, facecolor='#1565C0',
                                edgecolor='white', linewidth=0.5, zorder=6, alpha=0.9)
            ax.add_patch(circle)

    # ── 구역 라벨 ──
    label_x = vx_min + 1.5
    if view == 'zoom':
        ax.text(label_x, gate_y_top + 1.5, 'Paid Zone',
                fontsize=9, color='#2E7D32', fontweight='bold', alpha=0.7)
        ax.text(label_x, gate_y_bottom - 1, 'Free Zone',
                fontsize=9, color='#E65100', fontweight='bold', alpha=0.7)
    else:
        ax.text(3, CONCOURSE_WIDTH - 1, 'PAID ZONE (Platform)',
                fontsize=10, color='#2E7D32', fontweight='bold', alpha=0.6)
        ax.text(3, 1.5, 'FREE ZONE (Exit)',
                fontsize=10, color='#E65100', fontweight='bold', alpha=0.6)

    # ── 정보 박스 ──
    n_agents = sim.agent_count()
    info = f't = {time_sec:.1f}s | {n_agents} peds'
    ax.text(vx_max - 0.5, vy_max - 0.5, info,
            ha='right', va='top', fontsize=10, fontweight='bold', color='#333',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#999', alpha=0.9), zorder=7)

    # ── 범례 (줌인 뷰에서만) ──
    if view == 'zoom':
        legend_items = [
            mpatches.Patch(facecolor='#C8E6C9', edgecolor='#2E7D32',
                           label=f'Normal ({GATE_PASSAGE_WIDTH*100:.0f}cm)'),
            mpatches.Patch(facecolor='#FFE0B2', edgecolor='#FF8F00',
                           label=f'Wide ({GATE_WIDE_PASSAGE_WIDTH*100:.0f}cm)'),
            mpatches.Patch(facecolor='#37474F', label='Housing (30cm)'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#1565C0',
                       markersize=8, label='Pedestrian'),
        ]
        ax.legend(handles=legend_items, loc='upper left', fontsize=7,
                  framealpha=0.9, edgecolor='#999')

    # ── 축 설정 ──
    ax.set_xlim(vx_min, vx_max)
    ax.set_ylim(vy_min, vy_max)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)', fontsize=9)
    ax.set_ylabel('y (m)', fontsize=9)
    ax.tick_params(labelsize=8)


def run_and_save():
    sim, gates, walkable, obstacles = create_simulation()

    total_steps = int(SIM_TIME / DT)

    # ── 프레임 데이터 수집 ──
    print("Running simulation...")
    frame_data = []
    gif_interval = int(0.3 / DT)  # 0.3초마다

    for step in range(total_steps):
        if sim.agent_count() == 0:
            print(f"  All exited at t={step * DT:.1f}s")
            break

        if step % gif_interval == 0:
            positions = [(a.position[0], a.position[1]) for a in sim.agents()]
            frame_data.append((step * DT, positions, sim.agent_count()))

        sim.iterate()

    print(f"  Collected {len(frame_data)} frames")

    # ── 스냅샷 (전체 뷰 + 줌인 뷰 합본) ──
    print("Saving snapshots...")
    sim2, _, _, _ = create_simulation()
    snapshot_times = [0, 10, 20, 30, 40]
    snapshot_step_interval = int(10.0 / DT)

    fig_snap, axes_snap = plt.subplots(len(snapshot_times), 2, figsize=(22, len(snapshot_times) * 4))
    fig_snap.suptitle('Seongsu Station Pedestrian Simulation - Snapshots',
                      fontsize=16, fontweight='bold', y=0.995)

    for idx, t_target in enumerate(snapshot_times):
        target_step = int(t_target / DT)
        current_step = 0

        while current_step < target_step and sim2.agent_count() > 0:
            sim2.iterate()
            current_step += 1

        # 전체 뷰
        draw_frame(axes_snap[idx, 0], sim2, gates, obstacles, t_target, view='full')
        axes_snap[idx, 0].set_title(f'Full View (t={t_target}s)', fontsize=10, fontweight='bold')

        # 줌인 뷰
        draw_frame(axes_snap[idx, 1], sim2, gates, obstacles, t_target, view='zoom')
        axes_snap[idx, 1].set_title(f'Gate Zoom (t={t_target}s)', fontsize=10, fontweight='bold')

    fig_snap.tight_layout()
    fig_snap.savefig(OUTPUT_DIR / "snapshots_combined.png", dpi=130, bbox_inches='tight')
    plt.close(fig_snap)
    print("  snapshots_combined.png saved")

    # ── GIF (줌인 뷰) ──
    print(f"Creating GIF ({len(frame_data)} frames)...")

    # GIF용 시뮬레이션 재실행
    sim3, _, _, _ = create_simulation()
    gif_frames = []
    gif_step_interval = int(0.3 / DT)

    for step in range(total_steps):
        if sim3.agent_count() == 0:
            break
        if step % gif_step_interval == 0:
            gif_frames.append(step)
            # 프레임 이미지 저장
        sim3.iterate()

    # 실제 GIF 생성
    sim4, _, _, _ = create_simulation()
    fig_gif, ax_gif = plt.subplots(1, 1, figsize=(14, 7))

    frame_images = []
    frame_count = 0

    for step in range(total_steps):
        if sim4.agent_count() == 0:
            break

        if step % gif_step_interval == 0:
            draw_frame(ax_gif, sim4, gates, obstacles, step * DT, view='zoom')
            fig_gif.canvas.draw()
            frame_count += 1

            if frame_count % 20 == 0:
                print(f"  Frame {frame_count}...")

        sim4.iterate()

    # FuncAnimation으로 GIF
    sim5, _, _, _ = create_simulation()
    fig_anim, ax_anim = plt.subplots(1, 1, figsize=(14, 7))

    # 미리 모든 프레임의 agent 위치를 수집
    all_frames = []
    for step in range(total_steps):
        if sim5.agent_count() == 0:
            break
        if step % gif_step_interval == 0:
            agents_pos = [(a.position[0], a.position[1]) for a in sim5.agents()]
            all_frames.append((step * DT, agents_pos))
        sim5.iterate()

    class SimAnimator:
        def __init__(self, fig, ax, gates, obstacles, frames):
            self.fig = fig
            self.ax = ax
            self.gates = gates
            self.obstacles = obstacles
            self.frames = frames

        def __call__(self, i):
            t, positions = self.frames[i]
            self.ax.clear()

            gate_y_bottom = GATE_LINE_Y - GATE_LENGTH / 2
            gate_y_top = GATE_LINE_Y + GATE_LENGTH / 2
            vx_min, vx_max = 18, 48
            vy_min, vy_max = 2, 14

            # 바닥
            self.ax.axhspan(gate_y_top, CONCOURSE_WIDTH, color='#E8F5E9', zorder=0)
            self.ax.axhspan(0, gate_y_bottom, color='#FFF8E1', zorder=0)
            self.ax.axhspan(gate_y_bottom, gate_y_top, color='#ECEFF1', zorder=0)

            # 게이트 본체
            for obs in self.obstacles:
                ox, oy = obs.exterior.xy
                self.ax.fill(ox, oy, color='#37474F', edgecolor='#263238',
                             linewidth=0.8, zorder=3)

            # 게이트 통로 + 플랩
            for g in self.gates:
                is_wide = g["type"] == "wide"
                pw = g["passage_width"]
                gx = g["x"]

                passage_color = '#FFE0B2' if is_wide else '#C8E6C9'
                self.ax.add_patch(mpatches.Rectangle(
                    (gx - pw / 2, gate_y_bottom), pw, GATE_LENGTH,
                    facecolor=passage_color, edgecolor='none', zorder=2))

                flap_len = GATE_LENGTH * 0.35
                flap_color = '#FF8F00' if is_wide else '#2E7D32'

                for side in [-1, 1]:
                    x = gx + side * pw / 2
                    self.ax.plot([x, x], [gate_y_top, gate_y_top - flap_len],
                                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)
                    self.ax.plot([x, x], [gate_y_bottom, gate_y_bottom + flap_len],
                                color=flap_color, linewidth=2.5, solid_capstyle='round', zorder=4)

                self.ax.annotate('', xy=(gx, gate_y_bottom + 0.15),
                                xytext=(gx, gate_y_top - 0.15),
                                arrowprops=dict(arrowstyle='->', color='#B0BEC5', lw=0.7),
                                zorder=2)

            # 게이트 번호
            for g in self.gates:
                gx = g["x"]
                if vx_min <= gx <= vx_max:
                    self.ax.text(gx, gate_y_top + 0.25, str(g["id"] + 1),
                                ha='center', va='bottom', fontsize=6.5,
                                fontweight='bold', color='#455A64', zorder=5)

            # 경계선
            self.ax.axhline(gate_y_top, color='#1565C0', linewidth=1,
                            linestyle='--', alpha=0.4, zorder=1)
            self.ax.axhline(gate_y_bottom, color='#E65100', linewidth=1,
                            linestyle='--', alpha=0.4, zorder=1)

            # 계단
            for sx in [35]:
                if vx_min - 5 <= sx <= vx_max + 5:
                    self.ax.add_patch(mpatches.FancyBboxPatch(
                        (sx - 2.5, 12.8), 5, 1.0,
                        boxstyle="round,pad=0.15", facecolor='#E53935',
                        edgecolor='#B71C1C', linewidth=1, alpha=0.85, zorder=4))
                    self.ax.text(sx, 13.3, 'STAIR/ESC', ha='center', va='center',
                                fontsize=6.5, fontweight='bold', color='white', zorder=5)

            # 구역 라벨
            self.ax.text(vx_min + 0.5, gate_y_top + 1.5, 'Paid Zone (Platform side)',
                         fontsize=8, color='#2E7D32', fontweight='bold', alpha=0.6)
            self.ax.text(vx_min + 0.5, gate_y_bottom - 1.2, 'Free Zone (Exit side)',
                         fontsize=8, color='#BF360C', fontweight='bold', alpha=0.6)

            # 보행자
            for px, py in positions:
                if vx_min <= px <= vx_max and vy_min <= py <= vy_max:
                    self.ax.add_patch(plt.Circle(
                        (px, py), 0.2, facecolor='#0D47A1',
                        edgecolor='white', linewidth=0.4, zorder=6, alpha=0.9))

            # 정보 박스
            self.ax.text(vx_max - 0.5, vy_max - 0.3,
                         f't = {t:.1f}s | {len(positions)} peds',
                         ha='right', va='top', fontsize=10, fontweight='bold', color='#333',
                         bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                                   edgecolor='#999', alpha=0.9), zorder=7)

            # 범례
            legend_items = [
                mpatches.Patch(facecolor='#C8E6C9', edgecolor='#2E7D32',
                               label=f'Normal Gate ({GATE_PASSAGE_WIDTH*100:.0f}cm)'),
                mpatches.Patch(facecolor='#FFE0B2', edgecolor='#FF8F00',
                               label=f'Wide Gate ({GATE_WIDE_PASSAGE_WIDTH*100:.0f}cm)'),
                mpatches.Patch(facecolor='#37474F', label='Gate Housing'),
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#0D47A1',
                           markersize=8, label='Pedestrian'),
            ]
            self.ax.legend(handles=legend_items, loc='lower right', fontsize=7,
                           framealpha=0.9, edgecolor='#999')

            self.ax.set_xlim(vx_min, vx_max)
            self.ax.set_ylim(vy_min, vy_max)
            self.ax.set_aspect('equal')
            self.ax.set_xlabel('x (m)', fontsize=9)
            self.ax.set_ylabel('y (m)', fontsize=9)
            self.ax.set_title('Seongsu Station Gate Area - Pedestrian Flow',
                              fontsize=12, fontweight='bold')

    animator = SimAnimator(fig_anim, ax_anim, gates, obstacles, all_frames)

    anim = FuncAnimation(fig_anim, animator, frames=len(all_frames), interval=80)
    gif_path = OUTPUT_DIR / "pedestrian_simulation.gif"
    anim.save(str(gif_path), writer=PillowWriter(fps=12))
    plt.close(fig_anim)
    print(f"  GIF saved: {gif_path}")
    print("Done!")


if __name__ == "__main__":
    run_and_save()
