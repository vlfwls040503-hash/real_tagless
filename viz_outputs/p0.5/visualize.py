"""
Blender 3D 시각화 스크립트 — 성수역 태그리스 시뮬레이션
실행: blender --background --python visualize.py -- [--test]

재생: 2x 속도 (120s sim → 60s video @ 30fps = 1800 frames)
엔진: EEVEE Next
출력: 1920x1080 H.264 MP4
"""
import bpy
import bmesh
import csv
import json
import math
import os
import sys
import time
from collections import defaultdict
from mathutils import Vector

# ── 경로 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
TRAJ_CSV = os.path.join(OUT_DIR, "trajectory.csv")
GEOM_JSON = os.path.join(OUT_DIR, "geometry.json")
MP4_PATH = os.path.join(OUT_DIR, "output_p0.5.mp4")
BLEND_PATH = os.path.join(OUT_DIR, "scene_p0.5.blend")
FRAMES_DIR = os.path.join(OUT_DIR, "frames_p0.5")
TEST_PNG = os.path.join(OUT_DIR, "test_frame.png")

TEST_MODE = ("--test" in sys.argv)

# ── 렌더 파라미터 ────────────────────────────────────
FPS = 30
PLAYBACK_SPEED = 2.0            # 2x: 120s sim → 60s video
RES_X, RES_Y = 1920, 1080
EEVEE_SAMPLES = 16              # 빠른 렌더
LENS_MM = 35
LENS_FALLBACK_CHAIN = [28, 22, 18, 15]

# ── 색상 (16진 → 0..1 RGB) ────────────────────────────
def hex2rgb(h):
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    # Blender sRGB 입력은 linear로 변환 필요
    def srgb2lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (srgb2lin(r), srgb2lin(g), srgb2lin(b))

COLOR_FLOOR = hex2rgb("#9CA3AF")       # 회색 바닥
COLOR_GATE_TAG = hex2rgb("#F2C94C")    # 노란색 — tag
COLOR_GATE_TAGLESS = hex2rgb("#2EC4B6")# 청록색 — tagless
COLOR_SPAWN = hex2rgb("#E63946")       # 빨강 — spawn
COLOR_EXIT = hex2rgb("#1D4ED8")        # 파랑 — exit
COLOR_PED_TAG = hex2rgb("#FB8500")     # 주황 — tag pedestrian
COLOR_PED_TAGLESS = hex2rgb("#7B2CBF") # 보라 — tagless pedestrian
COLOR_STRUCTURE = hex2rgb("#6B7280")   # 회색 — 비통행 구조물
COLOR_ESC = hex2rgb("#4B5563")         # 에스컬레이터

# ── 보행자 치수 ──────────────────────────────────────
HEAD_R = 0.12
BODY_R = 0.18
BODY_H = 1.4
HEAD_Z = BODY_H + HEAD_R  # 몸통 위에 자연스럽게

# 게이트 치수
GATE_W = 0.6
GATE_D = 1.5
GATE_H = 1.0


def log(msg):
    print(f"[viz] {time.strftime('%H:%M:%S')} {msg}", flush=True)


# ══════════════════════════════════════════════════════
# 1. 씬 초기화
# ══════════════════════════════════════════════════════
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # 사용자 컬렉션만 삭제 (Master/Scene 컬렉션은 보존)
    for coll in list(bpy.data.collections):
        try:
            bpy.data.collections.remove(coll)
        except Exception:
            pass
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def target_collection():
    """Scene의 master collection 반환 (항상 존재)."""
    return bpy.context.scene.collection


def make_material(name, color, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.7
    if alpha < 1.0:
        mat.blend_method = "BLEND"
        # Alpha 소켓 이름 호환 처리
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
    return mat


# ══════════════════════════════════════════════════════
# 2. 바닥 (대합실 polygon)
# ══════════════════════════════════════════════════════
def create_floor(polygon, thickness=0.05):
    mesh = bpy.data.meshes.new("FloorMesh")
    obj = bpy.data.objects.new("Floor", mesh)
    target_collection().objects.link(obj)

    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], 0)) for p in polygon]
    bm.faces.new(verts)
    bm.normal_update()
    # solidify (z 방향 두께)
    ret = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    verts_ext = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, -thickness), verts=verts_ext)
    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(make_material("FloorMat", COLOR_FLOOR))
    return obj


# ══════════════════════════════════════════════════════
# 3. 게이트
# ══════════════════════════════════════════════════════
def create_gates(gates, gate_x_override=None):
    mat_tag = make_material("GateTagMat", COLOR_GATE_TAG)
    mat_tagless = make_material("GateTaglessMat", COLOR_GATE_TAGLESS)
    for g in gates:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(g["x"] + GATE_D / 2, g["y"], GATE_H / 2))
        obj = bpy.context.active_object
        obj.name = f"Gate_{g['idx']}"
        obj.scale = (GATE_D, GATE_W, GATE_H)
        mat = mat_tagless if g["type"] == "tagless" else mat_tag
        obj.data.materials.append(mat)


# ══════════════════════════════════════════════════════
# 4. 스폰 / 출구 / 구조물
# ══════════════════════════════════════════════════════
def create_rect_plane(name, x1, y1, x2, y2, z, material):
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    sx = abs(x2 - x1)
    sy = abs(y2 - y1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, z))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, 1)
    obj.data.materials.append(material)
    return obj


def create_spawns(stairs):
    mat = make_material("SpawnMat", COLOR_SPAWN, alpha=0.55)
    for s in stairs:
        create_rect_plane(f"Spawn_{s['id']}", s["x_start"], s["y_start"],
                          s["x_end"], s["y_end"], 0.02, mat)


def create_exits(exits):
    mat = make_material("ExitMat", COLOR_EXIT, alpha=0.55)
    for e in exits:
        create_rect_plane(f"Exit_{e['id']}", e["x_start"], e["y_start"],
                          e["x_end"], e["y_end"], 0.02, mat)


def create_structures(structures, escalators):
    mat_struct = make_material("StructMat", COLOR_STRUCTURE)
    mat_esc = make_material("EscMat", COLOR_ESC)
    for s in structures:
        coords = s["coords"]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        bpy.ops.mesh.primitive_cube_add(size=1,
            location=((x1 + x2) / 2, (y1 + y2) / 2, 0.5))
        obj = bpy.context.active_object
        obj.name = f"Struct_{s['id']}"
        obj.scale = (x2 - x1, y2 - y1, 1.0)
        obj.data.materials.append(mat_struct)
    for e in escalators:
        x1, x2 = e["x_range"]
        y1, y2 = e["y_range"]
        bpy.ops.mesh.primitive_cube_add(size=1,
            location=((x1 + x2) / 2, (y1 + y2) / 2, 0.12))
        obj = bpy.context.active_object
        obj.name = f"Esc_{e['id']}"
        obj.scale = (x2 - x1, y2 - y1, 0.2)
        obj.data.materials.append(mat_esc)


# ══════════════════════════════════════════════════════
# 5. 보행자 템플릿 (linked duplicate용)
# ══════════════════════════════════════════════════════
def make_person_template(name, color):
    mat = make_material(f"{name}_mat", color)
    # Body (cylinder)
    bpy.ops.mesh.primitive_cylinder_add(radius=BODY_R, depth=BODY_H, vertices=10,
                                        location=(0, 0, BODY_H / 2))
    body = bpy.context.active_object
    body.name = f"{name}_body_tmpl"
    body.data.materials.append(mat)
    # Head (sphere)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_R, segments=10, ring_count=6,
                                         location=(0, 0, HEAD_Z))
    head = bpy.context.active_object
    head.name = f"{name}_head_tmpl"
    head.data.materials.append(mat)
    # Join into single mesh
    head.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    tmpl = bpy.context.active_object
    tmpl.name = f"Person_{name}_TMPL"
    # hide template from render
    tmpl.hide_render = True
    tmpl.hide_viewport = True
    return tmpl


def duplicate_linked(template, new_name):
    """같은 mesh data를 공유하는 linked duplicate (메모리 절약)."""
    obj = bpy.data.objects.new(new_name, template.data)
    target_collection().objects.link(obj)
    return obj


# ══════════════════════════════════════════════════════
# 6. 카메라 + 조명
# ══════════════════════════════════════════════════════
def create_camera_and_light(bounds):
    x_mid = (bounds["x_min"] + bounds["x_max"]) / 2
    y_mid = (bounds["y_min"] + bounds["y_max"]) / 2
    y_span = bounds["y_max"] - bounds["y_min"]
    x_span = bounds["x_max"] - bounds["x_min"]
    margin = y_span * 0.15
    height = max(x_span, y_span) * 0.9

    bpy.ops.object.camera_add(location=(x_mid, bounds["y_min"] - margin, height))
    cam = bpy.context.active_object
    cam.name = "MainCam"
    # track-to target
    target_empty = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(target_empty)
    target_empty.location = (x_mid, y_mid, 0)
    constr = cam.constraints.new("TRACK_TO")
    constr.target = target_empty
    constr.track_axis = "TRACK_NEGATIVE_Z"
    constr.up_axis = "UP_Y"
    cam.data.lens = LENS_MM
    bpy.context.scene.camera = cam

    # Sun
    bpy.ops.object.light_add(type="SUN", location=(x_mid, y_mid, 30))
    sun = bpy.context.active_object
    sun.name = "SunLight"
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(35), math.radians(15), 0)
    # World
    world = bpy.context.scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.85, 0.88, 0.92, 1.0)
        bg.inputs["Strength"].default_value = 1.2

    return cam, target_empty


def check_camera_framing(cam, bounds):
    """대합실 4모서리가 프레임 내로 들어오도록 렌즈를 자동 선택."""
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    corners = [
        (bounds["x_min"], bounds["y_min"], 0),
        (bounds["x_max"], bounds["y_min"], 0),
        (bounds["x_max"], bounds["y_max"], 0),
        (bounds["x_min"], bounds["y_max"], 0),
    ]

    def all_in(lens_mm):
        cam.data.lens = lens_mm
        bpy.context.view_layer.update()
        for c in corners:
            co = world_to_camera_view(scene, cam, Vector(c))
            if not (0.01 <= co.x <= 0.99 and 0.01 <= co.y <= 0.99 and co.z > 0):
                return False
        return True

    for lens in [LENS_MM] + LENS_FALLBACK_CHAIN:
        if all_in(lens):
            cam.data.lens = lens
            log(f"camera framing OK at {lens}mm")
            return
    log(f"WARN: even {LENS_FALLBACK_CHAIN[-1]}mm does not fit; using widest")
    cam.data.lens = LENS_FALLBACK_CHAIN[-1]


# ══════════════════════════════════════════════════════
# 7. 궤적 파싱 + 애니메이션
# ══════════════════════════════════════════════════════
def load_trajectories():
    agents = defaultdict(list)
    t_min = float("inf")
    t_max = 0.0
    with open(TRAJ_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = float(row["time"])
            aid = row["agent_id"]
            x = float(row["x"])
            y = float(row["y"])
            is_tagless = bool(int(row["is_tagless"]))
            agents[aid].append((t, x, y, is_tagless))
            if t < t_min:
                t_min = t
            if t > t_max:
                t_max = t
    for aid in agents:
        agents[aid].sort(key=lambda r: r[0])
    return agents, t_min, t_max


def animate(agents, t_min, t_max, tmpl_tag, tmpl_tagless):
    scene = bpy.context.scene
    scene.render.fps = FPS
    # 기본 keyframe 보간을 LINEAR로 (등속 이동용)
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    except Exception:
        pass

    # 2x 재생: video_duration = sim_span / PLAYBACK_SPEED
    video_dur = (t_max - t_min) / PLAYBACK_SPEED
    total_frames = int(video_dur * FPS) + 2
    scene.frame_start = 1
    scene.frame_end = total_frames
    log(f"sim {t_min:.1f}~{t_max:.1f}s -> video {video_dur:.1f}s, frames={total_frames}")

    def t_to_frame(t):
        return int((t - t_min) / PLAYBACK_SPEED * FPS) + 1

    total = len(agents)
    for i, (aid, records) in enumerate(agents.items()):
        if i % 25 == 0:
            log(f"  keyframing {i}/{total}")
        is_tagless = records[0][3]
        tmpl = tmpl_tagless if is_tagless else tmpl_tag
        obj = duplicate_linked(tmpl, f"P{aid}")

        # 시작 전: hidden
        first_t = records[0][0]
        last_t = records[-1][0]
        first_frame = max(1, t_to_frame(first_t))
        last_frame = min(total_frames, t_to_frame(last_t))

        if first_frame > 1:
            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path="hide_viewport", frame=1)
            obj.keyframe_insert(data_path="hide_render", frame=1)
            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert(data_path="hide_viewport", frame=first_frame)
            obj.keyframe_insert(data_path="hide_render", frame=first_frame)
        else:
            obj.hide_viewport = False
            obj.hide_render = False

        # 위치 keyframe — frame별로 uniq
        seen_frames = {}
        prev_xy = None
        for (t, x, y, _isl) in records:
            f = t_to_frame(t)
            if f < 1 or f > total_frames:
                continue
            seen_frames[f] = (x, y, prev_xy)
            prev_xy = (x, y)

        sorted_frames = sorted(seen_frames.items())
        prev_pos = None
        for f, (x, y, _prev) in sorted_frames:
            obj.location = (x, y, 0)
            # yaw: 이동 방향 (이전 프레임 대비)
            if prev_pos is not None:
                dx = x - prev_pos[0]
                dy = y - prev_pos[1]
                if dx * dx + dy * dy > 1e-6:
                    obj.rotation_euler = (0, 0, math.atan2(dy, dx) - math.pi / 2)
            obj.keyframe_insert(data_path="location", frame=f)
            obj.keyframe_insert(data_path="rotation_euler", frame=f)
            prev_pos = (x, y)

        # 사라진 후: hidden
        hide_frame = last_frame + 1
        if hide_frame <= total_frames:
            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path="hide_viewport", frame=hide_frame)
            obj.keyframe_insert(data_path="hide_render", frame=hide_frame)

    log("animation done")
    return total_frames


# ══════════════════════════════════════════════════════
# 8. 렌더 설정
# ══════════════════════════════════════════════════════
def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    log("render engine: BLENDER_EEVEE (Next)")

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS

    try:
        scene.eevee.taa_render_samples = EEVEE_SAMPLES
        scene.eevee.taa_samples = 4
    except Exception as e:
        log(f"eevee sample set warn: {e}")
    # 그림자 (시간 절약)
    try:
        scene.eevee.use_shadows = False
    except Exception:
        pass

    # PNG 시퀀스 (외부 ffmpeg로 합성)
    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = os.path.join(FRAMES_DIR, "f_")


# ══════════════════════════════════════════════════════
# 9. 메인
# ══════════════════════════════════════════════════════
def main():
    t_start = time.time()
    log("=== visualize.py start ===")
    log(f"test_mode = {TEST_MODE}")

    with open(GEOM_JSON, "r", encoding="utf-8") as f:
        geom = json.load(f)
    log(f"geometry loaded: gates={len(geom['gates'])} stairs={len(geom['stairs'])}")

    clear_scene()
    log("scene cleared")

    create_floor(geom["concourse_polygon"])
    log("floor created")

    create_structures(geom["structures"], geom["escalators"])
    log("structures + escalators")

    create_gates(geom["gates"])
    log("gates created")

    create_spawns(geom["stairs"])
    create_exits(geom["exits"])
    log("spawn/exit planes")

    tmpl_tag = make_person_template("tag", COLOR_PED_TAG)
    tmpl_tagless = make_person_template("tagless", COLOR_PED_TAGLESS)
    log("person templates")

    cam, target_empty = create_camera_and_light(geom["bounds"])
    check_camera_framing(cam, geom["bounds"])
    log("camera + light")

    agents, t_min, t_max = load_trajectories()
    log(f"trajectory loaded: {len(agents)} agents, t range {t_min:.1f}..{t_max:.1f}")

    n_frames = animate(agents, t_min, t_max, tmpl_tag, tmpl_tagless)

    setup_render()

    # .blend 저장 (렌더 전)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    log(f".blend saved: {BLEND_PATH}")

    if TEST_MODE:
        mid = max(1, n_frames // 2)
        bpy.context.scene.frame_set(mid)
        bpy.context.scene.render.filepath = TEST_PNG
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
        log(f"test frame rendered: {TEST_PNG}")
    else:
        log(f"rendering animation: {MP4_PATH}")
        bpy.ops.render.render(animation=True)
        log(f"render done: {MP4_PATH}")

    elapsed = time.time() - t_start
    log(f"=== visualize.py done in {elapsed:.1f}s ===")


if __name__ == "__main__":
    main()
