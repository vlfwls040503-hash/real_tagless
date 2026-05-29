"""
Blender BPY script — JuPedSim trajectory → 3D 보행자 애니메이션.

사용법:
    1. Blender 4.x 설치 (https://blender.org)
    2. Blender 실행 → Scripting 탭
    3. 본 파일 열기 → CONFIG 섹션에서 TRAJ_PATH 만 수정
    4. ▶ Run Script (또는 Alt+P)
    5. F12 = 단일 프레임 렌더 / Ctrl+F12 = 애니메이션 mp4 렌더

출력:
    - mp4 (animation): C:/Users/aaron/tagless/output/blender_3d_<scenario>.mp4
    - 단일 프레임: 동일 폴더 png
"""
import bpy
import csv
import math
from pathlib import Path

# ─────── CONFIG (사용자 수정 영역) ───────
TRAJ_PATH = "C:/Users/aaron/tagless/data_package_for_llm/trajectory_p50_cfg2.csv"
AGENTS_PATH = "C:/Users/aaron/tagless/data_package_for_llm/agents_p50_cfg2.csv"
OUTPUT_NAME = "p50_cfg2"   # 또는 "p50_cfg3"
TAGLESS_GATES = [3, 5]     # cfg2 = [3,5] / cfg3 = [3,4,5] (1-indexed)

START_TIME = 200.0   # 시뮬 시작 (s)
END_TIME = 280.0     # 시뮬 끝 (s)
TIME_STEP = 0.5      # CSV 의 dt
FPS = 30             # 렌더 fps

ROOT = "C:/Users/aaron/tagless"
OUT_DIR = f"{ROOT}/output"

# 색상 (RGBA, 0~1)
COLOR_TAG = (0.37, 0.37, 0.35, 1.0)         # 진회색
COLOR_TAGLESS = (0.33, 0.29, 0.72, 1.0)     # 보라
COLOR_POSTGATE = (0.48, 0.47, 0.44, 1.0)    # 연회색
COLOR_GATE_TAG = (0.55, 0.55, 0.50, 1.0)    # 게이트 (태그)
COLOR_GATE_TAGLESS = (0.50, 0.46, 0.86, 1.0)
COLOR_ESC = (0.91, 0.87, 0.96, 1.0)         # 에스컬 corridor
COLOR_WALL = (0.78, 0.78, 0.75, 1.0)
COLOR_FLOOR = (0.96, 0.96, 0.96, 1.0)


# ─────── HELPER ───────
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for m in bpy.data.materials:
        bpy.data.materials.remove(m)
    for me in bpy.data.meshes:
        bpy.data.meshes.remove(me)


def make_material(name, color, emit=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.55
    if emit > 0:
        bsdf.inputs["Emission Strength"].default_value = emit
        bsdf.inputs["Emission Color"].default_value = color
    return mat


def make_box(name, x0, y0, z0, dx, dy, dz, color, emit=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1,
                                    location=(x0 + dx/2, y0 + dy/2, z0 + dz/2))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (dx/2, dy/2, dz/2)
    obj.data.materials.append(make_material(f"mat_{name}", color, emit))
    return obj


def make_capsule(name, color):
    """보행자 capsule (Cylinder + 2 Spheres)."""
    bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=1.4,
                                        vertices=16, location=(0, 0, 0.7))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(make_material(f"mat_{name}", color, emit=0.3))
    return obj


# ─────── BUILD GEOMETRY ───────
def build_geometry():
    # 바닥
    make_box("floor", -2, -2, -0.05, 50, 30, 0.05, COLOR_FLOOR)

    # 외곽 벽 (간단히 4벽)
    make_box("wall_S", -2, -2, 0, 50, 0.2, 3.0, COLOR_WALL)
    make_box("wall_N", -2, 27.8, 0, 50, 0.2, 3.0, COLOR_WALL)
    make_box("wall_W", -2, -2, 0, 0.2, 30, 3.0, COLOR_WALL)

    # 비통행 구조물 (벽 안)
    structures = [
        (35, 16, 13, 8),  # upper right
        (35, 3, 13, 8),   # lower right
    ]
    for i, (x, y, w, h) in enumerate(structures):
        make_box(f"struct_{i}", x, y, 0, w, h, 3.0, COLOR_WALL)

    # 게이트 7개
    gate_y = [9.95, 10.80, 11.65, 12.50, 13.35, 14.20, 15.05]
    for i, gy in enumerate(gate_y):
        is_tagless = (i + 1) in TAGLESS_GATES
        color = COLOR_GATE_TAGLESS if is_tagless else COLOR_GATE_TAG
        make_box(f"gate_{i+1}", 12, gy - 0.275, 0, 1.5, 0.55, 1.2, color, emit=0.2)

    # 에스컬레이터 (upper)
    make_box("esc_upper", 28, 25, 0, 12, 1.2, 0.3, COLOR_ESC, emit=0.15)
    make_box("esc_lower", 28, -1.2, 0, 12, 1.2, 0.3, COLOR_ESC, emit=0.15)


# ─────── LOAD TRAJECTORY ───────
def load_trajectory():
    traj = {}  # {time: [(agent_id, x, y), ...]}
    with open(TRAJ_PATH, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            t = float(row["time"])
            if t < START_TIME or t > END_TIME:
                continue
            traj.setdefault(t, []).append(
                (int(row["agent_id"]), float(row["x"]), float(row["y"])))

    is_tagless = {}
    with open(AGENTS_PATH, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            is_tagless[int(row["agent_id"])] = int(row["is_tagless"])

    return traj, is_tagless


# ─────── ANIMATE PEDESTRIANS ───────
def animate(traj, is_tagless):
    times = sorted(traj.keys())
    all_aids = set()
    for t in times:
        all_aids.update(a[0] for a in traj[t])

    # 각 agent 마다 capsule 생성 (한 번만)
    objs = {}
    print(f"creating {len(all_aids)} capsules...")
    for aid in all_aids:
        tag_state = is_tagless.get(aid)
        if tag_state == 1:
            color = COLOR_TAGLESS
        elif tag_state == 0:
            color = COLOR_TAG
        else:
            color = COLOR_POSTGATE
        obj = make_capsule(f"ped_{aid}", color)
        obj.location = (0, 0, -10)  # 초기 숨김
        objs[aid] = obj

    # 프레임마다 위치 keyframe
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = len(times)
    bpy.context.scene.render.fps = FPS

    for fi, t in enumerate(times, start=1):
        active_aids = set()
        for aid, x, y in traj[t]:
            obj = objs[aid]
            obj.location = (x, y, 0.7)
            obj.keyframe_insert(data_path="location", frame=fi)
            active_aids.add(aid)

        # 비활성 (이 프레임에 없음) → 숨김
        for aid in all_aids - active_aids:
            obj = objs[aid]
            obj.location = (0, 0, -10)
            obj.keyframe_insert(data_path="location", frame=fi)


# ─────── CAMERA + LIGHT ───────
def setup_camera():
    # 게이트 + 에스컬 를 모두 보는 각도 (오른쪽 위에서)
    bpy.ops.object.camera_add(location=(20, -10, 25),
                               rotation=(math.radians(60), 0, math.radians(20)))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    # Sun light
    bpy.ops.object.light_add(type="SUN", location=(20, 10, 30),
                              rotation=(math.radians(45), 0, math.radians(30)))
    sun = bpy.context.active_object
    sun.data.energy = 2.0

    # 보조 area light
    bpy.ops.object.light_add(type="AREA", location=(20, 10, 15))
    area = bpy.context.active_object
    area.data.energy = 500
    area.data.size = 20


# ─────── RENDER SETTINGS ───────
def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.ops, "eevee_next") else "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.filepath = f"{OUT_DIR}/blender_3d_{OUTPUT_NAME}.mp4"

    # 월드 배경 (밝게)
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.95, 0.95, 0.97, 1.0)
    bg.inputs[1].default_value = 1.5


# ─────── MAIN ───────
def main():
    print(f"=== Blender 3D Render — {OUTPUT_NAME} ===")
    clear_scene()
    print("[1/4] geometry...")
    build_geometry()
    print("[2/4] trajectory load...")
    traj, is_tagless = load_trajectory()
    print(f"  {len(traj)} frames, {sum(len(v) for v in traj.values())} positions")
    print("[3/4] animate...")
    animate(traj, is_tagless)
    print("[4/4] camera + render setup...")
    setup_camera()
    setup_render()
    print(f"\n준비 완료. Ctrl+F12 로 mp4 렌더.")
    print(f"출력: {OUT_DIR}/blender_3d_{OUTPUT_NAME}.mp4")


if __name__ == "__main__":
    main()
