"""
Blender 3D 렌더링 스크립트
사용법: blender --background --python blender_render.py

- seongsu_west.py 기하구조를 3D로 변환 (벽 extrude, 바닥)
- trajectories.csv 읽어서 보행자 애니메이션
- MP4 렌더링
"""
import bpy
import bmesh
import csv
import math
import sys
import os
from collections import defaultdict

# ── 설정 ───────────────────────────────────────────────
PROJECT_ROOT = r"C:\Users\aaron\tagless"
CSV_PATH = os.path.join(PROJECT_ROOT, "output", "trajectories.csv")
OUTPUT_MP4 = os.path.join(PROJECT_ROOT, "output", "blender_3d.mp4")

WALL_HEIGHT = 3.0          # 벽 높이 (m)
PERSON_HEIGHT = 1.7        # 사람 높이
PERSON_RADIUS = 0.25       # 사람 반경
FPS = 10                   # 영상 재생 fps
TIME_PER_FRAME = 0.5       # 2D mp4와 동일: 1 video frame = 0.5s 시뮬 (5배속)
START_TIME = 0.0
END_TIME = 120.0
MAX_AGENTS = 9999          # 전체 (제한 없음)

# 성수역 기하구조 (seongsu_west.py 에서 복사)
CONCOURSE_LENGTH = 32.0
CONCOURSE_WIDTH = 25.0
NOTCH_X = 14.0
NOTCH_Y = 22.0
GATE_X = 12.0
GATE_LENGTH = 1.5
N_GATES = 7
GATE_PASSAGE_WIDTH = 0.55
GATE_HOUSING_WIDTH = 0.30

STAIRS = [
    {"id": "upper", "x": 1.0, "y_start": 15.0, "y_end": 18.0},
    {"id": "lower", "x": 1.0, "y_start": 8.0,  "y_end": 11.0},
]
EXITS = [
    {"x_start": 26.0, "x_end": 29.0, "y": 24.0},
    {"x_start": 26.0, "x_end": 29.0, "y": 3.0},
]

# 게이트 y 좌표 계산
BARRIER_Y_BOTTOM = 9.5
BARRIER_Y_TOP = 15.5
GATE_YS = []
cluster_height = N_GATES * GATE_PASSAGE_WIDTH + (N_GATES + 1) * GATE_HOUSING_WIDTH
barrier_center_y = (BARRIER_Y_BOTTOM + BARRIER_Y_TOP) / 2
cluster_bottom = barrier_center_y - cluster_height / 2
for i in range(N_GATES):
    y = cluster_bottom + GATE_HOUSING_WIDTH + (GATE_PASSAGE_WIDTH + GATE_HOUSING_WIDTH) * i + GATE_PASSAGE_WIDTH / 2
    GATE_YS.append(y)


# ── 씬 초기화 ─────────────────────────────────────────
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def add_material(name, color):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    return mat


# ── 바닥 ───────────────────────────────────────────────
def create_floor():
    bpy.ops.mesh.primitive_plane_add(size=1)
    obj = bpy.context.active_object
    obj.name = "Floor"
    obj.scale = (CONCOURSE_LENGTH, CONCOURSE_WIDTH, 1)
    obj.location = (CONCOURSE_LENGTH / 2, CONCOURSE_WIDTH / 2, 0)
    mat = add_material("FloorMat", (0.85, 0.85, 0.80))
    obj.data.materials.append(mat)


# ── 외벽 ───────────────────────────────────────────────
def create_wall(p1, p2, name, height=WALL_HEIGHT):
    """두 점 사이 벽 생성"""
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    angle = math.atan2(y2 - y1, x2 - x1)

    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (length, 0.15, height)
    obj.location = (cx, cy, height / 2)
    obj.rotation_euler = (0, 0, angle)
    return obj


def create_outer_walls():
    # 대합실 외곽
    corners = [
        (0, 0),
        (CONCOURSE_LENGTH, 0),
        (CONCOURSE_LENGTH, CONCOURSE_WIDTH),
        (NOTCH_X, CONCOURSE_WIDTH),
        (NOTCH_X, NOTCH_Y),
        (0, NOTCH_Y),
    ]
    mat = add_material("WallMat", (0.6, 0.55, 0.5))
    for i in range(len(corners)):
        p1 = corners[i]
        p2 = corners[(i + 1) % len(corners)]
        obj = create_wall(p1, p2, f"Wall_{i}")
        obj.data.materials.append(mat)


# ── 게이트 배리어 ──────────────────────────────────────
def create_gate_barriers():
    # 게이트 housing: 회색
    mat_barrier = add_material("GateBarrier", (0.35, 0.4, 0.45))
    # 게이트 통로 표시: 초록색
    mat_opening = add_material("GateOpening", (0.2, 0.85, 0.3))

    # 게이트 클러스터 상하 여백
    top_barrier_start = GATE_YS[-1] + GATE_PASSAGE_WIDTH / 2
    bottom_barrier_end = GATE_YS[0] - GATE_PASSAGE_WIDTH / 2

    # 위쪽 배리어 (게이트 클러스터 위)
    if NOTCH_Y > top_barrier_start:
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = "Barrier_Top"
        obj.scale = (GATE_LENGTH, NOTCH_Y - top_barrier_start, WALL_HEIGHT)
        obj.location = (GATE_X + GATE_LENGTH / 2, (top_barrier_start + NOTCH_Y) / 2, WALL_HEIGHT / 2)
        obj.data.materials.append(mat_barrier)

    # 아래쪽 배리어
    if bottom_barrier_end > 0:
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = "Barrier_Bottom"
        obj.scale = (GATE_LENGTH, bottom_barrier_end - 0, WALL_HEIGHT)
        obj.location = (GATE_X + GATE_LENGTH / 2, bottom_barrier_end / 2, WALL_HEIGHT / 2)
        obj.data.materials.append(mat_barrier)

    # 게이트 사이 housing (게이트 사이 벽)
    for i in range(N_GATES + 1):
        if i == 0:
            y_center = GATE_YS[0] - GATE_PASSAGE_WIDTH / 2 - GATE_HOUSING_WIDTH / 2
        elif i == N_GATES:
            y_center = GATE_YS[-1] + GATE_PASSAGE_WIDTH / 2 + GATE_HOUSING_WIDTH / 2
        else:
            y_center = (GATE_YS[i - 1] + GATE_YS[i]) / 2

        if i == 0 or i == N_GATES:
            continue  # 상하 배리어로 대체
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = f"GateHousing_{i}"
        obj.scale = (GATE_LENGTH, GATE_HOUSING_WIDTH, WALL_HEIGHT * 0.8)
        obj.location = (GATE_X + GATE_LENGTH / 2, y_center, WALL_HEIGHT * 0.4)
        obj.data.materials.append(mat_barrier)

    # 게이트 번호 표시 (green light)
    for i, y in enumerate(GATE_YS):
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = f"GateLight_{i+1}"
        obj.scale = (GATE_LENGTH * 0.8, GATE_PASSAGE_WIDTH * 0.8, 0.1)
        obj.location = (GATE_X + GATE_LENGTH / 2, y, WALL_HEIGHT + 0.1)
        obj.data.materials.append(mat_opening)


# ── 계단 + 출구 시각화 ────────────────────────────────
def create_stairs_and_exits():
    # 계단: 빨간색 (에이전트 등장점)
    mat_stair = add_material("Stair", (0.9, 0.15, 0.15))
    # 출구: 노란색 (퇴장점)
    mat_exit = add_material("Exit", (0.95, 0.85, 0.15))

    for s in STAIRS:
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = f"Stair_{s['id']}"
        obj.scale = (0.4, s['y_end'] - s['y_start'], 0.5)
        obj.location = (s['x'], (s['y_start'] + s['y_end']) / 2, 0.25)
        obj.data.materials.append(mat_stair)

    for i, e in enumerate(EXITS):
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.active_object
        obj.name = f"Exit_{i}"
        obj.scale = (e['x_end'] - e['x_start'], 0.4, 0.5)
        obj.location = ((e['x_start'] + e['x_end']) / 2, e['y'], 0.25)
        obj.data.materials.append(mat_exit)


# ── 조명 & 카메라 ─────────────────────────────────────
def create_lighting_and_camera():
    # Sun light
    bpy.ops.object.light_add(type='SUN')
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(45), math.radians(30), 0)

    # Ambient
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.8, 0.85, 0.9, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    # Camera: 대합실 전체 오버뷰 (게이트 + 계단 영역 모두 보이게)
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.location = (CONCOURSE_LENGTH / 2, -5, 22)  # 전면 위쪽
    target = (CONCOURSE_LENGTH / 2, CONCOURSE_WIDTH / 2, 0)
    import mathutils
    direction = mathutils.Vector(target) - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    cam.data.lens = 24  # 광각
    bpy.context.scene.camera = cam


# ── 보행자 생성 & 애니메이션 ──────────────────────────
def load_trajectories():
    agents = defaultdict(list)
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            t = float(r['time'])
            if t < START_TIME or t > END_TIME:
                continue
            agents[r['agent_id']].append({
                't': t,
                'x': float(r['x']),
                'y': float(r['y']),
                'state': r['state'],
            })
    # 시간 정렬
    for aid in agents:
        agents[aid].sort(key=lambda r: r['t'])
    # 첫 등장 시간순으로 정렬 후 샘플링
    sorted_aids = sorted(agents.keys(), key=lambda a: agents[a][0]['t'])
    # 균등 샘플 (전체에서 MAX_AGENTS명)
    if len(sorted_aids) > MAX_AGENTS:
        step = len(sorted_aids) / MAX_AGENTS
        picked = [sorted_aids[int(i * step)] for i in range(MAX_AGENTS)]
        agents = {aid: agents[aid] for aid in picked}
    return agents


def create_person(name, color=(0.4, 0.75, 0.95)):  # 하늘색
    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.active_object
    body.scale = (PERSON_RADIUS * 1.2, PERSON_RADIUS * 0.8, PERSON_HEIGHT * 0.55)
    body.location = (0, 0, PERSON_HEIGHT * 0.35)
    mat = add_material(f"{name}_body", color)
    body.data.materials.append(mat)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=PERSON_RADIUS * 0.6, segments=8, ring_count=6)
    head = bpy.context.active_object
    head.location = (0, 0, PERSON_HEIGHT * 0.85)
    head.data.materials.append(mat)  # 머리도 같은 하늘색

    head.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def animate_agents(agents):
    """각 에이전트에 대해 프레임별 keyframe 설정"""
    scene = bpy.context.scene
    scene.frame_start = 1
    # 전체 프레임 수 = 시뮬 시간 / (프레임당 시뮬 시간)
    scene.frame_end = int((END_TIME - START_TIME) / TIME_PER_FRAME)
    scene.render.fps = FPS

    # 기본 키프레임 보간: LINEAR (등속 이동)
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass

    print(f"Animating {len(agents)} agents...")

    mat_move = add_material("PersonMove", (0.2, 0.4, 0.9))
    mat_queue = add_material("PersonQueue", (0.95, 0.5, 0.1))
    mat_pass = add_material("PersonPass", (0.2, 0.7, 0.3))

    for idx, (aid, records) in enumerate(agents.items()):
        if idx % 100 == 0:
            print(f"  {idx}/{len(agents)}")
        obj = create_person(f"Person_{aid}")
        obj.data.materials.clear()
        obj.data.materials.append(mat_move)

        first_t = records[0]['t']
        start_frame = max(1, int((first_t - START_TIME) / TIME_PER_FRAME))

        # 숨김 → 등장
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_viewport", frame=1)
        obj.keyframe_insert(data_path="hide_render", frame=1)

        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
        obj.keyframe_insert(data_path="hide_render", frame=start_frame)

        # 위치 keyframe — TIME_PER_FRAME 기준 매핑 (5배속이면 0.5s → 1 프레임)
        frame_pos = {}
        for r in records:
            frame = int(round((r['t'] - START_TIME) / TIME_PER_FRAME)) + 1
            if frame < 1:
                continue
            frame_pos[frame] = (r['x'], r['y'])

        for frame, (x, y) in sorted(frame_pos.items()):
            obj.location = (x, y, PERSON_HEIGHT / 2)
            obj.keyframe_insert(data_path="location", frame=frame)

        # 마지막 프레임 이후 숨김
        last_frame = max(frame_pos.keys()) + 1 if frame_pos else start_frame + 1
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_viewport", frame=last_frame)
        obj.keyframe_insert(data_path="hide_render", frame=last_frame)


# ── 렌더 설정 ──────────────────────────────────────────
def setup_render():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'  # 가벼운 엔진
    # Workbench: material 색상 사용 + 스튜디오 조명
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.show_shadows = False
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    # Blender 5.1: PNG 시퀀스로 렌더 후 별도 ffmpeg로 합성
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.join(PROJECT_ROOT, "output", "blender_frames", "f_")


def main():
    print("=" * 50)
    print("Blender 3D 렌더링 시작")
    print("=" * 50)

    clear_scene()
    create_floor()
    create_outer_walls()
    create_gate_barriers()
    create_stairs_and_exits()
    create_lighting_and_camera()
    print("기하구조 생성 완료")

    agents = load_trajectories()
    print(f"궤적 로드: {len(agents)}명")

    animate_agents(agents)
    print("애니메이션 완료")

    setup_render()

    # 테스트 모드: 첫 프레임만 렌더
    test_mode = '--test' in sys.argv
    if test_mode:
        bpy.context.scene.frame_set(300)  # 60초 시점
        bpy.context.scene.render.filepath = os.path.join(PROJECT_ROOT, "output", "blender_test.png")
        bpy.ops.render.render(write_still=True)
        print("테스트 프레임 저장")
    else:
        print(f"렌더링 시작 → {OUTPUT_MP4}")
        bpy.ops.render.render(animation=True)
        print("완료!")


if __name__ == "__main__":
    main()
