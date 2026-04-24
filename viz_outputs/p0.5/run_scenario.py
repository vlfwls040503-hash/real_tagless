"""
시나리오 1회 실행 래퍼:
  - run_west_simulation_cfsm_escalator 를 batch 파라미터로 monkey-patch
  - TAGLESS_RATIO=0.5, SIM_TIME=120, SEED=42
  - trajectory.csv + geometry.json 저장
  - 실패 시 시드 변경 최대 3회 재시도
"""
import sys
import os
import pathlib
import json
import traceback
import time

WORK_DIR = pathlib.Path(__file__).resolve().parent
REPO_DIR = WORK_DIR / "real_tagless"
SIM_DIR = REPO_DIR / "simulation"
OUT_DIR = WORK_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAJ_PATH = OUT_DIR / "trajectory.csv"
GEOM_PATH = OUT_DIR / "geometry.json"
ERR_LOG = OUT_DIR / "sim_error.log"

sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(REPO_DIR))

os.chdir(str(REPO_DIR))

import importlib
import run_west_simulation_cfsm_escalator as sim  # noqa: E402
import seongsu_west_escalator as geom  # noqa: E402


SEEDS = [42, 1337, 2024]


def dump_geometry():
    # 게이트 정보
    gates_raw = geom.calculate_gate_positions()
    # 게이트 타입: 시각화용 convention (시뮬은 코드 기본값=공용)
    # idx 0~3 = tag(노랑), 4~6 = tagless(청록)
    gates = []
    for i, g in enumerate(gates_raw):
        gate_type = "tagless" if i >= 4 else "tag"
        gates.append({
            "idx": i,
            "x": g["x"],
            "y": g["y"],
            "length": geom.GATE_LENGTH,
            "passage_width": geom.GATE_PASSAGE_WIDTH,
            "type": gate_type,
        })

    # 외곽 polygon (대합실)
    # 기존 코드 패턴: notch 있는 L자형
    CL = geom.CONCOURSE_LENGTH
    CW = geom.CONCOURSE_WIDTH
    NX = geom.NOTCH_X
    NY = geom.NOTCH_Y
    concourse_polygon = [
        [0, 0], [CL, 0], [CL, CW], [NX, CW], [NX, NY], [0, NY]
    ]

    # 계단 = 스폰 영역
    stairs = []
    for s in geom.STAIRS:
        stairs.append({
            "id": s["id"],
            "x_start": s["x_start"],
            "x_end": s["x_end"],
            "y_start": s["y_start"],
            "y_end": s["y_end"],
        })

    # 출구 = 에스컬레이터 capture zone
    exits = []
    for e in geom.EXITS:
        # EXITS의 y 단일값 → polygon 너비 0.8m로 대체
        y_c = e["y"]
        exits.append({
            "id": e["id"],
            "x_start": e["x_start"],
            "x_end": e["x_end"],
            "y_start": y_c - 0.4,
            "y_end": y_c + 0.4,
        })

    # 비통행 구조물
    structures = []
    for s in geom.STRUCTURES:
        structures.append({"id": s["id"], "coords": s["coords"]})

    # 에스컬레이터 통로
    escalators = []
    for e in geom.ESCALATORS:
        escalators.append({
            "id": e["id"],
            "direction": e["direction"],
            "x_range": list(e["x_range"]),
            "y_range": list(e["y_range"]),
        })

    bounds = {
        "x_min": 0.0,
        "x_max": float(CL),
        "y_min": 0.0,
        "y_max": float(CW),
    }

    data = {
        "concourse_polygon": concourse_polygon,
        "gates": gates,
        "stairs": stairs,
        "exits": exits,
        "structures": structures,
        "escalators": escalators,
        "bounds": bounds,
        "n_gates": geom.N_GATES,
    }

    with open(GEOM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[geometry] saved: {GEOM_PATH}")


def run_once(seed):
    print(f"\n{'=' * 60}\n[SIM] seed={seed} p=0.5 SIM_TIME=120\n{'=' * 60}")
    # monkey-patch
    sim.TAGLESS_RATIO = 0.5
    sim.BATCH_SEED = seed
    sim.SIM_TIME = 120.0
    sim.BATCH_SKIP_HEAVY_OUTPUTS = True   # mp4/snapshot 생략 (시간 단축)
    sim.BATCH_SAVE_TRAJECTORY = True
    sim.BATCH_TRAJECTORY_INTERVAL = 0.1   # 10 Hz 샘플링 (30fps 애니메이션에 충분)
    sim.BATCH_TRAJECTORY_OUT = TRAJ_PATH
    sim.BATCH_TAGLESS_ONLY_GATES = frozenset()  # 코드 기본값 = 전용 없음

    t0 = time.time()
    stats, spawned = sim.run_simulation()
    t1 = time.time()
    print(f"[SIM] done in {t1-t0:.1f}s, spawned={spawned}")
    return stats, spawned


def main():
    print(f"WORK_DIR = {WORK_DIR}")
    print(f"REPO_DIR = {REPO_DIR}")
    print(f"SIM_DIR  = {SIM_DIR}")

    # geometry 먼저 저장 (시뮬 실패해도 확보)
    try:
        dump_geometry()
    except Exception:
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- geometry dump fail {time.asctime()} ---\n")
            f.write(traceback.format_exc())
        print("[geometry] FAILED (logged)")

    last_err = None
    for attempt, seed in enumerate(SEEDS, 1):
        try:
            stats, spawned = run_once(seed)
            if TRAJ_PATH.exists() and TRAJ_PATH.stat().st_size > 1000:
                print(f"[OK] trajectory {TRAJ_PATH} ({TRAJ_PATH.stat().st_size} bytes)")
                return 0
            else:
                raise RuntimeError("trajectory file too small or missing")
        except Exception as e:
            last_err = e
            print(f"[SIM] attempt {attempt} (seed={seed}) FAILED: {e}")
            with open(ERR_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n--- attempt {attempt} seed={seed} {time.asctime()} ---\n")
                f.write(traceback.format_exc())

    print(f"[FATAL] all {len(SEEDS)} simulation attempts failed. See {ERR_LOG}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
